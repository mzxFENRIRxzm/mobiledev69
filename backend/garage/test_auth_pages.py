import secrets
from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class LoginRecoveryTests(TestCase):
    def test_wrong_password_keeps_oidc_destination_and_never_echoes_password(self):
        password = secrets.token_urlsafe(24)
        get_user_model().objects.create_user(username='rider', password=password)
        destination = '/openid/authorize/?client_id=the-x-web&state=original&code_challenge=challenge'
        response = self.client.post('/accounts/login/', {
            'username': 'rider', 'password': password + '-wrong', 'next': destination,
        })
        self.assertContains(response, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
        self.assertEqual(response.context['next'], destination)
        self.assertNotContains(response, password)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'autocomplete="current-password"')

    def test_login_preserves_oidc_state_and_ignores_posted_role(self):
        password = secrets.token_urlsafe(24)
        user = get_user_model().objects.create_user(username='rider', password=password)
        destination = '/openid/authorize/?client_id=the-x-web&state=original&code_challenge=challenge'
        response = self.client.post('/accounts/login/', {
            'username': 'rider', 'password': password, 'next': destination, 'role': 'admin',
        })
        self.assertEqual(response['Location'], destination)
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)

    def test_login_rejects_external_next_url(self):
        password = secrets.token_urlsafe(24)
        get_user_model().objects.create_user(username='rider', password=password)
        response = self.client.post('/accounts/login/', {
            'username': 'rider', 'password': password, 'next': 'https://example.com/steal',
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('example.com', response['Location'])

    def test_stale_form_rejected_then_fresh_form_switches_account(self):
        password = secrets.token_urlsafe(24)
        users = get_user_model()
        first = users.objects.create_user(username="first", password=password)
        second = users.objects.create_user(username="second", password=password)
        client = Client(enforce_csrf_checks=True)
        url = "/accounts/login/?next=/openid/authorize/%3Fclient_id%3Dthe-x-web"
        form = client.get(url)
        token = client.cookies['csrftoken'].value
        self.assertIn('no-store', form['Cache-Control'])
        response = client.post(url, {'username': 'first', 'password': password, 'csrfmiddlewaretoken': token, 'next': '/api/me/'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session['_auth_user_id'], str(first.pk))
        # A second tab still holds the pre-login token while the cookie has rotated.
        response = client.post(url, {'username': 'second', 'password': password, 'csrfmiddlewaretoken': token})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'เปิดฟอร์มเข้าสู่ระบบใหม่', status_code=403)
        self.assertNotContains(response, password, status_code=403)
        self.assertEqual(client.session['_auth_user_id'], str(first.pk))
        retry = response.context['retry_url']
        self.assertIn('next=', retry)
        client.get(retry)
        response = client.post(retry, {'username': 'second', 'password': password,
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value, 'next': '/api/me/'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session['_auth_user_id'], str(second.pk))

    def test_missing_token_is_still_rejected_and_retry_is_local(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/accounts/login/?next=https://example.com', {'username': 'someone'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.context['retry_url'], '/accounts/login/')
        self.assertNotIn('example.com', response.context['retry_url'])
        self.assertIn('no-store', response['Cache-Control'])
