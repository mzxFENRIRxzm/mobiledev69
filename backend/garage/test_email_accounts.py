import re
import secrets
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(PUBLIC_SIGNUP_ENABLED=True,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailAccountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.password = secrets.token_urlsafe(24)

    def email_path(self, index=-1):
        link = re.search(r'https?://\S+', mail.outbox[index].body).group()
        return urlparse(link).path

    def test_signup_activates_without_email_or_message(self):
        response = self.client.post('/accounts/register/', {
            'username': 'new-rider', 'email': '', 'phone': '0812345678',
            'account_type': 'customer', 'password1': self.password,
            'password2': self.password,
        })
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username='new-rider')
        self.assertTrue(user.is_active)
        self.assertFalse(user.profile.awaiting_signup_verification)
        self.assertEqual(mail.outbox, [])

    def test_profile_email_is_pending_until_confirmed(self):
        user = get_user_model().objects.create_user(
            username='profile-email', email='old@example.com', password=self.password)
        api = APIClient()
        api.force_authenticate(user)
        response = api.patch('/api/profile/', {'email': 'NEW@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], 'old@example.com')
        self.assertEqual(response.data['pending_email'], 'new@example.com')
        self.assertEqual(mail.outbox[-1].to, ['new@example.com'])
        path = self.email_path()
        self.assertTrue(self.client.post(path).context['verified'])
        user.refresh_from_db()
        self.assertEqual(user.email, 'new@example.com')
        self.assertEqual(user.profile.pending_email, '')
        self.assertIsNotNone(user.profile.email_verified_at)
        self.assertFalse(self.client.post(path).context['verified'])

    def test_replaced_pending_email_invalidates_old_link(self):
        user = get_user_model().objects.create_user(
            username='profile-email', email='old@example.com', password=self.password)
        api = APIClient()
        api.force_authenticate(user)
        api.patch('/api/profile/', {'email': 'first@example.com'}, format='json')
        first = self.email_path()
        api.patch('/api/profile/', {'email': 'second@example.com'}, format='json')
        self.assertFalse(self.client.post(first).context['verified'])
        self.assertTrue(self.client.post(self.email_path()).context['verified'])
        user.refresh_from_db()
        self.assertEqual(user.email, 'second@example.com')

    def test_profile_verification_expiry_and_resend_are_generic(self):
        user = get_user_model().objects.create_user(
            username='profile-email', email='old@example.com', password=self.password)
        api = APIClient()
        api.force_authenticate(user)
        api.patch('/api/profile/', {'email': 'new@example.com'}, format='json')
        path = self.email_path()
        self.assertFalse(self.client.post(path.rstrip('/') + 'x/').context['verified'])
        with override_settings(EMAIL_VERIFICATION_TIMEOUT=-1):
            self.assertFalse(self.client.post(path).context['verified'])
        before = len(mail.outbox)
        unknown = self.client.post('/accounts/resend-verification/', {
            'email': 'unknown@example.com'})
        known = self.client.post('/accounts/resend-verification/', {
            'email': 'new@example.com'})
        self.assertEqual(unknown.status_code, known.status_code)
        self.assertEqual(len(mail.outbox), before + 1)
        self.client.post('/accounts/resend-verification/', {'email': 'new@example.com'})
        self.assertEqual(len(mail.outbox), before + 1)

    def test_verification_requires_csrf_on_post(self):
        user = get_user_model().objects.create_user(
            username='profile-email', email='old@example.com', password=self.password)
        api = APIClient()
        api.force_authenticate(user)
        api.patch('/api/profile/', {'email': 'new@example.com'}, format='json')
        path = self.email_path()
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.post(path).status_code, 403)
        browser.get(path)
        response = browser.post(path, {
            'csrfmiddlewaretoken': browser.cookies['csrftoken'].value})
        self.assertTrue(response.context['verified'])

    def test_admin_disabled_account_cannot_self_activate(self):
        user = get_user_model().objects.create_user(
            username='disabled', email='disabled@example.com', password=self.password,
            is_active=False)
        from .email_accounts import verification_token
        path = '/accounts/verify-email/' + verification_token(user, user.email, 'signup') + '/'
        self.assertFalse(self.client.post(path).context['verified'])
        self.client.post('/accounts/resend-verification/', {'email': user.email})
        self.assertEqual(len(mail.outbox), 0)
