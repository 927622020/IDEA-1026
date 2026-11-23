
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import Tenant
from app.schemas.product import ProductCreate
from app.services.product_service import create_product, get_product


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
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


def product_payload(sku="SKU-001"):
    return ProductCreate(
        sku_code=sku,
        product_name="Sunflower Oil 1L",
        brand="Demo Foods",
        category="Cooking Oil",
        unit_of_measure="PCS",
    )


def test_same_sku_allowed_for_different_tenants(db):
    tenant_a = make_tenant(db, "TENANT-A")
    tenant_b = make_tenant(db, "TENANT-B")
    product_a = create_product(db, tenant_a.id, product_payload())
    product_b = create_product(db, tenant_b.id, product_payload())
    assert product_a.id != product_b.id


def test_cross_tenant_product_lookup_is_not_found(db):
    tenant_a = make_tenant(db, "TENANT-A")
    tenant_b = make_tenant(db, "TENANT-B")
    product = create_product(db, tenant_a.id, product_payload())
    with pytest.raises(HTTPException) as error:
        get_product(db, tenant_b.id, product.id)
    assert error.value.status_code == 404
