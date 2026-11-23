from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Location
from app.schemas.location import LocationCreate
from app.services.product_service import require_active_tenant


def create_location(
    db: Session, tenant_id: UUID, payload: LocationCreate
) -> Location:
    require_active_tenant(db, tenant_id)

    location = Location(tenant_id=tenant_id, **payload.model_dump())
    db.add(location)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A location with this code already exists for this tenant",
        ) from exc

    db.refresh(location)
    return location


def list_locations(
    db: Session,
    tenant_id: UUID,
    *,
    search: str | None,
    active_only: bool,
    limit: int,
    offset: int,
) -> tuple[list[Location], int]:
    require_active_tenant(db, tenant_id)

    filters = [Location.tenant_id == tenant_id]

    if active_only:
        filters.append(Location.is_active.is_(True))

    if search:
        term = f"%{search.strip()}%"
        filters.append(
            Location.location_code.ilike(term)
            | Location.location_name.ilike(term)
            | Location.location_type.ilike(term)
        )

    total = db.scalar(
        select(func.count()).select_from(Location).where(*filters)
    ) or 0

    items = list(
        db.scalars(
            select(Location)
            .where(*filters)
            .order_by(Location.location_name.asc(), Location.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )

    return items, total
