from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.integrations.erp.interfaces import ErpPurchaseOrderRequest
from app.integrations.erp.mock.adapter import MockErpAdapter
from app.models import (
    InventoryBalance,
    InventoryTransaction,
    Location,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Supplier,
    SupplierProduct,
    Tenant,
)
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderReceive,
)
from app.services.inventory_service import _get_balance

erp_adapter = MockErpAdapter()

def require_active_tenant(db: Session, tenant_id: UUID) -> None:
    tenant = db.scalar(
        select(Tenant).where(
            Tenant.id == tenant_id,
            Tenant.is_active.is_(True),
        )
    )
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active tenant not found.",
        )


def create_purchase_order(
    db: Session,
    tenant_id: UUID,
    payload: PurchaseOrderCreate,
) -> PurchaseOrder:
    require_active_tenant(db, tenant_id)

    # Return the original PO when this request was already processed.
    existing = db.scalar(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(
            PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        return existing

    supplier = db.scalar(
        select(Supplier).where(
            Supplier.id == payload.supplier_id,
            Supplier.tenant_id == tenant_id,
            Supplier.is_active.is_(True),
        )
    )
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active supplier not found for this tenant.",
        )

    location = db.scalar(
        select(Location).where(
            Location.id == payload.location_id,
            Location.tenant_id == tenant_id,
            Location.is_active.is_(True),
        )
    )
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active location not found for this tenant.",
        )

    prepared_lines = []
    total_amount = 0

    # Reject duplicate products in the same PO.
    product_ids = [line.product_id for line in payload.lines]
    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A product can appear only once in a purchase order.",
        )

    for requested_line in payload.lines:
        product = db.scalar(
            select(Product).where(
                Product.id == requested_line.product_id,
                Product.tenant_id == tenant_id,
                Product.is_active.is_(True),
            )
        )
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active product not found for this tenant.",
            )

        supplier_item = db.scalar(
            select(SupplierProduct).where(
                SupplierProduct.id == requested_line.supplier_product_id,
                SupplierProduct.tenant_id == tenant_id,
                SupplierProduct.supplier_id == supplier.id,
                SupplierProduct.product_id == product.id,
                SupplierProduct.is_active.is_(True),
            )
        )
        if supplier_item is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Supplier catalog item must be active and match "
                    "the selected supplier and product."
                ),
            )

        if supplier_item.currency != payload.currency:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="PO currency must match the supplier catalog currency.",
            )

        quantity = requested_line.ordered_quantity
        unit_cost = supplier_item.unit_cost
        line_total = quantity * unit_cost
        total_amount += line_total

        prepared_lines.append(
            {
                "product_id": product.id,
                "supplier_product_id": supplier_item.id,
                "supplier_sku": supplier_item.supplier_sku,
                "ordered_quantity": quantity,
                "received_quantity": 0,
                "unit_cost": unit_cost,
                "line_total": line_total,
            }
        )

    purchase_order = PurchaseOrder(
        id=uuid4(),
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        location_id=location.id,
        po_number=payload.po_number,
        status="DRAFT",
        currency=payload.currency,
        total_amount=total_amount,
        expected_delivery_date=payload.expected_delivery_date,
        idempotency_key=payload.idempotency_key,
        notes=payload.notes,
    )

    try:
        db.add(purchase_order)
        db.flush()

        for line_data in prepared_lines:
            db.add(
                PurchaseOrderLine(
                    purchase_order_id=purchase_order.id,
                    **line_data,
                )
            )

        db.commit()

    except IntegrityError as exc:
        db.rollback()

        # Handle a concurrent retry with the same idempotency key.
        existing = db.scalar(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .where(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.idempotency_key == payload.idempotency_key,
            )
        )
        if existing is not None:
            return existing

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Purchase order number already exists or conflicts with another record.",
        ) from exc

    db.refresh(purchase_order)
    return purchase_order


def list_purchase_orders(
    db: Session,
    tenant_id: UUID,
    *,
    supplier_id: UUID | None = None,
    location_id: UUID | None = None,
    po_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PurchaseOrder], int]:
    require_active_tenant(db, tenant_id)

    filters = [PurchaseOrder.tenant_id == tenant_id]

    if supplier_id is not None:
        filters.append(PurchaseOrder.supplier_id == supplier_id)

    if location_id is not None:
        filters.append(PurchaseOrder.location_id == location_id)

    if po_status is not None:
        filters.append(PurchaseOrder.status == po_status)

    total = db.scalar(
        select(func.count())
        .select_from(PurchaseOrder)
        .where(*filters)
    ) or 0

    items = list(
        db.scalars(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .where(*filters)
            .order_by(
                PurchaseOrder.created_at.desc(),
                PurchaseOrder.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
    )

    return items, total
def approve_purchase_order(
    db: Session,
    tenant_id: UUID,
    purchase_order_id: UUID,
) -> PurchaseOrder:
    require_active_tenant(db, tenant_id)

    purchase_order = db.scalar(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.tenant_id == tenant_id,
        )
        .with_for_update()
    )

    if purchase_order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found.",
        )

    if purchase_order.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft purchase orders can be approved.",
        )

    purchase_order.status = "APPROVED"
    purchase_order.approved_at = datetime.now(UTC)

    try:
        db.commit()
        db.refresh(purchase_order)
    except Exception:
        db.rollback()
        raise

    return purchase_order
def submit_purchase_order(
    db: Session,
    tenant_id: UUID,
    purchase_order_id: UUID,
) -> PurchaseOrder:
    require_active_tenant(db, tenant_id)

    purchase_order = db.scalar(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.lines),
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.location),
        )
        .where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.tenant_id == tenant_id,
        )
        .with_for_update()
    )

    if purchase_order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found.",
        )

    # A retry after successful submission must not add inbound stock again.
    if purchase_order.status == "SUBMITTED":
        return purchase_order

    if purchase_order.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only approved purchase orders can be submitted.",
        )

    if not purchase_order.lines:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Purchase order has no lines.",
        )

    erp_request = ErpPurchaseOrderRequest(
        idempotency_key=(
            f"purchase-order:{tenant_id}:{purchase_order.id}"
        ),
        po_number=purchase_order.po_number,
        supplier_code=purchase_order.supplier.supplier_code,
        supplier_name=purchase_order.supplier.supplier_name,
        destination_location=purchase_order.location.location_code,
        currency=purchase_order.currency,
        lines=[
            {
                "supplier_sku": line.supplier_sku,
                "quantity": line.ordered_quantity,
                "unit_cost": line.unit_cost,
            }
            for line in purchase_order.lines
        ],
    )

    try:
        # Submit to the ERP first. Its idempotency key makes retries safe.
        erp_result = erp_adapter.submit_purchase_order(erp_request)

        # Record ordered quantities as inbound, not on-hand stock.
        for line in purchase_order.lines:
            balance = db.scalar(
                select(InventoryBalance)
                .where(
                    InventoryBalance.tenant_id == tenant_id,
                    InventoryBalance.location_id == purchase_order.location_id,
                    InventoryBalance.product_id == line.product_id,
                )
                .with_for_update()
            )

            if balance is None:
                balance = InventoryBalance(
                    tenant_id=tenant_id,
                    location_id=purchase_order.location_id,
                    product_id=line.product_id,
                    on_hand=0,
                    reserved=0,
                    inbound=0,
                    version=0,
                )
                db.add(balance)
                db.flush()

            balance.inbound += line.ordered_quantity
            balance.version += 1
            balance.updated_at = datetime.now(UTC)

        purchase_order.external_reference = erp_result.external_document_id
        purchase_order.status = "SUBMITTED"
        purchase_order.submitted_at = erp_result.created_at

        db.commit()
        db.refresh(purchase_order)

    except Exception:
        db.rollback()
        raise

    return purchase_order


def receive_purchase_order(
    db: Session,
    tenant_id: UUID,
    purchase_order_id: UUID,
    payload: PurchaseOrderReceive,
) -> PurchaseOrder:
    require_active_tenant(db, tenant_id)

    purchase_order = db.scalar(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.tenant_id == tenant_id,
        )
        .with_for_update()
    )

    if purchase_order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found.",
        )

    line = next(
        (
            item
            for item in purchase_order.lines
            if item.id == payload.line_id
        ),
        None,
    )

    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order line not found.",
        )

    reference = (
        f"PO:{purchase_order.id}:LINE:{line.id}"
    )

    try:
        existing = db.scalar(
            select(InventoryTransaction).where(
                InventoryTransaction.tenant_id == tenant_id,
                InventoryTransaction.idempotency_key
                == payload.idempotency_key,
            )
        )

        if existing is not None:
            if (
                existing.transaction_type != "RECEIVE"
                or existing.location_id != purchase_order.location_id
                or existing.product_id != line.product_id
                or existing.quantity != payload.quantity
                or existing.reference != reference
                or existing.notes != payload.notes
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Idempotency key was already used "
                        "for a different receiving request."
                    ),
                )

            db.refresh(purchase_order)
            return purchase_order

        if purchase_order.status not in (
            "SUBMITTED",
            "PARTIALLY_RECEIVED",
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only submitted or partially received "
                    "purchase orders can receive goods."
                ),
            )

        outstanding = (
            line.ordered_quantity - line.received_quantity
        )

        if payload.quantity > outstanding:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Received quantity exceeds outstanding "
                    f"quantity ({outstanding})."
                ),
            )

        balance = _get_balance(
            db,
            tenant_id,
            purchase_order.location_id,
            line.product_id,
        )

        if balance.inbound < payload.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inbound inventory is insufficient.",
            )

        now = datetime.now(UTC)

        balance.on_hand += payload.quantity
        balance.inbound -= payload.quantity
        balance.version += 1
        balance.updated_at = now

        line.received_quantity += payload.quantity

        transaction = InventoryTransaction(
            tenant_id=tenant_id,
            location_id=purchase_order.location_id,
            product_id=line.product_id,
            transaction_type="RECEIVE",
            quantity=payload.quantity,
            reference=reference,
            idempotency_key=payload.idempotency_key,
            notes=payload.notes,
        )
        db.add(transaction)

        if all(
            item.received_quantity == item.ordered_quantity
            for item in purchase_order.lines
        ):
            purchase_order.status = "RECEIVED"
        else:
            purchase_order.status = "PARTIALLY_RECEIVED"

        purchase_order.updated_at = now

        db.commit()
        db.refresh(purchase_order)

    except IntegrityError:
        db.rollback()

        existing = db.scalar(
            select(InventoryTransaction).where(
                InventoryTransaction.tenant_id == tenant_id,
                InventoryTransaction.idempotency_key
                == payload.idempotency_key,
            )
        )

        if (
            existing is not None
            and existing.transaction_type == "RECEIVE"
            and existing.location_id == purchase_order.location_id
            and existing.product_id == line.product_id
            and existing.quantity == payload.quantity
            and existing.reference == reference
            and existing.notes == payload.notes
        ):
            return db.scalar(
                select(PurchaseOrder)
                .options(selectinload(PurchaseOrder.lines))
                .where(
                    PurchaseOrder.id == purchase_order_id,
                    PurchaseOrder.tenant_id == tenant_id,
                )
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Receiving request conflicts with an existing transaction.",
        ) from None

    except Exception:
        db.rollback()
        raise

    return purchase_order
