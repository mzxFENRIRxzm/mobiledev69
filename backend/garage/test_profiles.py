from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Shop, UserProfile


class ProfileTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.customer = users.objects.create_user(username='profile-customer', email='customer@example.com')
        self.mechanic = users.objects.create_user(username='profile-mechanic', email='mechanic@example.com')
        self.mechanic.groups.add(Group.objects.create(name='mechanics'))
        self.client = APIClient()
        self.client.force_authenticate(self.customer)

    def test_authentication_required(self):
        self.client.force_authenticate(None)
        for method in ('get', 'patch'):
            self.assertEqual(getattr(self.client, method)('/api/profile/').status_code, 401)

    def test_legacy_profile_read_has_no_side_effect_and_is_private(self):
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response.data['phone'], '')
        self.assertNotIn('password', response.data)
        self.assertFalse(UserProfile.objects.exists())

    def test_customer_and_mechanic_update_only_their_own_profile(self):
        for user, role in ((self.customer, 'customer'), (self.mechanic, 'mechanic')):
            self.client.force_authenticate(user)
            response = self.client.patch('/api/profile/', {'first_name': ' สมชาย ', 'last_name': 'ทดสอบ',
                'phone': '+66812345678', 'email': f'{role.upper()}@example.com'}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['role'], role)
            self.assertEqual(response.data['first_name'], 'สมชาย')
            self.assertEqual(response.data['email'], f'{role}@example.com')
            user.refresh_from_db()
            self.assertEqual(user.profile.phone, '+66812345678')
            self.assertFalse(user.is_staff or user.is_superuser)

    def test_sensitive_or_foreign_fields_rejected_without_partial_update(self):
        for field, value in [('role', 'admin'), ('is_staff', True), ('is_superuser', True),
                             ('user_id', self.mechanic.pk), ('username', 'other'), ('password', 'unsafe')]:
            response = self.client.patch('/api/profile/', {field: value, 'first_name': 'Changed'}, format='json')
            self.assertEqual(response.status_code, 400)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, '')
        self.assertEqual(self.client.patch(f'/api/profile/{self.mechanic.pk}/', {}, format='json').status_code, 404)

    def test_validation_and_duplicate_email_do_not_save_other_fields(self):
        for values in [{'email': 'MECHANIC@example.com'}, {'email': 'invalid'}, {'email': ''},
                       {'phone': '123'}, {'phone': '12345x789'}, {'phone': None}, {'first_name': 'x' * 151}]:
            response = self.client.patch('/api/profile/', {**values, 'last_name': 'Changed'}, format='json')
            self.assertEqual(response.status_code, 400)
            self.customer.refresh_from_db()
            self.assertEqual(self.customer.last_name, '')

    def test_email_race_cannot_replace_primary_address_before_verification(self):
        with patch('garage.profiles.ProfileUpdateSerializer.validate_email', return_value=self.mechanic.email):
            response = self.client.patch('/api/profile/', {'email': 'race@example.com', 'first_name': 'Changed',
                'phone': '0812345678'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, 'Changed')
        self.assertEqual(self.customer.email, 'customer@example.com')
        self.assertEqual(self.customer.profile.pending_email, self.mechanic.email)

    def test_personal_phone_does_not_change_public_shop_phone(self):
        shop = Shop.objects.create(name='Test', address='Test', phone='0899999999')
        shop.mechanics.add(self.mechanic)
        self.client.force_authenticate(self.mechanic)
        response = self.client.patch('/api/profile/', {'phone': '0812345678'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/me/').data['phone'], '0812345678')
        shop.refresh_from_db()
        self.assertEqual(shop.phone, '0899999999')
