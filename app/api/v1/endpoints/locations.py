from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.schemas.location import LocationCreate, LocationPage, LocationRead
from app.services import location_service

router = APIRouter()


@router.post("", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
def create_location(
    payload: LocationCreate,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return location_service.create_location(db, tenant_id, payload)


@router.get("", response_model=LocationPage)
def list_locations(
    search: str | None = Query(default=None, max_length=120),
    active_only: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    items, total = location_service.list_locations(
        db,
        tenant_id,
        search=search,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return LocationPage(items=items, total=total, limit=limit, offset=offset)
