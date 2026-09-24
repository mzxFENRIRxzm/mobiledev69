"""Configure the public OIDC client for the current frontend origin."""

from django.conf import settings
from django.core.management import call_command
from oidc_provider.models import Client, RSAKey, ResponseType


def configure_public_client():
    client, _ = Client.objects.get_or_create(client_id="the-x-web")
    client.name = "THE_X"
    client.client_type = "public"
    client.client_secret = ""
    origins = [origin.rstrip("/") for origin in settings.CORS_ALLOWED_ORIGINS]
    client.redirect_uris = [f"{origin}/callback" for origin in origins]
    client.post_logout_redirect_uris = [f"{origin}/login" for origin in origins]
    client.scope = ["openid", "profile", "email"]
    client.require_consent = True
    client.save()
    response, _ = ResponseType.objects.get_or_create(
        value="code", defaults={"description": "Authorization Code"}
    )
    client.response_types.set([response])
    if not RSAKey.objects.exists():
        call_command("creatersakey", verbosity=0)
    return client
