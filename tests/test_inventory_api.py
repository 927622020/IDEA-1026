
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import Location, Product, Tenant


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    def override_get_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestingSession() as session:
        tenant_a = Tenant(
            name="Inventory API Tenant A",
            code=f"API-A-{uuid4().hex[:8]}",
        )
        tenant_b = Tenant(
            name="Inventory API Tenant B",
            code=f"API-B-{uuid4().hex[:8]}",
        )
        session.add_all([tenant_a, tenant_b])
        session.flush()

        product = Product(
            tenant_id=tenant_a.id,
            sku_code="OIL-001",
            product_name="Sunflower Oil 1L",
            brand="Demo Foods",
            category="Cooking Oil",
            unit_of_measure="PCS",
        )

        location = Location(
            tenant_id=tenant_a.id,
            location_code="WH-001",
            location_name="Main Warehouse",
            location_type="WAREHOUSE",
        )

        session.add_all([product, location])
        session.commit()
        session.refresh(tenant_a)
        session.refresh(tenant_b)
        session.refresh(product)
        session.refresh(location)

        tenant_a_id = str(tenant_a.id)
        tenant_b_id = str(tenant_b.id)
        product_id = str(product.id)
        location_id = str(location.id)

    with TestClient(app) as test_client:
        test_client.tenant_a_id = tenant_a_id
        test_client.tenant_b_id = tenant_b_id
        test_client.product_id = product_id
        test_client.location_id = location_id
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def inventory_payload(client, quantity, key):
    return {
        "location_id": client.location_id,
        "product_id": client.product_id,
        "quantity": quantity,
        "idempotency_key": key,
        "reference": "API-TEST-001",
        "notes": "Inventory API integration test",
    }


def test_receive_stock_api(client):
    headers = {"X-Tenant-ID": client.tenant_a_id}

    response = client.post(
        "/api/v1/inventory/receive",
        json=inventory_payload(client, "100", "API-RECEIVE-001"),
        headers=headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["balance"]["on_hand"] == "100.000"
    assert data["balance"]["reserved"] == "0.000"
    assert data["balance"]["available"] == "100.000"
    assert data["transaction"]["transaction_type"] == "RECEIVE"


def test_reserve_and_release_stock_api(client):
    headers = {"X-Tenant-ID": client.tenant_a_id}

    received = client.post(
        "/api/v1/inventory/receive",
        json=inventory_payload(client, "100", "API-RECEIVE-002"),
        headers=headers,
    )
    assert received.status_code == 200, received.text

    reserved = client.post(
        "/api/v1/inventory/reserve",
        json=inventory_payload(client, "20", "API-RESERVE-001"),
        headers=headers,
    )
    assert reserved.status_code == 200, reserved.text
    assert reserved.json()["balance"]["reserved"] == "20.000"
    assert reserved.json()["balance"]["available"] == "80.000"

    released = client.post(
        "/api/v1/inventory/release",
        json=inventory_payload(client, "5", "API-RELEASE-001"),
        headers=headers,
    )
    assert released.status_code == 200, released.text
    assert released.json()["balance"]["reserved"] == "15.000"
    assert released.json()["balance"]["available"] == "85.000"


def test_inventory_list_api(client):
    headers = {"X-Tenant-ID": client.tenant_a_id}

    received = client.post(
        "/api/v1/inventory/receive",
        json=inventory_payload(client, "50", "API-RECEIVE-003"),
        headers=headers,
    )
    assert received.status_code == 200, received.text

    response = client.get(
        "/api/v1/inventory",
        params={
            "location_id": client.location_id,
            "product_id": client.product_id,
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["on_hand"] == "50.000"


def test_inventory_tenant_header_required(client):
    response = client.get("/api/v1/inventory")

    assert response.status_code == 422


def test_cross_tenant_inventory_access_is_rejected(client):
    headers = {"X-Tenant-ID": client.tenant_b_id}

    response = client.post(
        "/api/v1/inventory/receive",
        json=inventory_payload(client, "10", "API-CROSS-TENANT-001"),
        headers=headers,
    )

    assert response.status_code == 404
