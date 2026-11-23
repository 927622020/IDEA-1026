from datetime import UTC, datetime
from hashlib import sha256
from threading import Lock
from uuid import NAMESPACE_URL, uuid5

from app.integrations.erp.interfaces import (
    ErpAdapter,
    ErpDraftRequest,
    ErpDraftResult,
    ErpPurchaseOrderRequest,
    ErpPurchaseOrderResult,
)


class MockErpAdapter(ErpAdapter):
    """Development adapter. In-memory only; not durable or production-safe."""

    def __init__(self) -> None:
        self._documents: dict[str, tuple[str, ErpDraftResult]] = {}
        self._purchase_orders: dict[
            str, tuple[str, ErpPurchaseOrderResult]
        ] = {}
        self._lock = Lock()

    def create_draft(self, request: ErpDraftRequest) -> ErpDraftResult:
        fingerprint = sha256(
            request.model_dump_json().encode()
        ).hexdigest()

        with self._lock:
            existing = self._documents.get(request.idempotency_key)
            if existing:
                if existing[0] != fingerprint:
                    raise ValueError(
                        "Idempotency key reused with different draft data"
                    )
                return existing[1]

            result = ErpDraftResult(
                external_document_id=f"MOCK-{uuid5(NAMESPACE_URL, request.idempotency_key).hex[:12].upper()}",
                status="DRAFT",
                created_at=datetime.now(UTC),
                idempotency_key=request.idempotency_key,
            )
            self._documents[request.idempotency_key] = (
                fingerprint,
                result,
            )
            return result

    def submit_purchase_order(
        self,
        request: ErpPurchaseOrderRequest,
    ) -> ErpPurchaseOrderResult:
        fingerprint = sha256(
            request.model_dump_json().encode()
        ).hexdigest()

        with self._lock:
            existing = self._purchase_orders.get(request.idempotency_key)
            if existing:
                if existing[0] != fingerprint:
                    raise ValueError(
                        "Idempotency key reused with different purchase order data"
                    )
                return existing[1]

            result = ErpPurchaseOrderResult(
                external_document_id=(
                    f"MOCK-PO-{uuid5(NAMESPACE_URL, request.idempotency_key).hex[:12].upper()}"
                ),
                status="SUBMITTED",
                created_at=datetime.now(UTC),
                idempotency_key=request.idempotency_key,
            )
            self._purchase_orders[request.idempotency_key] = (
                fingerprint,
                result,
            )
            return result
