
"""LightGBM stockout prediction service."""

from functools import lru_cache
from pathlib import Path
from uuid import UUID

import joblib
import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.feature_contract import FEATURE_COLUMNS
from app.models.location import Location
from app.models.product import Product
from app.schemas.stockout import (
    StockoutPredictionRead,
    StockoutPredictionRequest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "artifacts" / "stockout_lightgbm.joblib"


@lru_cache(maxsize=1)
def load_stockout_model():
    """Load the trained LightGBM model once."""

    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Stockout model artifact not found: {MODEL_PATH}"
        )

    return joblib.load(MODEL_PATH)


def predict_stockout(
    db: Session,
    tenant_id: UUID,
    payload: StockoutPredictionRequest,
) -> StockoutPredictionRead:
    """Generate a seven-day stockout risk prediction."""

    location = db.scalar(
        select(Location.id).where(
            Location.id == payload.location_id,
            Location.tenant_id == tenant_id,
            Location.is_active.is_(True),
        )
    )

    if location is None:
        raise HTTPException(
            status_code=404,
            detail="Active location not found for this tenant",
        )

    product = db.scalar(
        select(Product.id).where(
            Product.id == payload.product_id,
            Product.tenant_id == tenant_id,
            Product.is_active.is_(True),
        )
    )

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Active product not found for this tenant",
        )

    feature_values = payload.model_dump(
        include=set(FEATURE_COLUMNS)
    )

    features = pd.DataFrame(
        [feature_values],
        columns=FEATURE_COLUMNS,
    )

    try:
        model = load_stockout_model()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Stockout prediction model is unavailable",
        ) from exc

    probability = float(model.predict_proba(features)[0, 1])

    if probability < 0.30:
        risk_level = "low"
    elif probability < 0.70:
        risk_level = "medium"
    else:
        risk_level = "high"

    return StockoutPredictionRead(
        tenant_id=tenant_id,
        location_id=payload.location_id,
        product_id=payload.product_id,
        prediction_date=payload.prediction_date,
        stockout_probability=probability,
        risk_level=risk_level,
    )
