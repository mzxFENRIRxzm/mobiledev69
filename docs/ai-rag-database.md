# THE_X: PostgreSQL for n8n memory and RAG

The optional AI stack has a dedicated PostgreSQL 17 container with pgvector 0.8.6. It does not replace the Django database or n8n's internal database. Its named volume, `the_x_deploy_ai_postgres_data`, persists separately. No host port is published.

## Start and verify (PowerShell, from the repository root)

```powershell
python scripts/setup_rag_db.py
python scripts/connect_rag_nodes.py
docker compose --env-file deploy/.env -f compose.deploy.yaml -f compose.ai.yaml ps ai-postgres
```

The script adds three random passwords to the ignored `deploy/.env` without printing them. Back up that file together with the AI database volume. Running the script again checks the existing databases; it does not rotate credentials or remove data. If a volume exists but its passwords are missing, restore the original `.env` rather than generating new ones.

`connect_rag_nodes.py` backs up the saved n8n workflow to ignored `.local/n8n`, creates two **Postgres** credentials in its existing project, and attaches them to the corresponding nodes in **THE_X RAG - THE_ONE structure - SETUP REQUIRED**. It preserves the saved node parameters, other nodes, and unpublished state. The fields you should see in n8n at `http://localhost:15678` are:

- **Postgres Chat Memory**: Host `ai-postgres`, port `5432`, database `the_x_ai_memory`, user `the_x_ai_memory`, password from `AI_MEMORY_DB_PASSWORD` in `deploy/.env`; SSL off inside the private Compose network. Keep table name `the_x_ai_memory`. n8n creates the memory table on first use.
- **Postgres PGVector Store**: Host `ai-postgres`, port `5432`, database `the_x_ai_vectors`, user `the_x_ai_vectors`, password from `AI_VECTOR_DB_PASSWORD`; SSL off inside the private Compose network. Keep table name `the_x_manual_vectors` and columns `id`, `embedding`, `content`, `metadata`.

Do not use `AI_DB_ADMIN_PASSWORD` in n8n. The two node users cannot connect to each other's database. The pgvector extension is enabled in `the_x_ai_vectors`. The vector table is intentionally left to n8n's **Insert Documents** operation when the first reviewed source and embedding model are ready; this avoids creating an incompatible vector dimension or schema in advance. The retrieval node alone does not populate it.

## Reviewed motorcycle documents

Only import manuals/specifications after checking the source, reuse rights, exact make/model/year and document revision. Do not put customer profiles, VINs, registration numbers, phone numbers or private bookings into this RAG database. During ingestion, split documents into short passages with title, source URL, model, year, revision and page/section metadata. Use the **same Gemini embedding model** (`models/gemini-embedding-001` in the current draft) and output dimensions for insertion and retrieval; re-embed the whole corpus if that model changes. Start with a small reviewed corpus and test model/year-specific questions and missing-evidence answers before scaling up. Consider metadata filtering, then hybrid keyword/vector search and reranking only when retrieval evaluations show a need.

For web collection, maintain a separate source inventory and raw snapshots first. Fetch only permitted public pages at a controlled rate, record source URL and fetch date, then review and normalize the motorcycle model/year/specification fields. The review gate comes before embedding and insert. The two n8n nodes shown here are **memory** and **retrieval**; they are not a scraping or embedding pipeline. The vector table will hold reviewed passages after a separate insertion flow is built and tested.

The first catalog source is [Honda BigWing Thailand](https://www.thaihonda.co.th/hondabigbike/motorcycle). Run from the repository root:

```powershell
python scripts/scrape_honda_bigwing.py
```

This fetches the public model index and each linked model page with a one-second pause between model requests, extracting factual table cells only. The ignored `.local/honda-bigwing/catalog.json` holds source URLs, page hashes and specifications, `.local/honda-bigwing/raw/` holds the HTML snapshots, and `.local/honda-bigwing/review.csv` lists models for review. A later run preserves review entries only when the page hash is unchanged. Use `--offline` to reparse the snapshots without network requests, or `--max-models 2` for a small live check. A year inferred from a URL is only a hint; blank years are flagged for review. Do not commit raw pages or import this pending-review output directly to RAG. The public website's `robots.txt` returned 404 during the first fetch; check source terms/reuse rights before embedding or redistributing any substantial text.

## Three-model vector pilot (3 October 2026)

The user checked the collected specifications preliminarily. `scripts/ingest_bigwing_pilot.py` takes the first three unflagged models with matching cached page hashes (New GB350C 2026, New CB1000GT 2026, New FORZA750 2025), converts factual specification groups to bounded passages, and records model, year, section, source URL, source hash, fetch date and `review_level=user_preliminary_pilot` in metadata. It does not mark the whole catalog formally approved or copy repair-manual prose. To validate the local input, import, or repeat fixed retrieval checks:

```powershell
python scripts/ingest_bigwing_pilot.py --dry-run
python scripts/ingest_bigwing_pilot.py
python scripts/ingest_bigwing_pilot.py --verify
```

The import prompts for the Embedding API key without displaying it. It embeds all passages before a single transactional PostgreSQL upsert; stable UUIDs prevent duplicates on a repeat import. The `--verify` operation makes three query embeddings and checks the top PGVector hit for each model/year. On 3 October, the pilot inserted **9 passages** (3 per model) with **3,072-dimensional** `gemini-embedding-001` vectors; all three model/year test questions ranked the matching engine section first. The vector table remains local in the private AI database; do not expose its contents as a public download.

This establishes direct PGVector retrieval, not an end-to-end n8n/Django citation path. The RAG draft remains unpublished. Before publication, implement citation IDs that Django can validate against retrieved evidence, run real Agent and cross-user tests, check output correctness and no-evidence behavior, and settle the source reuse terms for production. See [AI chat workflow](ai-chat-n8n.md).

## Full cached BigWing catalog (3 October 2026)

After the three-model pilot passed, the user requested ingestion of every model in the cached Honda BigWing catalog. Run:

```powershell
python scripts/ingest_bigwing_pilot.py --all --dry-run
python scripts/ingest_bigwing_pilot.py --all
```

The full import reads **32 cached model pages and 656 extracted factual specification cells**, divided into **95 passages**. Six models have a `year_not_in_url` review flag; their passage and metadata year remain explicitly unknown instead of guessing. This is preliminary user-reviewed catalog data, not a verified repair manual. Each passage carries the manufacturer page URL, page hash, section, model and review flags. The script checks cached page hashes, uses Gemini `batchEmbedContents` in groups of five, checkpoints returned vectors under ignored `.local/honda-bigwing/`, and transactionally upserts each group. On a quota error, rerun the same command; already current passages are skipped. A repeat run after completion reported `Already current: 95; remaining: 0`. PostgreSQL verification found **95 rows from 32 source URLs**, all vectors 3,072-dimensional, and no missing source hashes. The 6 unknown-year models account for 17 passages.

The n8n RAG draft remains unpublished. Direct vector ingestion alone does not make Django citation IDs available to the agent or confirm that n8n's retrieval node gives good answers. Source reuse rights and production terms still need confirmation before public use.
