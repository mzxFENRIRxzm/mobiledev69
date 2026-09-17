import re
from django.http import JsonResponse


class RequirePKCE:
    """The public THE_X client must never downgrade to a non-PKCE code flow."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.rstrip("/") == "/openid/authorize":
            params = request.GET if request.method == "GET" else request.POST
            if params.get("client_id") == "the-x-web" and (
                params.get("code_challenge_method") != "S256"
                or not re.fullmatch(r"[A-Za-z0-9_-]{43}", params.get("code_challenge", ""))
            ):
                return JsonResponse({"error": "invalid_request", "error_description": "PKCE S256 required"}, status=400)
        return self.get_response(request)
