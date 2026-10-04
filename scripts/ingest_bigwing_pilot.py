"""Embed preliminarily reviewed Honda BigWing catalog specs in PGVector.

Only factual specification cells from the local catalog are used. This does
not publish the n8n workflow or claim the source is a repair manual.
"""

import argparse
import csv
import getpass
import hashlib
from io import StringIO
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

from scrape_honda_bigwing import HOST, cache_path
from setup_n8n import COMPOSE, ROOT


CATALOG = ROOT / ".local" / "honda-bigwing" / "catalog.json"
RAW = CATALOG.parent / "raw"
EMBEDDING_MODEL = "models/gemini-embedding-001"
DIMENSIONS = 3072
PILOT_SIZE = 3
MAX_CHARS = 1100
CACHE = CATALOG.parent / "embedding-cache-gemini-embedding-001.json"
BATCH_SIZE = 5


def eligible_records(catalog, all_models=False):
    records = []
    for record in catalog.get("records", []):
        flags = set(record.get("review_flags") or [])
        if flags and (not all_models or flags != {"year_not_in_url"}):
            continue
        if record.get("review_status") != "pending" or not record.get("specifications"):
            continue
        url = record.get("source_url", "")
        if not url.startswith(f"https://{HOST}/hondabigbike/motorcycle/"):
            continue
        path = cache_path(RAW, url)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record.get("source_sha256"):
            continue
        records.append(record)
    return records if all_models else records[:PILOT_SIZE]


def passages(record, fetched_at):
    """Keep model/year in each passage; split long specification sections."""
    name = record["name"]
    year = record["url_year_hint"]
    year_label = str(year) if year is not None else "ไม่ระบุปีในหน้าข้อมูล"
    grouped = {}
    for item in record["specifications"]:
        group = " ".join(item["group"].split())
        label = " ".join(item["label"].split())
        value = " ".join(item["value"].split())
        if group and label and value:
            grouped.setdefault(group, []).append(f"{label}: {value}")
    for group, facts in grouped.items():
        header = f"Honda {name} ปี {year_label}\nหัวข้อ: {group}\n"
        if len(header) >= MAX_CHARS:
            raise ValueError("Specification heading is too long")
        batches = []
        current = []
        for fact in facts:
            if len(header) + len(fact) > MAX_CHARS:
                raise ValueError("Specification fact is too long")
            if current and len(header) + len("\n".join(current + [fact])) > MAX_CHARS:
                batches.append(current)
                current = []
            current.append(fact)
        if current:
            batches.append(current)
        for part, batch in enumerate(batches, 1):
            content = header + "\n".join(batch)
            chunk_key = f"{record['source_url']}|{group}|{part}"
            yield {
                "id": str(uuid5(NAMESPACE_URL, chunk_key)),
                "content": content,
                "metadata": {
                    "title": f"Honda {name} ({year_label}) — {group}",
                    "source_url": record["source_url"],
                    "manufacturer": "Honda", "model": name, "year": year,
                    "section": group, "part": part,
                    "source_type": "manufacturer_specifications",
                    "source_sha256": record["source_sha256"],
                    "fetched_at_utc": fetched_at,
                    "review_level": "user_preliminary_catalog",
                    "review_flags": record.get("review_flags") or [],
                    "embedding_model": EMBEDDING_MODEL,
                },
            }


def embed(key, content, task_type="RETRIEVAL_DOCUMENT"):
    request = Request(
        "https://generativelanguage.googleapis.com/v1beta/" + EMBEDDING_MODEL + ":embedContent",
        data=json.dumps({"model": EMBEDDING_MODEL, "content": {"parts": [{"text": content}]},
                         "taskType": task_type}, ensure_ascii=False).encode("utf-8"),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            values = json.load(response)["embedding"]["values"]
    except HTTPError as error:
        raise RuntimeError(f"Gemini embedding returned HTTP {error.code}") from None
    except (URLError, TimeoutError):
        raise RuntimeError("Gemini embedding network failure") from None
    if len(values) != DIMENSIONS or not all(isinstance(v, (int, float)) for v in values):
        raise RuntimeError("Unexpected Gemini embedding dimensions or values")
    return values


def batch_embed(key, chunks):
    requests = [{"model": EMBEDDING_MODEL,
                 "content": {"parts": [{"text": chunk["content"]}]},
                 "taskType": "RETRIEVAL_DOCUMENT"} for chunk in chunks]
    request = Request(
        "https://generativelanguage.googleapis.com/v1beta/" + EMBEDDING_MODEL + ":batchEmbedContents",
        data=json.dumps({"requests": requests}, ensure_ascii=False).encode("utf-8"),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=60) as response:
            results = json.load(response)["embeddings"]
    except HTTPError as error:
        raise RuntimeError(f"Gemini batch embedding returned HTTP {error.code}") from None
    except (URLError, TimeoutError):
        raise RuntimeError("Gemini batch embedding network failure") from None
    if len(results) != len(chunks) or any(
        len(result.get("values", [])) != DIMENSIONS or
        not all(isinstance(value, (int, float)) for value in result.get("values", []))
        for result in results
    ):
        raise RuntimeError("Unexpected Gemini batch size or embedding dimensions")
    return [result["values"] for result in results]


def existing_hashes():
    result = subprocess.run(
        [*COMPOSE, "exec", "-T", "ai-postgres", "psql", "-X", "-A", "-t", "-F", "|",
         "-U", "the_x_ai_vectors", "-d", "the_x_ai_vectors"], cwd=ROOT,
        input=("CREATE TABLE IF NOT EXISTS the_x_manual_vector_history ("
               "revision_id bigserial PRIMARY KEY, id uuid NOT NULL, content text NOT NULL, "
               "metadata jsonb NOT NULL, embedding vector(3072) NOT NULL, "
               "action text NOT NULL, reason text NOT NULL, actor_id bigint NOT NULL, "
               "archived_at timestamptz NOT NULL DEFAULT now());\n"
               "SELECT id, md5(replace(content, E'\\r\\n', E'\\n')), metadata->>'source_sha256', "
               "metadata->>'embedding_model' FROM the_x_manual_vectors;\n"
               "SELECT id, 'MANAGED', '', '' FROM the_x_manual_vector_history "
               "WHERE action IN ('edited', 'deleted');\n"),
        text=True, encoding="utf-8", capture_output=True, check=True)
    return {parts[0]: parts[1:] for line in result.stdout.splitlines()
            if len(parts := line.split("|")) == 4}


def read_cache():
    if not CACHE.exists():
        return {}
    payload = json.loads(CACHE.read_text(encoding="utf-8"))
    if payload.get("model") != EMBEDDING_MODEL or payload.get("dimensions") != DIMENSIONS:
        raise ValueError("Embedding cache uses a different model or dimensions")
    return payload.get("chunks", {})


def save_cache(chunks):
    temporary = CACHE.with_suffix(".tmp")
    temporary.write_text(json.dumps({"model": EMBEDDING_MODEL, "dimensions": DIMENSIONS,
                                     "chunks": chunks}, ensure_ascii=False), encoding="utf-8")
    temporary.replace(CACHE)


def content_hash(chunk):
    return hashlib.md5(chunk["content"].encode("utf-8")).hexdigest()


def import_rows(rows):
    """Insert atomically through psql stdin; no database password in arguments."""
    data = StringIO()
    writer = csv.writer(data, lineterminator="\n")
    for row in rows:
        writer.writerow((row["id"], row["content"],
                         json.dumps(row["metadata"], ensure_ascii=False, separators=(",", ":")),
                         "[" + ",".join(format(number, ".9g") for number in row["embedding"]) + "]"))
    sql = (
        "CREATE TABLE IF NOT EXISTS the_x_manual_vectors ("
        "id uuid PRIMARY KEY, content text, metadata jsonb, embedding vector(3072));\n"
        "CREATE TABLE IF NOT EXISTS the_x_manual_vector_history ("
        "revision_id bigserial PRIMARY KEY, id uuid NOT NULL, content text NOT NULL, "
        "metadata jsonb NOT NULL, embedding vector(3072) NOT NULL, "
        "action text NOT NULL, reason text NOT NULL, actor_id bigint NOT NULL, "
        "archived_at timestamptz NOT NULL DEFAULT now());\n"
        "CREATE TEMP TABLE pilot_import (LIKE the_x_manual_vectors INCLUDING DEFAULTS);\n"
        "COPY pilot_import (id, content, metadata, embedding) FROM STDIN WITH (FORMAT csv);\n"
        + data.getvalue() + "\\.\n"
        "INSERT INTO the_x_manual_vectors (id, content, metadata, embedding) "
        "SELECT p.id, p.content, p.metadata, p.embedding FROM pilot_import p "
        "WHERE NOT EXISTS (SELECT 1 FROM the_x_manual_vector_history h "
        "WHERE h.id = p.id AND h.action IN ('edited', 'deleted')) "
        "ON CONFLICT (id) DO UPDATE SET content=EXCLUDED.content, "
        "metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding;\n"
    )
    result = subprocess.run(
        [*COMPOSE, "exec", "-T", "ai-postgres", "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
         "--single-transaction", "-U", "the_x_ai_vectors", "-d", "the_x_ai_vectors"],
        cwd=ROOT, input=sql.encode("utf-8"), capture_output=True)
    if result.returncode:
        raise RuntimeError("PGVector import failed; transaction rolled back: " +
                           result.stderr.decode("utf-8", errors="replace")[:600])


def verify_retrieval(key, records):
    for record in records:
        question = f"Honda {record['name']} ปี {record['url_year_hint']} ปริมาตรกระบอกสูบเท่าไร"
        vector = embed(key, question, "RETRIEVAL_QUERY")
        vector_text = "[" + ",".join(format(number, ".9g") for number in vector) + "]"
        sql = ("SELECT metadata->>'model', metadata->>'year', metadata->>'section', "
               f"round((embedding <=> '{vector_text}'::vector)::numeric, 4) "
               "FROM the_x_manual_vectors ORDER BY embedding <=> '" + vector_text +
               "'::vector LIMIT 3")
        result = subprocess.run(
            [*COMPOSE, "exec", "-T", "ai-postgres", "psql", "-X", "-A", "-t", "-F", "|",
             "-U", "the_x_ai_vectors", "-d", "the_x_ai_vectors"],
            cwd=ROOT, input=sql + ";\n", text=True, encoding="utf-8", capture_output=True, check=True)
        matches = [line.split("|") for line in result.stdout.splitlines() if line.strip()]
        if not matches or matches[0][0] != record["name"] or matches[0][1] != str(record["url_year_hint"]):
            raise RuntimeError(f"Retrieval did not rank {record['name']} first: {matches[:3]}")
        print(f"Retrieval {record['name']}: top match {matches[0][2]}, distance {matches[0][3]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate and report the pilot without API or DB writes")
    parser.add_argument("--verify", action="store_true", help="Embed three fixed questions and inspect vector ranking")
    parser.add_argument("--all", action="store_true", help="Import all cached models, preserving unknown-year flags")
    args = parser.parse_args()
    if not CATALOG.is_file():
        raise SystemExit("Run scripts/scrape_honda_bigwing.py first.")
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    records = eligible_records(catalog, all_models=args.all)
    expected = len(catalog.get("records", [])) if args.all else PILOT_SIZE
    if len(records) != expected:
        raise SystemExit(f"Validated {len(records)}/{expected} cached models; no changes made.")
    chunks = [chunk for record in records for chunk in passages(record, catalog["fetched_at_utc"])]
    if not chunks or len({chunk["id"] for chunk in chunks}) != len(chunks):
        raise SystemExit("Invalid or duplicate chunks; no changes made.")
    print(f"Catalog: {len(records)} models, {len(chunks)} factual passages.")
    for record in records:
        if not args.all or record["url_year_hint"] is None:
            print(f"  {record['name']} ({record['url_year_hint'] or 'year unknown'}) — {record['source_url']}")
    if args.dry_run:
        return
    if args.verify:
        key = getpass.getpass("Gemini Embedding API key: ").strip()
        if not key:
            raise SystemExit("Embedding key is required; no changes made.")
        verify_retrieval(key, records[:PILOT_SIZE])
        return
    existing = existing_hashes()
    pending = [chunk for chunk in chunks if existing.get(chunk["id"], [None])[0] != "MANAGED"
               and existing.get(chunk["id"]) != [
                   content_hash(chunk), chunk["metadata"]["source_sha256"], EMBEDDING_MODEL]]
    print(f"Already current: {len(chunks)-len(pending)}; remaining: {len(pending)}", flush=True)
    if not pending:
        return
    cache = read_cache()
    key = None
    imported = 0
    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start+BATCH_SIZE]
        missing = [chunk for chunk in batch if not (
            (entry := cache.get(chunk["id"], {})).get("content_md5") == content_hash(chunk)
            and entry.get("source_sha256") == chunk["metadata"]["source_sha256"]
            and len(entry.get("embedding", [])) == DIMENSIONS)]
        if missing:
            if key is None:
                key = getpass.getpass("Gemini Embedding API key: ").strip()
                if not key:
                    raise SystemExit("Embedding key is required; no changes made.")
            try:
                vectors = batch_embed(key, missing) if args.all else [
                    embed(key, chunk["content"]) for chunk in missing]
            except RuntimeError as error:
                raise SystemExit(f"Stopped after {imported} new passages: {error}. "
                                 "Re-run the same command to resume without duplicates.") from None
            for chunk, vector in zip(missing, vectors):
                cache[chunk["id"]] = {"content_md5": content_hash(chunk),
                                      "source_sha256": chunk["metadata"]["source_sha256"],
                                      "embedding": vector}
            save_cache(cache)
        for chunk in batch:
            chunk["embedding"] = cache[chunk["id"]]["embedding"]
        import_rows(batch)
        imported += len(batch)
        print(f"Imported {imported}/{len(pending)} remaining passages", flush=True)
        if start+BATCH_SIZE < len(pending) and missing:
            time.sleep(2)
    print("Catalog passages imported into the_x_manual_vectors. RAG draft remains unpublished.")


if __name__ == "__main__":
    main()
