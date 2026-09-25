from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings


class CheckDeployConfigTests(SimpleTestCase):
    @override_settings(
        DEBUG=False, SECRET_KEY="local-test-secret-that-is-long-enough-123456",
    )
    @patch.dict("os.environ", {
        "APP_ORIGIN": "http://localhost:18080",
        "POSTGRES_PASSWORD": "__GENERATE_POSTGRES_PASSWORD__",
    })
    def test_placeholder_database_password_is_rejected(self):
        with self.assertRaisesMessage(CommandError, "POSTGRES_PASSWORD"):
            call_command("check_deploy_config")

    @override_settings(
        DEBUG=False, SECRET_KEY="local-test-secret-that-is-long-enough-123456",
        SITE_URL="http://localhost:18080", CORS_ALLOWED_ORIGINS=["http://localhost:18080"],
        ALLOWED_HOSTS=["localhost"], SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
        SECURE_SSL_REDIRECT=False, DEMO_EMAIL_VERIFICATION_LINK=True,
        PUBLIC_SIGNUP_ENABLED=True, LOCAL_USERNAME_RESET_ENABLED=True,
    )
    @patch.dict("os.environ", {"APP_ORIGIN": "http://localhost:18080", "HTTP_BIND": "127.0.0.1:18080", "POSTGRES_PASSWORD": "local-test-database-password-123456"})
    def test_local_demo_is_accepted(self):
        call_command("check_deploy_config")

    @override_settings(
        DEBUG=False, SECRET_KEY="production-secret-that-is-long-enough-123456",
        SITE_URL="https://the-x.example", CORS_ALLOWED_ORIGINS=["https://the-x.example"],
        ALLOWED_HOSTS=["the-x.example"], SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
        SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        DEMO_EMAIL_VERIFICATION_LINK=True, PUBLIC_SIGNUP_ENABLED=False,
    )
    @patch.dict("os.environ", {"APP_ORIGIN": "https://the-x.example", "HTTP_BIND": "0.0.0.0:80", "POSTGRES_PASSWORD": "local-test-database-password-123456"})
    def test_public_demo_verification_is_rejected(self):
        with self.assertRaisesMessage(CommandError, "only for the loopback demo"):
            call_command("check_deploy_config")

    @override_settings(
        DEBUG=False, SECRET_KEY="production-secret-that-is-long-enough-123456",
        SITE_URL="https://the-x.example", CORS_ALLOWED_ORIGINS=["https://the-x.example"],
        ALLOWED_HOSTS=["the-x.example"], SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
        SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        DEMO_EMAIL_VERIFICATION_LINK=False, PUBLIC_SIGNUP_ENABLED=False,
    )
    @patch.dict("os.environ", {"APP_ORIGIN": "https://the-x.example", "HTTP_BIND": "0.0.0.0:80", "POSTGRES_PASSWORD": "local-test-database-password-123456"})
    def test_https_without_public_signup_is_accepted(self):
        call_command("check_deploy_config")

    @override_settings(
        DEBUG=False, SECRET_KEY="production-secret-that-is-long-enough-123456",
        SITE_URL="https://the-x.example", CORS_ALLOWED_ORIGINS=["https://the-x.example"],
        ALLOWED_HOSTS=["the-x.example"], SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
        SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        DEMO_EMAIL_VERIFICATION_LINK=False, PUBLIC_SIGNUP_ENABLED=False,
        LOCAL_USERNAME_RESET_ENABLED=True,
    )
    @patch.dict("os.environ", {"APP_ORIGIN": "https://the-x.example", "HTTP_BIND": "0.0.0.0:80", "POSTGRES_PASSWORD": "local-test-database-password-123456"})
    def test_public_username_reset_is_rejected(self):
        with self.assertRaisesMessage(CommandError, "only for the loopback demo"):
            call_command("check_deploy_config")
