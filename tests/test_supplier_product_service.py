
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import Supplier, Tenant
from app.schemas.product import ProductCreate
from app.schemas.supplier_product import SupplierProductCreate
from app.services.product_service import create_product
from app.services.supplier_product_service import (
    create_supplier_product,
    list_supplier_products,
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


def make_tenant(db, code: str) -> Tenant:
    tenant = Tenant(name=f"Tenant {code}", code=code)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def make_supplier(db, tenant_id, code: str) -> Supplier:
    supplier = Supplier(
        tenant_id=tenant_id,
        supplier_code=code,
        supplier_name=f"Supplier {code}",
        default_lead_time_days=7,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def make_product(db, tenant_id, sku: str):
    return create_product(
        db,
        tenant_id,
        ProductCreate(
            sku_code=sku,
            product_name="Mango Drink 200ml",
            brand="Demo Foods",
            category="Beverages",
            unit_of_measure="PCS",
        ),
    )


def make_payload(supplier_id, product_id, preferred=False):
    return SupplierProductCreate(
        supplier_id=supplier_id,
        product_id=product_id,
        supplier_sku="SUP-SKU-001",
        unit_cost=Decimal("12.5000"),
        currency="BDT",
        lead_time_days=5,
        minimum_order_quantity=Decimal(10),
        pack_size=Decimal(5),
        is_preferred=preferred,
    )


def test_create_supplier_product(db):
    tenant = make_tenant(db, "TENANT-A")
    supplier = make_supplier(db, tenant.id, "SUP-A")
    product = make_product(db, tenant.id, "SKU-001")

    item = create_supplier_product(
        db,
        tenant.id,
        make_payload(supplier.id, product.id),
    )

    assert item.tenant_id == tenant.id
    assert item.supplier_id == supplier.id
    assert item.product_id == product.id
    assert item.currency == "BDT"
    assert item.is_active is True
    assert item.is_preferred is False


def test_duplicate_supplier_product_returns_conflict(db):
    tenant = make_tenant(db, "TENANT-B")
    supplier = make_supplier(db, tenant.id, "SUP-B")
    product = make_product(db, tenant.id, "SKU-002")
    payload = make_payload(supplier.id, product.id)

    create_supplier_product(db, tenant.id, payload)

    with pytest.raises(HTTPException) as error:
        create_supplier_product(db, tenant.id, payload)

    assert error.value.status_code == 409


def test_cross_tenant_supplier_is_rejected(db):
    tenant_a = make_tenant(db, "TENANT-C")
    tenant_b = make_tenant(db, "TENANT-D")

    supplier_b = make_supplier(db, tenant_b.id, "SUP-D")
    product_a = make_product(db, tenant_a.id, "SKU-003")

    with pytest.raises(HTTPException) as error:
        create_supplier_product(
            db,
            tenant_a.id,
            make_payload(supplier_b.id, product_a.id),
        )

    assert error.value.status_code == 404


def test_preferred_supplier_replaces_previous_preferred(db):
    tenant = make_tenant(db, "TENANT-E")
    supplier_a = make_supplier(db, tenant.id, "SUP-E1")
    supplier_b = make_supplier(db, tenant.id, "SUP-E2")
    product = make_product(db, tenant.id, "SKU-004")

    first = create_supplier_product(
        db,
        tenant.id,
        make_payload(supplier_a.id, product.id, preferred=True),
    )

    second = create_supplier_product(
        db,
        tenant.id,
        make_payload(supplier_b.id, product.id, preferred=True),
    )

    db.refresh(first)
    db.refresh(second)

    assert first.is_preferred is False
    assert second.is_preferred is True


def test_list_supplier_products_is_tenant_scoped(db):
    tenant_a = make_tenant(db, "TENANT-F")
    tenant_b = make_tenant(db, "TENANT-G")

    supplier = make_supplier(db, tenant_a.id, "SUP-F")
    product = make_product(db, tenant_a.id, "SKU-005")

    create_supplier_product(
        db,
        tenant_a.id,
        make_payload(supplier.id, product.id),
    )

    result = list_supplier_products(db, tenant_b.id)

    assert result["total"] == 0
    assert result["items"] == []
