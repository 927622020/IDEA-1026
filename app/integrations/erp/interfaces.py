
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field


class ErpDocumentType(StrEnum):
    PURCHASE_ORDER = "purchase_order"
    STOCK_TRANSFER_ORDER = "stock_transfer_order"


class ErpDraftRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    document_type: ErpDocumentType
    source_location: str = Field(min_length=1, max_length=64)
    destination_location: str = Field(min_length=1, max_length=64)
    sku: str = Field(min_length=1, max_length=64)
    quantity: float = Field(gt=0)


class ErpDraftResult(BaseModel):
    external_document_id: str
    status: str
    created_at: datetime
    idempotency_key: str


class ErpPurchaseOrderLine(BaseModel):
    supplier_sku: str = Field(min_length=1, max_length=100)
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class ErpPurchaseOrderRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    po_number: str = Field(min_length=1, max_length=80)
    supplier_code: str = Field(min_length=1, max_length=80)
    supplier_name: str = Field(min_length=1, max_length=200)
    destination_location: str = Field(min_length=1, max_length=50)
    currency: str = Field(min_length=3, max_length=3)
    lines: list[ErpPurchaseOrderLine] = Field(min_length=1)


class ErpPurchaseOrderResult(BaseModel):
    external_document_id: str
    status: str
    created_at: datetime
    idempotency_key: str


class ErpAdapter(Protocol):
    def create_draft(self, request: ErpDraftRequest) -> ErpDraftResult:
        """Create or return an existing ERP draft for this idempotency key."""
        ...

    def submit_purchase_order(
        self,
        request: ErpPurchaseOrderRequest,
    ) -> ErpPurchaseOrderResult:
        """Create or return an existing ERP purchase order for this key."""
        ...
