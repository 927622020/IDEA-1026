from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    InventoryBalance,
    InventoryTransaction,
    Location,
    Product,
)
from app.schemas.inventory import InventoryOperationCreate
from app.services.product_service import require_active_tenant


def _find_existing_transaction(
    db: Session, tenant_id: UUID, key: str
) -> InventoryTransaction | None:
    return db.scalar(
        select(InventoryTransaction).where(
            InventoryTransaction.tenant_id == tenant_id,
            InventoryTransaction.idempotency_key == key,
        )
    )


def _validate_duplicate(
    existing: InventoryTransaction,
    payload: InventoryOperationCreate,
    transaction_type: str,
) -> None:
    same_request = (
        existing.transaction_type == transaction_type
        and existing.location_id == payload.location_id
        and existing.product_id == payload.product_id
        and existing.quantity == payload.quantity
        and existing.reference == payload.reference
        and existing.notes == payload.notes
    )

    if not same_request:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was already used for a different request",
        )

def _get_balance(
    db: Session,
    tenant_id: UUID,
    location_id: UUID,
    product_id: UUID,
) -> InventoryBalance:
    # Create the balance row if it does not exist.
    # The unique constraint makes this safe under concurrent requests.
    now = datetime.now(UTC)

    values = {
        "tenant_id": tenant_id,
        "location_id": location_id,
        "product_id": product_id,
        "on_hand": Decimal(0),
        "reserved": Decimal(0),
        "inbound": Decimal(0),
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }

    dialect_name = db.get_bind().dialect.name

    if dialect_name == "postgresql":
        statement = pg_insert(InventoryBalance).values(**values)
    elif dialect_name == "sqlite":
        statement = sqlite_insert(InventoryBalance).values(**values)
    else:
        raise RuntimeError(
            f"Unsupported database dialect: {dialect_name}"
        )

    statement = statement.on_conflict_do_nothing(
        index_elements=["tenant_id", "location_id", "product_id"]
    )

    db.execute(statement)

    # Lock the row until this transaction commits or rolls back.
    balance = db.scalar(
        select(InventoryBalance)
        .where(
            InventoryBalance.tenant_id == tenant_id,
            InventoryBalance.location_id == location_id,
            InventoryBalance.product_id == product_id,
        )
        .with_for_update()
    )

    if balance is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to create or retrieve inventory balance",
        )

    return balance

def _get_existing_result(
    db: Session,
    tenant_id: UUID,
    existing: InventoryTransaction,
    payload: InventoryOperationCreate,
    transaction_type: str,
) -> dict:
    _validate_duplicate(existing, payload, transaction_type)

    balance = db.scalar(
        select(InventoryBalance).where(
            InventoryBalance.tenant_id == tenant_id,
            InventoryBalance.location_id == existing.location_id,
            InventoryBalance.product_id == existing.product_id,
        )
    )

    if balance is None:
        raise HTTPException(
            status_code=404,
            detail="Inventory balance not found",
        )

    return {"balance": balance, "transaction": existing}


def apply_inventory_operation(
    db: Session,
    tenant_id: UUID,
    payload: InventoryOperationCreate,
    transaction_type: str,
) -> dict:
    allowed_types = {
        "RECEIVE",
        "ADJUST_INCREASE",
        "ADJUST_DECREASE",
        "RESERVE",
        "RELEASE",
    }

    if transaction_type not in allowed_types:
        raise ValueError("Unsupported inventory transaction type")

    require_active_tenant(db, tenant_id)

    # Check idempotency before performing any stock changes.
    existing = _find_existing_transaction(
        db, tenant_id, payload.idempotency_key
    )

    if existing is not None:
        return _get_existing_result(
            db, tenant_id, existing, payload, transaction_type
        )

    # Validate that both records belong to this tenant.
    location = db.scalar(
        select(Location).where(
            Location.id == payload.location_id,
            Location.tenant_id == tenant_id,
            Location.is_active.is_(True),
        )
    )

    if location is None:
        raise HTTPException(
            status_code=404,
            detail="Active location not found",
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
            status_code=404,
            detail="Active product not found",
        )

    try:
        balance = _get_balance(
            db,
            tenant_id,
            payload.location_id,
            payload.product_id,
        )

        quantity = payload.quantity

        if transaction_type in {"RECEIVE", "ADJUST_INCREASE"}:
            balance.on_hand += quantity

        elif transaction_type == "ADJUST_DECREASE":
            if balance.available < quantity:
                raise HTTPException(
                    status_code=409,
                    detail="Insufficient available stock for adjustment",
                )
            balance.on_hand -= quantity

        elif transaction_type == "RESERVE":
            if balance.available < quantity:
                raise HTTPException(
                    status_code=409,
                    detail="Insufficient available stock to reserve",
                )
            balance.reserved += quantity

        elif transaction_type == "RELEASE":
            if balance.reserved < quantity:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot release more stock than currently reserved",
                )
            balance.reserved -= quantity

        balance.version += 1
        balance.updated_at = datetime.now(UTC)

        transaction = InventoryTransaction(
            tenant_id=tenant_id,
            location_id=payload.location_id,
            product_id=payload.product_id,
            transaction_type=transaction_type,
            quantity=quantity,
            reference=payload.reference,
            idempotency_key=payload.idempotency_key,
            notes=payload.notes,
        )

        db.add(transaction)
        db.commit()

        db.refresh(balance)
        db.refresh(transaction)

        return {"balance": balance, "transaction": transaction}

    except IntegrityError as exc:
        db.rollback()

        # A concurrent request may have committed the same key.
        existing = _find_existing_transaction(
            db, tenant_id, payload.idempotency_key
        )

        if existing is not None:
            return _get_existing_result(
                db, tenant_id, existing, payload, transaction_type
            )

        raise HTTPException(
            status_code=409,
            detail="Inventory operation conflicts with an existing database record",
        ) from exc

    except Exception:
        db.rollback()
        raise


def list_inventory(
    db: Session,
    tenant_id: UUID,
    *,
    location_id: UUID | None,
    product_id: UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[InventoryBalance], int]:
    require_active_tenant(db, tenant_id)

    filters = [InventoryBalance.tenant_id == tenant_id]

    if location_id is not None:
        filters.append(InventoryBalance.location_id == location_id)

    if product_id is not None:
        filters.append(InventoryBalance.product_id == product_id)



    total = db.scalar(
        select(func.count())
        .select_from(InventoryBalance)
        .where(*filters)
    ) or 0

    items = list(
        db.scalars(
            select(InventoryBalance)
            .where(*filters)
            .order_by(InventoryBalance.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )

    return items, total
