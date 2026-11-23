from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.schemas.product import ProductCreate, ProductPage, ProductRead, ProductUpdate
from app.services import product_service

router = APIRouter()


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return product_service.create_product(db, tenant_id, payload)


@router.get("", response_model=ProductPage)
def list_products(
    search: str | None = Query(default=None, max_length=120),
    active_only: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    items, total = product_service.list_products(
        db, tenant_id, search=search, active_only=active_only, limit=limit, offset=offset
    )
    return ProductPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return product_service.get_product(db, tenant_id, product_id)


@router.put("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return product_service.update_product(db, tenant_id, product_id, payload)


@router.patch("/{product_id}/deactivate", response_model=ProductRead)
def deactivate_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return product_service.deactivate_product(db, tenant_id, product_id)
