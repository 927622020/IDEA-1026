from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.inventory import InventoryBalance
from app.models.inventory_snapshot import InventorySnapshot
from app.models.location import Location
from app.models.product import Product
from app.models.tenant import Tenant


def capture_inventory_snapshots(
    db: Session,
    tenant_id: UUID,
    location_id: UUID | None = None,
) -> dict[str, Any]:
    """Capture current inventory balances once per location-local calendar day."""
    tenant = db.scalar(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    if tenant is None or not tenant.is_active:
        raise ValueError("Tenant not found or inactive")

    statement = (
        select(InventoryBalance, Location, Product)
        .join(
            Location,
            (Location.id == InventoryBalance.location_id)
            & (Location.tenant_id == InventoryBalance.tenant_id),
        )
        .join(
            Product,
            (Product.id == InventoryBalance.product_id)
            & (Product.tenant_id == InventoryBalance.tenant_id),
        )
        .where(
            InventoryBalance.tenant_id == tenant_id,
            Location.is_active.is_(True),
            Product.is_active.is_(True),
        )
        .order_by(
            InventoryBalance.location_id,
            InventoryBalance.product_id,
        )
    )

    if location_id is not None:
        statement = statement.where(
            InventoryBalance.location_id == location_id
        )

    rows = db.execute(statement).all()
    captured_at = datetime.now(UTC)

    created = 0
    skipped = 0

    try:
        for balance, location, product in rows:
            try:
                local_date = captured_at.astimezone(
                    ZoneInfo(location.timezone)
                ).date()
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError(
                    f"Invalid timezone for location {location.id}: "
                    f"{location.timezone}"
                ) from exc

            available = balance.on_hand - balance.reserved

            snapshot_values = {
                "tenant_id": tenant_id,
                "location_id": location.id,
                "product_id": product.id,
                "snapshot_date": local_date,
                "captured_at": captured_at,
                "on_hand": balance.on_hand,
                "reserved": balance.reserved,
                "available": available,
                "inbound": balance.inbound,
                "is_stockout": available == 0,
            }

            if db.get_bind().dialect.name == "sqlite":
                statement = (
                    sqlite_insert(InventorySnapshot)
                    .values(**snapshot_values)
                    .on_conflict_do_nothing(
                        index_elements=[
                            "tenant_id",
                            "location_id",
                            "product_id",
                            "snapshot_date",
                        ]
                    )
                    .returning(InventorySnapshot.id)
                )
            else:
                statement = (
                    pg_insert(InventorySnapshot)
                    .values(**snapshot_values)
                    .on_conflict_do_nothing(
                        constraint="uq_inventory_snapshot_daily"
                    )
                    .returning(InventorySnapshot.id)
                )

            inserted_id = db.execute(statement).scalar_one_or_none()

            if inserted_id is None:
                skipped += 1
            else:
                created += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "tenant_id": str(tenant_id),
        "captured_at": captured_at.isoformat(),
        "created": created,
        "skipped": skipped,
        "total": len(rows),
    }
