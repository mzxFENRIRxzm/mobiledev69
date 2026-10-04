"""Configure separate Gemini credentials for the saved RAG draft.

Keys are read with hidden terminal prompts. They are never passed as command
arguments or stored in a tracked file. The temporary n8n import is removed.
"""

import getpass
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from setup_n8n import COMPOSE, ENV, LOCAL, ROOT


WORKFLOW_ID = "theXOneRagDraft"
HOST = "https://generativelanguage.googleapis.com"
CHAT = ("theXGeminiChatConfigured", "THE_X Gemini Chat")
EMBEDDING = ("theXGeminiEmbeddingConfigured", "THE_X Gemini Embedding")
NODE_CREDENTIALS = {
    "Google Gemini Chat Model": CHAT,
    "Google Gemini - RAG answer": CHAT,
    "Embeddings Google Gemini": EMBEDDING,
}


def compose(*args, capture=False):
    return subprocess.run([*COMPOSE, *args], cwd=ROOT, check=True,
                          capture_output=capture, text=capture)


def available_models(key):
    request = Request(f"{HOST}/v1beta/models?pageSize=1000",
                      headers={"x-goog-api-key": key})
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except HTTPError as error:
        try:
            details = json.load(error).get("error", {})
            status = str(details.get("status", "unknown"))
            reasons = [str(item.get("reason")) for item in details.get("details", [])
                       if isinstance(item, dict) and item.get("reason")]
        except (ValueError, OSError):
            status = "unknown"
            reasons = []
        suffix = f"; reason={','.join(reasons)}" if reasons else ""
        raise RuntimeError(f"Google model list returned HTTP {error.code} ({status}{suffix})") from None
    except URLError as error:
        raise RuntimeError(f"Google model list could not be reached: {error.reason}") from None
    return {model["name"]: model.get("supportedGenerationMethods", [])
            for model in payload.get("models", [])}


def smoke_test():
    """Check one minimal generation and one embedding without printing content."""
    checks = (
        ("Chat", "models/gemini-3.5-flash-lite:generateContent",
         {"contents": [{"parts": [{"text": "ตอบว่า OK"}]}],
          "generationConfig": {"maxOutputTokens": 20}}, "candidates"),
        ("Embedding", "models/gemini-embedding-001:embedContent",
         {"model": "models/gemini-embedding-001",
          "content": {"parts": [{"text": "ทดสอบ"}]}}, "embedding"),
    )
    for label, endpoint, payload, result_field in checks:
        key = getpass.getpass(f"Gemini {label} API key: ").strip()
        request = Request(f"{HOST}/v1beta/{endpoint}",
                          data=json.dumps(payload).encode("utf-8"),
                          headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                          method="POST")
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response)
        except HTTPError as error:
            try:
                details = json.load(error).get("error", {})
                status = str(details.get("status", "unknown"))
            except (ValueError, OSError):
                status = "unknown"
            print(f"{label}: HTTP {error.code} ({status})")
            continue
        except URLError:
            print(f"{label}: network error")
            continue
        if result_field == "embedding":
            dimension = len(result.get("embedding", {}).get("values", []))
            print(f"{label}: success, vector dimensions={dimension}")
        else:
            print(f"{label}: success, candidate count={len(result.get('candidates', []))}")


def main():
    if not ENV.exists():
        raise SystemExit("Run python scripts/init_docker.py first.")
    LOCAL.mkdir(parents=True, exist_ok=True)
    backup = LOCAL / ("rag-before-gemini-" +
                      datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    compose("run", "--rm", "--no-deps", "-v", f"{LOCAL.as_posix()}:/output", "n8n",
            "export:workflow", f"--id={WORKFLOW_ID}", f"--output=/output/{backup.name}")
    workflow = json.loads(backup.read_text(encoding="utf-8"))[0]
    if workflow.get("id") != WORKFLOW_ID or workflow.get("active"):
        raise SystemExit("Expected the saved, unpublished RAG draft; no changes made.")
    project_ids = {entry.get("projectId") for entry in workflow.get("shared", [])
                   if entry.get("role") == "workflow:owner"}
    if len(project_ids) != 1 or not next(iter(project_ids)):
        raise SystemExit("Cannot identify workflow owner project; no changes made.")
    project_id = next(iter(project_ids))
    nodes = {node["name"]: node for node in workflow["nodes"]}
    if not NODE_CREDENTIALS.keys() <= nodes.keys():
        raise SystemExit("Expected Gemini nodes are missing; no changes made.")
    rows = compose("exec", "-T", "n8n-postgres", "psql", "-U", "n8n", "-d", "n8n",
                   "-Atc", "SELECT id FROM credentials_entity WHERE id IN "
                   "('theXGeminiChatConfigured','theXGeminiEmbeddingConfigured')",
                   capture=True).stdout.splitlines()
    if rows:
        raise SystemExit("Configured credential ID already exists. Inspect n8n; no changes made.")

    chat_key = getpass.getpass("Gemini Chat API key: ").strip()
    embedding_key = getpass.getpass("Gemini Embedding API key: ").strip()
    if not chat_key or not embedding_key or chat_key == embedding_key:
        raise SystemExit("Two distinct, nonempty keys are required; no changes made.")
    results = {}
    errors = []
    for label, key in (("Chat", chat_key), ("Embedding", embedding_key)):
        try:
            results[label] = available_models(key)
        except RuntimeError as error:
            errors.append(f"{label}: {error}")
    if errors:
        raise SystemExit("Credential check failed: " + "; ".join(errors) +
                         "; no changes made.")
    chat_models = results["Chat"]
    embedding_models = results["Embedding"]
    chat_model = nodes["Google Gemini Chat Model"]["parameters"].get("modelName")
    if chat_model not in chat_models or "generateContent" not in chat_models[chat_model]:
        candidates = sorted(name for name, methods in chat_models.items()
                            if "generateContent" in methods and "flash-lite" in name)
        raise SystemExit(f"Configured chat model is unavailable for this key: {chat_model}. "
                         f"Available flash-lite models: {', '.join(candidates) or 'none'}. "
                         "No changes made.")
    if "models/gemini-embedding-001" not in embedding_models:
        raise SystemExit("Gemini embedding model is unavailable for this key; no changes made.")
    for node_name, credential in NODE_CREDENTIALS.items():
        current = (nodes[node_name].get("credentials") or {}).get("googlePalmApi")
        if current and current.get("id") not in {"theXGeminiNative", credential[0]}:
            raise SystemExit(f"{node_name} uses an unexpected credential; no changes made.")

    with TemporaryDirectory(prefix="gemini-import-", dir=LOCAL) as temp_path:
        temp = Path(temp_path)
        credentials_file = temp / "credentials.json"
        workflow_file = temp / "workflow.json"
        credentials = [
            {"id": credential_id, "name": name, "type": "googlePalmApi",
             "data": {"host": HOST, "apiKey": key}}
            for (credential_id, name), key in [(CHAT, chat_key), (EMBEDDING, embedding_key)]
        ]
        credentials_file.write_text(json.dumps(credentials), encoding="utf-8")
        # Drop references before invoking n8n; imported secrets remain encrypted there.
        del credentials, chat_key, embedding_key
        relative = temp.relative_to(LOCAL).as_posix()
        compose("run", "--rm", "--no-deps", "n8n", "import:credentials",
                f"--input=/bootstrap/{relative}/credentials.json", f"--projectId={project_id}")
        for node_name, (credential_id, name) in NODE_CREDENTIALS.items():
            nodes[node_name]["credentials"] = {
                "googlePalmApi": {"id": credential_id, "name": name}}
        workflow_file.write_text(json.dumps([workflow], ensure_ascii=False), encoding="utf-8")
        compose("run", "--rm", "--no-deps", "n8n", "import:workflow",
                f"--input=/bootstrap/{relative}/workflow.json", f"--projectId={project_id}")
    compose("restart", "n8n")
    print(f"Connected separate Chat and Embedding credentials. Backup: {backup}")
    print("RAG workflow remains unpublished; no document embeddings or chat requests were made.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--smoke-test"]:
        smoke_test()
    else:
        main()
