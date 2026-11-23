from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

PurchaseOrderStatus = Literal[
    "DRAFT",
    "APPROVED",
    "SUBMITTED",
    "PARTIALLY_RECEIVED",
    "RECEIVED",
]


class PurchaseOrderLineCreate(BaseModel):
    product_id: UUID
    supplier_product_id: UUID
    ordered_quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class PurchaseOrderCreate(BaseModel):
    supplier_id: UUID
    location_id: UUID
    po_number: str = Field(min_length=1, max_length=80)
    currency: str = Field(min_length=3, max_length=3)
    expected_delivery_date: date | None = None
    idempotency_key: str = Field(min_length=1, max_length=150)
    notes: str | None = None
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)

    @field_validator("po_number", "idempotency_key")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha() or not value.isascii():
            raise ValueError("Currency must be a three-letter ISO currency code")
        return value

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class PurchaseOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: UUID
    product_id: UUID
    supplier_product_id: UUID
    supplier_sku: str | None
    ordered_quantity: Decimal
    received_quantity: Decimal
    unit_cost: Decimal
    line_total: Decimal


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    supplier_id: UUID
    location_id: UUID
    po_number: str
    status: PurchaseOrderStatus
    currency: str
    total_amount: Decimal
    expected_delivery_date: date | None
    approved_at: datetime | None
    submitted_at: datetime | None
    external_reference: str | None
    idempotency_key: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    lines: list[PurchaseOrderLineRead]


class PurchaseOrderPage(BaseModel):
    items: list[PurchaseOrderRead]
    total: int
    limit: int
    offset: int


class PurchaseOrderReceive(BaseModel):
    line_id: UUID
    quantity: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=3,
    )
    idempotency_key: str = Field(
        min_length=1,
        max_length=120,
    )
    notes: str | None = None

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Idempotency key cannot be blank")
        return value

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None
