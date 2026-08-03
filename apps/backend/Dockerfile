# One image, two roles: the API server and every Celery worker tier all run
# from this image — only the container CMD differs (see
# infra/docker/docker-compose.prod.yml). That keeps "does the worker have
# the same code as the API" a non-question rather than a two-image drift risk.

FROM python:3.12-slim AS base

# Native deps for psycopg[binary]'s runtime libs and building any C
# extensions in the dependency tree (e.g. tree-sitter grammars).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependencies first, keyed only on the lock/manifest files, so an
# application-code-only change doesn't invalidate the dependency layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Runs as the API by default; docker-compose overrides the command for
# worker services and the one-shot migration job.
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
