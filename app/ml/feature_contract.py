"""Versioned feature contract for stockout prediction."""

from typing import Final

FEATURE_CONTRACT_VERSION: Final[str] = "1.0.0"

# Prediction target: stockout within the next 7 days.
PREDICTION_HORIZON_DAYS: Final[int] = 7

# Historical demand lookback windows.
LOOKBACK_WINDOWS: Final[tuple[int, ...]] = (7, 14, 28)

# Features available at prediction time.
FEATURE_COLUMNS: Final[tuple[str, ...]] = (
    "sales_lag_1",
    "sales_lag_7",
    "sales_7d",
    "sales_14d",
    "sales_28d",
    "avg_daily_sales_7d",
    "available_stock",
    "day_of_week",
)

# Target column is never a model input.
TARGET_COLUMN: Final[str] = "stockout_next_7d"

# All features must be calculated using data available
# on or before the prediction date.
FEATURE_CUTOFF_RULE: Final[str] = "prediction_date"

IDENTIFIER_COLUMNS: Final[tuple[str, ...]] = (
    "tenant_id",
    "location_id",
    "product_id",
    "prediction_date",
)
