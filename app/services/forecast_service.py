from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Location
from app.schemas.forecast import (
    DailyForecast,
    DemandForecastResponse,
)
from app.services.demand_service import get_daily_demand
from app.services.product_service import require_active_tenant

ZERO = Decimal(0)
PRECISION = Decimal("0.001")


def forecast_daily_demand(
    db: Session,
    tenant_id: UUID,
    *,
    location_id: UUID,
    product_id: UUID,
) -> DemandForecastResponse:
    require_active_tenant(db, tenant_id)

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

    today = datetime.now(ZoneInfo(location.timezone)).date()

    # Use the previous 28 completed local calendar days.
    historical_end = today - timedelta(days=1)
    historical_start = historical_end - timedelta(days=27)

    history = get_daily_demand(
        db,
        tenant_id,
        location_id=location_id,
        product_id=product_id,
        start_date=historical_start,
        end_date=historical_end,
    )

    days_with_sales = sum(
        1 for item in history if item["transaction_count"] > 0
    )

    common = {
        "tenant_id": tenant_id,
        "location_id": location_id,
        "product_id": product_id,
        "historical_start_date": historical_start,
        "historical_end_date": historical_end,
        "forecast_start_date": today + timedelta(days=1),
        "forecast_end_date": today + timedelta(days=7),
        "history_days": len(history),
        "days_with_sales": days_with_sales,
    }

    # Never interpret missing sales history as zero future demand.
    if days_with_sales == 0:
        return DemandForecastResponse(
            **common,
            method="none",
            status="insufficient_history",
            message=(
                "No historical sales records were found. "
                "Add sales data before generating a demand forecast."
            ),
            daily_forecasts=[],
            total_forecast_demand=ZERO,
        )

    total_sales = sum(
        (item["quantity_sold"] for item in history),
        ZERO,
    )

    overall_average = (
        total_sales / Decimal(len(history))
    ).quantize(PRECISION)

    # Group the 28 historical days by weekday.
    weekday_totals = defaultdict(lambda: ZERO)
    weekday_sales_days = defaultdict(int)
    weekday_observations = defaultdict(int)

    for item in history:
        day = item["date"].weekday()
        weekday_totals[day] += item["quantity_sold"]
        weekday_observations[day] += 1

        if item["transaction_count"] > 0:
            weekday_sales_days[day] += 1

    # Require at least two sales days for every weekday.
    # Otherwise, use the overall average instead.
    enough_weekday_history = all(
        weekday_observations[day] >= 2
        and weekday_sales_days[day] >= 2
        for day in range(7)
    )

    if enough_weekday_history:
        method = "weekday_average"
        status_value = "ok"
        message = (
            "Forecast generated using average sales for each weekday "
            "from the previous 28 completed days."
        )
    else:
        method = "overall_daily_average"
        status_value = "limited_history"
        message = (
            "Limited weekday history. Forecast uses the overall "
            "average daily sales from the previous 28 days."
        )

    forecasts = []

    for offset in range(1, 8):
        forecast_date = today + timedelta(days=offset)

        if enough_weekday_history:
            weekday = forecast_date.weekday()
            demand = (
                weekday_totals[weekday]
                / Decimal(weekday_observations[weekday])
            ).quantize(PRECISION)
        else:
            demand = overall_average

        forecasts.append(
            DailyForecast(
                date=forecast_date,
                forecast_demand=demand,
            )
        )

    total_forecast = sum(
        (item.forecast_demand for item in forecasts),
        ZERO,
    ).quantize(PRECISION)

    return DemandForecastResponse(
        **common,
        method=method,
        status=status_value,
        message=message,
        daily_forecasts=forecasts,
        total_forecast_demand=total_forecast,
    )
