from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.product_service import require_active_tenant


def get_current_tenant_id(
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
) -> UUID:
    """
    LOCAL DEVELOPMENT ONLY.
    Replace this header-based tenant selector with tenant identity from an
    authenticated principal before production deployment.
    """
    require_active_tenant(db, x_tenant_id)
    return x_tenant_id
