
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import Location, Product, SalesRecord, Tenant
from app.services.demand_service import get_daily_demand


@pytest.fixture()
def demand_db():
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

    with TestingSession() as session:
        tenant_a = Tenant(
            name="Demand Tenant A",
            code=f"DEMAND-A-{uuid4().hex[:8]}",
        )
        tenant_b = Tenant(
            name="Demand Tenant B",
            code=f"DEMAND-B-{uuid4().hex[:8]}",
        )
        session.add_all([tenant_a, tenant_b])
        session.flush()

        product = Product(
            tenant_id=tenant_a.id,
            sku_code="DEMAND-001",
            product_name="Demand Test Product",
            brand="Demo Foods",
            category="Beverages",
            unit_of_measure="PCS",
        )

        location = Location(
            tenant_id=tenant_a.id,
            location_code="DEMAND-WH-001",
            location_name="Demand Warehouse",
            location_type="WAREHOUSE",
            timezone="Asia/Kolkata",
        )

        session.add_all([product, location])
        session.commit()

        for item in (tenant_a, tenant_b, product, location):
            session.refresh(item)

        yield {
            "session": session,
            "tenant_a_id": tenant_a.id,
            "tenant_b_id": tenant_b.id,
            "product_id": product.id,
            "location_id": location.id,
        }

    Base.metadata.drop_all(engine)
    engine.dispose()


def add_sale(
    session,
    tenant_id,
    location_id,
    product_id,
    quantity,
    sold_at,
    key,
):
    sale = SalesRecord(
        tenant_id=tenant_id,
        location_id=location_id,
        product_id=product_id,
        quantity=Decimal(quantity),
        sold_at=sold_at,
        idempotency_key=key,
    )
    session.add(sale)
    session.commit()


def test_daily_demand_groups_sales_by_local_date(demand_db):
    session = demand_db["session"]

    # Both timestamps fall on November 20 in Asia/Kolkata.
    add_sale(
        session,
        demand_db["tenant_a_id"],
        demand_db["location_id"],
        demand_db["product_id"],
        "10",
        datetime(2026, 11, 19, 18, 45, tzinfo=UTC),
        "DEMAND-GROUP-001",
    )
    add_sale(
        session,
        demand_db["tenant_a_id"],
        demand_db["location_id"],
        demand_db["product_id"],
        "15",
        datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
        "DEMAND-GROUP-002",
    )

    results = get_daily_demand(
        session,
        demand_db["tenant_a_id"],
        location_id=demand_db["location_id"],
        product_id=demand_db["product_id"],
        start_date=date(2026, 11, 20),
        end_date=date(2026, 11, 20),
    )

    assert len(results) == 1
    assert results[0]["date"] == date(2026, 11, 20)
    assert results[0]["quantity_sold"] == Decimal("25.000")
    assert results[0]["transaction_count"] == 2


def test_daily_demand_includes_zero_sales_days(demand_db):
    session = demand_db["session"]

    add_sale(
        session,
        demand_db["tenant_a_id"],
        demand_db["location_id"],
        demand_db["product_id"],
        "12",
        datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
        "DEMAND-ZERO-001",
    )

    results = get_daily_demand(
        session,
        demand_db["tenant_a_id"],
        location_id=demand_db["location_id"],
        product_id=demand_db["product_id"],
        start_date=date(2026, 11, 20),
        end_date=date(2026, 11, 22),
    )

    assert len(results) == 3
    assert results[0]["quantity_sold"] == Decimal("12.000")
    assert results[0]["transaction_count"] == 1
    assert results[1]["quantity_sold"] == Decimal(0)
    assert results[1]["transaction_count"] == 0
    assert results[2]["quantity_sold"] == Decimal(0)
    assert results[2]["transaction_count"] == 0


def test_daily_demand_respects_local_midnight_boundary(demand_db):
    session = demand_db["session"]

    # 18:29 UTC = 23:59 IST on November 20.
    add_sale(
        session,
        demand_db["tenant_a_id"],
        demand_db["location_id"],
        demand_db["product_id"],
        "5",
        datetime(2026, 11, 20, 18, 29, tzinfo=UTC),
        "DEMAND-BOUNDARY-001",
    )

    # 18:30 UTC = 00:00 IST on November 21.
    add_sale(
        session,
        demand_db["tenant_a_id"],
        demand_db["location_id"],
        demand_db["product_id"],
        "7",
        datetime(2026, 11, 20, 18, 30, tzinfo=UTC),
        "DEMAND-BOUNDARY-002",
    )

    results = get_daily_demand(
        session,
        demand_db["tenant_a_id"],
        location_id=demand_db["location_id"],
        product_id=demand_db["product_id"],
        start_date=date(2026, 11, 20),
        end_date=date(2026, 11, 21),
    )

    assert results[0]["quantity_sold"] == Decimal("5.000")
    assert results[0]["transaction_count"] == 1
    assert results[1]["quantity_sold"] == Decimal("7.000")
    assert results[1]["transaction_count"] == 1


def test_daily_demand_does_not_include_another_tenant(demand_db):
    session = demand_db["session"]

    add_sale(
        session,
        demand_db["tenant_a_id"],
        demand_db["location_id"],
        demand_db["product_id"],
        "10",
        datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
        "DEMAND-TENANT-001",
    )

    # Create another tenant's own product and location.
    other_product = Product(
        tenant_id=demand_db["tenant_b_id"],
        sku_code="OTHER-001",
        product_name="Other Tenant Product",
        brand="Other Foods",
        category="Beverages",
        unit_of_measure="PCS",
    )
    other_location = Location(
        tenant_id=demand_db["tenant_b_id"],
        location_code="OTHER-WH-001",
        location_name="Other Warehouse",
        location_type="WAREHOUSE",
        timezone="Asia/Kolkata",
    )
    session.add_all([other_product, other_location])
    session.commit()

    session.refresh(other_product)
    session.refresh(other_location)

    add_sale(
        session,
        demand_db["tenant_b_id"],
        other_location.id,
        other_product.id,
        "100",
        datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
        "DEMAND-TENANT-002",
    )

    results = get_daily_demand(
        session,
        demand_db["tenant_a_id"],
        location_id=demand_db["location_id"],
        product_id=demand_db["product_id"],
        start_date=date(2026, 11, 20),
        end_date=date(2026, 11, 20),
    )

    assert results[0]["quantity_sold"] == Decimal("10.000")
    assert results[0]["transaction_count"] == 1


def test_daily_demand_rejects_invalid_date_range(demand_db):
    with pytest.raises(HTTPException) as exc_info:
        get_daily_demand(
            demand_db["session"],
            demand_db["tenant_a_id"],
            location_id=demand_db["location_id"],
            product_id=demand_db["product_id"],
            start_date=date(2026, 11, 22),
            end_date=date(2026, 11, 20),
        )

    assert exc_info.value.status_code == 422
