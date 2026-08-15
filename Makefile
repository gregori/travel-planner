.PHONY: dev dev-backend dev-frontend test lint e2e install

install:
	cd backend && uv sync
	cd frontend && npm install

dev:
	@trap 'kill 0' EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest --cov=app --cov-report=term-missing

lint:
	cd backend && uv run ruff check .
	cd frontend && npm run lint && npm run typecheck

e2e:
	cd backend && uv run pytest tests/e2e -v
