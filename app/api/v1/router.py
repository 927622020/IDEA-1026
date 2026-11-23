
from fastapi import APIRouter

from app.api.v1.endpoints import (
    demand,
    health,
    inventory,
    locations,
    products,
    purchase_orders,
    replenishment,
    sales,
    stockout,
    supplier_products,
    suppliers,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(replenishment.router, prefix="/replenishment", tags=["replenishment"])
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(sales.router, prefix="/sales", tags=["sales"])
api_router.include_router(demand.router, prefix="/demand", tags=["demand"])
api_router.include_router(
    stockout.router,
    prefix="/stockout",
    tags=["stockout"],
)
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["suppliers"])
api_router.include_router(
    supplier_products.router,
    prefix="/supplier-products",
    tags=["supplier-products"],
)
api_router.include_router(
    purchase_orders.router,
    prefix="/purchase-orders",
    tags=["purchase-orders"],
)
