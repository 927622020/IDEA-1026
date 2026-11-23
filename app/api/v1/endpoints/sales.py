
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.schemas.sales import SalesCreate, SalesPage, SalesRead
from app.services import sales_service

router = APIRouter()


@router.post(
    "",
    response_model=SalesRead,
    status_code=status.HTTP_201_CREATED,
)
def create_sale(
    payload: SalesCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return sales_service.create_sale(db, tenant_id, payload)
@router.post(
    "/checkout",
    response_model=SalesRead,
    status_code=status.HTTP_201_CREATED,
)
def checkout_sale(
    payload: SalesCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return sales_service.checkout_sale(db, tenant_id, payload)

@router.get("", response_model=SalesPage)
def get_sales(
    product_id: UUID | None = Query(default=None),
    location_id: UUID | None = Query(default=None),
    sold_from: datetime | None = Query(default=None),
    sold_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    if sold_from is not None and sold_to is not None and sold_from > sold_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="sold_from must be earlier than or equal to sold_to",
        )

    items, total = sales_service.list_sales(
        db,
        tenant_id,
        product_id=product_id,
        location_id=location_id,
        sold_from=sold_from,
        sold_to=sold_to,
        limit=limit,
        offset=offset,
    )

    return SalesPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
