import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    InventoryBalance,
    InventoryTransaction,
    Location,
    Product,
    SalesRecord,
)
from app.schemas.sales import SalesCreate
from app.services.product_service import require_active_tenant


def _normalize_datetime(value: datetime) -> datetime:
    """Normalize aware or database-returned naive timestamps to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _find_existing_sale(
    db: Session, tenant_id: UUID, idempotency_key: str
) -> SalesRecord | None:
    return db.scalar(
        select(SalesRecord).where(
            SalesRecord.tenant_id == tenant_id,
            SalesRecord.idempotency_key == idempotency_key,
        )
    )


def _validate_duplicate(
    existing: SalesRecord, payload: SalesCreate
) -> SalesRecord:
    same_request = (
        existing.location_id == payload.location_id
        and existing.product_id == payload.product_id
        and existing.quantity == payload.quantity
        and _normalize_datetime(existing.sold_at)
        == _normalize_datetime(payload.sold_at)
        and existing.external_reference == payload.external_reference
    )

    if not same_request:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was already used for a different sale",
        )

    return existing


def create_sale(
    db: Session, tenant_id: UUID, payload: SalesCreate
) -> SalesRecord:
    require_active_tenant(db, tenant_id)

    existing = _find_existing_sale(
        db, tenant_id, payload.idempotency_key
    )
    if existing is not None:
        return _validate_duplicate(existing, payload)

    location = db.scalar(
        select(Location).where(
            Location.id == payload.location_id,
            Location.tenant_id == tenant_id,
            Location.is_active.is_(True),
        )
    )
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active location not found for this tenant",
        )

    product = db.scalar(
        select(Product).where(
            Product.id == payload.product_id,
            Product.tenant_id == tenant_id,
            Product.is_active.is_(True),
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active product not found for this tenant",
        )

    sale_data = payload.model_dump()
    sale_data['sold_at'] = _normalize_datetime(payload.sold_at)

    sale = SalesRecord(
        tenant_id=tenant_id,
        **sale_data,
    )
    db.add(sale)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        # Another request may have inserted the same key concurrently.
        existing = _find_existing_sale(
            db, tenant_id, payload.idempotency_key
        )
        if existing is not None:
            return _validate_duplicate(existing, payload)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create sale because of a database conflict",
        ) from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(sale)
    return sale


def list_sales(
    db: Session,
    tenant_id: UUID,
    *,
    product_id: UUID | None,
    location_id: UUID | None,
    sold_from: datetime | None,
    sold_to: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[SalesRecord], int]:
    require_active_tenant(db, tenant_id)

    filters = [SalesRecord.tenant_id == tenant_id]

    if product_id is not None:
        filters.append(SalesRecord.product_id == product_id)

    if location_id is not None:
        filters.append(SalesRecord.location_id == location_id)

    if sold_from is not None:
        filters.append(SalesRecord.sold_at >= sold_from)

    if sold_to is not None:
        filters.append(SalesRecord.sold_at <= sold_to)

    total = db.scalar(
        select(func.count())
        .select_from(SalesRecord)
        .where(*filters)
    ) or 0

    items = list(
        db.scalars(
            select(SalesRecord)
            .where(*filters)
            .order_by(
                SalesRecord.sold_at.desc(),
                SalesRecord.created_at.desc(),
                SalesRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )

    return items, total


def checkout_sale(
    db: Session, tenant_id: UUID, payload: SalesCreate
) -> SalesRecord:
    """Create a live sale and deduct available inventory atomically."""
    require_active_tenant(db, tenant_id)

    existing = _find_existing_sale(
        db, tenant_id, payload.idempotency_key
    )
    if existing is not None:
        return _validate_duplicate(existing, payload)

    location = db.scalar(
        select(Location).where(
            Location.id == payload.location_id,
            Location.tenant_id == tenant_id,
            Location.is_active.is_(True),
        )
    )
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active location not found for this tenant",
        )

    product = db.scalar(
        select(Product).where(
            Product.id == payload.product_id,
            Product.tenant_id == tenant_id,
            Product.is_active.is_(True),
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active product not found for this tenant",
        )

    balance = db.scalar(
        select(InventoryBalance)
        .where(
            InventoryBalance.tenant_id == tenant_id,
            InventoryBalance.location_id == payload.location_id,
            InventoryBalance.product_id == payload.product_id,
        )
        .with_for_update()
    )

    # Recheck after locking: another checkout may have completed
    # while this request was waiting for the inventory row.
    existing = _find_existing_sale(
        db, tenant_id, payload.idempotency_key
    )
    if existing is not None:
        return _validate_duplicate(existing, payload)

    if balance is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No inventory balance exists for this product at this location",
        )

    if balance.available < payload.quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Insufficient available stock. "
                f"Available: {balance.available}, "
                f"Requested: {payload.quantity}"
            ),
        )

    sale_data = payload.model_dump()
    sale_data["sold_at"] = _normalize_datetime(payload.sold_at)

    sale = SalesRecord(tenant_id=tenant_id, **sale_data)

    try:
        db.add(sale)
        db.flush()

        balance.on_hand -= payload.quantity
        balance.version += 1

        transaction_key = "SALE-" + hashlib.sha256(
            f"{tenant_id}:{payload.idempotency_key}".encode()
        ).hexdigest()

        transaction = InventoryTransaction(
            tenant_id=tenant_id,
            location_id=payload.location_id,
            product_id=payload.product_id,
            transaction_type="SALE",
            quantity=payload.quantity,
            reference=payload.external_reference or str(sale.id),
            idempotency_key=transaction_key,
            notes="Live checkout sale",
        )

        db.add(transaction)
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        existing = _find_existing_sale(
            db, tenant_id, payload.idempotency_key
        )
        if existing is not None:
            return _validate_duplicate(existing, payload)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to complete checkout because of a database conflict",
        ) from exc

    except Exception:
        db.rollback()
        raise

    db.refresh(sale)
    return sale
