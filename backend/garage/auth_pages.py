from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from urllib.parse import urlencode
from garage.username_reset import local_reset_available


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

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            signup_enabled=settings.PUBLIC_SIGNUP_ENABLED,
            local_username_reset_enabled=local_reset_available(self.request), **kwargs)


@never_cache
def csrf_failure(request, reason=""):
    # Reject the original POST and open a fresh copy of the same safe form.
    # Never replay credentials or other submitted fields.
    retry_paths = {
        "/accounts/login/": ("ฟอร์มเข้าสู่ระบบ", "เปิดฟอร์มเข้าสู่ระบบใหม่"),
        "/accounts/register/": ("ฟอร์มสมัครสมาชิก", "เปิดฟอร์มสมัครสมาชิกใหม่"),
        "/accounts/password-reset/": ("ฟอร์มกู้รหัสผ่าน", "เปิดฟอร์มกู้รหัสผ่านใหม่"),
        "/accounts/resend-verification/": (
            "ฟอร์มส่งลิงก์ยืนยันอีเมล", "เปิดฟอร์มส่งลิงก์ใหม่"),
    }
    retry_url = request.path if request.path in retry_paths else "/accounts/login/"
    form_name, button_label = retry_paths.get(
        retry_url, ("ฟอร์มเข้าสู่ระบบ", "เปิดฟอร์มเข้าสู่ระบบใหม่"))
    if request.path.startswith("/accounts/verify-email/"):
        retry_url = request.path
        form_name, button_label = "หน้ายืนยันอีเมล", "เปิดหน้ายืนยันอีเมลใหม่"
    elif request.path.startswith("/accounts/password-reset/"):
        retry_url = request.path
        form_name, button_label = "ฟอร์มตั้งรหัสผ่าน", "เปิดฟอร์มตั้งรหัสผ่านใหม่"
    destination = request.POST.get("next") or request.GET.get("next")
    if destination and url_has_allowed_host_and_scheme(
            destination, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        retry_url += "?" + urlencode({"next": destination})
    return render(request, "registration/csrf_failure.html", {
        "retry_url": retry_url,
        "form_name": form_name,
        "button_label": button_label,
    }, status=403)
