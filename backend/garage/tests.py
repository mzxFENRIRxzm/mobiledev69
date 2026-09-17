import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from oidc_provider.models import Client, ResponseType, Token
from rest_framework.test import APIClient
from .models import Motorcycle


class GarageTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="owner")
        self.other = get_user_model().objects.create_user(username="other")
        self.oidc = Client.objects.create(client_id="the-x-web", client_type="public")
        self.token = Token.objects.create(user=self.owner, client=self.oidc,
            access_token=secrets.token_urlsafe(), refresh_token=secrets.token_urlsafe(),
            expires_at=timezone.now() + timedelta(hours=1), _scope="openid profile")
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")
        self.payload = dict(brand="Honda", model="PCX", license_plate="กข 1234", year=2024, mileage=100)

    def test_crud(self):
        response = self.api.post("/api/motorcycles/", self.payload)
        self.assertEqual(response.status_code, 201)
        url = f"/api/motorcycles/{response.data['id']}/"
        self.assertEqual(self.api.get(url).status_code, 200)
        self.assertEqual(self.api.patch(url, {"mileage": 250}).data["mileage"], 250)
        self.assertEqual(self.api.delete(url).status_code, 204)

    def test_other_owner_is_hidden_and_cannot_be_modified(self):
        bike = Motorcycle.objects.create(owner=self.other, **self.payload)
        url = f"/api/motorcycles/{bike.pk}/"
        self.assertEqual(self.api.get("/api/motorcycles/").data["count"], 0)
        self.assertEqual(self.api.get(url).status_code, 404)
        self.assertEqual(self.api.patch(url, {"mileage": 0}).status_code, 404)
        self.assertEqual(self.api.delete(url).status_code, 404)

    def test_cannot_spoof_owner(self):
        response = self.api.post("/api/motorcycles/", {**self.payload, "owner": self.other.pk})
        self.assertEqual(Motorcycle.objects.get(pk=response.data["id"]).owner, self.owner)

    def test_validation_and_duplicate_plate(self):
        self.assertEqual(self.api.post("/api/motorcycles/", {**self.payload, "mileage": -1}).status_code, 400)
        self.api.post("/api/motorcycles/", self.payload)
        self.assertEqual(self.api.post("/api/motorcycles/", self.payload).status_code, 400)

    def test_unauthenticated_and_expired_token(self):
        self.assertEqual(APIClient().get("/api/motorcycles/").status_code, 401)
        self.token.expires_at = timezone.now() - timedelta(seconds=1)
        self.token.save()
        self.assertEqual(self.api.get("/api/me/").status_code, 401)

    def test_logout_revokes_token(self):
        self.assertEqual(self.api.post("/api/logout/").status_code, 204)
        self.assertEqual(self.api.get("/api/me/").status_code, 401)

    def test_pkce_is_required(self):
        response = self.client.get("/openid/authorize/", {"client_id": "the-x-web"})
        self.assertEqual(response.status_code, 400)

    def test_discovery_advertises_scopes_for_flutter(self):
        metadata = self.client.get("/openid/.well-known/openid-configuration").json()
        self.assertEqual(metadata["scopes_supported"], ["openid", "profile", "email"])
        self.assertEqual(metadata["code_challenge_methods_supported"], ["S256"])
        self.assertIn("none", metadata["token_endpoint_auth_methods_supported"])

    def test_oidc_authorization_code_pkce_roundtrip(self):
        from django.core.management import call_command
        call_command("creatersakey", verbosity=0)
        self.oidc.redirect_uris = ["http://localhost:50000/callback"]
        self.oidc.scope = ["openid", "profile", "email"]
        self.oidc.require_consent = False
        self.oidc.save()
        code_type, _ = ResponseType.objects.get_or_create(value="code", defaults={"description": "code"})
        self.oidc.response_types.set([code_type])
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        self.client.force_login(self.owner)
        params = {
            "client_id": "the-x-web", "redirect_uri": self.oidc.redirect_uris[0],
            "response_type": "code", "scope": "openid profile email", "state": "test-state",
            "code_challenge": challenge, "code_challenge_method": "S256",
        }
        response = self.client.get("/openid/authorize/", params)
        if response.status_code == 200:
            response = self.client.post("/openid/authorize/", {**params, "allow": "Authorize"})
        self.assertEqual(response.status_code, 302, response.content)
        query = parse_qs(urlparse(response["Location"]).query)
        self.assertEqual(query["state"], ["test-state"])
        body = {"client_id": "the-x-web", "redirect_uri": self.oidc.redirect_uris[0],
                "grant_type": "authorization_code", "code": query["code"][0]}
        self.assertEqual(self.client.post("/openid/token/", {**body, "code_verifier": "wrong"}).status_code, 400)
        response = self.client.post("/openid/token/", {**body, "code_verifier": verifier})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("id_token", response.json())
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access_token']}")
        self.assertEqual(self.api.get("/api/me/").data["username"], "owner")
        self.assertEqual(self.client.post("/openid/token/", {**body, "code_verifier": verifier}).status_code, 400)
