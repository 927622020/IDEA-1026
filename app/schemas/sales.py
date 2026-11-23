from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SalesCreate(BaseModel):
    location_id: UUID
    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    sold_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    external_reference: str | None = Field(default=None, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=120)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Idempotency key cannot be blank")
        return value

    @field_validator("external_reference")
    @classmethod
    def clean_external_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("sold_at")
    @classmethod
    def validate_sold_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sold_at must include a timezone")
        return value


class SalesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    location_id: UUID
    product_id: UUID
    quantity: Decimal
    sold_at: datetime
    external_reference: str | None
    idempotency_key: str
    created_at: datetime


class SalesPage(BaseModel):
    items: list[SalesRead]
    total: int
    limit: int
    offset: int
