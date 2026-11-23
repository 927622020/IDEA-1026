from decimal import Decimal


def calculate_replenishment_quantity(
    *,
    forecast_demand: Decimal,
    safety_stock: Decimal,
    available_inventory: Decimal,
    confirmed_inbound: Decimal,
) -> Decimal:
    """Return the replenishment quantity before pack-size/MOQ constraints.

    Inputs must be non-negative. Reservations and inventory quality adjustments
    should be incorporated into the definition of available_inventory upstream.
    """
    values = (forecast_demand, safety_stock, available_inventory, confirmed_inbound)
    if any(value < 0 for value in values):
        raise ValueError("Replenishment inputs must be non-negative.")

    required = forecast_demand + safety_stock - available_inventory - confirmed_inbound
    return max(Decimal(0), required)

from decimal import ROUND_CEILING


def calculate_supplier_order_quantity(
    *,
    required_quantity: Decimal,
    minimum_order_quantity: Decimal,
    pack_size: Decimal,
) -> Decimal:
    """Apply supplier MOQ and pack-size constraints to a required quantity."""

    if required_quantity < 0:
        raise ValueError("Required quantity must be non-negative.")

    if minimum_order_quantity <= 0:
        raise ValueError("Minimum order quantity must be positive.")

    if pack_size <= 0:
        raise ValueError("Pack size must be positive.")

    if required_quantity == 0:
        return Decimal(0)

    order_quantity = max(required_quantity, minimum_order_quantity)

    packs = (order_quantity / pack_size).to_integral_value(
        rounding=ROUND_CEILING
    )

    return packs * pack_size
