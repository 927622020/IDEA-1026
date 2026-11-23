from app.integrations.erp.interfaces import ErpDocumentType, ErpDraftRequest
from app.integrations.erp.mock.adapter import MockErpAdapter


def test_mock_erp_is_idempotent_for_same_key() -> None:
    adapter = MockErpAdapter()
    request = ErpDraftRequest(
        idempotency_key="test-order-0001",
        document_type=ErpDocumentType.STOCK_TRANSFER_ORDER,
        source_location="WH-01",
        destination_location="STORE-01",
        sku="SKU-100",
        quantity=25,
    )

    first = adapter.create_draft(request)
    second = adapter.create_draft(request)

    assert first.external_document_id == second.external_document_id
    assert first.status == "DRAFT"
