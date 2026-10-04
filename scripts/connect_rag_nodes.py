"""Attach isolated PostgreSQL credentials to the saved n8n RAG draft."""

import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from setup_n8n import COMPOSE, ENV, LOCAL, ROOT


WORKFLOW_ID = "theXOneRagDraft"
CONNECTIONS = (
    ("Postgres Chat Memory", "theXAiMemoryDb", "THE_X AI Memory DB",
     "the_x_ai_memory", "the_x_ai_memory", "AI_MEMORY_DB_PASSWORD"),
    ("Postgres PGVector Store", "theXAiVectorDb", "THE_X AI Vector DB",
     "the_x_ai_vectors", "the_x_ai_vectors", "AI_VECTOR_DB_PASSWORD"),
)


def compose(*args, capture=False):
    return subprocess.run([*COMPOSE, *args], cwd=ROOT, check=True,
                          capture_output=capture, text=capture)


def main():
    if not ENV.exists():
        raise SystemExit("Run python scripts/init_docker.py first.")
    settings = dict(line.split("=", 1) for line in ENV.read_text(encoding="utf-8-sig").splitlines()
                    if "=" in line and not line.startswith("#"))
    if any(not settings.get(connection[-1]) for connection in CONNECTIONS):
        raise SystemExit("Run python scripts/setup_rag_db.py first.")
    LOCAL.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = LOCAL / f"rag-before-postgres-{stamp}.json"
    compose("run", "--rm", "--no-deps", "-v", f"{LOCAL.as_posix()}:/output", "n8n",
            "export:workflow", f"--id={WORKFLOW_ID}", f"--output=/output/{backup.name}")
    workflow = json.loads(backup.read_text(encoding="utf-8"))[0]
    if workflow.get("id") != WORKFLOW_ID or workflow.get("active"):
        raise SystemExit("Expected the saved, unpublished RAG draft; no changes made.")
    shared = workflow.get("shared") or []
    project_ids = {entry.get("projectId") for entry in shared if entry.get("role") == "workflow:owner"}
    if len(project_ids) != 1 or not next(iter(project_ids)):
        raise SystemExit("Cannot identify the RAG workflow project; no changes made.")
    project_id = next(iter(project_ids))
    nodes = {node["name"]: node for node in workflow["nodes"]}
    for node_name, credential_id, _, _, _, _ in CONNECTIONS:
        node = nodes.get(node_name)
        if node is None:
            raise SystemExit(f"Node {node_name} is missing; no changes made.")
        current = (node.get("credentials") or {}).get("postgres")
        if current and current.get("id") != credential_id:
            raise SystemExit(f"{node_name} already has a different credential; no changes made.")

    existing = compose("exec", "-T", "n8n-postgres", "psql", "-U", "n8n", "-d", "n8n",
                       "-Atc", "SELECT id, name, type FROM credentials_entity WHERE id IN "
                       "('theXAiMemoryDb', 'theXAiVectorDb')", capture=True)
    existing_credentials = {row[0]: row[1:] for line in existing.stdout.splitlines()
                            if (row := line.split("|"))}
    for _, credential_id, name, _, _, _ in CONNECTIONS:
        if credential_id in existing_credentials and existing_credentials[credential_id] != [name, "postgres"]:
            raise SystemExit(f"Unexpected existing credential {credential_id}; no changes made.")
    if all(credential_id in existing_credentials and
           (nodes[node_name].get("credentials") or {}).get("postgres", {}).get("id") == credential_id
           for node_name, credential_id, _, _, _, _ in CONNECTIONS):
        print("Both PostgreSQL nodes are already connected; no changes made.")
        return
    to_create = []
    for _, credential_id, name, database, user, password_key in CONNECTIONS:
        if credential_id not in existing_credentials:
            to_create.append({
                "id": credential_id, "name": name, "type": "postgres",
                "data": {"host": "ai-postgres", "port": 5432, "database": database,
                         "user": user, "password": settings[password_key],
                         "ssl": "disable", "allowUnauthorizedCerts": False,
                         "maxConnections": 5},
            })
    secrets_file = LOCAL / "rag-postgres-credentials.json"
    workflow_file = LOCAL / "rag-postgres-connected.json"
    try:
        if to_create:
            with secrets_file.open("x", encoding="utf-8") as output:
                json.dump(to_create, output)
            compose("run", "--rm", "--no-deps", "n8n", "import:credentials",
                    "--input=/bootstrap/rag-postgres-credentials.json", f"--projectId={project_id}")
        for node_name, credential_id, name, _, _, _ in CONNECTIONS:
            nodes[node_name]["credentials"] = {"postgres": {"id": credential_id, "name": name}}
        with workflow_file.open("x", encoding="utf-8") as output:
            json.dump([workflow], output, ensure_ascii=False)
        compose("run", "--rm", "--no-deps", "n8n", "import:workflow",
                "--input=/bootstrap/rag-postgres-connected.json", f"--projectId={project_id}")
    finally:
        secrets_file.unlink(missing_ok=True)
        workflow_file.unlink(missing_ok=True)
    compose("restart", "n8n")
    print(f"Connected both PostgreSQL nodes to the unpublished RAG draft. Backup: {backup}")
    print("No Gemini key, scraped documents, embeddings, or workflow publication were added.")


if __name__ == "__main__":
    main()
