from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderPage,
    PurchaseOrderRead,
    PurchaseOrderReceive,
    PurchaseOrderStatus,
)
from app.services import purchase_order_service

router = APIRouter()


@router.post(
    "",
    response_model=PurchaseOrderRead,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return purchase_order_service.create_purchase_order(
        db, tenant_id, payload
    )


@router.get("", response_model=PurchaseOrderPage)
def list_purchase_orders(
    supplier_id: UUID | None = None,
    location_id: UUID | None = None,
    po_status: PurchaseOrderStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    items, total = purchase_order_service.list_purchase_orders(
        db,
        tenant_id,
        supplier_id=supplier_id,
        location_id=location_id,
        po_status=po_status,
        limit=limit,
        offset=offset,
    )

    return PurchaseOrderPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
@router.post(
    "/{purchase_order_id}/approve",
    response_model=PurchaseOrderRead,
)
def approve_purchase_order(
    purchase_order_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return purchase_order_service.approve_purchase_order(
        db,
        tenant_id,
        purchase_order_id,
    )


@router.post(
    "/{purchase_order_id}/submit",
    response_model=PurchaseOrderRead,
)
def submit_purchase_order(
    purchase_order_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return purchase_order_service.submit_purchase_order(
        db, tenant_id, purchase_order_id
    )


@router.post(
    "/{purchase_order_id}/receive",
    response_model=PurchaseOrderRead,
)
def receive_purchase_order(
    purchase_order_id: UUID,
    payload: PurchaseOrderReceive,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return purchase_order_service.receive_purchase_order(
        db,
        tenant_id,
        purchase_order_id,
        payload,
    )
