import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
# Keep public signup off by default in production until SMTP and shared cache are configured.
PUBLIC_SIGNUP_ENABLED = os.getenv("PUBLIC_SIGNUP_ENABLED", str(DEBUG)).lower() == "true"
# A tunnel demo can use HTTPS with DEBUG disabled while still letting a tester
# complete signup without a configured SMTP server. Never enable this in a real
# deployment because it does not prove ownership of the submitted email address.
DEMO_EMAIL_VERIFICATION_LINK = os.getenv(
    "DEMO_EMAIL_VERIFICATION_LINK", "false"
).lower() == "true"
GEOCODING_REVERSE_URL = os.getenv('GEOCODING_REVERSE_URL', 'https://photon.komoot.io/reverse')
GEOCODING_FORWARD_URL = os.getenv('GEOCODING_FORWARD_URL', 'https://photon.komoot.io/api')
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "corsheaders", "rest_framework", "oidc_provider", "garage",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "garage.middleware.RequirePKCE",
]
ROOT_URLCONF = "the_x.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "the_x.wsgi.application"
DATABASES = {"default": dj_database_url.parse(
    os.environ["DATABASE_URL"], conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "0"))
)}
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"]["OPTIONS"] = {"connect_timeout": 8}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "th"
TIME_ZONE = "Asia/Bangkok"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
CORS_ALLOWED_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:50000").split(",")
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
if redis_url := os.getenv("REDIS_URL"):
    CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": redis_url,
    }}
if os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_FAILURE_VIEW = "garage.auth_pages.csrf_failure"
COOKIE_SECURE = os.getenv("DJANGO_COOKIE_SECURE", str(not DEBUG)).lower() == "true"
SESSION_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_SECURE = COOKIE_SECURE
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "false").lower() == "true"
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "0"))
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = os.getenv("FRONTEND_LOGIN_URL", CORS_ALLOWED_ORIGINS[0].rstrip('/') + '/login')
SITE_URL = os.getenv("OIDC_SITE_URL", "http://localhost:8000")
EMAIL_BACKEND = os.getenv('DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'false').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'THE_X <noreply@localhost>')
EMAIL_VERIFICATION_TIMEOUT = int(os.getenv('EMAIL_VERIFICATION_TIMEOUT', '86400'))
PASSWORD_RESET_TIMEOUT = int(os.getenv('PASSWORD_RESET_TIMEOUT', '3600'))
OIDC_USERINFO = "garage.auth.userinfo"
OIDC_GRANT_TYPE_PASSWORD_ENABLE = False
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["garage.auth.OIDCBearerAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 30,
}
