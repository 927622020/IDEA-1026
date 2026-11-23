
"""Generate reproducible synthetic data for stockout model development."""

from datetime import date, timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pandas as pd

from app.ml.feature_contract import (
    FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
    PREDICTION_HORIZON_DAYS,
    TARGET_COLUMN,
)

SYNTHETIC_TENANT_ID = uuid5(NAMESPACE_URL, "idea-1026-synthetic-tenant")


def generate_synthetic_dataset(
    start_date: date = date(2025, 1, 1),
    days: int = 365,
    seed: int = 42,
    location_count: int = 3,
    product_count: int = 5,
) -> pd.DataFrame:
    """Generate simulated daily sales and stockout labels.

    Synthetic data is for pipeline demonstration only. It does not
    represent actual POS, ERP, or operational inventory history.
    """

    import numpy as np

    if days < 60:
        raise ValueError("days must be at least 60")

    if location_count < 1 or product_count < 1:
        raise ValueError("location_count and product_count must be positive")

    rng = np.random.default_rng(seed)

    rows: list[dict[str, Any]] = []
    total_days = days + PREDICTION_HORIZON_DAYS

    for location_number in range(location_count):
        location_id = uuid5(
            NAMESPACE_URL,
            f"idea-1026-synthetic-location-{location_number}",
        )

        for product_number in range(product_count):
            product_id = uuid5(
                NAMESPACE_URL,
                f"idea-1026-synthetic-product-{product_number}",
            )

            base_demand = float(rng.uniform(5, 20))
            initial_stock = float(rng.uniform(100, 220))
            stock = initial_stock

            sales_history: list[float] = []
            stockout_history: list[bool] = []
            available_history: list[float] = []

            for day_number in range(total_days):
                current_date = start_date + timedelta(days=day_number)

                weekday_factor = (
                    1.25 if current_date.weekday() >= 5 else 1.0
                )
                seasonal_factor = (
                    1.0
                    + 0.20
                    * np.sin(2 * np.pi * day_number / 90)
                )

                demand = max(
                    0.0,
                    float(
                        rng.poisson(
                            base_demand
                            * weekday_factor
                            * seasonal_factor
                        )
                    ),
                )

                # Simulate weekly replenishment with variable quantities.
                if day_number > 0 and day_number % 7 == 0:
                    stock += float(rng.uniform(100, 160))

                actual_sales = min(stock, demand)
                stock -= actual_sales

                available = max(0.0, stock)
                is_stockout = available == 0.0

                sales_history.append(actual_sales)
                stockout_history.append(is_stockout)
                available_history.append(available)

            # Create prediction rows only where all required history
            # and seven future daily labels are available.
            for day_number in range(28, days):
                prediction_date = start_date + timedelta(days=day_number)

                history = sales_history[day_number - 28:day_number]

                sales_7d = sum(history[-7:])
                sales_14d = sum(history[-14:])
                sales_28d = sum(history)

                future_stockouts = stockout_history[
                    day_number + 1:
                    day_number + PREDICTION_HORIZON_DAYS + 1
                ]

                if len(future_stockouts) != PREDICTION_HORIZON_DAYS:
                    continue

                rows.append(
                    {
                        "tenant_id": SYNTHETIC_TENANT_ID,
                        "location_id": location_id,
                        "product_id": product_id,
                        "prediction_date": prediction_date,
                        "sales_lag_1": history[-1],
                        "sales_lag_7": history[-7],
                        "sales_7d": sales_7d,
                        "sales_14d": sales_14d,
                        "sales_28d": sales_28d,
                        "avg_daily_sales_7d": sales_7d / 7.0,
                        "available_stock": available_history[day_number],
                        "day_of_week": prediction_date.weekday(),
                        TARGET_COLUMN: int(any(future_stockouts)),
                    }
                )

    columns = [
        *IDENTIFIER_COLUMNS,
        *FEATURE_COLUMNS,
        TARGET_COLUMN,
    ]

    return pd.DataFrame(rows, columns=columns)
