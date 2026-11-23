from decimal import Decimal

import pytest

from app.services.replenishment_service import (
    calculate_replenishment_quantity,
    calculate_supplier_order_quantity,
)


def test_calculates_positive_replenishment_quantity() -> None:
    result = calculate_replenishment_quantity(
        forecast_demand=Decimal(200),
        safety_stock=Decimal(40),
        available_inventory=Decimal(100),
        confirmed_inbound=Decimal(30),
    )
    assert result == Decimal(110)


def test_returns_zero_when_stock_is_sufficient() -> None:
    result = calculate_replenishment_quantity(
        forecast_demand=Decimal(50),
        safety_stock=Decimal(10),
        available_inventory=Decimal(80),
        confirmed_inbound=Decimal(10),
    )
    assert result == Decimal(0)


def test_rejects_negative_inputs() -> None:
    with pytest.raises(ValueError):
        calculate_replenishment_quantity(
            forecast_demand=Decimal(-1),
            safety_stock=Decimal(0),
            available_inventory=Decimal(0),
            confirmed_inbound=Decimal(0),
        )

def test_rounds_order_quantity_to_pack_size() -> None:
    result = calculate_supplier_order_quantity(
        required_quantity=Decimal(23),
        minimum_order_quantity=Decimal(10),
        pack_size=Decimal(5),
    )
    assert result == Decimal(25)


def test_enforces_minimum_order_quantity() -> None:
    result = calculate_supplier_order_quantity(
        required_quantity=Decimal(7),
        minimum_order_quantity=Decimal(10),
        pack_size=Decimal(5),
    )
    assert result == Decimal(10)


def test_returns_zero_when_no_replenishment_is_required() -> None:
    result = calculate_supplier_order_quantity(
        required_quantity=Decimal(0),
        minimum_order_quantity=Decimal(10),
        pack_size=Decimal(5),
    )
    assert result == Decimal(0)


def test_rejects_invalid_supplier_order_values() -> None:
    with pytest.raises(ValueError):
        calculate_supplier_order_quantity(
            required_quantity=Decimal(10),
            minimum_order_quantity=Decimal(0),
            pack_size=Decimal(5),
        )
