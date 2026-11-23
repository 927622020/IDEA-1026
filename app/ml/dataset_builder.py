"""Build leakage-safe training datasets for stockout prediction."""

from datetime import date, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.feature_contract import (
    FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
    LOOKBACK_WINDOWS,
    PREDICTION_HORIZON_DAYS,
    TARGET_COLUMN,
)
from app.models.inventory_snapshot import InventorySnapshot
from app.models.location import Location
from app.models.sales import SalesRecord


def build_training_dataset(
    db: Session,
    tenant_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """
    Build a training dataset from historical sales and inventory snapshots.

    Features use sales from the 28 days before prediction_date.
    The target examines the next seven daily inventory snapshots.

    Rows with incomplete future snapshot coverage are excluded.
    """

    snapshot_query = (
        select(InventorySnapshot, Location.timezone)
        .join(
            Location,
            Location.id == InventorySnapshot.location_id,
        )
        .where(
            InventorySnapshot.tenant_id == tenant_id,
            Location.tenant_id == tenant_id,
            Location.is_active.is_(True),
        )
        .order_by(
            InventorySnapshot.location_id,
            InventorySnapshot.product_id,
            InventorySnapshot.snapshot_date,
        )
    )

    if start_date is not None:
        snapshot_query = snapshot_query.where(
            InventorySnapshot.snapshot_date >= start_date
        )

    if end_date is not None:
        snapshot_query = snapshot_query.where(
            InventorySnapshot.snapshot_date
            <= end_date + timedelta(days=PREDICTION_HORIZON_DAYS)
        )
    snapshots = db.execute(snapshot_query).all()

    if not snapshots:
        return pd.DataFrame(
            columns=[
                *IDENTIFIER_COLUMNS,
                *FEATURE_COLUMNS,
                TARGET_COLUMN,
            ]
        )

    sales_records = db.scalars(
        select(SalesRecord).where(
            SalesRecord.tenant_id == tenant_id,
        )
    ).all()

    snapshot_groups: dict[tuple[UUID, UUID], dict[date, Any]] = {}
    timezone_map: dict[UUID, str] = {}

    for snapshot, timezone_name in snapshots:

        key = (snapshot.location_id, snapshot.product_id)

        snapshot_groups.setdefault(key, {})[
            snapshot.snapshot_date
        ] = snapshot

        timezone_map[snapshot.location_id] = timezone_name

    sales_by_group: dict[
        tuple[UUID, UUID], dict[date, float]
    ] = {}

    for sale in sales_records:
        timezone_name = timezone_map.get(sale.location_id)

        if timezone_name is None:
            continue

        local_timezone = ZoneInfo(timezone_name)

        sold_at = sale.sold_at

        if sold_at.tzinfo is None:
            raise ValueError(
                f"Sale {sale.id} has a timezone-naive sold_at value"
            )

        local_date = sold_at.astimezone(local_timezone).date()

        key = (sale.location_id, sale.product_id)

        daily_sales = sales_by_group.setdefault(key, {})

        daily_sales[local_date] = (
            daily_sales.get(local_date, 0.0)
            + float(sale.quantity)
        )

    rows: list[dict[str, Any]] = []

    for (location_id, product_id), daily_snapshots in snapshot_groups.items():
        daily_sales = sales_by_group.get(
            (location_id, product_id),
            {},
        )

        ordered_dates = sorted(daily_snapshots)

        for prediction_date in ordered_dates:
            if start_date is not None and prediction_date < start_date:
                continue

            if end_date is not None and prediction_date > end_date:
                continue

            current_snapshot = daily_snapshots[prediction_date]

            history_dates = [
                prediction_date - timedelta(days=offset)
                for offset in range(1, max(LOOKBACK_WINDOWS) + 1)
            ]

            history_sales = {
                day: daily_sales.get(day, 0.0)
                for day in history_dates
            }

            sales_lag_1 = history_sales[
                prediction_date - timedelta(days=1)
            ]

            sales_lag_7 = history_sales[
                prediction_date - timedelta(days=7)
            ]

            sales_7d = sum(
                history_sales[
                    prediction_date - timedelta(days=offset)
                ]
                for offset in range(1, 8)
            )

            sales_14d = sum(
                history_sales[
                    prediction_date - timedelta(days=offset)
                ]
                for offset in range(1, 15)
            )

            sales_28d = sum(history_sales.values())

            future_dates = [
                prediction_date + timedelta(days=offset)
                for offset in range(1, PREDICTION_HORIZON_DAYS + 1)
            ]

            future_snapshots = [
                daily_snapshots.get(day)
                for day in future_dates
            ]

            # Never create a negative label when future data is missing.
            if any(snapshot is None for snapshot in future_snapshots):
                continue

            stockout_next_7d = int(
                any(snapshot.is_stockout for snapshot in future_snapshots)
            )

            rows.append(
                {
                    "tenant_id": tenant_id,
                    "location_id": location_id,
                    "product_id": product_id,
                    "prediction_date": prediction_date,
                    "sales_lag_1": sales_lag_1,
                    "sales_lag_7": sales_lag_7,
                    "sales_7d": sales_7d,
                    "sales_14d": sales_14d,
                    "sales_28d": sales_28d,
                    "avg_daily_sales_7d": sales_7d / 7.0,
                    "available_stock": float(current_snapshot.available),
                    "day_of_week": prediction_date.weekday(),
                    TARGET_COLUMN: stockout_next_7d,
                }
            )

    columns = [
        *IDENTIFIER_COLUMNS,
        *FEATURE_COLUMNS,
        TARGET_COLUMN,
    ]

    if not rows:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(rows, columns=columns)
