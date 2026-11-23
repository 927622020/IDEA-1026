from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import (
    InventoryBalance,
    InventoryTransaction,
    Location,
    Product,
    SalesRecord,
    Tenant,
)
from app.schemas.sales import SalesCreate
from app.services.sales_service import checkout_sale


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


def make_checkout_context(db, on_hand="100", reserved="0"):
    tenant = Tenant(name="Checkout Tenant", code="CHECKOUT-001")
    db.add(tenant)
    db.flush()

    product = Product(
        tenant_id=tenant.id,
        sku_code="CHECKOUT-SKU-001",
        product_name="Demo Product",
        brand="Demo Brand",
        category="Beverages",
        unit_of_measure="PCS",
    )

    location = Location(
        tenant_id=tenant.id,
        location_code="CHECKOUT-WH-001",
        location_name="Checkout Warehouse",
        location_type="WAREHOUSE",
    )

    db.add_all([product, location])
    db.flush()

    balance = InventoryBalance(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
        on_hand=Decimal(on_hand),
        reserved=Decimal(reserved),
        inbound=Decimal(0),
        version=1,
    )
    db.add(balance)
    db.commit()

    return tenant, product, location, balance


def make_payload(location, product, quantity="5", key="CHECKOUT-001"):
    return SalesCreate(
        location_id=location.id,
        product_id=product.id,
        quantity=Decimal(quantity),
        idempotency_key=key,
        external_reference="TEST-ORDER-001",
    )


def get_balance(db, tenant, location, product):
    return db.scalar(
        select(InventoryBalance).where(
            InventoryBalance.tenant_id == tenant.id,
            InventoryBalance.location_id == location.id,
            InventoryBalance.product_id == product.id,
        )
    )


def test_checkout_deducts_stock_and_creates_sale_transaction(db):
    tenant, product, location, _ = make_checkout_context(
        db, on_hand="100", reserved="20"
    )
    payload = make_payload(location, product, quantity="5")

    sale = checkout_sale(db, tenant.id, payload)

    balance = get_balance(db, tenant, location, product)
    transaction = db.scalar(
        select(InventoryTransaction).where(
            InventoryTransaction.tenant_id == tenant.id,
            InventoryTransaction.product_id == product.id,
        )
    )

    assert sale.quantity == Decimal("5.000")
    assert balance.on_hand == Decimal("95.000")
    assert balance.reserved == Decimal("20.000")
    assert balance.available == Decimal("75.000")
    assert balance.version == 2

    assert transaction is not None
    assert transaction.transaction_type == "SALE"
    assert transaction.quantity == Decimal("5.000")


def test_duplicate_checkout_does_not_deduct_stock_twice(db):
    tenant, product, location, _ = make_checkout_context(db)
    payload = make_payload(
        location, product, quantity="5", key="DUPLICATE-CHECKOUT-001"
    )

    first_sale = checkout_sale(db, tenant.id, payload)
    second_sale = checkout_sale(db, tenant.id, payload)

    balance = get_balance(db, tenant, location, product)
    sales = db.scalars(
        select(SalesRecord).where(
            SalesRecord.tenant_id == tenant.id,
            SalesRecord.idempotency_key == payload.idempotency_key,
        )
    ).all()
    transactions = db.scalars(
        select(InventoryTransaction).where(
            InventoryTransaction.tenant_id == tenant.id,
            InventoryTransaction.transaction_type == "SALE",
        )
    ).all()

    assert first_sale.id == second_sale.id
    assert balance.on_hand == Decimal("95.000")
    assert len(sales) == 1
    assert len(transactions) == 1


def test_checkout_rejects_insufficient_available_stock(db):
    tenant, product, location, _ = make_checkout_context(
        db, on_hand="10", reserved="4"
    )
    payload = make_payload(location, product, quantity="7")

    with pytest.raises(HTTPException) as error:
        checkout_sale(db, tenant.id, payload)

    assert error.value.status_code == 409

    balance = get_balance(db, tenant, location, product)
    assert balance.on_hand == Decimal("10.000")
    assert balance.reserved == Decimal("4.000")
    assert balance.available == Decimal("6.000")

    assert db.scalar(select(SalesRecord)) is None
    assert db.scalar(select(InventoryTransaction)) is None


def test_checkout_cannot_consume_reserved_stock(db):
    tenant, product, location, _ = make_checkout_context(
        db, on_hand="10", reserved="8"
    )
    payload = make_payload(location, product, quantity="3")

    with pytest.raises(HTTPException) as error:
        checkout_sale(db, tenant.id, payload)

    assert error.value.status_code == 409

    balance = get_balance(db, tenant, location, product)
    assert balance.on_hand == Decimal("10.000")
    assert balance.reserved == Decimal("8.000")
    assert balance.available == Decimal("2.000")


def test_checkout_rejects_missing_inventory_balance(db):
    tenant, product, location, balance = make_checkout_context(db)
    db.delete(balance)
    db.commit()

    payload = make_payload(location, product, quantity="1")

    with pytest.raises(HTTPException) as error:
        checkout_sale(db, tenant.id, payload)

    assert error.value.status_code == 409
    assert db.scalar(select(SalesRecord)) is None
    assert db.scalar(select(InventoryTransaction)) is None
