from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import (
    InventoryBalance,
    Location,
    Product,
    Supplier,
    SupplierProduct,
    Tenant,
)
from app.schemas.replenishment import SupplierReplenishmentRequest
from app.services.supplier_replenishment_service import (
    recommend_supplier_replenishment,
)


@pytest.fixture()
def db():
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
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def make_context(db):
    tenant = Tenant(name="Test Tenant", code="TEST-TENANT")
    db.add(tenant)
    db.flush()

    product = Product(
        tenant_id=tenant.id,
        sku_code="MANGO-001",
        product_name="Mango Drink 200ml",
        brand="Demo Foods",
        category="Beverages",
        unit_of_measure="PCS",
    )

    location = Location(
        tenant_id=tenant.id,
        location_code="WH-001",
        location_name="Main Warehouse",
        location_type="WAREHOUSE",
    )

    db.add_all([product, location])
    db.flush()

    balance = InventoryBalance(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
        on_hand=Decimal(100),
        reserved=Decimal(20),
        inbound=Decimal(10),
        version=1,
    )

    db.add(balance)
    db.commit()

    return tenant, product, location, balance


def make_supplier(db, tenant, code, name, lead_time):
    supplier = Supplier(
        tenant_id=tenant.id,
        supplier_code=code,
        supplier_name=name,
        default_lead_time_days=lead_time,
        is_active=True,
    )
    db.add(supplier)
    db.flush()
    return supplier


def add_supplier_product(
    db,
    tenant,
    supplier,
    product,
    *,
    preferred=False,
    lead_time=5,
    unit_cost="12.5000",
    active=True,
):
    item = SupplierProduct(
        tenant_id=tenant.id,
        supplier_id=supplier.id,
        product_id=product.id,
        supplier_sku="SUP-MANGO-001",
        unit_cost=Decimal(unit_cost),
        currency="BDT",
        lead_time_days=lead_time,
        minimum_order_quantity=Decimal(10),
        pack_size=Decimal(5),
        is_preferred=preferred,
        is_active=active,
    )
    db.add(item)
    db.commit()
    return item


def make_payload(location, product):
    return SupplierReplenishmentRequest(
        location_id=location.id,
        product_id=product.id,
        forecast_demand=Decimal(110),
        safety_stock=Decimal(8),
    )


def test_recommendation_selects_preferred_supplier(db):
    tenant, product, location, _ = make_context(db)

    faster_supplier = make_supplier(
        db, tenant, "SUP-FAST", "Fast Supplier", 2
    )
    preferred_supplier = make_supplier(
        db, tenant, "SUP-PREFERRED", "Preferred Supplier", 7
    )

    add_supplier_product(
        db, tenant, faster_supplier, product,
        lead_time=2,
    )
    add_supplier_product(
        db, tenant, preferred_supplier, product,
        preferred=True,
        lead_time=7,
    )

    result = recommend_supplier_replenishment(
        db, tenant.id, make_payload(location, product)
    )

    assert result.supplier_id == preferred_supplier.id
    assert result.supplier_name == "Preferred Supplier"
    assert result.is_preferred_supplier is True


def test_recommendation_calculates_inventory_and_order_quantity(db):
    tenant, product, location, _ = make_context(db)

    supplier = make_supplier(
        db, tenant, "SUP-CALC", "Calculation Supplier", 5
    )
    add_supplier_product(
        db, tenant, supplier, product,
        preferred=True,
    )

    result = recommend_supplier_replenishment(
        db, tenant.id, make_payload(location, product)
    )

    # Available = 100 on hand - 20 reserved = 80.
    # Required = 110 forecast + 8 safety - 80 available - 10 inbound = 28.
    # MOQ = 10 and pack size = 5, so order quantity = 30.
    assert result.available_inventory == Decimal("80.000")
    assert result.confirmed_inbound == Decimal("10.000")
    assert result.required_quantity == Decimal("28.000")
    assert result.recommended_quantity == Decimal("30.000")
    assert result.requires_replenishment is True


def test_recommendation_calculates_estimated_total_cost(db):
    tenant, product, location, _ = make_context(db)

    supplier = make_supplier(
        db, tenant, "SUP-COST", "Cost Supplier", 5
    )
    add_supplier_product(
        db, tenant, supplier, product,
        preferred=True,
        unit_cost="12.5000",
    )

    result = recommend_supplier_replenishment(
        db, tenant.id, make_payload(location, product)
    )

    assert result.unit_cost == Decimal("12.5000")
    assert result.currency == "BDT"
    assert result.estimated_total_cost == Decimal("375.0000")


def test_inactive_supplier_is_not_selected(db):
    tenant, product, location, _ = make_context(db)

    supplier = make_supplier(
        db, tenant, "SUP-INACTIVE", "Inactive Supplier", 5
    )
    supplier.is_active = False

    add_supplier_product(
        db, tenant, supplier, product,
        preferred=True,
    )

    with pytest.raises(HTTPException) as error:
        recommend_supplier_replenishment(
            db, tenant.id, make_payload(location, product)
        )

    assert error.value.status_code == 404


def test_missing_inventory_balance_returns_404(db):
    tenant, product, location, balance = make_context(db)

    db.delete(balance)
    db.commit()

    supplier = make_supplier(
        db, tenant, "SUP-NOBALANCE", "No Balance Supplier", 5
    )
    add_supplier_product(
        db, tenant, supplier, product,
        preferred=True,
    )

    with pytest.raises(HTTPException) as error:
        recommend_supplier_replenishment(
            db, tenant.id, make_payload(location, product)
        )

    assert error.value.status_code == 404


def test_forecast_recommendation_uses_supplier_lead_time(
    db, monkeypatch
):
    from datetime import date, timedelta

    from app.schemas.forecast import (
        DailyForecast,
        DemandForecastResponse,
    )
    from app.services.supplier_replenishment_service import (
        recommend_forecast_supplier_replenishment,
    )

    tenant, product, location, _ = make_context(db)

    supplier = make_supplier(
        db, tenant, "SUP-FORECAST", "Forecast Supplier", 3
    )
    add_supplier_product(
        db, tenant, supplier, product,
        preferred=True,
        lead_time=3,
    )

    start = date(2026, 11, 25)
    daily_values = [40, 50, 60, 100, 100, 100, 100]

    fake_forecast = DemandForecastResponse(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
        historical_start_date=start - timedelta(days=29),
        historical_end_date=start - timedelta(days=2),
        forecast_start_date=start,
        forecast_end_date=start + timedelta(days=6),
        history_days=28,
        days_with_sales=28,
        method="weekday_average",
        status="ok",
        message="Test forecast",
        daily_forecasts=[
            DailyForecast(
                date=start + timedelta(days=index),
                forecast_demand=Decimal(value),
            )
            for index, value in enumerate(daily_values)
        ],
        total_forecast_demand=Decimal(550),
    )

    monkeypatch.setattr(
        "app.services.forecast_service.forecast_daily_demand",
        lambda *args, **kwargs: fake_forecast,
    )

    result = recommend_forecast_supplier_replenishment(
        db,
        tenant.id,
        location_id=location.id,
        product_id=product.id,
        safety_stock=Decimal(8),
    )

    # Only the first 3 forecast days are used: 40 + 50 + 60 = 150.
    # Required = 150 + 8 safety - 80 available - 10 inbound = 68.
    # MOQ 10 and pack size 5 produce an order quantity of 70.
    assert result.forecast_demand == Decimal(150)
    assert result.lead_time_forecast_days == 3
    assert len(result.lead_time_daily_forecasts) == 3
    assert result.recommended_quantity == Decimal(70)
    assert result.forecast_method == "weekday_average"


def test_forecast_recommendation_rejects_insufficient_history(
    db, monkeypatch
):
    from app.schemas.forecast import DemandForecastResponse
    from app.services.supplier_replenishment_service import (
        recommend_forecast_supplier_replenishment,
    )

    tenant, product, location, _ = make_context(db)

    fake_forecast = DemandForecastResponse(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
        historical_start_date=date(2026, 10, 27),
        historical_end_date=date(2026, 11, 23),
        forecast_start_date=date(2026, 11, 25),
        forecast_end_date=date(2026, 12, 1),
        history_days=28,
        days_with_sales=0,
        method="none",
        status="insufficient_history",
        message="No history",
        daily_forecasts=[],
        total_forecast_demand=Decimal(0),
    )

    monkeypatch.setattr(
        "app.services.forecast_service.forecast_daily_demand",
        lambda *args, **kwargs: fake_forecast,
    )

    with pytest.raises(HTTPException) as error:
        recommend_forecast_supplier_replenishment(
            db,
            tenant.id,
            location_id=location.id,
            product_id=product.id,
            safety_stock=Decimal(8),
        )

    assert error.value.status_code == 422
