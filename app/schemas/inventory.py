from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InventoryOperationCreate(BaseModel):
    location_id: UUID
    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    idempotency_key: str = Field(min_length=1, max_length=120)
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None

    @field_validator("idempotency_key")
    @classmethod
    def strip_idempotency_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Idempotency key cannot be blank")
        return value

    @field_validator("reference", "notes")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class InventoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    location_id: UUID
    product_id: UUID
    on_hand: Decimal
    reserved: Decimal
    inbound: Decimal
    available: Decimal
    version: int
    created_at: datetime
    updated_at: datetime


class InventoryTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    location_id: UUID
    product_id: UUID
    transaction_type: str
    quantity: Decimal
    reference: str | None
    idempotency_key: str
    notes: str | None
    created_at: datetime


class InventoryOperationResult(BaseModel):
    balance: InventoryRead
    transaction: InventoryTransactionRead


class InventoryPage(BaseModel):
    items: list[InventoryRead]
    total: int
    limit: int
    offset: int
