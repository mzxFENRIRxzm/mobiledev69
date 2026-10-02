import json
import os
from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from unittest import skipUnless
from urllib.error import HTTPError

from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from .models import AiConversation, AiTurn, KnowledgeChunk
from .test_bookings import BookingSetup
from .ai_chat import retrieve


@override_settings(AI_CHAT_WEBHOOK_URL='https://example.test/webhook', AI_CHAT_WEBHOOK_TOKEN='test-only')
class AiTests(BookingSetup, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.room = AiConversation.objects.create(owner=self.customer)
        self.payload = {'message': 'สตาร์ทไม่ติด', 'conversation_id': str(self.room.pk), 'request_id': str(uuid4())}

    def post(self):
        return self.api.post('/api/ai-chat/', self.payload, format='json')

    @patch('garage.ai_chat.urlopen')
    def test_history_ownership_replay_and_minimal_provider_payload(self, upstream):
        upstream.return_value.__enter__.return_value = BytesIO(b'{"reply":"Safe reply","citation_ids":[]}')
        first = self.post()
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(self.post().data, first.data)
        self.assertEqual(upstream.call_count, 1)
        self.assertEqual(AiTurn.objects.count(), 1)
        outgoing = json.loads(upstream.call_args.args[0].data)
        self.assertEqual(set(outgoing), {'message', 'conversation_id', 'history', 'sources'})
        self.assertEqual(outgoing['conversation_id'], str(self.room.pk))
        self.assertNotIn('customer', json.dumps(outgoing))
        self.assertEqual(self.api.get('/api/ai-conversations/').data[0]['id'], str(self.room.pk))
        path = f'/api/ai-conversations/{self.room.pk}/'
        self.assertEqual(self.api.get(path).data['turns'][0]['reply'], 'Safe reply')
        self.assertEqual(self.api.get(path)['Cache-Control'], 'no-store')
        other = self.client_for(self.other)
        self.assertEqual(other.get(path).status_code, 404)
        self.assertEqual(other.post('/api/ai-chat/', self.payload, format='json').status_code, 404)
        self.assertEqual(other.get('/api/ai-conversations/').data, [])
        self.assertEqual(APIClient().get(path).status_code, 401)
        self.payload['message'] = 'Changed'
        self.assertEqual(self.post().status_code, 400)

    @patch('garage.ai_chat.urlopen')
    def test_new_conversation_sends_server_created_uuid_to_rag(self, upstream):
        upstream.return_value.__enter__.return_value = BytesIO(b'{"reply":"Safe reply","citation_ids":[]}')
        self.payload.pop('conversation_id')
        result = self.post()
        self.assertEqual(result.status_code, 200, result.data)
        outgoing = json.loads(upstream.call_args.args[0].data)
        self.assertEqual(outgoing['conversation_id'], result.data['conversation_id'])
        self.assertEqual(AiConversation.objects.get(pk=outgoing['conversation_id']).owner, self.customer)

    @patch('garage.ai_chat.urlopen')
    def test_timeout_retry_keeps_one_turn(self, upstream):
        upstream.side_effect = TimeoutError()
        self.assertEqual(self.post().status_code, 503)
        self.assertEqual(AiTurn.objects.get().status, 'failed')
        upstream.side_effect = None
        upstream.return_value.__enter__.return_value = BytesIO(b'{"reply":"Recovered"}')
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(AiTurn.objects.count(), 1)

    @patch('garage.ai_chat.urlopen')
    def test_rate_limit_and_no_error_body_leak(self, upstream):
        upstream.side_effect = HTTPError('https://example.test', 429, 'private upstream error', {}, None)
        result = self.post()
        self.assertEqual(result.status_code, 429)
        self.assertNotIn('private', str(result.data))
        self.assertEqual(AiTurn.objects.get().error_code, 'rate_limited')

    @patch('garage.ai_chat.urlopen')
    def test_pending_conflict_and_stale_recovery(self, upstream):
        turn = AiTurn.objects.create(conversation=self.room, message='Waiting')
        self.assertEqual(self.post().status_code, 409)
        upstream.assert_not_called()
        AiTurn.objects.filter(pk=turn.pk).update(updated_at=timezone.now()-timedelta(seconds=61))
        result = self.api.get(f'/api/ai-conversations/{self.room.pk}/')
        self.assertEqual(result.data['turns'][0]['status'], 'failed')

    @patch('garage.ai_chat.urlopen')
    def test_only_reviewed_matched_sources_can_be_cited(self, upstream):
        chunk = KnowledgeChunk.objects.create(title='Test manual', source_url='https://example.test/manual',
            locator='test section', content='Synthetic content', keywords=['สตาร์ท'], is_active=True)
        KnowledgeChunk.objects.create(title='Inactive', source_url='https://example.test/hidden',
            content='Must not send', keywords=['สตาร์ท'])
        upstream.return_value.__enter__.return_value = BytesIO(json.dumps(
            {'reply': 'Answer', 'citation_ids': [chunk.pk, 99999]}).encode())
        result = self.post()
        self.assertEqual(result.status_code, 200)
        self.assertEqual([s['id'] for s in result.data['sources']], [chunk.pk])
        self.assertNotIn('excerpt', result.data['sources'][0])
        self.assertEqual(len(json.loads(upstream.call_args.args[0].data)['sources']), 1)
        self.assertEqual(retrieve('ไม่มีคำค้น'), [])

    @patch('garage.ai_chat.urlopen')
    def test_context_is_bounded_and_excludes_failed_turns(self, upstream):
        for i in range(6):
            AiTurn.objects.create(conversation=self.room, message=str(i), reply='x'*2000, status='completed')
        AiTurn.objects.create(conversation=self.room, message='private failure', status='failed')
        upstream.return_value.__enter__.return_value = BytesIO(b'{"reply":"Answer"}')
        self.assertEqual(self.post().status_code, 200)
        history = json.loads(upstream.call_args.args[0].data)['history']
        self.assertEqual([h['message'] for h in history], ['2', '3', '4', '5'])
        self.assertEqual(len(history[0]['reply']), 1500)

    @patch('garage.ai_chat.urlopen')
    def test_bad_provider_responses_fail_without_storing_fake_answer(self, upstream):
        for body in [b'[]', b'{"reply":""}', b'{"error":"unavailable"}', b'{"reply":"x","citation_ids":"bad"}', b'x'*32769]:
            upstream.return_value.__enter__.return_value = BytesIO(body)
            self.assertEqual(self.post().status_code, 503)
        self.assertEqual(AiTurn.objects.get().reply, '')

    @patch('garage.ai_chat.urlopen')
    def test_internal_http_requires_exact_host_and_explicit_setting(self, upstream):
        with self.settings(AI_CHAT_WEBHOOK_URL='http://n8n:5678/webhook/test', AI_CHAT_INTERNAL_N8N=False):
            self.assertEqual(self.post().status_code, 503)
        with self.settings(AI_CHAT_WEBHOOK_URL='http://evil.test/webhook', AI_CHAT_INTERNAL_N8N=True):
            self.assertEqual(self.post().status_code, 503)
        with self.settings(AI_CHAT_WEBHOOK_TOKEN=''):
            self.assertEqual(self.post().status_code, 503)
        upstream.assert_not_called()
        with self.settings(AI_CHAT_WEBHOOK_URL='http://n8n:5678/webhook/test', AI_CHAT_INTERNAL_N8N=True):
            upstream.return_value.__enter__.return_value = BytesIO(b'{"reply":"OK"}')
            self.assertEqual(self.post().status_code, 200)

    def test_import_is_validated_atomic_and_inactive(self):
        item = {'title':'Test', 'source_url':'https://example.test/manual', 'keywords':['battery'], 'content':'Synthetic test excerpt'}
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'manual.json'
            path.write_text(json.dumps([item, {**item, 'keywords':'invalid'}]), encoding='utf-8')
            with self.assertRaises(CommandError):
                call_command('import_ai_knowledge', str(path))
            self.assertFalse(KnowledgeChunk.objects.exists())
            path.write_text(json.dumps([item]), encoding='utf-8')
            call_command('import_ai_knowledge', str(path))
            call_command('import_ai_knowledge', str(path))
            self.assertEqual(KnowledgeChunk.objects.count(), 1)
            self.assertFalse(KnowledgeChunk.objects.get().is_active)


@skipUnless(os.getenv('AI_N8N_SMOKE') == 'true', 'Requires the isolated synthetic n8n test workflow')
@override_settings(AI_CHAT_WEBHOOK_URL='http://n8n:5678/webhook/the-x-ai-smoke', AI_CHAT_INTERNAL_N8N=True)
class N8nSmokeTests(BookingSetup, TestCase):
    def test_real_n8n_webhook_normalizer_and_postgres_persistence(self):
        cache.clear()
        room = self.api.post('/api/ai-conversations/', {}, format='json').data['id']
        result = self.api.post('/api/ai-chat/', {'message': 'SMOKE_SYNTHETIC_ONLY',
                              'conversation_id': room, 'request_id': str(uuid4())}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['reply'], 'SMOKE SYNTHETIC ONLY - not a Gemini answer')
        self.assertEqual(AiTurn.objects.get().status, 'completed')
        limited = self.api.post('/api/ai-chat/', {'message': 'SMOKE_429',
                               'conversation_id': room, 'request_id': str(uuid4())}, format='json')
        self.assertEqual(limited.status_code, 429, limited.data)
        self.assertEqual(AiTurn.objects.filter(status='failed').count(), 1)
