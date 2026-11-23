
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
    Tenant,
)
from app.schemas.inventory import InventoryOperationCreate
from app.services.inventory_service import (
    apply_inventory_operation,
    list_inventory,
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


def make_inventory_context(db, code="TENANT-A"):
    tenant = Tenant(
        name=f"Tenant {code}",
        code=code,
    )
    db.add(tenant)
    db.flush()

    product = Product(
        tenant_id=tenant.id,
        sku_code="SKU-001",
        product_name="Sunflower Oil 1L",
        brand="Demo Foods",
        category="Cooking Oil",
        unit_of_measure="PCS",
    )

    location = Location(
        tenant_id=tenant.id,
        location_code="WH-001",
        location_name="Main Warehouse",
        location_type="WAREHOUSE",
    )

    db.add_all([product, location])
    db.commit()

    return tenant, product, location


def make_payload(location, product, quantity, key):
    return InventoryOperationCreate(
        location_id=location.id,
        product_id=product.id,
        quantity=Decimal(str(quantity)),
        idempotency_key=key,
        reference="TEST-ORDER-001",
        notes="Automated inventory test",
    )


def receive_stock(db, tenant, location, product, quantity="100"):
    payload = make_payload(
        location,
        product,
        quantity,
        "RECEIVE-001",
    )
    return apply_inventory_operation(
        db,
        tenant.id,
        payload,
        "RECEIVE",
    )


def test_receive_stock_creates_inventory_balance(db):
    tenant, product, location = make_inventory_context(db)

    result = receive_stock(db, tenant, location, product)

    balance = result["balance"]
    transaction = result["transaction"]

    assert balance.on_hand == Decimal("100.000")
    assert balance.reserved == Decimal("0.000")
    assert balance.available == Decimal("100.000")
    assert balance.version == 2

    assert transaction.transaction_type == "RECEIVE"
    assert transaction.quantity == Decimal(100)


def test_reserve_stock_reduces_available_quantity(db):
    tenant, product, location = make_inventory_context(db)

    receive_stock(db, tenant, location, product)

    payload = make_payload(
        location,
        product,
        "20",
        "RESERVE-001",
    )

    result = apply_inventory_operation(
        db,
        tenant.id,
        payload,
        "RESERVE",
    )

    balance = result["balance"]

    assert balance.on_hand == Decimal("100.000")
    assert balance.reserved == Decimal("20.000")
    assert balance.available == Decimal("80.000")
    assert balance.version == 3


def test_release_reserved_stock(db):
    tenant, product, location = make_inventory_context(db)

    receive_stock(db, tenant, location, product)

    reserve_payload = make_payload(
        location,
        product,
        "20",
        "RESERVE-001",
    )

    apply_inventory_operation(
        db,
        tenant.id,
        reserve_payload,
        "RESERVE",
    )

    release_payload = make_payload(
        location,
        product,
        "5",
        "RELEASE-001",
    )

    result = apply_inventory_operation(
        db,
        tenant.id,
        release_payload,
        "RELEASE",
    )

    balance = result["balance"]

    assert balance.on_hand == Decimal("100.000")
    assert balance.reserved == Decimal("15.000")
    assert balance.available == Decimal("85.000")
    assert balance.version == 4


def test_insufficient_stock_is_rejected_without_changing_balance(db):
    tenant, product, location = make_inventory_context(db)

    receive_stock(db, tenant, location, product)

    payload = make_payload(
        location,
        product,
        "101",
        "RESERVE-TOO-MUCH",
    )

    with pytest.raises(HTTPException) as error:
        apply_inventory_operation(
            db,
            tenant.id,
            payload,
            "RESERVE",
        )

    assert error.value.status_code == 409

    balance = db.scalar(
        select(InventoryBalance).where(
            InventoryBalance.tenant_id == tenant.id,
            InventoryBalance.location_id == location.id,
            InventoryBalance.product_id == product.id,
        )
    )

    assert balance is not None
    assert balance.on_hand == Decimal("100.000")
    assert balance.reserved == Decimal("0.000")
    assert balance.version == 2


def test_same_idempotency_key_does_not_duplicate_stock(db):
    tenant, product, location = make_inventory_context(db)

    payload = make_payload(
        location,
        product,
        "100",
        "IDEMPOTENT-RECEIVE-001",
    )

    first = apply_inventory_operation(
        db,
        tenant.id,
        payload,
        "RECEIVE",
    )

    second = apply_inventory_operation(
        db,
        tenant.id,
        payload,
        "RECEIVE",
    )

    assert first["transaction"].id == second["transaction"].id
    assert second["balance"].on_hand == Decimal("100.000")
    assert second["balance"].version == 2

    transactions = db.scalars(
        select(InventoryTransaction).where(
            InventoryTransaction.tenant_id == tenant.id,
        )
    ).all()

    assert len(transactions) == 1


def test_reusing_idempotency_key_with_different_request_is_rejected(db):
    tenant, product, location = make_inventory_context(db)

    original_payload = make_payload(
        location,
        product,
        "100",
        "DUPLICATE-KEY-001",
    )

    apply_inventory_operation(
        db,
        tenant.id,
        original_payload,
        "RECEIVE",
    )

    different_payload = make_payload(
        location,
        product,
        "200",
        "DUPLICATE-KEY-001",
    )

    with pytest.raises(HTTPException) as error:
        apply_inventory_operation(
            db,
            tenant.id,
            different_payload,
            "RECEIVE",
        )

    assert error.value.status_code == 409

    balance = db.scalar(
        select(InventoryBalance).where(
            InventoryBalance.tenant_id == tenant.id,
            InventoryBalance.location_id == location.id,
            InventoryBalance.product_id == product.id,
        )
    )

    assert balance.on_hand == Decimal("100.000")
    assert balance.version == 2


def test_cross_tenant_inventory_operation_is_rejected(db):
    _tenant_a, product_a, location_a = make_inventory_context(
        db,
        "TENANT-A",
    )

    tenant_b, _, _ = make_inventory_context(
        db,
        "TENANT-B",
    )

    payload = make_payload(
        location_a,
        product_a,
        "10",
        "CROSS-TENANT-001",
    )

    with pytest.raises(HTTPException) as error:
        apply_inventory_operation(
            db,
            tenant_b.id,
            payload,
            "RECEIVE",
        )

    assert error.value.status_code == 404

    transactions = db.scalars(
        select(InventoryTransaction)
    ).all()

    assert len(transactions) == 0


def test_list_inventory_returns_tenant_inventory(db):
    tenant, product, location = make_inventory_context(db)

    receive_stock(db, tenant, location, product)

    items, total = list_inventory(
        db,
        tenant.id,
        location_id=location.id,
        product_id=product.id,
        limit=20,
        offset=0,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].on_hand == Decimal("100.000")
    assert items[0].available == Decimal("100.000")
