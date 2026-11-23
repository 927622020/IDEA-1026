from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.schemas.inventory import (
    InventoryOperationCreate,
    InventoryOperationResult,
    InventoryPage,
)
from app.services import inventory_service

router = APIRouter()


def _operate(
    db: Session,
    tenant_id: UUID,
    payload: InventoryOperationCreate,
    transaction_type: str,
):
    return inventory_service.apply_inventory_operation(
        db, tenant_id, payload, transaction_type
    )


@router.post("/receive", response_model=InventoryOperationResult,
             status_code=status.HTTP_200_OK)
def receive_stock(
    payload: InventoryOperationCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return _operate(db, tenant_id, payload, "RECEIVE")


@router.post("/adjust/increase", response_model=InventoryOperationResult)
def increase_stock(
    payload: InventoryOperationCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return _operate(db, tenant_id, payload, "ADJUST_INCREASE")


@router.post("/adjust/decrease", response_model=InventoryOperationResult)
def decrease_stock(
    payload: InventoryOperationCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return _operate(db, tenant_id, payload, "ADJUST_DECREASE")


@router.post("/reserve", response_model=InventoryOperationResult)
def reserve_stock(
    payload: InventoryOperationCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return _operate(db, tenant_id, payload, "RESERVE")


@router.post("/release", response_model=InventoryOperationResult)
def release_stock(
    payload: InventoryOperationCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return _operate(db, tenant_id, payload, "RELEASE")


@router.get("", response_model=InventoryPage)
def get_inventory(
    location_id: UUID | None = None,
    product_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    items, total = inventory_service.list_inventory(
        db,
        tenant_id,
        location_id=location_id,
        product_id=product_id,
        limit=limit,
        offset=offset,
    )
    return InventoryPage(items=items, total=total, limit=limit, offset=offset)
