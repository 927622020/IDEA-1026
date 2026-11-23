from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product, Tenant
from app.schemas.product import ProductCreate, ProductUpdate


def require_active_tenant(db: Session, tenant_id: UUID) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active.is_(True)))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Active tenant not found")
    return tenant


def create_product(db: Session, tenant_id: UUID, payload: ProductCreate) -> Product:
    require_active_tenant(db, tenant_id)
    product = Product(tenant_id=tenant_id, **payload.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # The tenant/SKU unique constraint is the authoritative concurrency-safe check.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this SKU already exists for this tenant",
        ) from exc
    db.refresh(product)
    return product


def list_products(
    db: Session, tenant_id: UUID, *, search: str | None, active_only: bool, limit: int, offset: int
) -> tuple[list[Product], int]:
    require_active_tenant(db, tenant_id)
    filters = [Product.tenant_id == tenant_id]
    if active_only:
        filters.append(Product.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            (Product.sku_code.ilike(term))
            | (Product.product_name.ilike(term))
            | (Product.brand.ilike(term))
        )
    total = db.scalar(select(func.count()).select_from(Product).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Product)
            .where(*filters)
            .order_by(Product.product_name.asc(), Product.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return items, total


def get_product(db: Session, tenant_id: UUID, product_id: UUID) -> Product:
    require_active_tenant(db, tenant_id)
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def update_product(
    db: Session, tenant_id: UUID, product_id: UUID, payload: ProductUpdate
) -> Product:
    product = get_product(db, tenant_id, product_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


def deactivate_product(db: Session, tenant_id: UUID, product_id: UUID) -> Product:
    product = get_product(db, tenant_id, product_id)
    product.is_active = False
    db.commit()
    db.refresh(product)
    return product
