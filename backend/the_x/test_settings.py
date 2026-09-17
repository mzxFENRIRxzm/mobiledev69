import os
import secrets

os.environ["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DJANGO_DEBUG"] = "true"
from .settings import *  # noqa: F403,E402

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
