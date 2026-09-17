from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from .models import Booking, BookingEvent, Motorcycle, Shop


class AdminNavigationTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_superuser(username='admin')
        self.customer = users.objects.create_user(username='customer')
        self.mechanic = users.objects.create_user(username='mechanic')
        group = Group.objects.create(name='mechanics')
        self.mechanic.groups.add(group)
        # A legacy admin with this group must still appear only as Admin.
        self.admin.groups.add(group)
        self.shop = Shop.objects.create(name='North Garage', address='Bangkok', phone='Test')
        self.shop.mechanics.add(self.mechanic)
        self.bike = Motorcycle.objects.create(owner=self.customer, brand='Honda', model='PCX', license_plate='ADMIN-TEST', year=2024)
        self.booking = Booking.objects.create(customer=self.customer, motorcycle=self.bike, shop=self.shop,
            shop_name=self.shop.name, motorcycle_label='Honda PCX ADMIN-TEST', problem='Check brakes',
            appointment_at=timezone.now() + timedelta(days=1))
        self.event = BookingEvent.objects.create(booking=self.booking, actor=self.customer, status='pending')
        self.client.force_login(self.admin)

    def results(self, url, params):
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        return list(response.context['cl'].result_list)

    def test_role_filter_is_exclusive_and_searchable(self):
        for role, user in [('admin', self.admin), ('mechanic', self.mechanic), ('customer', self.customer)]:
            self.assertEqual(self.results('/admin/auth/user/', {'role': role}), [user])
        self.assertEqual(self.results('/admin/auth/user/', {'role': 'customer', 'q': 'mechanic'}), [])

    def test_admin_searches_motorcycle_shop_and_booking(self):
        self.assertEqual(self.results('/admin/garage/motorcycle/', {'q': 'ADMIN-TEST'}), [self.bike])
        shops = self.results('/admin/garage/shop/', {'q': 'mechanic'})
        self.assertEqual(shops, [self.shop])
        self.assertEqual(shops[0].member_count, 1)
        self.assertEqual(self.results('/admin/garage/booking/', {'q': 'ADMIN-TEST', 'status__exact': 'pending'}), [self.booking])
        self.assertEqual(self.results('/admin/garage/booking/', {'status__exact': 'completed'}), [])

    def test_history_is_visible_but_cannot_be_rewritten(self):
        url = f'/admin/garage/booking/{self.booking.pk}/change/'
        response = self.client.get(url)
        self.assertContains(response, 'Check brakes')
        self.assertEqual(len(response.context['inline_admin_formsets']), 1)
        self.assertNotContains(response, 'name="_save"')
        self.assertEqual(self.client.post(url, {'status': 'completed'}).status_code, 403)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'pending')
        event_url = f'/admin/garage/bookingevent/{self.event.pk}/change/'
        self.assertEqual(self.client.post(event_url, {'status': 'completed'}).status_code, 403)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, 'pending')

    def test_customers_cannot_access_admin_lists(self):
        self.client.force_login(self.customer)
        for model in ['motorcycle', 'shop', 'booking', 'bookingevent']:
            response = self.client.get(f'/admin/garage/{model}/')
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response['Location'].startswith('/admin/login/'))
