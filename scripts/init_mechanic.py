"""Add a random demo mechanic password to an existing local .env, without replacing values."""
from pathlib import Path
import secrets

target = Path(__file__).resolve().parents[1] / "backend" / ".env"
if not target.exists():
    raise SystemExit("Run scripts/init_dev.py first.")
content = target.read_text(encoding="utf-8")
if any(line.strip().startswith("MECHANIC_DEMO_PASSWORD=") for line in content.splitlines()):
    print("MECHANIC_DEMO_PASSWORD already configured; unchanged.")
else:
    with target.open("a", encoding="utf-8") as stream:
        stream.write(f"\nMECHANIC_DEMO_PASSWORD={secrets.token_urlsafe(16)}\n")
    print("Added MECHANIC_DEMO_PASSWORD to backend/.env. Run manage.py bootstrap_dev.")
