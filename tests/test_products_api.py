from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import Tenant


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestingSession() as session:
        tenant = Tenant(name="API Test Brand", code=f"API-{uuid4().hex[:8]}")
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        tenant_id = str(tenant.id)

    with TestClient(app) as test_client:
        test_client.tenant_id = tenant_id
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_create_and_list_product(client):
    headers = {"X-Tenant-ID": client.tenant_id}
    payload = {
        "sku_code": "OIL-001",
        "product_name": "Sunflower Oil 1L",
        "brand": "Demo Foods",
        "category": "Cooking Oil",
        "unit_of_measure": "PCS",
    }
    created = client.post("/api/v1/products", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["sku_code"] == "OIL-001"

    listed = client.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_tenant_header_required(client):
    response = client.get("/api/v1/products")
    assert response.status_code == 422
