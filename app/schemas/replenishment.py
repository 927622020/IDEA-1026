
"""Schemas for database-driven supplier replenishment recommendations."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SupplierReplenishmentRequest(BaseModel):
    """Inputs required to calculate a supplier replenishment recommendation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    location_id: UUID
    product_id: UUID
    forecast_demand: Decimal = Field(ge=0)
    safety_stock: Decimal = Field(ge=0)


class SupplierReplenishmentResponse(BaseModel):
    """Recommended purchase quantity and selected supplier details."""

    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    location_id: UUID
    product_id: UUID

    forecast_demand: Decimal
    safety_stock: Decimal
    available_inventory: Decimal
    confirmed_inbound: Decimal
    required_quantity: Decimal

    requires_replenishment: bool
    recommended_quantity: Decimal

    supplier_id: UUID
    supplier_name: str
    supplier_code: str
    supplier_sku: str | None

    unit_cost: Decimal
    currency: str
    estimated_total_cost: Decimal

    lead_time_days: int
    minimum_order_quantity: Decimal
    pack_size: Decimal
    is_preferred_supplier: bool
