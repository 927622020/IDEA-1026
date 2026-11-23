from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Supplier, Tenant
from app.schemas.supplier import SupplierCreate, SupplierUpdate


def require_active_tenant(db: Session, tenant_id: UUID) -> Tenant:
    tenant = db.scalar(
        select(Tenant).where(
            Tenant.id == tenant_id,
            Tenant.is_active.is_(True),
        )
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Active tenant not found")
    return tenant


def create_supplier(
    db: Session,
    tenant_id: UUID,
    payload: SupplierCreate,
) -> Supplier:
    require_active_tenant(db, tenant_id)

    supplier = Supplier(
        tenant_id=tenant_id,
        **payload.model_dump(),
    )
    db.add(supplier)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A supplier with this code already exists for this tenant",
        ) from exc

    db.refresh(supplier)
    return supplier


def list_suppliers(
    db: Session,
    tenant_id: UUID,
    *,
    search: str | None,
    active_only: bool,
    limit: int,
    offset: int,
) -> tuple[list[Supplier], int]:
    require_active_tenant(db, tenant_id)

    filters = [Supplier.tenant_id == tenant_id]

    if active_only:
        filters.append(Supplier.is_active.is_(True))

    if search:
        term = f"%{search.strip()}%"
        filters.append(
            Supplier.supplier_code.ilike(term)
            | Supplier.supplier_name.ilike(term)
        )

    total = db.scalar(
        select(func.count()).select_from(Supplier).where(*filters)
    ) or 0

    items = list(
        db.scalars(
            select(Supplier)
            .where(*filters)
            .order_by(Supplier.supplier_name.asc(), Supplier.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )

    return items, total


def get_supplier(
    db: Session,
    tenant_id: UUID,
    supplier_id: UUID,
) -> Supplier:
    require_active_tenant(db, tenant_id)

    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.tenant_id == tenant_id,
        )
    )

    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    return supplier


def update_supplier(
    db: Session,
    tenant_id: UUID,
    supplier_id: UUID,
    payload: SupplierUpdate,
) -> Supplier:
    supplier = get_supplier(db, tenant_id, supplier_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)

    db.commit()
    db.refresh(supplier)
    return supplier


def deactivate_supplier(
    db: Session,
    tenant_id: UUID,
    supplier_id: UUID,
) -> Supplier:
    supplier = get_supplier(db, tenant_id, supplier_id)
    supplier.is_active = False
    db.commit()
    db.refresh(supplier)
    return supplier
