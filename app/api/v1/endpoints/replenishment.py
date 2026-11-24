
"""Replenishment recommendation API endpoints."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.schemas.replenishment import (
    ForecastSupplierReplenishmentResponse,
    SupplierReplenishmentRequest,
    SupplierReplenishmentResponse,
)
from app.services.replenishment_service import calculate_replenishment_quantity
from app.services.supplier_replenishment_service import (
    recommend_forecast_supplier_replenishment,
    recommend_supplier_replenishment,
)

router = APIRouter()


class ReplenishmentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    forecast_demand: Decimal = Field(
        ge=0,
        description="Forecast demand over replenishment lead time",
    )
    safety_stock: Decimal = Field(ge=0)
    available_inventory: Decimal = Field(ge=0)
    confirmed_inbound: Decimal = Field(ge=0)


class ReplenishmentResponse(BaseModel):
    recommended_quantity: Decimal
    requires_replenishment: bool


@router.post("/recommendation", response_model=ReplenishmentResponse)
def recommendation(payload: ReplenishmentRequest) -> ReplenishmentResponse:
    """Calculate a replenishment quantity from supplied inventory values."""

    try:
        quantity = calculate_replenishment_quantity(
            forecast_demand=payload.forecast_demand,
            safety_stock=payload.safety_stock,
            available_inventory=payload.available_inventory,
            confirmed_inbound=payload.confirmed_inbound,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ReplenishmentResponse(
        recommended_quantity=quantity,
        requires_replenishment=quantity > 0,
    )


@router.post(
    "/supplier-recommendation",
    response_model=SupplierReplenishmentResponse,
)
def supplier_recommendation(
    payload: SupplierReplenishmentRequest,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> SupplierReplenishmentResponse:
    """Recommend an order quantity using live inventory and supplier data."""

    return recommend_supplier_replenishment(
        db=db,
        tenant_id=tenant_id,
        payload=payload,
    )



class ForecastSupplierReplenishmentRequest(BaseModel):
    """Inputs for forecast-based supplier replenishment."""

    location_id: UUID
    product_id: UUID
    safety_stock: Decimal = Field(ge=0)


@router.post(
    "/forecast-supplier-recommendation",
    response_model=ForecastSupplierReplenishmentResponse,
)
def forecast_supplier_recommendation(
    payload: ForecastSupplierReplenishmentRequest,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> ForecastSupplierReplenishmentResponse:
    """Recommend supplier replenishment using forecast lead-time demand."""

    return recommend_forecast_supplier_replenishment(
        db=db,
        tenant_id=tenant_id,
        location_id=payload.location_id,
        product_id=payload.product_id,
        safety_stock=payload.safety_stock,
    )
