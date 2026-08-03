.PHONY: backend frontend worker migrate infra infra-down test test-db-up test-db-down seed

# FastAPI dev server.
backend:
	cd apps/backend && uv run uvicorn src.main:app --reload

# Vite dev server.
frontend:
	cd apps/frontend && npm run dev

# Celery worker. Consumes all four queues; split into separate processes
# (-Q extraction / -Q verification / -Q matching) to scale each independently.
worker:
	cd apps/backend && uv run celery -A src.jobs.celery_app:celery_app worker \
		--loglevel=info -Q extraction,verification,matching,dead_letter

migrate:
	cd apps/backend && uv run alembic upgrade head

# Postgres + Redis + MinIO (with the resume bucket created).
infra:
	docker compose -f infra/docker/docker-compose.yml up -d

infra-down:
	docker compose -f infra/docker/docker-compose.yml down

# Separate, disposable Postgres for the test suite — see tests/conftest.py's
# module docstring for why this must never be the same database `infra`
# starts. Applies migrations against it (not DATABASE_URL) before the first
# test can run.
test-db-up:
	docker compose -f infra/docker/docker-compose.yml up -d postgres-test
	@echo "Waiting for postgres-test to become healthy..."
	@until [ "$$(docker inspect --format='{{.State.Health.Status}}' groundtruth-postgres-test 2>/dev/null)" = "healthy" ]; do sleep 1; done
	cd apps/backend && DATABASE_URL=$$(grep '^TEST_DATABASE_URL=' .env | cut -d= -f2-) uv run alembic upgrade head

test-db-down:
	docker compose -f infra/docker/docker-compose.yml stop postgres-test

test: test-db-up
	cd apps/backend && uv run pytest

seed:
	cd apps/backend && uv run python -m scripts.seed
