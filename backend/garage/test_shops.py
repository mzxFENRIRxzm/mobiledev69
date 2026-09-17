from django.contrib.auth import get_user_model
from django.test import TestCase
from .test_bookings import BookingSetup
from .models import Booking, Shop


class ShopTests(BookingSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.outsider = get_user_model().objects.create_user(username="outside")
        self.outsider.groups.set(self.mechanic.groups.all())
        self.shop_b = Shop.objects.create(name="Shop B", address="Chiang Mai", phone="contact B")
        self.shop_b.mechanics.add(self.outsider)

    def test_other_shop_cannot_see_or_transition_booking(self):
        pk = self.create()
        api = self.client_for(self.outsider)
        self.assertEqual(api.get('/api/bookings/').data['count'], 0)
        self.assertEqual(api.get(f'/api/bookings/{pk}/').status_code, 404)
        for action in ['accept', 'start', 'complete', 'cancel']:
            self.assertEqual(self.transition(self.outsider, pk, action, cancellation_reason='closed').status_code, 404)
        self.assertEqual(Booking.objects.get(pk=pk).status, 'pending')

    def test_shop_required_and_closed_shop_rejected(self):
        payload = {k: v for k, v in self.payload.items() if k != 'shop'}
        self.assertEqual(self.api.post('/api/bookings/', payload).status_code, 400)
        self.assertEqual(self.api.post('/api/bookings/', {**payload, 'shop': ''}).status_code, 400)
        self.shop.accepting_bookings = False
        self.shop.save()
        self.assertEqual(self.api.post('/api/bookings/', self.payload).status_code, 400)

    def test_only_members_can_edit_shop_and_cannot_change_membership(self):
        endpoint = f'/api/shops/{self.shop.pk}/'
        self.assertEqual(self.api.patch(endpoint, {'name': 'hacked'}).status_code, 403)
        self.assertEqual(self.client_for(self.outsider).patch(endpoint, {'name': 'hacked'}).status_code, 403)
        api = self.client_for(self.mechanic)
        response = api.patch(endpoint, {'name': 'New name', 'mechanics': [self.outsider.pk]}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.shop.mechanics.filter(pk=self.outsider.pk).exists())
        self.assertEqual(api.post('/api/shops/', {'name': 'new'}).status_code, 405)
        self.assertEqual(api.delete(endpoint).status_code, 405)
        self.assertEqual(api.patch(endpoint, {'phone': ' '}).status_code, 400)

    def test_shop_cancel_requires_reason_and_keeps_history(self):
        pk = self.create()
        self.transition(self.mechanic, pk, 'accept')
        self.assertEqual(self.transition(self.mechanic, pk, 'cancel').status_code, 400)
        response = self.transition(self.mechanic, pk, 'cancel', cancellation_reason='อะไหล่ไม่พร้อม')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['cancellation_reason'], 'อะไหล่ไม่พร้อม')
        self.assertEqual(response.data['events'][-1]['actor'], self.mechanic.username)
        self.create()

    def test_closed_shop_can_finish_existing_job_and_snapshot_stays(self):
        pk = self.create()
        self.client_for(self.mechanic).patch(f'/api/shops/{self.shop.pk}/', {'name': 'Renamed', 'accepting_bookings': False}, format='json')
        self.assertEqual(self.transition(self.mechanic, pk, 'accept').status_code, 200)
        self.assertEqual(self.api.get(f'/api/bookings/{pk}/').data['shop_name'], 'Shop A')

    def test_removed_member_loses_access_to_assigned_job(self):
        pk = self.create()
        self.transition(self.mechanic, pk, 'accept')
        self.shop.mechanics.remove(self.mechanic)
        self.assertEqual(self.client_for(self.mechanic).get(f'/api/bookings/{pk}/').status_code, 404)
        self.assertEqual(self.transition(self.mechanic, pk, 'start').status_code, 404)

    def test_legacy_pending_is_private_and_customer_can_cancel(self):
        pk = self.create()
        Booking.objects.filter(pk=pk).update(shop=None, shop_name='')
        self.assertEqual(self.client_for(self.mechanic).get(f'/api/bookings/{pk}/').status_code, 404)
        self.assertEqual(self.transition(self.mechanic, pk, 'accept').status_code, 404)
        self.assertEqual(self.transition(self.customer, pk, 'cancel').status_code, 200)

    def test_legacy_assigned_job_can_finish(self):
        pk = self.create()
        self.transition(self.mechanic, pk, 'accept')
        Booking.objects.filter(pk=pk).update(shop=None, shop_name='')
        self.assertEqual(self.transition(self.mechanic, pk, 'start').status_code, 200)
        self.assertEqual(self.transition(self.mechanic, pk, 'complete', repair_notes='done').status_code, 200)
