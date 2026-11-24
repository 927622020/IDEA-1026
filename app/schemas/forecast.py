from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DailyForecast(BaseModel):
    date: date
    forecast_demand: Decimal = Field(ge=0)


class DemandForecastResponse(BaseModel):
    tenant_id: UUID
    location_id: UUID
    product_id: UUID
    historical_start_date: date
    historical_end_date: date
    forecast_start_date: date
    forecast_end_date: date
    history_days: int
    days_with_sales: int
    method: Literal["weekday_average", "overall_daily_average", "none"]
    status: Literal["ok", "limited_history", "insufficient_history"]
    message: str
    daily_forecasts: list[DailyForecast]
    total_forecast_demand: Decimal = Field(ge=0)
