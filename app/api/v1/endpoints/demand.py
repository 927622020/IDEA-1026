
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.schemas.demand import DailyDemandRead
from app.services.demand_service import get_daily_demand

router = APIRouter()


@router.get("/daily", response_model=list[DailyDemandRead])
def read_daily_demand(
    location_id: UUID,
    product_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    return get_daily_demand(
        db,
        tenant_id,
        location_id=location_id,
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
    )
