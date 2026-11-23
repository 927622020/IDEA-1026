from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import (
    InventoryBalance,
    InventoryTransaction,
    Location,
    PurchaseOrderLine,
    Supplier,
    Tenant,
)
from app.schemas.product import ProductCreate
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderReceive,
)
from app.schemas.supplier_product import SupplierProductCreate
from app.services.product_service import create_product
from app.services.purchase_order_service import (
    approve_purchase_order,
    create_purchase_order,
    receive_purchase_order,
    submit_purchase_order,
)
from app.services.supplier_product_service import create_supplier_product


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    with TestingSession() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def make_tenant(db, code: str) -> Tenant:
    tenant = Tenant(name=f"Tenant {code}", code=code)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def make_supplier(db, tenant_id, code: str) -> Supplier:
    supplier = Supplier(
        tenant_id=tenant_id,
        supplier_code=code,
        supplier_name=f"Supplier {code}",
        default_lead_time_days=7,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def make_location(db, tenant_id):
    location = Location(
        tenant_id=tenant_id,
        location_code="LOC-001",
        location_name="Main Warehouse",
        location_type="WAREHOUSE",
        timezone="Asia/Dhaka",
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def make_product(db, tenant_id, sku: str):
    return create_product(
        db,
        tenant_id,
        ProductCreate(
            sku_code=sku,
            product_name="Mango Drink 200ml",
            brand="Demo Foods",
            category="Beverages",
            unit_of_measure="PCS",
        ),
    )


def make_supplier_product(db, tenant_id, supplier_id, product_id):
    return create_supplier_product(
        db,
        tenant_id,
        SupplierProductCreate(
            supplier_id=supplier_id,
            product_id=product_id,
            supplier_sku="SUP-MANGO-001",
            unit_cost=Decimal("12.5000"),
            currency="BDT",
            lead_time_days=5,
            minimum_order_quantity=Decimal(10),
            pack_size=Decimal(5),
        ),
    )


def make_payload(supplier_id, location_id, product_id, supplier_product_id):
    return PurchaseOrderCreate(
        supplier_id=supplier_id,
        location_id=location_id,
        po_number="PO-TEST-001",
        currency="BDT",
        idempotency_key="PO-IDEM-001",
        lines=[
            PurchaseOrderLineCreate(
                product_id=product_id,
                supplier_product_id=supplier_product_id,
                ordered_quantity=Decimal(20),
            )
        ],
    )


def test_create_purchase_order_uses_catalog_price_and_calculates_total(db):
    tenant = make_tenant(db, "PO-A")
    supplier = make_supplier(db, tenant.id, "SUP-PO-A")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-SKU-001")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)

    assert purchase_order.tenant_id == tenant.id
    assert purchase_order.supplier_id == supplier.id
    assert purchase_order.location_id == location.id
    assert purchase_order.po_number == "PO-TEST-001"
    assert purchase_order.status == "DRAFT"
    assert purchase_order.currency == "BDT"
    assert purchase_order.total_amount == Decimal("250.0000")

    assert len(purchase_order.lines) == 1
    line = purchase_order.lines[0]

    assert line.product_id == product.id
    assert line.ordered_quantity == Decimal("20.000")
    assert line.unit_cost == Decimal("12.5000")
    assert line.line_total == Decimal("250.0000")
    assert line.received_quantity == Decimal("0.000")


def test_duplicate_idempotency_key_returns_existing_purchase_order(db):
    tenant = make_tenant(db, "PO-B")
    supplier = make_supplier(db, tenant.id, "SUP-PO-B")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-SKU-002")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    first = create_purchase_order(db, tenant.id, payload)
    second = create_purchase_order(db, tenant.id, payload)

    assert first.id == second.id

    count = len(
        db.query(PurchaseOrderLine).all()
    )
    assert count == 1


def test_cross_tenant_supplier_is_rejected(db):
    tenant_a = make_tenant(db, "PO-C")
    tenant_b = make_tenant(db, "PO-D")

    supplier_b = make_supplier(db, tenant_b.id, "SUP-PO-D")
    location_a = make_location(db, tenant_a.id)
    product_a = make_product(db, tenant_a.id, "PO-SKU-003")


    payload = PurchaseOrderCreate(
        supplier_id=supplier_b.id,
        location_id=location_a.id,
        po_number="PO-CROSS-TENANT",
        currency="BDT",
        idempotency_key="PO-CROSS-001",
        lines=[
            PurchaseOrderLineCreate(
                product_id=product_a.id,
                supplier_product_id=product_a.id,
                ordered_quantity=Decimal(10),
            )
        ],
    )

    with pytest.raises(HTTPException) as error:
        create_purchase_order(db, tenant_a.id, payload)

    assert error.value.status_code == 404


def test_supplier_product_must_match_selected_supplier(db):
    tenant = make_tenant(db, "PO-E")
    supplier_a = make_supplier(db, tenant.id, "SUP-PO-E1")
    supplier_b = make_supplier(db, tenant.id, "SUP-PO-E2")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-SKU-005")

    supplier_item_b = make_supplier_product(
        db, tenant.id, supplier_b.id, product.id
    )

    payload = make_payload(
        supplier_a.id,
        location.id,
        product.id,
        supplier_item_b.id,
    )

    with pytest.raises(HTTPException) as error:
        create_purchase_order(db, tenant.id, payload)

    assert error.value.status_code == 422


def test_draft_purchase_order_does_not_change_inventory(db):
    tenant = make_tenant(db, "PO-F")
    supplier = make_supplier(db, tenant.id, "SUP-PO-F")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-SKU-006")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    balance = InventoryBalance(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
        on_hand=Decimal(100),
        reserved=Decimal(15),
        inbound=Decimal(5),
        version=3,
    )
    db.add(balance)
    db.commit()
    db.refresh(balance)

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    create_purchase_order(db, tenant.id, payload)

    db.refresh(balance)

    assert balance.on_hand == Decimal("100.000")
    assert balance.reserved == Decimal("15.000")
    assert balance.inbound == Decimal("5.000")
    assert balance.version == 3
def test_approve_draft_purchase_order(db):
    tenant = make_tenant(db, "PO-G")
    supplier = make_supplier(db, tenant.id, "SUP-PO-G")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-SKU-007")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)

    approved_order = approve_purchase_order(
        db,
        tenant.id,
        purchase_order.id,
    )

    assert approved_order.status == "APPROVED"
    assert approved_order.approved_at is not None
def test_cannot_approve_purchase_order_twice(db):
    tenant = make_tenant(db, "PO-H")
    supplier = make_supplier(db, tenant.id, "SUP-PO-H")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-SKU-008")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)

    approve_purchase_order(db, tenant.id, purchase_order.id)

    with pytest.raises(HTTPException) as error:
        approve_purchase_order(db, tenant.id, purchase_order.id)

    assert error.value.status_code == 409
def test_cannot_approve_another_tenants_purchase_order(db):
    tenant_a = make_tenant(db, "PO-I")
    tenant_b = make_tenant(db, "PO-J")

    supplier = make_supplier(db, tenant_b.id, "SUP-PO-J")
    location = make_location(db, tenant_b.id)
    product = make_product(db, tenant_b.id, "PO-SKU-009")
    supplier_item = make_supplier_product(
        db, tenant_b.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant_b.id, payload)

    with pytest.raises(HTTPException) as error:
        approve_purchase_order(db, tenant_a.id, purchase_order.id)

    assert error.value.status_code == 404


def test_submit_approved_purchase_order_updates_inbound_inventory(db):
    tenant = make_tenant(db, "PO-K")
    supplier = make_supplier(db, tenant.id, "SUP-PO-K")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-SKU-010")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    balance = InventoryBalance(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
        on_hand=Decimal(100),
        reserved=Decimal(15),
        inbound=Decimal(5),
        version=3,
    )
    db.add(balance)
    db.commit()

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)
    approve_purchase_order(db, tenant.id, purchase_order.id)

    submitted_order = submit_purchase_order(
        db, tenant.id, purchase_order.id
    )

    db.refresh(balance)

    assert submitted_order.status == "SUBMITTED"
    assert submitted_order.external_reference is not None
    assert submitted_order.external_reference.startswith("MOCK-PO-")
    assert submitted_order.submitted_at is not None

    assert balance.on_hand == Decimal("100.000")
    assert balance.reserved == Decimal("15.000")
    assert balance.inbound == Decimal("25.000")
    assert balance.version == 4



def test_repeated_submission_does_not_duplicate_inbound_inventory(db):
    tenant = make_tenant(db, "PO-L")
    supplier = make_supplier(db, tenant.id, "SUP-PO-L")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-SKU-011")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)
    approve_purchase_order(db, tenant.id, purchase_order.id)

    first = submit_purchase_order(db, tenant.id, purchase_order.id)
    second = submit_purchase_order(db, tenant.id, purchase_order.id)

    balance = db.query(InventoryBalance).filter_by(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
    ).one()

    assert first.id == second.id
    assert first.external_reference == second.external_reference
    assert balance.inbound == Decimal("20.000")
    assert balance.version == 1

def test_draft_purchase_order_cannot_be_submitted(db):
    tenant = make_tenant(db, "PO-M")
    supplier = make_supplier(db, tenant.id, "SUP-PO-M")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-SKU-012")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)

    with pytest.raises(HTTPException) as exc:
        submit_purchase_order(db, tenant.id, purchase_order.id)

    assert exc.value.status_code == 409

    balance = db.query(InventoryBalance).filter_by(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
    ).first()

    assert balance is None


def test_partial_purchase_order_receiving_updates_inventory(db):
    tenant = make_tenant(db, "PO-RECEIVE-A")
    supplier = make_supplier(db, tenant.id, "SUP-RECEIVE-A")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-RECEIVE-SKU-A")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)
    approve_purchase_order(db, tenant.id, purchase_order.id)
    submit_purchase_order(db, tenant.id, purchase_order.id)

    line = purchase_order.lines[0]

    result = receive_purchase_order(
        db,
        tenant.id,
        purchase_order.id,
        PurchaseOrderReceive(
            line_id=line.id,
            quantity=Decimal(8),
            idempotency_key="PO-RECEIVE-KEY-A",
        ),
    )

    balance = db.query(InventoryBalance).filter_by(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
    ).one()

    transaction = db.query(InventoryTransaction).filter_by(
        tenant_id=tenant.id,
        idempotency_key="PO-RECEIVE-KEY-A",
    ).one()

    db.refresh(line)

    assert result.status == "PARTIALLY_RECEIVED"
    assert line.received_quantity == Decimal("8.000")

    assert balance.on_hand == Decimal("8.000")
    assert balance.inbound == Decimal("12.000")
    assert balance.version == 2

    assert transaction.transaction_type == "RECEIVE"
    assert transaction.quantity == Decimal("8.000")


def test_duplicate_purchase_order_receiving_is_idempotent(db):
    tenant = make_tenant(db, "PO-RECEIVE-IDEMPOTENT")
    supplier = make_supplier(db, tenant.id, "SUP-RECEIVE-IDEMPOTENT")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-RECEIVE-SKU-IDEMPOTENT")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)
    approve_purchase_order(db, tenant.id, purchase_order.id)
    submit_purchase_order(db, tenant.id, purchase_order.id)

    line = purchase_order.lines[0]

    receive_payload = PurchaseOrderReceive(
        line_id=line.id,
        quantity=Decimal(8),
        idempotency_key="PO-RECEIVE-IDEMPOTENT-KEY",
    )

    first_result = receive_purchase_order(
        db, tenant.id, purchase_order.id, receive_payload
    )
    second_result = receive_purchase_order(
        db, tenant.id, purchase_order.id, receive_payload
    )

    balance = db.query(InventoryBalance).filter_by(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
    ).one()

    transaction_count = db.query(InventoryTransaction).filter_by(
        tenant_id=tenant.id,
        idempotency_key="PO-RECEIVE-IDEMPOTENT-KEY",
    ).count()

    assert first_result.status == "PARTIALLY_RECEIVED"
    assert second_result.status == "PARTIALLY_RECEIVED"
    assert balance.on_hand == Decimal("8.000")
    assert balance.inbound == Decimal("12.000")
    assert balance.version == 2
    assert transaction_count == 1


def test_fully_received_purchase_order_updates_status(db):
    tenant = make_tenant(db, "PO-RECEIVE-FULL")
    supplier = make_supplier(db, tenant.id, "SUP-RECEIVE-FULL")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-RECEIVE-SKU-FULL")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)
    approve_purchase_order(db, tenant.id, purchase_order.id)
    submit_purchase_order(db, tenant.id, purchase_order.id)

    line = purchase_order.lines[0]

    first_result = receive_purchase_order(
        db,
        tenant.id,
        purchase_order.id,
        PurchaseOrderReceive(
            line_id=line.id,
            quantity=Decimal(8),
            idempotency_key="PO-RECEIVE-FULL-KEY-1",
        ),
    )
    first_status = first_result.status

    second_result = receive_purchase_order(
        db,
        tenant.id,
        purchase_order.id,
        PurchaseOrderReceive(
            line_id=line.id,
            quantity=Decimal(12),
            idempotency_key="PO-RECEIVE-FULL-KEY-2",
        ),
    )

    balance = db.query(InventoryBalance).filter_by(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
    ).one()

    db.refresh(line)

    assert first_status == "PARTIALLY_RECEIVED"
    assert second_result.status == "RECEIVED"
    assert line.received_quantity == Decimal("20.000")
    assert balance.on_hand == Decimal("20.000")
    assert balance.inbound == Decimal("0.000")
    assert balance.version == 3




def test_purchase_order_rejects_over_receiving(db):
    tenant = make_tenant(db, "PO-RECEIVE-OVER")
    supplier = make_supplier(db, tenant.id, "SUP-RECEIVE-OVER")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-RECEIVE-SKU-OVER")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)
    approve_purchase_order(db, tenant.id, purchase_order.id)
    submit_purchase_order(db, tenant.id, purchase_order.id)

    line = purchase_order.lines[0]

    with pytest.raises(HTTPException) as exc_info:
        receive_purchase_order(
            db,
            tenant.id,
            purchase_order.id,
            PurchaseOrderReceive(
                line_id=line.id,
                quantity=Decimal(21),
                idempotency_key="PO-RECEIVE-OVER-KEY",
            ),
        )

    assert exc_info.value.status_code == 409

    balance = db.query(InventoryBalance).filter_by(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
    ).one()

    db.refresh(line)

    assert line.received_quantity == Decimal("0.000")
    assert balance.on_hand == Decimal("0.000")
    assert balance.inbound == Decimal("20.000")
    assert balance.version == 1

    transaction_count = db.query(InventoryTransaction).filter_by(
        tenant_id=tenant.id,
        idempotency_key="PO-RECEIVE-OVER-KEY",
    ).count()

    assert transaction_count == 0


def test_draft_purchase_order_rejects_receiving(db):
    tenant = make_tenant(db, "PO-RECEIVE-DRAFT")
    supplier = make_supplier(db, tenant.id, "SUP-RECEIVE-DRAFT")
    location = make_location(db, tenant.id)
    product = make_product(db, tenant.id, "PO-RECEIVE-SKU-DRAFT")
    supplier_item = make_supplier_product(
        db, tenant.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant.id, payload)
    line = purchase_order.lines[0]

    with pytest.raises(HTTPException) as exc_info:
        receive_purchase_order(
            db,
            tenant.id,
            purchase_order.id,
            PurchaseOrderReceive(
                line_id=line.id,
                quantity=Decimal(5),
                idempotency_key="PO-RECEIVE-DRAFT-KEY",
            ),
        )

    assert exc_info.value.status_code == 409

    balance = db.query(InventoryBalance).filter_by(
        tenant_id=tenant.id,
        location_id=location.id,
        product_id=product.id,
    ).one_or_none()

    assert balance is None
    assert line.received_quantity == Decimal("0.000")

    transaction_count = db.query(InventoryTransaction).filter_by(
        tenant_id=tenant.id,
        idempotency_key="PO-RECEIVE-DRAFT-KEY",
    ).count()

    assert transaction_count == 0


def test_tenant_cannot_receive_another_tenants_purchase_order(db):
    tenant_a = make_tenant(db, "PO-RECEIVE-TENANT-A")
    supplier = make_supplier(db, tenant_a.id, "SUP-RECEIVE-TENANT-A")
    location = make_location(db, tenant_a.id)
    product = make_product(db, tenant_a.id, "PO-RECEIVE-SKU-TENANT-A")
    supplier_item = make_supplier_product(
        db, tenant_a.id, supplier.id, product.id
    )

    payload = make_payload(
        supplier.id,
        location.id,
        product.id,
        supplier_item.id,
    )

    purchase_order = create_purchase_order(db, tenant_a.id, payload)
    approve_purchase_order(db, tenant_a.id, purchase_order.id)
    submit_purchase_order(db, tenant_a.id, purchase_order.id)

    line = purchase_order.lines[0]
    tenant_b = make_tenant(db, "PO-RECEIVE-TENANT-B")

    with pytest.raises(HTTPException) as exc_info:
        receive_purchase_order(
            db,
            tenant_b.id,
            purchase_order.id,
            PurchaseOrderReceive(
                line_id=line.id,
                quantity=Decimal(5),
                idempotency_key="PO-RECEIVE-CROSS-TENANT-KEY",
            ),
        )

    assert exc_info.value.status_code == 404

    balance = db.query(InventoryBalance).filter_by(
        tenant_id=tenant_a.id,
        location_id=location.id,
        product_id=product.id,
    ).one()

    assert balance.on_hand == Decimal("0.000")
    assert balance.inbound == Decimal("20.000")

    transaction_count = db.query(InventoryTransaction).filter_by(
        tenant_id=tenant_a.id,
        idempotency_key="PO-RECEIVE-CROSS-TENANT-KEY",
    ).count()

    assert transaction_count == 0
