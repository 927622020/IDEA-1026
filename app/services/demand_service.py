
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Location, Product, SalesRecord
from app.services.product_service import require_active_tenant


def _local_midnight_utc(day: date, timezone_name: str) -> datetime:
    """Convert a local calendar day's midnight to UTC."""
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Location has an invalid timezone configuration",
        ) from exc

    return datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)


def get_daily_demand(
    db: Session,
    tenant_id: UUID,
    *,
    location_id: UUID,
    product_id: UUID,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Return daily sales demand, including dates with zero sales."""

    require_active_tenant(db, tenant_id)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must be earlier than or equal to end_date",
        )

    location = db.scalar(
        select(Location).where(
            Location.id == location_id,
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
            Product.id == product_id,
            Product.tenant_id == tenant_id,
            Product.is_active.is_(True),
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active product not found for this tenant",
        )

    # Local midnight at the beginning of start_date.
    start_utc = _local_midnight_utc(start_date, location.timezone)

    # Local midnight after end_date: exclusive upper boundary.
    end_utc = _local_midnight_utc(
        end_date + timedelta(days=1),
        location.timezone,
    )


    # Fetch matching individual records to assign each sale to its
    # correct local calendar day.
    sales = db.scalars(
        select(SalesRecord).where(
            SalesRecord.tenant_id == tenant_id,
            SalesRecord.location_id == location_id,
            SalesRecord.product_id == product_id,
            SalesRecord.sold_at >= start_utc,
            SalesRecord.sold_at < end_utc,
        )
    ).all()

    tz = ZoneInfo(location.timezone)
    local_totals: dict[date, dict] = {}

    for sale in sales:
        sold_at = sale.sold_at

        # SQLite may return naive datetimes; PostgreSQL timezone-aware
        # timestamps are normalized to UTC before local conversion.
        if sold_at.tzinfo is None or sold_at.utcoffset() is None:
            sold_at = sold_at.replace(tzinfo=UTC)

        local_day = sold_at.astimezone(tz).date()

        if local_day not in local_totals:
            local_totals[local_day] = {
                "quantity_sold": Decimal(0),
                "transaction_count": 0,
            }

        local_totals[local_day]["quantity_sold"] += sale.quantity
        local_totals[local_day]["transaction_count"] += 1

    results = []
    current_day = start_date

    while current_day <= end_date:
        totals = local_totals.get(
            current_day,
            {
                "quantity_sold": Decimal(0),
                "transaction_count": 0,
            },
        )

        results.append(
            {
                "date": current_day,
                "tenant_id": tenant_id,
                "location_id": location_id,
                "product_id": product_id,
                "quantity_sold": totals["quantity_sold"],
                "transaction_count": totals["transaction_count"],
            }
        )

        current_day += timedelta(days=1)

    return results
