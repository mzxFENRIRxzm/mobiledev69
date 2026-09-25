from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import ShopMessage
from .test_bookings import BookingSetup


class ChatApiTests(BookingSetup, TestCase):
    def test_customer_and_shop_members_can_talk_without_leaking_to_others(self):
        created = self.api.post('/api/conversations/', {'shop': self.shop.pk})
        self.assertEqual(created.status_code, 201, created.data)
        room = created.data['id']
        self.assertEqual(self.api.post('/api/conversations/', {'shop': self.shop.pk}).data['id'], room)
        sent = self.api.post(f'/api/conversations/{room}/messages/', {'body': 'สวัสดีครับ'})
        self.assertEqual(sent.status_code, 201, sent.data)
        self.assertEqual(self.client_for(self.mechanic).get('/api/conversations/').data[0]['id'], room)
        answer = self.client_for(self.mechanic2).post(f'/api/conversations/{room}/messages/', {'body': 'ยินดีครับ'})
        self.assertEqual(answer.status_code, 201, answer.data)
        self.assertEqual(len(self.api.get(f'/api/conversations/{room}/messages/').data), 2)
        outsider = self.client_for(self.other)
        self.assertEqual(outsider.get('/api/conversations/').data, [])
        self.assertEqual(outsider.get(f'/api/conversations/{room}/messages/').status_code, 404)
        self.assertEqual(outsider.post(f'/api/conversations/{room}/messages/', {'body': 'hijack'}).status_code, 404)
        self.shop.mechanics.remove(self.mechanic)
        self.assertEqual(self.client_for(self.mechanic).get(f'/api/conversations/{room}/messages/').status_code, 404)
        self.assertEqual(ShopMessage.objects.count(), 2)

    def test_mechanic_cannot_start_room_and_empty_message_is_rejected(self):
        self.assertEqual(self.client_for(self.mechanic).post('/api/conversations/', {'shop': self.shop.pk}).status_code, 403)
        room = self.api.post('/api/conversations/', {'shop': self.shop.pk}).data['id']
        self.assertEqual(self.api.post(f'/api/conversations/{room}/messages/', {'body': '  '}).status_code, 400)
        self.assertEqual(ShopMessage.objects.count(), 0)

    @override_settings(AI_CHAT_WEBHOOK_URL='')
    def test_ai_chat_requires_configured_webhook(self):
        self.assertEqual(self.api.post('/api/ai-chat/', {'message': 'ทดสอบ'}).status_code, 503)
        self.assertEqual(APIClient().post('/api/ai-chat/', {'message': 'ทดสอบ'}).status_code, 401)

    @override_settings(AI_CHAT_WEBHOOK_URL='https://example.test/webhook', AI_CHAT_WEBHOOK_TOKEN='')
    @patch('garage.ai_chat.urlopen')
    def test_ai_chat_returns_webhook_reply(self, open_url):
        from io import BytesIO
        open_url.return_value.__enter__.return_value = BytesIO(b'{"reply":"Check the battery"}')
        response = self.api.post('/api/ai-chat/', {'message': 'รถสตาร์ตยาก'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['reply'], 'Check the battery')
