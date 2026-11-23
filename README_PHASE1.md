# IDEA-1026 Phase 1 — Multi-tenant Product Master

## Important
The `X-Tenant-ID` header is a local development tenant selector only. It is not authentication.
Before production, derive tenant identity from a verified authenticated principal and authorize
the caller for that tenant. Do not expose this header-based mechanism publicly.

## Install dependencies
From the project root, with your virtual environment active:

```bash
pip install -e ".[dev]"
```

The updated `pyproject.toml` includes Alembic.

## Apply database migration
Ensure `.env` points to the running PostgreSQL database. Then:

```bash
alembic revision --autogenerate -m "create tenants and products"
alembic upgrade head
```

Review the generated migration before applying it in shared or production environments.

## Seed a development tenant
```bash
python -m app.scripts.seed_tenant
```
Copy the printed UUID.

## Start the API
Use your root `main.py` launcher:
```bash
python3 main.py
```

Swagger: http://localhost:8000/docs

For every Product API request, set header:
`X-Tenant-ID: <the UUID printed by seed_tenant>`

## API examples

Create:
```bash
curl -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: YOUR_TENANT_UUID" \
  -d '{"sku_code":"OIL-001","product_name":"Sunflower Oil 1L","brand":"Demo Foods","category":"Cooking Oil","unit_of_measure":"PCS"}'
```

List:
```bash
curl http://localhost:8000/api/v1/products -H "X-Tenant-ID: YOUR_TENANT_UUID"
```

Get one:
```bash
curl http://localhost:8000/api/v1/products/PRODUCT_UUID -H "X-Tenant-ID: YOUR_TENANT_UUID"
```

Update:
```bash
curl -X PUT http://localhost:8000/api/v1/products/PRODUCT_UUID \
  -H "Content-Type: application/json" -H "X-Tenant-ID: YOUR_TENANT_UUID" \
  -d '{"product_name":"Sunflower Oil 1L - Updated"}'
```

Deactivate:
```bash
curl -X PATCH http://localhost:8000/api/v1/products/PRODUCT_UUID/deactivate \
  -H "X-Tenant-ID: YOUR_TENANT_UUID"
```

## Tests
```bash
pytest -q
```

Tests use isolated in-memory SQLite databases. Your application still uses PostgreSQL through `.env`.

## Files
This is an overlay for the existing starter project. Copy the included `app/`, `migrations/`,
`tests/`, `alembic.ini`, and `pyproject.toml` into the project root, preserving unrelated files.
