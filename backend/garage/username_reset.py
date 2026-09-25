"""Username-only password reset for the loopback Docker demo.

Knowing a username is not proof of account ownership. Never expose this view
on a public origin or allow it to change staff credentials.
"""

import os
from urllib.parse import urlsplit

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from oidc_provider.models import Token


def local_reset_available(request):
    return (
        settings.LOCAL_USERNAME_RESET_ENABLED
        and urlsplit(settings.SITE_URL).hostname in {"localhost", "127.0.0.1"}
        and os.getenv("HTTP_BIND", "").startswith("127.0.0.1:")
        and request.get_host().split(":")[0] in {"localhost", "127.0.0.1"}
    )


class UsernameResetForm(forms.Form):
    username = forms.CharField(label="ชื่อผู้ใช้", max_length=150)
    new_password1 = forms.CharField(
        label="รหัสผ่านใหม่", strip=False, widget=forms.PasswordInput())
    new_password2 = forms.CharField(
        label="ยืนยันรหัสผ่านใหม่", strip=False, widget=forms.PasswordInput())

    def clean(self):
        data = super().clean()
        username = data.get("username")
        user = get_user_model().objects.filter(username=username).first() if username else None
        if username and (user is None or not user.is_active or user.is_staff or user.is_superuser):
            self.add_error("username", "ไม่สามารถรีเซ็ตบัญชีนี้ได้")
        if data.get("new_password1") and data.get("new_password2"):
            if data["new_password1"] != data["new_password2"]:
                self.add_error("new_password2", "รหัสผ่านทั้งสองช่องไม่ตรงกัน")
            elif user and user.is_active and not (user.is_staff or user.is_superuser):
                try:
                    password_validation.validate_password(data["new_password1"], user)
                except forms.ValidationError as error:
                    self.add_error("new_password1", error)
        self.user = user
        return data


@sensitive_post_parameters("new_password1", "new_password2")
@never_cache
@require_http_methods(["GET", "POST"])
def username_password_reset(request):
    if not local_reset_available(request):
        raise Http404
    form = UsernameResetForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=form.user.pk)
            if not user.is_active or user.is_staff or user.is_superuser:
                form.add_error("username", "ไม่สามารถรีเซ็ตบัญชีนี้ได้")
            else:
                user.set_password(form.cleaned_data["new_password1"])
                user.save(update_fields=["password"])
                Token.objects.filter(user=user).delete()
                return redirect("/accounts/login/")
    return render(request, "registration/username_reset.html", {"form": form})
