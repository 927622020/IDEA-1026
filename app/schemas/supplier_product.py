
"""Schemas for supplier-product purchasing details."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupplierProductCreate(BaseModel):
    supplier_id: UUID
    product_id: UUID
    supplier_sku: str | None = Field(default=None, max_length=100)
    unit_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3)
    lead_time_days: int = Field(ge=0)
    minimum_order_quantity: Decimal = Field(
        gt=0, max_digits=14, decimal_places=3
    )
    pack_size: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    is_preferred: bool = False

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha() or not value.isascii():
            raise ValueError("Currency must be a 3-letter ISO currency code.")
        return value

    @field_validator("supplier_sku")
    @classmethod
    def clean_supplier_sku(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SupplierProductUpdate(BaseModel):
    supplier_sku: str | None = Field(default=None, max_length=100)
    unit_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=4
    )
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    lead_time_days: int | None = Field(default=None, ge=0)
    minimum_order_quantity: Decimal | None = Field(
        default=None, gt=0, max_digits=14, decimal_places=3
    )
    pack_size: Decimal | None = Field(
        default=None, gt=0, max_digits=14, decimal_places=3
    )
    is_preferred: bool | None = None
    is_active: bool | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha() or not value.isascii():
            raise ValueError("Currency must be a 3-letter ISO currency code.")
        return value

    @field_validator("supplier_sku")
    @classmethod
    def clean_supplier_sku(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SupplierProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    supplier_id: UUID
    product_id: UUID
    supplier_sku: str | None
    unit_cost: Decimal
    currency: str
    lead_time_days: int
    minimum_order_quantity: Decimal
    pack_size: Decimal
    is_preferred: bool
    is_active: bool


class SupplierProductPage(BaseModel):
    items: list[SupplierProductRead]
    total: int
    limit: int
    offset: int
