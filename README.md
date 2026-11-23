# IDEA-1026

AI-powered quick-commerce stockout prediction and replenishment platform.

## Local setup

Requires Python 3.11+ and Docker.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d db
uvicorn app.main:app --reload
```

Open:
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health/live
- Readiness: http://localhost:8000/api/v1/health/ready

## Docker setup

```bash
cp .env.example .env
docker compose up --build
```

## Current scope

This starter provides:
- FastAPI application and versioned API router
- Configuration via environment variables
- SQLAlchemy database connectivity
- Liveness/readiness endpoints
- Replenishment quantity domain logic
- ERP adapter contract and a mock adapter
- Unit tests for replenishment logic

The mock ERP is for development and integration testing only. Its in-memory document store is not durable across restarts and must not be used as a production ERP. Before production, implement a persistent integration outbox, durable idempotency records, authentication/authorization, tenant isolation, migrations, observability, secrets management, and ERP sandbox testing.

## Development checks

```bash
pytest
ruff check .
```
