from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.views.decorators.cache import never_cache


class TheXAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="ชื่อผู้ใช้", max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True,
                                     "placeholder": "ชื่อผู้ใช้ของคุณ", "autocapitalize": "none"}))
    password = forms.CharField(label="รหัสผ่าน", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "รหัสผ่านของคุณ"}))
    error_messages = {
        "invalid_login": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง กรุณาลองใหม่",
        "inactive": "ไม่สามารถเข้าสู่ระบบด้วยบัญชีนี้ได้ กรุณาติดต่อผู้ดูแล",
    }


class TheXLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = TheXAuthenticationForm
    # Credentials remain with Django; only the provider issues OIDC tokens.
    redirect_authenticated_user = False


@never_cache
def csrf_failure(request, reason=""):
    # Reject the original POST. Offer a GET of the login form; never replay credentials.
    retry_url = "/accounts/login/"
    if request.path == retry_url and request.GET:
        retry_url += "?" + request.GET.urlencode()
    return render(request, "registration/csrf_failure.html", {"retry_url": retry_url}, status=403)
