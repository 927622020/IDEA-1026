
"""Service layer for supplier-product purchasing details."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_product import SupplierProduct
from app.models.tenant import Tenant
from app.schemas.supplier_product import (
    SupplierProductCreate,
    SupplierProductUpdate,
)


def require_active_tenant(db: Session, tenant_id: UUID) -> None:
    tenant = db.scalar(
        select(Tenant).where(
            Tenant.id == tenant_id,
            Tenant.is_active.is_(True),
        )
    )
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active tenant not found.",
        )


def get_supplier_product(
    db: Session,
    tenant_id: UUID,
    supplier_product_id: UUID,
) -> SupplierProduct:
    item = db.scalar(
        select(SupplierProduct).where(
            SupplierProduct.id == supplier_product_id,
            SupplierProduct.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier-product record not found.",
        )
    return item


def validate_supplier_and_product(
    db: Session,
    tenant_id: UUID,
    supplier_id: UUID,
    product_id: UUID,
) -> None:
    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.tenant_id == tenant_id,
            Supplier.is_active.is_(True),
        )
    )
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active supplier not found for this tenant.",
        )

    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant_id,
            Product.is_active.is_(True),
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active product not found for this tenant.",
        )


def clear_other_preferred_suppliers(
    db: Session,
    tenant_id: UUID,
    product_id: UUID,
    exclude_id: UUID | None = None,
) -> None:
    query = update(SupplierProduct).where(
        SupplierProduct.tenant_id == tenant_id,
        SupplierProduct.product_id == product_id,
        SupplierProduct.is_preferred.is_(True),
        SupplierProduct.is_active.is_(True),
    )

    if exclude_id is not None:
        query = query.where(SupplierProduct.id != exclude_id)

    db.execute(query.values(is_preferred=False))


def create_supplier_product(
    db: Session,
    tenant_id: UUID,
    payload: SupplierProductCreate,
) -> SupplierProduct:
    require_active_tenant(db, tenant_id)

    validate_supplier_and_product(
        db,
        tenant_id,
        payload.supplier_id,
        payload.product_id,
    )

    try:
        if payload.is_preferred:
            clear_other_preferred_suppliers(
                db,
                tenant_id,
                payload.product_id,
            )

        item = SupplierProduct(
            tenant_id=tenant_id,
            **payload.model_dump(),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Supplier-product association already exists or conflicts with another record.",
        ) from exc


def list_supplier_products(
    db: Session,
    tenant_id: UUID,
    supplier_id: UUID | None = None,
    product_id: UUID | None = None,
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    require_active_tenant(db, tenant_id)

    query = select(SupplierProduct).where(
        SupplierProduct.tenant_id == tenant_id
    )

    if supplier_id is not None:
        query = query.where(SupplierProduct.supplier_id == supplier_id)

    if product_id is not None:
        query = query.where(SupplierProduct.product_id == product_id)

    if active_only:
        query = query.where(SupplierProduct.is_active.is_(True))

    total_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(total_query) or 0

    items = db.scalars(
        query.order_by(SupplierProduct.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def update_supplier_product(
    db: Session,
    tenant_id: UUID,
    supplier_product_id: UUID,
    payload: SupplierProductUpdate,
) -> SupplierProduct:
    require_active_tenant(db, tenant_id)

    item = get_supplier_product(db, tenant_id, supplier_product_id)
    changes = payload.model_dump(exclude_unset=True)

    changes = {
        key: value
        for key, value in changes.items()
        if value is not None or key == "supplier_sku"
    }

    if changes.get("is_active") is False:
        changes["is_preferred"] = False

    try:
        if changes.get("is_preferred") is True and item.is_active:
            clear_other_preferred_suppliers(
                db,
                tenant_id,
                item.product_id,
                exclude_id=item.id,
            )

        for key, value in changes.items():
            setattr(item, key, value)

        if not item.is_active:
            item.is_preferred = False

        db.commit()
        db.refresh(item)
        return item

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update conflicts with an existing supplier-product record.",
        ) from exc


def deactivate_supplier_product(
    db: Session,
    tenant_id: UUID,
    supplier_product_id: UUID,
) -> SupplierProduct:
    require_active_tenant(db, tenant_id)

    item = get_supplier_product(db, tenant_id, supplier_product_id)
    item.is_active = False
    item.is_preferred = False

    db.commit()
    db.refresh(item)
    return item
