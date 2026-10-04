"""Create an isolated PostgreSQL/pgvector service for n8n AI nodes."""

from pathlib import Path
import re
import secrets
import subprocess


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "deploy" / ".env"
KEYS = ("AI_DB_ADMIN_PASSWORD", "AI_MEMORY_DB_PASSWORD", "AI_VECTOR_DB_PASSWORD")
COMPOSE = (
    "docker", "compose", "--env-file", str(ENV),
    "-f", str(ROOT / "compose.deploy.yaml"),
    "-f", str(ROOT / "compose.ai.yaml"),
)


def main():
    if not ENV.exists():
        raise SystemExit("Run python scripts/init_docker.py first.")
    existing = ENV.read_text(encoding="utf-8-sig")
    settings = dict(line.split("=", 1) for line in existing.splitlines()
                    if "=" in line and not line.startswith("#"))
    volume = subprocess.run(
        ["docker", "volume", "inspect", "the_x_deploy_ai_postgres_data"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )
    if volume.returncode == 0 and any(not settings.get(key) for key in KEYS):
        raise SystemExit("AI database volume exists but a password is missing. Restore deploy/.env from backup.")
    for key in KEYS:
        value = settings.get(key)
        if value and not re.fullmatch(r"[0-9a-f]{64}", value):
            raise SystemExit(f"{key} must be a generated 64-character hex value.")
    additions = [f"{key}={secrets.token_hex(32)}" for key in KEYS if not settings.get(key)]
    if additions:
        with ENV.open("a", encoding="utf-8") as output:
            output.write("\n" + "\n".join(additions) + "\n")
    subprocess.run([*COMPOSE, "up", "-d", "--wait", "--no-deps", "ai-postgres"],
                   cwd=ROOT, check=True)
    for database, user in (("the_x_ai_memory", "the_x_ai_memory"),
                           ("the_x_ai_vectors", "the_x_ai_vectors")):
        subprocess.run([*COMPOSE, "exec", "-T", "ai-postgres", "psql", "-U",
                        "the_x_ai_admin", "-d", database, "-Atc",
                        f"SELECT current_database(), has_database_privilege('{user}', current_database(), 'CONNECT')"],
                       cwd=ROOT, check=True)
    subprocess.run([*COMPOSE, "exec", "-T", "ai-postgres", "psql", "-U",
                    "the_x_ai_admin", "-d", "the_x_ai_vectors", "-Atc",
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"],
                   cwd=ROOT, check=True)
    for role, database, password_key, smoke_sql in (
        ("the_x_ai_memory", "the_x_ai_memory", "AI_MEMORY_DB_PASSWORD",
         "BEGIN; CREATE TABLE ai_setup_smoke (id integer); ROLLBACK; SELECT current_user"),
        ("the_x_ai_vectors", "the_x_ai_vectors", "AI_VECTOR_DB_PASSWORD",
         "BEGIN; CREATE TABLE ai_setup_smoke (embedding vector(3)); "
         "INSERT INTO ai_setup_smoke VALUES ('[1,0,0]'); "
         "SELECT embedding <=> '[1,0,0]' FROM ai_setup_smoke; ROLLBACK; SELECT current_user"),
    ):
        check = (
            f'PGPASSWORD="${password_key}" psql -h 127.0.0.1 -U {role} '
            f'-d {database} -v ON_ERROR_STOP=1 -Atc "{smoke_sql}"'
        )
        result = subprocess.run([*COMPOSE, "exec", "-T", "ai-postgres", "sh", "-ec", check],
                                cwd=ROOT, check=True, capture_output=True, text=True)
        if result.stdout.splitlines()[-1].strip() != role:
            raise SystemExit(f"Login check failed for {role}.")
    denied = subprocess.run(
        [*COMPOSE, "exec", "-T", "ai-postgres", "sh", "-ec",
         'PGPASSWORD="$AI_MEMORY_DB_PASSWORD" psql -h 127.0.0.1 -U the_x_ai_memory '
         '-d the_x_ai_vectors -Atc "SELECT 1"'],
        cwd=ROOT, capture_output=True, text=True,
    )
    if denied.returncode == 0:
        raise SystemExit("Database isolation check failed: memory role reached vector database.")
    print("AI databases ready. Set n8n Postgres credentials using host ai-postgres and deploy/.env passwords.")


if __name__ == "__main__":
    main()
