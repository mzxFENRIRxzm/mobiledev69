import secrets
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from oidc_provider.models import Client as OIDCClient, Token


@override_settings(LOCAL_USERNAME_RESET_ENABLED=True, SITE_URL='http://localhost:18080')
@patch.dict('os.environ', {'HTTP_BIND': '127.0.0.1:18080'})
class UsernameResetTests(TestCase):
    url = '/accounts/password-reset/'
    host = {'HTTP_HOST': 'localhost:18080'}

    def test_customer_reset_revokes_oidc_tokens_without_email(self):
        old_password = secrets.token_urlsafe(24)
        new_password = secrets.token_urlsafe(24)
        user = get_user_model().objects.create_user(
            username='rider', password=old_password)
        oidc = OIDCClient.objects.create(client_id='the-x-web', client_type='public')
        Token.objects.create(user=user, client=oidc,
            access_token=secrets.token_urlsafe(), refresh_token=secrets.token_urlsafe(),
            expires_at=timezone.now() + timedelta(hours=1), _scope='openid profile')
        response = self.client.post(self.url, {
            'username': user.username,
            'new_password1': new_password,
            'new_password2': new_password,
        }, **self.host)
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))
        self.assertFalse(user.check_password(old_password))
        self.assertFalse(Token.objects.filter(user=user).exists())
        self.assertEqual(mail.outbox, [])

    def test_admin_and_inactive_accounts_cannot_be_reset(self):
        admin = get_user_model().objects.create_superuser('admin', password=secrets.token_urlsafe(24))
        inactive = get_user_model().objects.create_user(
            username='inactive', password=secrets.token_urlsafe(24), is_active=False)
        for user in (admin, inactive):
            old_hash = user.password
            response = self.client.post(self.url, {
                'username': user.username,
                'new_password1': secrets.token_urlsafe(24),
                'new_password2': secrets.token_urlsafe(24),
            }, **self.host)
            self.assertEqual(response.status_code, 200)
            self.assertIn('username', response.context['form'].errors)
            user.refresh_from_db()
            self.assertEqual(user.password, old_hash)

    def test_public_origin_and_direct_host_are_rejected(self):
        with override_settings(SITE_URL='https://the-x.example'):
            self.assertEqual(self.client.get(self.url, **self.host).status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        with patch.dict('os.environ', {'HTTP_BIND': '0.0.0.0:80'}):
            self.assertEqual(self.client.get(self.url, **self.host).status_code, 404)

    def test_reset_requires_csrf_and_valid_password(self):
        user = get_user_model().objects.create_user(
            username='rider', password=secrets.token_urlsafe(24))
        browser = Client(enforce_csrf_checks=True)
        data = {'username': user.username, 'new_password1': '123', 'new_password2': '123'}
        self.assertEqual(browser.post(self.url, data, **self.host).status_code, 403)
        browser.get(self.url, **self.host)
        response = browser.post(self.url, {
            **data, 'csrfmiddlewaretoken': browser.cookies['csrftoken'].value}, **self.host)
        self.assertEqual(response.status_code, 200)
        self.assertIn('new_password1', response.context['form'].errors)
