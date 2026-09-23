import secrets
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Shop, UserProfile
from .registration import CustomerRegistrationForm
from .email_accounts import verification_token
from django.urls import reverse
from .shops import ShopSerializer
from .uploads import clean_shop_photo
from django.core.exceptions import ValidationError


@override_settings(PUBLIC_SIGNUP_ENABLED=True)
class ProviderRegistrationTests(TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.folder.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        password = secrets.token_urlsafe(24)
        self.data = dict(username='provider', email='provider@example.com', phone='0812345678',
            account_type='mechanic', password1=password, password2=password,
            shop_name='Test Garage', shop_address='Test address', latitude='13.756300', longitude='100.501800')

    def photo(self):
        output = BytesIO()
        Image.new('RGB', (50, 40), 'red').save(output, format='PNG')
        return SimpleUploadedFile('untrusted-name.png', output.getvalue(), content_type='image/png')

    def test_provider_creates_profile_shop_and_membership_and_normalizes_photo(self):
        response = self.client.post('/accounts/register/', {**self.data, 'shop_photo': self.photo(), 'is_superuser': 'true'})
        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(username='provider')
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertFalse(user.is_active)
        self.assertEqual(user.profile.phone, self.data['phone'])
        self.assertTrue(user.groups.filter(name='mechanics').exists())
        shop = user.service_shops.get()
        self.assertTrue(shop.awaiting_owner_verification)
        self.assertFalse(shop.accepting_bookings)
        viewer = APIClient()
        viewer.force_authenticate(get_user_model().objects.create_user(username='shop-viewer'))
        self.assertEqual(viewer.get('/api/shops/').data['count'], 0)
        self.assertEqual(viewer.get(f'/api/shops/{shop.pk}/').status_code, 404)
        link = reverse('verify-email', args=[verification_token(user, user.email, 'signup')])
        self.assertTrue(self.client.post(link).context['verified'])
        shop.refresh_from_db()
        self.assertFalse(shop.awaiting_owner_verification)
        self.assertTrue(shop.accepting_bookings)
        self.assertEqual(viewer.get('/api/shops/').data['count'], 1)
        self.assertEqual(shop.latitude, Decimal('13.756300'))
        self.assertEqual(shop.longitude, Decimal('100.501800'))
        self.assertEqual(shop.phone, self.data['phone'])
        self.assertNotIn('untrusted-name', shop.photo.name)
        with Image.open(shop.photo.path) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertFalse(image.getexif())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_provider_requires_shop_photo_address_and_pin(self):
        response = self.client.post('/accounts/register/', {**self.data, 'shop_address': '', 'latitude': '', 'longitude': ''})
        for field in ('shop_address', 'shop_photo', 'latitude', 'longitude'):
            self.assertIn(field, response.context['form'].errors)
        self.assertFalse(get_user_model().objects.exists())

    def test_customer_does_not_gain_membership_from_posted_shop_or_admin_fields(self):
        response = self.client.post('/accounts/register/', {**self.data, 'account_type': 'customer',
            'is_staff': 'true', 'role': 'admin', 'shop_photo': self.photo()})
        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get()
        self.assertFalse(user.is_staff or user.is_superuser or user.groups.exists())
        self.assertEqual(user.profile.phone, '0812345678')
        self.assertFalse(Shop.objects.exists())
        self.assertFalse(list(Path(self.folder.name).rglob('*.jpg')))

    def test_rejects_admin_account_type_invalid_phone_and_invalid_coordinates(self):
        for changes, field in [({'account_type': 'admin'}, 'account_type'), ({'phone': ''}, 'phone'),
                ({'phone': 'not-a-phone'}, 'phone'), ({'latitude': '91'}, 'latitude'),
                ({'longitude': '-181'}, 'longitude'), ({'latitude': 'NaN'}, 'latitude')]:
            with self.subTest(field=field, changes=changes):
                form = CustomerRegistrationForm({**self.data, **changes}, {'shop_photo': self.photo()})
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_rejects_fake_oversized_or_unsupported_image(self):
        for file in [SimpleUploadedFile('fake.jpg', b'<script>invalid</script>', content_type='image/jpeg'),
                SimpleUploadedFile('big.png', b'x' * (5 * 1024 * 1024 + 1)),
                SimpleUploadedFile('vector.svg', b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')]:
            with self.subTest(file=file.name), self.assertRaises(ValidationError):
                clean_shop_photo(file)

    def test_membership_failure_rolls_back_account_profile_shop_and_stored_photo(self):
        form = CustomerRegistrationForm(self.data, {'shop_photo': self.photo()})
        self.assertTrue(form.is_valid(), form.errors)
        manager = Shop.mechanics.related_manager_cls
        with patch.object(manager, 'add', side_effect=IntegrityError), self.assertRaises(IntegrityError):
            form.save()
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(UserProfile.objects.exists())
        self.assertFalse(Shop.objects.exists())
        self.assertFalse(list(Path(self.folder.name).rglob('*.jpg')))

    def test_coordinates_constraint_rejects_half_pair_or_out_of_range(self):
        for coordinates in [dict(latitude=0), dict(latitude=91, longitude=0)]:
            with self.subTest(coordinates=coordinates), self.assertRaises(IntegrityError), transaction.atomic():
                Shop.objects.create(name='invalid', **coordinates)

    def test_new_shop_media_fields_are_readonly_in_api(self):
        fields = ShopSerializer().fields
        for name in ('photo', 'latitude', 'longitude'):
            self.assertTrue(fields[name].read_only)

    def test_password_controls_shared_by_login_signup_and_admin(self):
        for url in ('/accounts/login/', '/accounts/register/', '/admin/login/'):
            response = self.client.get(url)
            self.assertContains(response, 'garage/passwords.js')
            self.assertContains(response, 'garage/passwords.css')
