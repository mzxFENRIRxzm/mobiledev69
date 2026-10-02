from uuid import uuid4
from django.test import TestCase
from .test_bookings import BookingSetup
from .models import ShopConversation, ShopMessage, Notification, AiConversation, AiTurn


class HistoryTests(BookingSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.room = ShopConversation.objects.create(shop=self.shop, customer=self.customer)
        self.url = f'/api/conversations/{self.room.pk}/messages/'

    def test_retry_returns_original_without_duplicate_notifications(self):
        payload = {'body': 'retry test', 'request_id': str(uuid4())}
        first = self.api.post(self.url, payload)
        count = Notification.objects.count()
        second = self.api.post(self.url, payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(ShopMessage.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), count)
        self.assertEqual(self.api.post(self.url, {**payload, 'body': 'changed'}).status_code, 400)
        self.assertEqual(self.client_for(self.other).post(self.url, payload).status_code, 404)

    def test_cursor_history_and_arrivals_have_no_gaps_or_duplicates(self):
        ShopMessage.objects.bulk_create([ShopMessage(conversation=self.room, sender=self.customer, body=str(i)) for i in range(205)])
        latest = self.api.get(self.url, {'paged': 1}).data
        self.assertEqual(len(latest['results']), 100)
        middle = self.api.get(self.url, {'paged': 1, 'before': latest['cursor']}).data
        oldest = self.api.get(self.url, {'paged': 1, 'before': middle['cursor']}).data
        ids = [m['id'] for page in [oldest, middle, latest] for m in page['results']]
        self.assertEqual(ids, list(self.room.messages.order_by('pk').values_list('pk', flat=True)))
        self.assertFalse(oldest['has_more'])
        self.assertEqual(self.api.get(self.url, {'paged': 1, 'after': ids[-1]}).data['results'], [])
        self.assertEqual(self.api.get(self.url, {'before': 'invalid'}).status_code, 400)
        self.assertEqual(self.client_for(self.other).get(self.url, {'paged': 1, 'before': latest['cursor']}).status_code, 404)

    def test_ai_history_pages_preserve_owner_boundary(self):
        room = AiConversation.objects.create(owner=self.customer)
        AiTurn.objects.bulk_create([AiTurn(conversation=room, message=str(i), status='completed', reply='test') for i in range(55)])
        url = f'/api/ai-conversations/{room.pk}/'
        page = self.api.get(url, {'paged': 1}).data
        self.assertEqual(len(page['turns']), 50)
        older = self.api.get(url, {'paged': 1, 'before': page['cursor']}).data
        self.assertEqual(len(older['turns']), 5)
        self.assertFalse(older['has_more'])
        self.assertEqual(self.client_for(self.other).get(url, {'paged': 1}).status_code, 404)
