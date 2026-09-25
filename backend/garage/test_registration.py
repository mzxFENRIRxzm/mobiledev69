import secrets
import os
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from oidc_provider.models import Client as OIDCClient

from .roles import RoleChangeForm


@override_settings(PUBLIC_SIGNUP_ENABLED=True)
class RegistrationTests(TestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24)
        self.destination = '/openid/authorize/?client_id=the-x-web&state=keep-state&code_challenge=keep-challenge'
        self.data = dict(username='new-rider', email='Rider@Example.com',
            phone='0812345678', account_type='customer',
            password1=self.password, password2=self.password, next=self.destination)

    def test_customer_registration_and_login_preserve_oidc_destination(self):
        response = self.client.post('/accounts/register/', {
            **self.data, 'role': 'admin', 'is_superuser': 'true', 'is_staff': 'true', 'groups': ['mechanics'],
        })
        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlparse(response['Location']).query)
        self.assertEqual(query['next'], [self.destination])
        self.assertEqual(query['registered'], ['1'])
        user = get_user_model().objects.get(username='new-rider')
        self.assertEqual(user.email, 'rider@example.com')
        self.assertTrue(user.check_password(self.password))
        self.assertFalse(user.is_staff or user.is_superuser or user.groups.exists())
        self.assertTrue(user.is_active)
        self.assertFalse(user.profile.awaiting_signup_verification)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post('/accounts/login/', dict(username=user.username,
            password=self.password, next=self.destination))
        self.assertEqual(response['Location'], self.destination)

    def test_email_is_optional_at_signup(self):
        response = self.client.post('/accounts/register/', {**self.data, 'email': ''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_user_model().objects.get(username='new-rider').email, '')

    def test_duplicate_email_case_insensitive_and_username_rejected(self):
        get_user_model().objects.create_user(username='existing', email='RIDER@example.com')
        response = self.client.post('/accounts/register/', self.data)
        self.assertIn('email', response.context['form'].errors)
        response = self.client.post('/accounts/register/', {**self.data, 'username': 'existing', 'email': 'other@example.com'})
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_invalid_email_password_strength_and_mismatch(self):
        for changes, field in [({'email': 'invalid'}, 'email'),
                ({'password1': '123', 'password2': '123'}, 'password2'),
                ({'password2': self.password + 'different'}, 'password2')]:
            with self.subTest(field=field):
                response = self.client.post('/accounts/register/', {**self.data, **changes})
                self.assertIn(field, response.context['form'].errors)
                self.assertNotContains(response, self.password)
        self.assertFalse(get_user_model().objects.exists())

    def test_external_destination_removed(self):
        for destination in ['https://example.com/steal', '//example.com/steal', 'javascript:alert(1)']:
            response = self.client.get('/accounts/register/', {'next': destination})
            self.assertEqual(response.context['next'], '')
        response = self.client.post('/accounts/register/', {**self.data, 'next': 'https://example.com'})
        self.assertNotIn('example.com', response['Location'])

    @override_settings(LOGIN_REDIRECT_URL='http://localhost:50000/login')
    def test_direct_signup_login_returns_to_flutter_to_start_oidc(self):
        self.client.post('/accounts/register/', {**self.data, 'next': ''})
        response = self.client.post('/accounts/login/', dict(username=self.data['username'], password=self.password))
        self.assertEqual(response['Location'], 'http://localhost:50000/login')

    def test_csrf_required_and_valid_submission_works(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/accounts/register/', self.data).status_code, 403)
        response = client.get('/accounts/register/', {'next': self.destination})
        self.assertIn('no-store', response['Cache-Control'])
        self.assertNotContains(response, 'name="referrer" content="no-referrer"')
        response = client.post('/accounts/register/', {**self.data,
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)

    def test_stale_registration_form_reopens_registration_not_login(self):
        client = Client(enforce_csrf_checks=True)
        existing_password = secrets.token_urlsafe(24)
        get_user_model().objects.create_user(username='existing-login', password=existing_password)
        client.get('/accounts/register/', {'next': self.destination})
        stale_token = client.cookies['csrftoken'].value
        client.get('/accounts/login/')
        client.post('/accounts/login/', {
            'username': 'existing-login', 'password': existing_password,
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        })
        response = client.post('/accounts/register/', {
            **self.data, 'csrfmiddlewaretoken': stale_token,
        })
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'เปิดฟอร์มสมัครสมาชิกใหม่', status_code=403)
        self.assertTrue(response.context['retry_url'].startswith('/accounts/register/?'))
        self.assertIn('next=', response.context['retry_url'])

    @override_settings(PUBLIC_SIGNUP_ENABLED=False)
    def test_disabled_signup_has_no_form_or_login_link(self):
        self.assertEqual(self.client.get('/accounts/register/').status_code, 404)
        self.assertEqual(self.client.post('/accounts/register/', self.data).status_code, 404)
        self.assertNotContains(self.client.get('/accounts/login/'), 'สมัครสมาชิกใหม่')

    @override_settings(DEBUG=False)
    def test_production_signup_does_not_send_email(self):
        response = self.client.post('/accounts/register/', self.data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(DEBUG=False, DEMO_EMAIL_VERIFICATION_LINK=True)
    def test_tunnel_demo_signup_needs_no_email(self):
        response = self.client.post('/accounts/register/', self.data, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_logged_in_user_can_open_signup_without_redirect_loop_or_session_replacement(self):
        user = get_user_model().objects.create_user(username='existing')
        self.client.force_login(user)
        login = self.client.get('/accounts/login/', {'next': self.destination})
        self.assertContains(login, 'สมัครสมาชิกใหม่')
        form = self.client.get('/accounts/register/', {'next': self.destination})
        self.assertEqual(form.status_code, 200)
        self.assertEqual(form.context['next'], self.destination)
        self.assertContains(form, 'สร้างบัญชี')
        self.assertEqual(self.client.post('/accounts/register/', self.data).status_code, 302)
        self.assertEqual(self.client.session['_auth_user_id'], str(user.pk))
        new_user = get_user_model().objects.get(username=self.data['username'])
        self.assertFalse(new_user.is_staff or new_user.is_superuser or new_user.groups.exists())
        self.assertEqual(get_user_model().objects.count(), 2)

    def test_database_rejects_case_insensitive_duplicate_but_allows_empty_emails(self):
        users = get_user_model()
        users.objects.create_user(username='first', email='Case@example.com')
        with self.assertRaises(IntegrityError), transaction.atomic():
            users.objects.create_user(username='second', email='case@EXAMPLE.COM')
        users.objects.create_user(username='legacy-one')
        users.objects.create_user(username='legacy-two')

    def test_integrity_race_returns_form_error_without_echoing_password(self):
        with patch('garage.registration.CustomerRegistrationForm.save', side_effect=IntegrityError):
            response = self.client.post('/accounts/register/', self.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())
        self.assertNotContains(response, self.password)

    def test_admin_edit_validates_email_before_database_constraint(self):
        users = get_user_model()
        users.objects.create_user(username='first', email='taken@example.com')
        second = users.objects.create_user(username='second', email='second@example.com')
        form = RoleChangeForm(instance=second, data=dict(username='second', email='TAKEN@example.com',
            role='customer', is_active=True))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    @override_settings(DEBUG=True, CORS_ALLOWED_ORIGINS=[
        'http://localhost:50000', 'http://192.168.1.43:50000'])
    def test_dev_bootstrap_registers_each_configured_frontend_origin(self):
        with patch.dict(os.environ, {
                'DEMO_PASSWORD': secrets.token_urlsafe(24),
                'MECHANIC_DEMO_PASSWORD': ''}):
            call_command('bootstrap_dev', verbosity=0)
        client = OIDCClient.objects.get(client_id='the-x-web')
        self.assertEqual(client.redirect_uris, [
            'http://localhost:50000/callback',
            'http://192.168.1.43:50000/callback',
        ])
        self.assertEqual(client.post_logout_redirect_uris, [
            'http://localhost:50000/login',
            'http://192.168.1.43:50000/login',
        ])
