
"""Database-driven supplier replenishment recommendations."""

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    InventoryBalance,
    Location,
    Product,
    Supplier,
    SupplierProduct,
)
from app.schemas.replenishment import (
    ForecastSupplierReplenishmentResponse,
    SupplierReplenishmentRequest,
    SupplierReplenishmentResponse,
)
from app.services.product_service import require_active_tenant
from app.services.replenishment_service import (
    calculate_replenishment_quantity,
    calculate_supplier_order_quantity,
)


def recommend_supplier_replenishment(
    db: Session,
    tenant_id: UUID,
    payload: SupplierReplenishmentRequest,
) -> SupplierReplenishmentResponse:
    """Calculate a replenishment quantity and select an eligible supplier."""

    require_active_tenant(db, tenant_id)

    location = db.scalar(
        select(Location).where(
            Location.id == payload.location_id,
            Location.tenant_id == tenant_id,
            Location.is_active.is_(True),
        )
    )
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active product not found",
        )

    balance = db.scalar(
        select(InventoryBalance).where(
            InventoryBalance.tenant_id == tenant_id,
            InventoryBalance.location_id == payload.location_id,
            InventoryBalance.product_id == payload.product_id,
        )
    )
    if balance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory balance not found for this location and product",
        )

    available_inventory = balance.on_hand - balance.reserved
    confirmed_inbound = balance.inbound

    required_quantity = calculate_replenishment_quantity(
        forecast_demand=payload.forecast_demand,
        safety_stock=payload.safety_stock,
        available_inventory=available_inventory,
        confirmed_inbound=confirmed_inbound,
    )

    supplier_records = db.execute(
        select(SupplierProduct, Supplier)
        .join(
            Supplier,
            Supplier.id == SupplierProduct.supplier_id,
        )
        .where(
            SupplierProduct.tenant_id == tenant_id,
            SupplierProduct.product_id == payload.product_id,
            SupplierProduct.is_active.is_(True),
            Supplier.tenant_id == tenant_id,
            Supplier.is_active.is_(True),
        )
        .order_by(
            SupplierProduct.is_preferred.desc(),
            SupplierProduct.lead_time_days.asc(),
            SupplierProduct.unit_cost.asc(),
            Supplier.id.asc(),
        )
    ).all()

    if not supplier_records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active supplier is configured for this product",
        )

    supplier_product, supplier = supplier_records[0]

    recommended_quantity = calculate_supplier_order_quantity(
        required_quantity=required_quantity,
        minimum_order_quantity=supplier_product.minimum_order_quantity,
        pack_size=supplier_product.pack_size,
    )

    estimated_total_cost = (
        recommended_quantity * supplier_product.unit_cost
    ).quantize(Decimal("0.0001"))

    return SupplierReplenishmentResponse(
        tenant_id=tenant_id,
        location_id=payload.location_id,
        product_id=payload.product_id,
        forecast_demand=payload.forecast_demand,
        safety_stock=payload.safety_stock,
        available_inventory=available_inventory,
        confirmed_inbound=confirmed_inbound,
        required_quantity=required_quantity,
        requires_replenishment=required_quantity > 0,
        recommended_quantity=recommended_quantity,
        supplier_id=supplier.id,
        supplier_product_id=supplier_product.id,
        supplier_name=supplier.supplier_name,
        supplier_code=supplier.supplier_code,
        supplier_sku=supplier_product.supplier_sku,
        unit_cost=supplier_product.unit_cost,
        currency=supplier_product.currency,
        estimated_total_cost=estimated_total_cost,
        lead_time_days=supplier_product.lead_time_days,
        minimum_order_quantity=supplier_product.minimum_order_quantity,
        pack_size=supplier_product.pack_size,
        is_preferred_supplier=supplier_product.is_preferred,
    )


def recommend_forecast_supplier_replenishment(
    db: Session,
    tenant_id: UUID,
    *,
    location_id: UUID,
    product_id: UUID,
    safety_stock: Decimal,
):
    """Recommend replenishment using forecast demand over supplier lead time."""

    from app.services.forecast_service import forecast_daily_demand

    forecast = forecast_daily_demand(
        db,
        tenant_id,
        location_id=location_id,
        product_id=product_id,
    )

    if forecast.status == "insufficient_history":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient sales history for a forecast-based recommendation.",
        )

    # Identify the supplier before calculating lead-time demand.
    selection_payload = SupplierReplenishmentRequest(
        location_id=location_id,
        product_id=product_id,
        forecast_demand=Decimal(0),
        safety_stock=safety_stock,
    )

    supplier_selection = recommend_supplier_replenishment(
        db,
        tenant_id,
        selection_payload,
    )

    lead_time = supplier_selection.lead_time_days

    if lead_time < 1 or lead_time > len(forecast.daily_forecasts):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Supplier lead time is {lead_time} days, but the forecast "
                f"supports only {len(forecast.daily_forecasts)} days."
            ),
        )

    lead_time_forecasts = forecast.daily_forecasts[:lead_time]

    lead_time_demand = sum(
        (item.forecast_demand for item in lead_time_forecasts),
        Decimal(0),
    )

    final_payload = selection_payload.model_copy(
        update={"forecast_demand": lead_time_demand}
    )

    recommendation = recommend_supplier_replenishment(
        db,
        tenant_id,
        final_payload,
    )

    return ForecastSupplierReplenishmentResponse(
        **recommendation.model_dump(),
        forecast_method=forecast.method,
        forecast_start_date=lead_time_forecasts[0].date,
        forecast_end_date=lead_time_forecasts[-1].date,
        lead_time_forecast_days=lead_time,
        lead_time_daily_forecasts=lead_time_forecasts,
    )
