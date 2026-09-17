import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client, TestCase
from django.utils import timezone
from oidc_provider.models import Client as OIDCClient, ResponseType
from rest_framework.test import APIClient
from .models import Booking, Motorcycle, Shop


class RoleAdminTests(TestCase):
    def setUp(self):
        self.password = secrets.token_urlsafe(24)
        users = get_user_model()
        self.admin = users.objects.create_superuser(username="admin", password=self.password)
        self.customer = users.objects.create_user(username="customer", password=self.password)
        self.mechanic = users.objects.create_user(username="mechanic", password=self.password)
        self.mechanic.groups.add(Group.objects.create(name="mechanics"))
        self.client.force_login(self.admin)

    def change(self, user, role, **extra):
        return self.client.post(f"/admin/auth/user/{user.pk}/change/", {
            "username": user.username, "role": role, "is_active": "on", **extra,
        })

    def test_admin_assigns_all_three_roles(self):
        for role in ["mechanic", "admin", "customer"]:
            self.assertEqual(self.change(self.customer, role).status_code, 302)
            api = APIClient()
            self.customer.refresh_from_db()
            api.force_authenticate(self.customer)
            self.assertEqual(api.get('/api/me/').data['role'], role)
            self.assertEqual(self.customer.is_staff, role == 'admin')
            self.assertEqual(self.customer.is_superuser, role == 'admin')

    def test_admin_creates_user_with_role(self):
        response = self.client.post('/admin/auth/user/add/', {
            'username': 'new-mechanic', 'password1': self.password,
            'password2': self.password, 'role': 'mechanic',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(get_user_model().objects.get(username='new-mechanic').groups.filter(name='mechanics').exists())

    def test_last_admin_cannot_be_demoted_deactivated_or_deleted(self):
        response = self.change(self.admin, 'customer')
        self.assertContains(response, 'ต้องเหลือ Adminuser')
        response = self.change(self.admin, 'admin', is_active='')
        self.assertContains(response, 'ต้องเหลือ Adminuser')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active and self.admin.is_superuser)
        self.assertEqual(self.client.post(f'/admin/auth/user/{self.admin.pk}/delete/', {'post': 'yes'}).status_code, 403)

    def test_staff_with_legacy_change_permission_cannot_escalate(self):
        self.customer.is_staff = True
        self.customer.save()
        self.customer.user_permissions.add(Permission.objects.get(codename='change_user'))
        self.client.force_login(self.customer)
        self.assertEqual(self.change(self.customer, 'admin').status_code, 403)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_superuser)

    def test_customer_and_mechanic_cannot_manage_roles(self):
        for user in [self.customer, self.mechanic]:
            self.client.force_login(user)
            self.assertEqual(self.change(user, 'admin').status_code, 302)
            user.refresh_from_db()
            self.assertFalse(user.is_superuser)

    def test_removing_mechanic_clears_memberships_but_preserves_history(self):
        shop = Shop.objects.create(name='Shop', address='Test', phone='Test')
        shop.mechanics.add(self.mechanic)
        self.assertEqual(self.change(self.mechanic, 'customer').status_code, 302)
        self.assertFalse(shop.mechanics.exists())
        self.assertFalse(self.mechanic.groups.filter(name='mechanics').exists())

    def test_active_repair_blocks_role_change(self):
        bike = Motorcycle.objects.create(owner=self.customer, brand='Test', model='Test', license_plate='Test', year=2024)
        Booking.objects.create(customer=self.customer, motorcycle=bike, mechanic=self.mechanic,
            appointment_at=timezone.now() + timedelta(days=1), problem='Test', status='in_progress')
        self.assertContains(self.change(self.mechanic, 'customer'), 'ต้องปิดงานซ่อม')
        self.assertTrue(self.mechanic.groups.filter(name='mechanics').exists())

    def test_three_browser_profiles_have_independent_oidc_sessions(self):
        call_command('creatersakey', verbosity=0)
        oidc = OIDCClient.objects.create(client_id='the-x-web', client_type='public', require_consent=False)
        oidc.redirect_uris = ['http://localhost:50000/callback']
        oidc.scope = ['openid', 'profile', 'email']
        oidc.save()
        code_type, _ = ResponseType.objects.get_or_create(value='code')
        oidc.response_types.add(code_type)
        profiles = []
        for user, role in [(self.admin, 'admin'), (self.mechanic, 'mechanic'), (self.customer, 'customer')]:
            browser = Client(enforce_csrf_checks=True)
            browser.get('/accounts/login/')
            response = browser.post('/accounts/login/', {'username': user.username,
                'password': self.password, 'csrfmiddlewaretoken': browser.cookies['csrftoken'].value})
            self.assertEqual(response.status_code, 302)
            verifier = secrets.token_urlsafe(48)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
            params = {'client_id': oidc.client_id, 'redirect_uri': oidc.redirect_uris[0],
                'response_type': 'code', 'scope': 'openid profile email', 'state': secrets.token_urlsafe(),
                'code_challenge': challenge, 'code_challenge_method': 'S256'}
            response = browser.get('/openid/authorize/', params)
            if response.status_code == 200:
                response = browser.post('/openid/authorize/', {**params, 'allow': 'Authorize',
                    'csrfmiddlewaretoken': browser.cookies['csrftoken'].value})
            self.assertEqual(response.status_code, 302)
            code = parse_qs(urlparse(response['Location']).query)['code'][0]
            response = browser.post('/openid/token/', {'client_id': oidc.client_id,
                'redirect_uri': oidc.redirect_uris[0], 'grant_type': 'authorization_code',
                'code': code, 'code_verifier': verifier})
            self.assertEqual(response.status_code, 200)
            api = APIClient()
            api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access_token']}")
            profiles.append((browser, api, user, role))
        # Check all sessions after all three accounts have logged in.
        for browser, api, user, role in profiles:
            self.assertEqual(browser.session['_auth_user_id'], str(user.pk))
            self.assertEqual(api.get('/api/me/').data['role'], role)
        profiles[1][1].post('/api/logout/')
        self.assertEqual(profiles[1][1].get('/api/me/').status_code, 401)
        for index in [0, 2]:
            self.assertEqual(profiles[index][1].get('/api/me/').status_code, 200)
