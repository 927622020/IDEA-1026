from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductCreate(BaseModel):
    sku_code: str = Field(min_length=1, max_length=80)
    product_name: str = Field(min_length=1, max_length=200)
    brand: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=120)
    description: str | None = None
    unit_of_measure: str = Field(default="PCS", min_length=1, max_length=20)
    barcode: str | None = Field(default=None, max_length=64)

    @field_validator("sku_code", "product_name", "brand", "category", "unit_of_measure")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @field_validator("barcode")
    @classmethod
    def strip_barcode(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ProductUpdate(BaseModel):
    product_name: str | None = Field(default=None, min_length=1, max_length=200)
    brand: str | None = Field(default=None, min_length=1, max_length=160)
    category: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    unit_of_measure: str | None = Field(default=None, min_length=1, max_length=20)
    barcode: str | None = Field(default=None, max_length=64)

    @field_validator("product_name", "brand", "category", "unit_of_measure")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    sku_code: str
    product_name: str
    brand: str
    category: str
    description: str | None
    unit_of_measure: str
    barcode: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductPage(BaseModel):
    items: list[ProductRead]
    total: int
    limit: int
    offset: int
