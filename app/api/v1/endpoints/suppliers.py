from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.schemas.supplier import (
    SupplierCreate,
    SupplierPage,
    SupplierRead,
    SupplierUpdate,
)
from app.services import supplier_service

router = APIRouter()


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return supplier_service.create_supplier(db, tenant_id, payload)


@router.get("", response_model=SupplierPage)
def list_suppliers(
    search: str | None = Query(default=None, max_length=120),
    active_only: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    items, total = supplier_service.list_suppliers(
        db,
        tenant_id,
        search=search,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return SupplierPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return supplier_service.get_supplier(db, tenant_id, supplier_id)


@router.put("/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: UUID,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return supplier_service.update_supplier(db, tenant_id, supplier_id, payload)


@router.patch("/{supplier_id}/deactivate", response_model=SupplierRead)
def deactivate_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return supplier_service.deactivate_supplier(db, tenant_id, supplier_id)
