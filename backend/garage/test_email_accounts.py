import re
import secrets
from datetime import timedelta
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from unittest.mock import patch
from oidc_provider.models import Client as OIDCClient, Token
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

    def signup(self):
        response = self.client.post('/accounts/register/', {
            'username': 'email-test', 'email': 'Email-Test@example.com',
            'phone': '0812345678', 'account_type': 'customer',
            'password1': self.password, 'password2': self.password,
        })
        self.assertEqual(response.status_code, 200)
        return get_user_model().objects.get(username='email-test')

    def test_signup_requires_confirmation_and_link_is_single_use(self):
        user = self.signup()
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        path = self.email_path()
        self.assertNotIn(user.email, path)
        self.assertNotIn(user.password, path)
        self.assertEqual(self.client.post('/accounts/login/', {
            'username': user.username, 'password': self.password}).status_code, 200)
        self.assertFalse(get_user_model().objects.get(pk=user.pk).is_active)
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertContains(self.client.get(path), 'name="referrer" content="same-origin"')
        self.assertTrue(self.client.post(path).context['verified'])
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.profile.email_verified_at)
        self.assertFalse(self.client.post(path).context['verified'])

    def test_invalid_and_expired_links_and_resend_are_generic(self):
        user = self.signup()
        path = self.email_path()
        self.assertFalse(self.client.post(path.rstrip('/') + 'x/').context['verified'])
        with override_settings(EMAIL_VERIFICATION_TIMEOUT=-1):
            self.assertFalse(self.client.post(path).context['verified'])
        self.assertFalse(get_user_model().objects.get(pk=user.pk).is_active)
        before = len(mail.outbox)
        unknown = self.client.post('/accounts/resend-verification/', {'email': 'unknown@example.com'})
        known = self.client.post('/accounts/resend-verification/', {'email': user.email})
        self.assertEqual(unknown.status_code, known.status_code)
        self.assertEqual(len(mail.outbox), before + 1)
        self.client.post('/accounts/resend-verification/', {'email': user.email})
        self.assertEqual(len(mail.outbox), before + 1)

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

    def test_password_reset_is_generic_and_revokes_oidc_tokens(self):
        user = get_user_model().objects.create_user(
            username='reset-test', email='reset@example.com', password=self.password)
        oidc = OIDCClient.objects.create(client_id='the-x-web', client_type='public')
        Token.objects.create(user=user, client=oidc, access_token=secrets.token_urlsafe(),
            refresh_token=secrets.token_urlsafe(), expires_at=timezone.now() + timedelta(hours=1),
            _scope='openid profile')
        unknown = self.client.post('/accounts/password-reset/', {'email': 'unknown@example.com'})
        known = self.client.post('/accounts/password-reset/', {'email': user.email})
        self.assertEqual(unknown['Location'], known['Location'])
        self.assertEqual(len(mail.outbox), 1)
        self.client.post('/accounts/password-reset/', {'email': 'RESET@example.com'})
        self.assertEqual(len(mail.outbox), 1)
        link = self.email_path()
        redirect = self.client.get(link)
        self.assertEqual(redirect.status_code, 302)
        reset_form = redirect['Location']
        reset_page = self.client.get(reset_form)
        self.assertContains(reset_page, 'รีเซ็ตรหัสผ่านใหม่')
        self.assertContains(reset_page, 'name="new_password1"')
        self.assertContains(reset_page, 'name="new_password2"')
        new_password = secrets.token_urlsafe(24)
        completed = self.client.post(reset_form, {
            'new_password1': new_password, 'new_password2': new_password})
        self.assertEqual(completed.status_code, 302)
        self.assertEqual(completed['Location'], '/accounts/password-reset/complete/')
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))
        self.assertFalse(user.check_password(self.password))
        self.assertFalse(Token.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[-1].to, [user.email])
        self.assertIn('ถูกเปลี่ยนแล้ว', mail.outbox[-1].subject)
        self.assertContains(self.client.get(link, follow=True), 'ลิงก์ใช้ไม่ได้')

    def test_reset_notification_failure_does_not_undo_password_change(self):
        user = get_user_model().objects.create_user(
            username='reset-notify', email='notify@example.com', password=self.password)
        self.client.post('/accounts/password-reset/', {'email': user.email})
        link = self.email_path()
        reset_form = self.client.get(link)['Location']
        new_password = secrets.token_urlsafe(24)
        with patch('garage.email_accounts.send_mail', side_effect=OSError):
            response = self.client.post(reset_form, {
                'new_password1': new_password, 'new_password2': new_password})
        self.assertEqual(response['Location'], '/accounts/password-reset/complete/')
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))

    def test_inactive_account_gets_no_reset_link(self):
        user = self.signup()
        mail.outbox.clear()
        self.client.post('/accounts/password-reset/', {'email': user.email})
        self.assertEqual(len(mail.outbox), 0)

    def test_verification_send_failure_keeps_account_inactive(self):
        with patch('garage.email_accounts.send_mail', side_effect=OSError):
            user = self.signup()
        self.assertFalse(user.is_active)
        self.assertContains(self.client.get('/accounts/resend-verification/'), 'ส่งลิงก์ยืนยัน')

    def test_console_encoding_failure_does_not_break_registration(self):
        encoding_error = UnicodeEncodeError('cp1252', 'ยืนยัน', 0, 1, 'unsupported')
        with patch('garage.email_accounts.send_mail', side_effect=encoding_error):
            user = self.signup()
        self.assertFalse(user.is_active)

    def test_verification_requires_csrf_on_post(self):
        self.signup()
        path = self.email_path()
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.post(path).status_code, 403)
        browser.get(path)
        response = browser.post(path, {'csrfmiddlewaretoken': browser.cookies['csrftoken'].value})
        self.assertTrue(response.context['verified'])

    def test_expired_password_reset_link_is_rejected(self):
        user = get_user_model().objects.create_user(
            username='reset-expired', email='expired@example.com', password=self.password)
        self.client.post('/accounts/password-reset/', {'email': user.email})
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertContains(self.client.get(self.email_path(), follow=True), 'ลิงก์ใช้ไม่ได้')

    def test_admin_disabled_account_cannot_self_activate(self):
        user = get_user_model().objects.create_user(
            username='disabled', email='disabled@example.com', password=self.password,
            is_active=False)
        from .email_accounts import verification_token
        path = '/accounts/verify-email/' + verification_token(user, user.email, 'signup') + '/'
        self.assertFalse(self.client.post(path).context['verified'])
        self.client.post('/accounts/resend-verification/', {'email': user.email})
        self.assertEqual(len(mail.outbox), 0)
