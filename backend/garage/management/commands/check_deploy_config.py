"""Fail early on unsafe or inconsistent container deployment settings."""

import os
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Validate THE_X Docker origin, cookie and email settings."

    def handle(self, *args, **options):
        origin = os.getenv("APP_ORIGIN", "").rstrip("/")
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.path or parsed.query or parsed.fragment):
            raise CommandError("APP_ORIGIN must be one HTTP(S) origin without a path.")
        if settings.DEBUG:
            raise CommandError("Docker deployment requires DJANGO_DEBUG=false.")
        if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32 or "GENERATE" in settings.SECRET_KEY:
            raise CommandError("Generate a unique DJANGO_SECRET_KEY before deployment.")
        database_password = os.getenv("POSTGRES_PASSWORD", "")
        if len(database_password) < 24 or "GENERATE" in database_password:
            raise CommandError("Generate a unique POSTGRES_PASSWORD before deployment.")
        if settings.SITE_URL.rstrip("/") != origin or settings.CORS_ALLOWED_ORIGINS != [origin]:
            raise CommandError("OIDC_SITE_URL and FRONTEND_ORIGINS must equal APP_ORIGIN.")
        if parsed.hostname not in settings.ALLOWED_HOSTS:
            raise CommandError("APP_HOST must match the hostname in APP_ORIGIN.")

        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        if parsed.scheme == "http" and not local_http:
            raise CommandError("Public Docker deployments require HTTPS.")
        if local_http:
            if not os.getenv("HTTP_BIND", "").startswith("127.0.0.1:"):
                raise CommandError("Local HTTP demo must bind only to 127.0.0.1.")
            if settings.SESSION_COOKIE_SECURE or settings.SECURE_SSL_REDIRECT:
                raise CommandError("Local HTTP demo requires secure cookies and SSL redirect disabled.")
        elif (not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE
              or not settings.SECURE_SSL_REDIRECT
              or settings.SECURE_PROXY_SSL_HEADER != ("HTTP_X_FORWARDED_PROTO", "https")):
            raise CommandError("HTTPS deployment requires secure cookies, SSL redirect and trusted proxy headers.")

        if settings.DEMO_EMAIL_VERIFICATION_LINK and not local_http:
            raise CommandError("Demo email verification links are allowed only for the loopback demo.")
        if settings.PUBLIC_SIGNUP_ENABLED and not settings.DEMO_EMAIL_VERIFICATION_LINK:
            if (settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend"
                    or settings.EMAIL_HOST in {"", "localhost"}
                    or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD):
                raise CommandError("Public signup requires configured SMTP credentials.")

        self.stdout.write(self.style.SUCCESS(f"Docker settings valid for {origin}"))
