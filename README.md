
# IDEA-1026 — Quick-Commerce Stockout Predictor & Automated PO Ingestion Engine

An AI-assisted inventory management and replenishment platform for quick-commerce businesses. The system combines sales history, location-aware daily demand, stockout risk prediction, supplier-aware reorder recommendations, and automated purchase order workflows through a mock ERP integration.

## 1. Project Overview

IDEA-1026 helps quick-commerce operators:

- Manage products, locations, and inventory balances.
- Record historical sales and live checkout transactions.
- Calculate daily demand using each location's timezone.
- Predict stockout risk using a LightGBM model.
- Recommend reorder quantities based on available inventory and inbound stock.
- Select suppliers using lead time, cost, MOQ, and pack size.
- Create, approve, submit, and receive purchase orders.
- Integrate with an ERP through a defined adapter interface.

## 2. Technology Stack

| Component | Technology |
|---|---|
| Backend API | Python, FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy |
| Database migrations | Alembic |
| Validation | Pydantic |
| ML model | LightGBM |
| Data processing | Pandas, scikit-learn |
| ERP integration | Mock ERP adapter |
| Scheduling | APScheduler |
| Testing | Pytest, HTTPX |
| Code quality | Ruff |
| Containerization | Docker |

## 3. Architecture

The application follows a layered architecture:

- API layer: FastAPI endpoints and request/response schemas.
- Service layer: inventory, sales, demand, stockout, replenishment, supplier, and purchase order business logic.
- Data layer: SQLAlchemy models and PostgreSQL.
- ML layer: feature contract, dataset builder, synthetic data generator, and model training.
- Integration layer: ERP interface and mock adapter.
- Scheduler: daily inventory snapshot capture.

## 4. Project Structure

```text
idea-1026/
├── app/
│   ├── api/v1/endpoints/
│   ├── core/
│   ├── integrations/erp/
│   ├── ml/
│   ├── models/
│   ├── scheduler/
│   ├── schemas/
│   ├── scripts/
│   ├── services/
│   └── main.py
├── migrations/
│   └── versions/
├── tests/
├── artifacts/              # Generated ML artifacts; not committed
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## 5. Prerequisites

- Python 3.11 or newer
- Docker and Docker Compose
- Git
- PostgreSQL 16 (Docker Compose can provide it)

## 6. Local Installation

Clone the repository and enter the project directory.

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\activate
```

Install the application and development dependencies:

```bash
pip install -e ".[dev]"
```

Install optional machine-learning dependencies:

```bash
pip install -e ".[ml]"
```

Configure environment variables:

```bash
cp .env.example .env
```

Start PostgreSQL:

```bash
docker compose up -d db
```

Apply database migrations:

```bash
alembic upgrade head
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Open the API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Liveness: http://localhost:8000/api/v1/health/live
- Readiness: http://localhost:8000/api/v1/health/ready

## 7. Docker Installation

Configure the environment:

```bash
cp .env.example .env
```

Build and start the services:

```bash
docker compose up --build -d
```

Apply database migrations from the project environment:

```bash
alembic upgrade head
```

View service status:

```bash
docker compose ps
```

View API logs:

```bash
docker compose logs -f api
```

Stop services:

```bash
docker compose down
```

Database data is persisted in the `postgres_data` Docker volume.

## 8. Database Migrations

Apply all migrations:

```bash
alembic upgrade head
```

Check the current migration:

```bash
alembic current
```

Check for model/migration differences:

```bash
alembic check
```


## 9. Main API Endpoints

All application endpoints use the `/api/v1` prefix.

### Health

| Method | Endpoint |
|---|---|
| GET | `/health/live` |
| GET | `/health/ready` |

### Products and Locations

| Method | Endpoint |
|---|---|
| POST | `/products` |
| GET | `/products` |
| GET | `/products/{product_id}` |
| PUT | `/products/{product_id}` |
| PATCH | `/products/{product_id}/deactivate` |
| POST | `/locations` |
| GET | `/locations` |

### Inventory and Sales

| Method | Endpoint |
|---|---|
| GET | `/inventory` |
| POST | `/inventory/receive` |
| POST | `/inventory/adjust/increase` |
| POST | `/inventory/adjust/decrease` |
| POST | `/inventory/reserve` |
| POST | `/inventory/release` |
| POST | `/sales` |
| GET | `/sales` |
| POST | `/sales/checkout` |

### Demand and Stockout Prediction

| Method | Endpoint |
|---|---|
| GET | `/demand/daily` |
| POST | `/stockout/predict` |

### Suppliers and Replenishment

| Method | Endpoint |
|---|---|
| POST | `/suppliers` |
| GET | `/suppliers` |
| GET | `/suppliers/{supplier_id}` |
| PUT | `/suppliers/{supplier_id}` |
| PATCH | `/suppliers/{supplier_id}/deactivate` |
| POST | `/supplier-products` |
| GET | `/supplier-products` |
| GET | `/supplier-products/{supplier_product_id}` |
| PUT | `/supplier-products/{supplier_product_id}` |
| PATCH | `/supplier-products/{supplier_product_id}/deactivate` |
| POST | `/replenishment/recommendation` |
| POST | `/replenishment/supplier-recommendation` |

### Purchase Orders

| Method | Endpoint |
|---|---|
| POST | `/purchase-orders` |
| GET | `/purchase-orders` |
| POST | `/purchase-orders/{purchase_order_id}/approve` |
| POST | `/purchase-orders/{purchase_order_id}/submit` |
| POST | `/purchase-orders/{purchase_order_id}/receive` |

Refer to Swagger UI at `/docs` for request schemas, query parameters, response examples, and interactive API testing.

Most business endpoints require the development tenant header `X-Tenant-ID`. Use the tenant UUID configured in your local development database.


## 10. Inventory and Sales

Inventory balances track:

- On-hand quantity
- Reserved quantity
- Inbound quantity
- Available quantity
- Version for inventory updates

Available inventory is calculated as:

```text
Available = On-hand - Reserved
```

Historical sales ingestion records sales without changing inventory.

Live checkout records the sale and deducts available inventory atomically, while creating an inventory transaction. Reserved inventory is not consumed by checkout.

Idempotency keys help prevent duplicate processing.

## 11. Daily Demand Calculation

The demand service aggregates sales into daily quantities using the timezone configured for each location.

Features include:

- UTC timestamp conversion.
- Local calendar-day aggregation.
- Zero-sales day filling.
- Tenant, location, and product validation.
- Date-range filtering.

Daily inventory snapshots are captured by a scheduled job and used as inputs for stockout dataset construction.

## 12. Stockout Prediction

The ML pipeline uses LightGBM.

Features include:

- Previous-day sales.
- Seven-day sales lag.
- Seven-, fourteen-, and twenty-eight-day sales totals.
- Seven-day average daily sales.
- Available inventory.
- Day of week.

The prediction horizon is seven days.

The repository includes:

- Feature contract.
- Historical dataset builder.
- Deterministic synthetic dataset generator.
- Model training pipeline.
- Model artifact and metadata generation.
- Stockout prediction API.

Install ML dependencies:

```bash
pip install -e ".[ml]"
```

Generate synthetic training data and train the model:

```bash
python -m app.ml.synthetic_data
python -m app.ml.train_model
```

Generated model artifacts are stored in `artifacts/`.

**Important ML limitation:** Current demonstration metrics are based on synthetic data. They do not establish real-world predictive performance. Production deployment requires representative historical sales and inventory snapshots, validated labels, model calibration, and monitoring.

## 13. Replenishment Recommendation

The core reorder calculation is:

```text
Required Quantity =
max(0, Forecast Demand + Safety Stock
       - Available Inventory
       - Confirmed Inbound)
```

Supplier-aware recommendations additionally consider:

- Preferred supplier.
- Supplier lead time.
- Unit cost and currency.
- Minimum order quantity (MOQ).
- Pack-size rounding.

The recommendation endpoint does not itself create a purchase order or change inventory.

## 14. Purchase Orders and Mock ERP

The purchase order lifecycle is:

```text
DRAFT → APPROVED → SUBMITTED
                         |
                         v
                 PARTIALLY_RECEIVED
                         |
                         v
                     RECEIVED
```

The workflow supports:

- Purchase order creation.
- Supplier catalog price validation.
- Order line and total calculation.
- Approval.
- ERP submission.
- Inbound inventory updates.
- Partial and full receiving.
- Receipt transaction records.
- Idempotent submission and receiving.

The mock ERP implements the ERP adapter interface and uses deterministic external references for repeatable submissions.

**Important ERP limitation:** The mock ERP stores documents in memory. Its records are not durable across restarts. A production integration needs a real ERP connector, persistent outbox, durable idempotency, retry handling, and reconciliation.

## 15. Testing and Code Quality

Run all tests:

```bash
pytest -q
```

Run lint checks:

```bash
ruff check .
```

Run Python compilation checks:

```bash
python -m compileall -q app migrations tests
```

Check migrations:

```bash
alembic check
```

The project has previously passed 81 automated tests. Run the commands above against your current checkout to verify its status.

## 16. Development and Production Considerations

This repository is a functional demonstration and development project, not a production-ready deployment.

Before production use:

- Replace demo database credentials and use secure secret management.
- Implement authentication and authorization.
- Enforce tenant isolation across all data access paths.
- Use durable ERP integration and idempotency storage.
- Add integration and concurrency testing.
- Configure production logging, metrics, tracing, and alerting.
- Validate ML training data and prediction quality on real operational data.
- Calibrate risk thresholds and monitor model drift.
- Review scheduler behavior when running multiple API workers.
- Configure backups, recovery, and database security.
- Perform ERP sandbox and end-to-end acceptance testing.

## 17. Current Project Status

| Phase | Status |
|---|---|
| 1. Project setup and database | Complete |
| 2. Location and inventory management | Complete |
| 3. Sales history | Complete |
| 4. Daily demand and timezone handling | Complete |
| 5. Stockout prediction demo | Implemented; synthetic training data |
| 6. Reorder recommendation engine | Core implementation complete |
| 7. Mock ERP and automated PO ingestion | Core implementation complete |
| 8. Integration, testing, documentation and demo | In progress |

---

**IDEA-1026**
AI-powered quick-commerce stockout prediction and automated replenishment.
