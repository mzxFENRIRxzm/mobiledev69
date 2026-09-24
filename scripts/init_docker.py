"""Create ignored Docker deployment settings without overwriting existing ones."""

from pathlib import Path
import secrets


root = Path(__file__).resolve().parents[1]
source = root / "deploy" / ".env.local.example"
target = root / "deploy" / ".env"
settings = source.read_text(encoding="utf-8")
settings = settings.replace("__GENERATE_POSTGRES_PASSWORD__", secrets.token_hex(24))
settings = settings.replace("__GENERATE_DJANGO_SECRET_KEY__", secrets.token_urlsafe(48))
with target.open("x", encoding="utf-8") as output:
    output.write(settings)
print("Created deploy/.env for the local Docker demo. Existing settings were not changed.")
