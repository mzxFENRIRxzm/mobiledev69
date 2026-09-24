from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from oidc_provider.models import Client, RSAKey, ResponseType


class ConfigureOIDCClientTests(TestCase):
    @override_settings(CORS_ALLOWED_ORIGINS=["https://the-x.example"])
    def test_configures_public_client_without_demo_accounts_and_is_idempotent(self):
        call_command("configure_oidc_client", verbosity=0)
        call_command("configure_oidc_client", verbosity=0)

        client = Client.objects.get(client_id="the-x-web")
        self.assertEqual(client.client_type, "public")
        self.assertEqual(client.client_secret, "")
        self.assertEqual(client.redirect_uris, ["https://the-x.example/callback"])
        self.assertEqual(client.post_logout_redirect_uris, ["https://the-x.example/login"])
        self.assertEqual(list(client.response_types.values_list("value", flat=True)), ["code"])
        self.assertEqual(ResponseType.objects.filter(value="code").count(), 1)
        self.assertTrue(RSAKey.objects.exists())
        self.assertFalse(get_user_model().objects.filter(username="student01").exists())
