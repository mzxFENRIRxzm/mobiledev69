from django.utils import timezone
from oidc_provider.models import Token
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed


class OIDCBearerAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None
        if len(parts) != 2 or parts[0].lower() != b"bearer":
            raise AuthenticationFailed("Invalid authorization header")
        try:
            token = Token.objects.select_related("user", "client").get(access_token=parts[1].decode("ascii"))
        except (Token.DoesNotExist, UnicodeDecodeError):
            raise AuthenticationFailed("Invalid token")
        if token.expires_at <= timezone.now() or not token.user or not token.user.is_active:
            raise AuthenticationFailed("Session expired")
        if token.client.client_id != "the-x-web" or "openid" not in token.scope:
            raise AuthenticationFailed("Token not issued for THE_X")
        return token.user, token

    def authenticate_header(self, request):
        return "Bearer"


def userinfo(claims, user):
    claims["name"] = user.get_full_name() or user.username
    claims["preferred_username"] = user.username
    claims["email"] = user.email
    return claims
