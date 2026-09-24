FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

RUN pip install --no-cache-dir uv==0.9.0 \
    && groupadd --system app \
    && useradd --system --gid app --uid 10001 app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY --chown=app:app backend/ ./
RUN mkdir -p /app/staticfiles /app/media \
    && chown app:app /app/staticfiles /app/media

USER app
EXPOSE 8000
CMD ["gunicorn", "the_x.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
