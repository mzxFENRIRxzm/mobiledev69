from oidc_provider.views import ProviderInfoView


class TheXProviderInfoView(ProviderInfoView):
    """Advertise the scopes and public PKCE flow our Flutter client consumes."""

    def _build_response_dict(self, request):
        metadata = super()._build_response_dict(request)
        metadata["scopes_supported"] = ["openid", "profile", "email"]
        metadata["code_challenge_methods_supported"] = ["S256"]
        metadata["token_endpoint_auth_methods_supported"].append("none")
        return metadata
