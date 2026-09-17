from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.contrib.auth.models import Group
from .models import Booking


ROLE_CHOICES = [("customer", "Customeruser"), ("mechanic", "Mechanicuser"), ("admin", "Adminuser")]


def role_for(user):
    if user.is_superuser:
        return "admin"
    return "mechanic" if user.groups.filter(name="mechanics").exists() else "customer"


class RoleFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["role"] = role_for(self.instance) if self.instance.pk else "customer"

    def clean(self):
        data = super().clean()
        if self.instance.pk:
            # Admin POST views run inside a transaction. Serialize role edits to
            # prevent two concurrent requests removing the final administrators.
            users = get_user_model()
            list(users.objects.select_for_update().filter(is_superuser=True).order_by("pk"))
            original = users.objects.get(pk=self.instance.pk)
            role = data.get("role")
            if original.is_superuser and (role != "admin" or not data.get("is_active", True)):
                if not users.objects.filter(is_superuser=True, is_active=True).exclude(pk=original.pk).exists():
                    self.add_error("role", "ต้องเหลือ Adminuser ที่ใช้งานได้อย่างน้อยหนึ่งคน")
            if role != role_for(original) and original.repair_jobs.filter(
                status__in=[Booking.Status.ACCEPTED, Booking.Status.IN_PROGRESS]
            ).exists():
                self.add_error("role", "ต้องปิดงานซ่อมที่รับไว้ก่อนเปลี่ยนบทบาท")
        return data

    def save(self, commit=True):
        role = self.cleaned_data["role"]
        self.instance.is_staff = role == "admin"
        self.instance.is_superuser = role == "admin"
        return super().save(commit=commit)

    def _save_m2m(self):
        super()._save_m2m()
        role = self.cleaned_data["role"]
        # Roles are exclusive. Remove legacy grants when assigning a role.
        self.instance.groups.clear()
        self.instance.user_permissions.clear()
        if role == "mechanic":
            group, _ = Group.objects.get_or_create(name="mechanics")
            self.instance.groups.add(group)
        else:
            self.instance.service_shops.clear()


class RoleChangeForm(RoleFormMixin, UserChangeForm):
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="บทบาท THE_X")


class RoleCreationForm(RoleFormMixin, AdminUserCreationForm):
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="บทบาท THE_X", initial="customer")
