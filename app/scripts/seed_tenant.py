from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Tenant


def main() -> None:
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.code == "DEMO-BRAND"))
        if tenant is None:
            tenant = Tenant(name="Demo FMCG Brand", code="DEMO-BRAND", is_active=True)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        print(f"Tenant ID: {tenant.id}")
        print("Use this UUID in the X-Tenant-ID request header.")


if __name__ == "__main__":
    main()
