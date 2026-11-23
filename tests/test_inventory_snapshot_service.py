from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import InventoryBalance, Location, Product, Tenant
from app.models.inventory_snapshot import InventorySnapshot
from app.services.inventory_snapshot_service import (
    capture_inventory_snapshots,
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


def make_snapshot_context(db, on_hand="100", reserved="15"):
    tenant = Tenant(
        name="Snapshot Tenant",
        code="SNAPSHOT-001",
    )
    db.add(tenant)
    db.flush()

    product = Product(
        tenant_id=tenant.id,
        sku_code="SNAPSHOT-SKU-001",
        product_name="Snapshot Demo Product",
        brand="Demo Brand",
        category="Beverages",
        unit_of_measure="PCS",
    )

    location = Location(
        tenant_id=tenant.id,
        location_code="SNAPSHOT-WH-001",
        location_name="Snapshot Warehouse",
        location_type="WAREHOUSE",
        timezone="Asia/Dhaka",
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


def test_capture_creates_inventory_snapshot(db):
    tenant, product, location, _ = make_snapshot_context(db)

    result = capture_inventory_snapshots(
        db,
        tenant.id,
        location.id,
    )

    snapshot = db.scalar(
        select(InventorySnapshot).where(
            InventorySnapshot.tenant_id == tenant.id,
            InventorySnapshot.location_id == location.id,
            InventorySnapshot.product_id == product.id,
        )
    )

    assert result["created"] == 1
    assert result["skipped"] == 0
    assert result["total"] == 1

    assert snapshot is not None
    assert snapshot.on_hand == Decimal("100.000")
    assert snapshot.reserved == Decimal("15.000")
    assert snapshot.available == Decimal("85.000")
    assert snapshot.inbound == Decimal("0.000")
    assert snapshot.is_stockout is False

    captured_at = datetime.fromisoformat(result["captured_at"])
    expected_date = captured_at.astimezone(
        ZoneInfo("Asia/Dhaka")
    ).date()

    assert snapshot.snapshot_date == expected_date


def test_duplicate_capture_skips_existing_snapshot(db):
    tenant, _, location, _ = make_snapshot_context(db)

    first_result = capture_inventory_snapshots(
        db,
        tenant.id,
        location.id,
    )
    second_result = capture_inventory_snapshots(
        db,
        tenant.id,
        location.id,
    )

    snapshots = db.scalars(
        select(InventorySnapshot).where(
            InventorySnapshot.tenant_id == tenant.id,
            InventorySnapshot.location_id == location.id,
        )
    ).all()

    assert first_result["created"] == 1
    assert second_result["created"] == 0
    assert second_result["skipped"] == 1
    assert len(snapshots) == 1


def test_capture_marks_zero_available_stock_as_stockout(db):
    tenant, product, location, _ = make_snapshot_context(
        db,
        on_hand="10",
        reserved="10",
    )

    result = capture_inventory_snapshots(
        db,
        tenant.id,
        location.id,
    )

    snapshot = db.scalar(
        select(InventorySnapshot).where(
            InventorySnapshot.tenant_id == tenant.id,
            InventorySnapshot.product_id == product.id,
        )
    )

    assert result["created"] == 1
    assert snapshot is not None
    assert snapshot.on_hand == Decimal("10.000")
    assert snapshot.reserved == Decimal("10.000")
    assert snapshot.available == Decimal("0.000")
    assert snapshot.is_stockout is True


def test_capture_rejects_inactive_tenant(db):
    tenant, _, location, _ = make_snapshot_context(db)

    tenant.is_active = False
    db.commit()

    with pytest.raises(
        ValueError,
        match="Tenant not found or inactive",
    ):
        capture_inventory_snapshots(
            db,
            tenant.id,
            location.id,
        )

    assert db.scalar(select(InventorySnapshot)) is None
