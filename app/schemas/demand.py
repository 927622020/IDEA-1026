
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DailyDemandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    tenant_id: UUID
    location_id: UUID
    product_id: UUID
    quantity_sold: Decimal = Field(ge=0)
    transaction_count: int = Field(ge=0)


class DailyDemandPage(BaseModel):
    items: list[DailyDemandRead]
    total: int
    limit: int
    offset: int
