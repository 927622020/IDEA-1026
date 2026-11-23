from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupplierCreate(BaseModel):
    supplier_code: str = Field(min_length=1, max_length=80)
    supplier_name: str = Field(min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = None
    country: str | None = Field(default=None, max_length=100)
    default_lead_time_days: int = Field(default=7, ge=0)

    @field_validator("supplier_code", "supplier_name")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @field_validator("contact_person", "email", "phone", "address", "country")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SupplierUpdate(BaseModel):
    supplier_name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = None
    country: str | None = Field(default=None, max_length=100)
    default_lead_time_days: int | None = Field(default=None, ge=0)

    @field_validator(
        "supplier_name", "contact_person", "email", "phone", "address", "country"
    )
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    supplier_code: str
    supplier_name: str
    contact_person: str | None
    email: str | None
    phone: str | None
    address: str | None
    country: str | None
    default_lead_time_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierPage(BaseModel):
    items: list[SupplierRead]
    total: int
    limit: int
    offset: int
