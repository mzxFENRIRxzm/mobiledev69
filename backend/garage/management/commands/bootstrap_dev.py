import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import BaseCommand, CommandError, call_command
from oidc_provider.models import Client, ResponseType, RSAKey
from garage.models import Shop


class Command(BaseCommand):
    help = "Create the local demo user, public OIDC client and signing key (idempotent)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("bootstrap_dev is restricted to DEBUG=true")
        password = os.environ.get("DEMO_PASSWORD")
        if not password:
            raise CommandError("Set DEMO_PASSWORD in backend/.env")
        user, created = get_user_model().objects.get_or_create(username="student01")
        if created:
            user.set_password(password)
            user.save()
        mechanic_password = os.environ.get("MECHANIC_DEMO_PASSWORD")
        if mechanic_password:
            mechanic, created = get_user_model().objects.get_or_create(username="mechanic01")
            if created:
                mechanic.set_password(mechanic_password)
                mechanic.save()
            if created:
                group, _ = Group.objects.get_or_create(name="mechanics")
                mechanic.groups.add(group)
            if mechanic.groups.filter(name="mechanics").exists() and not mechanic.is_superuser and not mechanic.service_shops.exists():
                shop = Shop.objects.create(name="THE_X Demo Service", address="ร้านทดสอบ local กรุณาแก้ไขที่อยู่ก่อนใช้งาน", phone="กรุณาระบุเบอร์โทร")
                shop.mechanics.add(mechanic)
            self.stdout.write("Ready: mechanic01 (existing password unchanged).")
        else:
            self.stdout.write("Set MECHANIC_DEMO_PASSWORD in backend/.env to create mechanic01.")
        client, _ = Client.objects.get_or_create(client_id="the-x-web")
        client.name = "THE_X"
        client.client_type = "public"
        client.client_secret = ""
        frontend_origins = [origin.rstrip('/') for origin in settings.CORS_ALLOWED_ORIGINS]
        client.redirect_uris = [f"{origin}/callback" for origin in frontend_origins]
        client.post_logout_redirect_uris = [f"{origin}/login" for origin in frontend_origins]
        client.scope = ["openid", "profile", "email"]
        client.require_consent = True
        client.save()
        response, _ = ResponseType.objects.get_or_create(value="code", defaults={"description": "Authorization Code"})
        client.response_types.set([response])
        if not RSAKey.objects.exists():
            call_command("creatersakey", verbosity=0)
        self.stdout.write(self.style.SUCCESS("Ready: student01 and THE_X public OIDC client. Existing password unchanged."))
