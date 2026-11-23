
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import InventoryBalance, Location, Product, Tenant


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
            name="Sales API Tenant A",
            code=f"SALES-A-{uuid4().hex[:8]}",
        )
        tenant_b = Tenant(
            name="Sales API Tenant B",
            code=f"SALES-B-{uuid4().hex[:8]}",
        )
        session.add_all([tenant_a, tenant_b])
        session.flush()

        product = Product(
            tenant_id=tenant_a.id,
            sku_code="SALES-001",
            product_name="Demo Mango Drink",
            brand="Demo Foods",
            category="Beverages",
            unit_of_measure="PCS",
        )

        location = Location(
            tenant_id=tenant_a.id,
            location_code="SALES-WH-001",
            location_name="Sales Warehouse",
            location_type="WAREHOUSE",
        )

        inactive_product = Product(
            tenant_id=tenant_a.id,
            sku_code="SALES-002",
            product_name="Inactive Product",
            brand="Demo Foods",
            category="Beverages",
            unit_of_measure="PCS",
            is_active=False,
        )

        session.add_all([product, location, inactive_product])
        session.flush()

        inventory_balance = InventoryBalance(
            tenant_id=tenant_a.id,
            location_id=location.id,
            product_id=product.id,
            on_hand=100,
            reserved=0,
            inbound=0,
            version=1,
        )
        session.add(inventory_balance)
        session.commit()

        for item in (tenant_a, tenant_b, product, location, inactive_product):
            session.refresh(item)

        tenant_a_id = str(tenant_a.id)
        tenant_b_id = str(tenant_b.id)
        product_id = str(product.id)
        location_id = str(location.id)
        inactive_product_id = str(inactive_product.id)

    with TestClient(app) as test_client:
        test_client.tenant_a_id = tenant_a_id
        test_client.tenant_b_id = tenant_b_id
        test_client.product_id = product_id
        test_client.location_id = location_id
        test_client.inactive_product_id = inactive_product_id
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def sales_payload(client, quantity="10", key="SALE-001"):
    return {
        "location_id": client.location_id,
        "product_id": client.product_id,
        "quantity": quantity,
        "sold_at": "2026-11-20T10:00:00+05:30",
        "external_reference": "POS-ORDER-001",
        "idempotency_key": key,
    }


def test_create_sale_api(client):
    headers = {"X-Tenant-ID": client.tenant_a_id}

    response = client.post(
        "/api/v1/sales",
        json=sales_payload(client),
        headers=headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["quantity"] == "10.000"
    assert data["product_id"] == client.product_id
    assert data["location_id"] == client.location_id
    assert data["external_reference"] == "POS-ORDER-001"


def test_duplicate_sale_api_is_idempotent(client):
    headers = {"X-Tenant-ID": client.tenant_a_id}
    payload = sales_payload(client)

    first = client.post("/api/v1/sales", json=payload, headers=headers)
    second = client.post("/api/v1/sales", json=payload, headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]


def test_reusing_idempotency_key_with_different_data_is_rejected(client):
    headers = {"X-Tenant-ID": client.tenant_a_id}

    first = client.post(
        "/api/v1/sales",
        json=sales_payload(client, quantity="10"),
        headers=headers,
    )
    second = client.post(
        "/api/v1/sales",
        json=sales_payload(client, quantity="15"),
        headers=headers,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text


def test_cross_tenant_sale_is_rejected(client):
    headers = {"X-Tenant-ID": client.tenant_b_id}

    response = client.post(
        "/api/v1/sales",
        json=sales_payload(client),
        headers=headers,
    )

    assert response.status_code == 404


def test_inactive_product_sale_is_rejected(client):
    headers = {"X-Tenant-ID": client.tenant_a_id}
    payload = sales_payload(client)
    payload["product_id"] = client.inactive_product_id

    response = client.post(
        "/api/v1/sales",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 404


def test_sales_list_and_filters(client):
    headers = {"X-Tenant-ID": client.tenant_a_id}

    for index, quantity in enumerate(("10", "20")):
        response = client.post(
            "/api/v1/sales",
            json=sales_payload(
                client,
                quantity=quantity,
                key=f"SALE-LIST-{index}",
            ),
            headers=headers,
        )
        assert response.status_code == 201, response.text

    response = client.get(
        "/api/v1/sales",
        params={
            "product_id": client.product_id,
            "location_id": client.location_id,
            "sold_from": "2026-11-20T00:00:00+05:30",
            "sold_to": "2026-11-20T23:59:59+05:30",
            "limit": 10,
            "offset": 0,
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["quantity"] == "20.000"


def test_sales_date_filter_rejects_invalid_range(client):
    headers = {"X-Tenant-ID": client.tenant_a_id}

    response = client.get(
        "/api/v1/sales",
        params={
            "sold_from": "2026-11-21T00:00:00+05:30",
            "sold_to": "2026-11-20T00:00:00+05:30",
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_sales_tenant_header_required(client):
    response = client.get("/api/v1/sales")

    assert response.status_code == 422


def test_checkout_sale_api(client):
    headers = {"X-Tenant-ID": client.tenant_a_id}

    response = client.post(
        "/api/v1/sales/checkout",
        json=sales_payload(
            client,
            quantity="5",
            key="API-CHECKOUT-001",
        ),
        headers=headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["quantity"] == "5.000"
    assert data["product_id"] == client.product_id
    assert data["location_id"] == client.location_id
    assert data["idempotency_key"] == "API-CHECKOUT-001"
