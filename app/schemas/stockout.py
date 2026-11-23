
"""Schemas for stockout prediction requests and responses."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ml.feature_contract import FEATURE_CONTRACT_VERSION


class StockoutPredictionRequest(BaseModel):
    """Input features for a seven-day stockout prediction."""

    location_id: UUID
    product_id: UUID
    prediction_date: date

    sales_lag_1: float = Field(ge=0)
    sales_lag_7: float = Field(ge=0)
    sales_7d: float = Field(ge=0)
    sales_14d: float = Field(ge=0)
    sales_28d: float = Field(ge=0)
    avg_daily_sales_7d: float = Field(ge=0)
    available_stock: float = Field(ge=0)
    day_of_week: int = Field(ge=0, le=6)


class StockoutPredictionRead(BaseModel):
    """Stockout prediction response."""

    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    location_id: UUID
    product_id: UUID
    prediction_date: date

    stockout_probability: float = Field(ge=0, le=1)
    risk_level: Literal["low", "medium", "high"]
    prediction_horizon_days: int = 7

    model_version: str = FEATURE_CONTRACT_VERSION
    data_source: Literal["synthetic_demo"] = "synthetic_demo"
    is_production_ready: bool = False
