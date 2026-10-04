#!/bin/sh
set -eu

# These values are generated as hex by setup_rag_db.py. Validate again before SQL interpolation.
for value in "$AI_MEMORY_DB_PASSWORD" "$AI_VECTOR_DB_PASSWORD"; do
  if ! printf '%s' "$value" | grep -Eq '^[0-9a-f]{64}$'; then
    echo "AI database passwords must be generated 64-character hex values" >&2
    exit 1
  fi
done

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE ROLE the_x_ai_memory LOGIN PASSWORD '$AI_MEMORY_DB_PASSWORD';
CREATE ROLE the_x_ai_vectors LOGIN PASSWORD '$AI_VECTOR_DB_PASSWORD';
CREATE DATABASE the_x_ai_memory OWNER the_x_ai_memory;
CREATE DATABASE the_x_ai_vectors OWNER the_x_ai_vectors;
REVOKE ALL ON DATABASE the_x_ai_memory FROM PUBLIC;
REVOKE ALL ON DATABASE the_x_ai_vectors FROM PUBLIC;
GRANT CONNECT ON DATABASE the_x_ai_memory TO the_x_ai_memory;
GRANT CONNECT ON DATABASE the_x_ai_vectors TO the_x_ai_vectors;
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname the_x_ai_vectors <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
SQL
