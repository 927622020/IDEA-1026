from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocationCreate(BaseModel):
    location_code: str = Field(min_length=1, max_length=50)
    location_name: str = Field(min_length=1, max_length=160)
    location_type: str = Field(min_length=1, max_length=30)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("location_code", "location_name", "location_type")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @field_validator("address")
    @classmethod
    def strip_address(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    location_code: str
    location_name: str
    location_type: str
    address: str | None
    is_active: bool
    created_at: datetime


class LocationPage(BaseModel):
    items: list[LocationRead]
    total: int
    limit: int
    offset: int
