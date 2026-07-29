.PHONY: backend frontend worker migrate

backend:
	cd apps/backend && uv run uvicorn src.main:app --reload

frontend:
	cd apps/frontend && npm run dev

worker:
	cd apps/backend && uv run celery -A src.workers.celery_app worker --loglevel=info

migrate:
	cd apps/backend && uv run alembic upgrade head
