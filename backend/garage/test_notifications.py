from django.test import TestCase
from rest_framework.test import APIClient
from .models import Notification
from .test_bookings import BookingSetup


class NotificationTests(BookingSetup, TestCase):
    def send(self, body='Hello'):
        room = self.api.post('/api/conversations/', {'shop': self.shop.pk}).data['id']
        response = self.api.post(f'/api/conversations/{room}/messages/', {'body': body})
        self.assertEqual(response.status_code, 201)
        return room, response.data['id']

    def test_message_recipients_privacy_and_read_boundary(self):
        room, first = self.send()
        mechanic = self.client_for(self.mechanic)
        data = mechanic.get('/api/notifications/').data
        self.assertEqual(data['unread_count'], 1)
        self.assertEqual(self.api.get('/api/notifications/').data['unread_count'], 0)
        self.assertEqual(self.client_for(self.other).get('/api/notifications/').data['results'], [])
        notification_id = data['results'][0]['id']
        self.assertEqual(self.client_for(self.other).post(f'/api/notifications/{notification_id}/read/').status_code, 404)
        self.send('Second')
        self.assertEqual(mechanic.get('/api/conversations/').data[0]['unread_count'], 2)
        self.assertEqual(mechanic.post(f'/api/conversations/{room}/read/', {'through_message': first}).status_code, 200)
        self.assertEqual(mechanic.get('/api/notifications/').data['unread_count'], 1)
        self.assertEqual(self.client_for(self.mechanic2).get('/api/notifications/').data['unread_count'], 2)
        self.assertEqual(mechanic.get('/api/conversations/').data[0]['last_message'], 'Second')
        self.shop.mechanics.remove(self.mechanic)
        self.assertEqual(mechanic.get('/api/notifications/').data['results'], [])
        self.assertEqual(mechanic.post(f'/api/notifications/{notification_id}/read/').status_code, 404)

    def test_booking_events_notify_other_participants_and_failed_transition_is_silent(self):
        pk = self.create()
        self.assertEqual(Notification.objects.filter(booking_id=pk).count(), 2)
        self.transition(self.mechanic, pk, 'accept')
        self.assertEqual(self.api.get('/api/notifications/').data['unread_count'], 1)
        count = Notification.objects.count()
        self.assertEqual(self.transition(self.mechanic2, pk, 'accept').status_code, 409)
        self.assertEqual(Notification.objects.count(), count)
        for action in ['start', 'complete']:
            self.transition(self.mechanic, pk, action, repair_notes='Done')
        self.assertEqual(self.api.get('/api/notifications/').data['unread_count'], 3)

    def test_read_all_is_bounded_idempotent_and_requires_auth(self):
        self.send()
        client = self.client_for(self.mechanic)
        boundary = client.get('/api/notifications/').data['latest_id']
        self.send('Later')
        for _ in range(2):
            self.assertEqual(client.post('/api/notifications/read-all/', {'through_id': boundary}).status_code, 200)
        self.assertEqual(client.get('/api/notifications/').data['unread_count'], 1)
        self.assertEqual(client.post('/api/notifications/read-all/', {}).status_code, 400)
        self.assertEqual(APIClient().get('/api/notifications/').status_code, 401)

    def test_staff_reply_notifies_customer_and_colleague_not_sender(self):
        room, _ = self.send()
        Notification.objects.all().delete()  # Disposable test database only.
        client = self.client_for(self.mechanic)
        client.post(f'/api/conversations/{room}/messages/', {'body': 'Welcome'})
        self.assertEqual(self.api.get('/api/notifications/').data['unread_count'], 1)
        self.assertEqual(client.get('/api/notifications/').data['unread_count'], 0)
        self.assertEqual(self.client_for(self.mechanic2).get('/api/notifications/').data['unread_count'], 1)
