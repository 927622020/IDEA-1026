
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.schemas.supplier_product import (
    SupplierProductCreate,
    SupplierProductPage,
    SupplierProductRead,
    SupplierProductUpdate,
)
from app.services import supplier_product_service

router = APIRouter()


@router.post(
    "",
    response_model=SupplierProductRead,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_product(
    payload: SupplierProductCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return supplier_product_service.create_supplier_product(
        db, tenant_id, payload
    )


@router.get("", response_model=SupplierProductPage)
def list_supplier_products(
    supplier_id: UUID | None = None,
    product_id: UUID | None = None,
    active_only: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return supplier_product_service.list_supplier_products(
        db,
        tenant_id,
        supplier_id=supplier_id,
        product_id=product_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )


@router.get("/{supplier_product_id}", response_model=SupplierProductRead)
def get_supplier_product(
    supplier_product_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return supplier_product_service.get_supplier_product(
        db, tenant_id, supplier_product_id
    )


@router.put("/{supplier_product_id}", response_model=SupplierProductRead)
def update_supplier_product(
    supplier_product_id: UUID,
    payload: SupplierProductUpdate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return supplier_product_service.update_supplier_product(
        db, tenant_id, supplier_product_id, payload
    )


@router.patch(
    "/{supplier_product_id}/deactivate",
    response_model=SupplierProductRead,
)
def deactivate_supplier_product(
    supplier_product_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return supplier_product_service.deactivate_supplier_product(
        db, tenant_id, supplier_product_id
    )
