
from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.stockout import StockoutPredictionRequest
from app.services.stockout_service import predict_stockout

TENANT_ID = uuid4()
LOCATION_ID = uuid4()
PRODUCT_ID = uuid4()


@pytest.fixture
def prediction_payload() -> StockoutPredictionRequest:
    return StockoutPredictionRequest(
        location_id=LOCATION_ID,
        product_id=PRODUCT_ID,
        prediction_date=date(2026, 11, 21),
        sales_lag_1=12,
        sales_lag_7=0,
        sales_7d=14,
        sales_14d=14,
        sales_28d=14,
        avg_daily_sales_7d=2,
        available_stock=83,
        day_of_week=5,
    )


@pytest.mark.parametrize(
    ("probability", "expected_risk"),
    [
        (0.10, "low"),
        (0.50, "medium"),
        (0.90, "high"),
    ],
)
def test_predict_stockout_risk_levels(
    prediction_payload: StockoutPredictionRequest,
    probability: float,
    expected_risk: str,
) -> None:
    db = MagicMock()
    db.scalar.side_effect = [LOCATION_ID, PRODUCT_ID]

    model = MagicMock()
    model.predict_proba.return_value = __import__("numpy").array([[1 - probability, probability]])

    with patch(
        "app.services.stockout_service.load_stockout_model",
        return_value=model,
    ):
        result = predict_stockout(
            db=db,
            tenant_id=TENANT_ID,
            payload=prediction_payload,
        )

    assert result.stockout_probability == probability
    assert result.risk_level == expected_risk
    assert result.prediction_horizon_days == 7
    assert result.data_source == "synthetic_demo"
    assert result.is_production_ready is False


def test_predict_stockout_rejects_invalid_location(
    prediction_payload: StockoutPredictionRequest,
) -> None:
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        predict_stockout(db, TENANT_ID, prediction_payload)

    assert exc_info.value.status_code == 404
    assert "location" in exc_info.value.detail.lower()


def test_predict_stockout_rejects_invalid_product(
    prediction_payload: StockoutPredictionRequest,
) -> None:
    db = MagicMock()
    db.scalar.side_effect = [LOCATION_ID, None]

    with pytest.raises(HTTPException) as exc_info:
        predict_stockout(db, TENANT_ID, prediction_payload)

    assert exc_info.value.status_code == 404
    assert "product" in exc_info.value.detail.lower()


def test_predict_stockout_handles_missing_model(
    prediction_payload: StockoutPredictionRequest,
) -> None:
    db = MagicMock()
    db.scalar.side_effect = [LOCATION_ID, PRODUCT_ID]

    with patch(
        "app.services.stockout_service.load_stockout_model",
        side_effect=FileNotFoundError,
    ), pytest.raises(HTTPException) as exc_info:
        predict_stockout(db, TENANT_ID, prediction_payload)

    assert exc_info.value.status_code == 503
    assert "model is unavailable" in exc_info.value.detail
