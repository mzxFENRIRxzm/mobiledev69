"""Create ignored local credentials; never overwrite an existing configuration."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
targets = [root / ".env", root / "backend" / ".env"]
if any(path.exists() for path in targets):
    raise SystemExit("Configuration already exists. Keep it or edit it manually; nothing overwritten.")
database_password = secrets.token_urlsafe(24)
targets[0].write_text(f"POSTGRES_PASSWORD={database_password}\n", encoding="utf-8")
targets[1].write_text(
    f"DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}\n"
    "DJANGO_DEBUG=true\nDJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\n"
    f"DATABASE_URL=postgresql://the_x:{database_password}@127.0.0.1:55432/the_x\n"
    f"DEMO_PASSWORD={secrets.token_urlsafe(16)}\n"
    f"MECHANIC_DEMO_PASSWORD={secrets.token_urlsafe(16)}\n"
    "OIDC_SITE_URL=http://localhost:8000\nFRONTEND_ORIGINS=http://localhost:50000\n",
    encoding="utf-8",
)
print("Created local configuration. Demo username: student01. Read DEMO_PASSWORD privately in backend/.env.")
