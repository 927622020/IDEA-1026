
"""Stockout prediction API endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id
from app.schemas.stockout import (
    StockoutPredictionRead,
    StockoutPredictionRequest,
)
from app.services.stockout_service import predict_stockout

router = APIRouter()


@router.post("/predict", response_model=StockoutPredictionRead)
def create_stockout_prediction(
    payload: StockoutPredictionRequest,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Predict stockout risk for the next seven days."""

    return predict_stockout(
        db=db,
        tenant_id=tenant_id,
        payload=payload,
    )
