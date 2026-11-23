import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.services.inventory_snapshot_service import (
    capture_inventory_snapshots,
)

logger = logging.getLogger(__name__)


def run_daily_inventory_snapshot_job() -> None:
    """Capture one daily inventory snapshot for every active tenant."""

    discovery_db = SessionLocal()

    try:
        tenant_ids = discovery_db.scalars(
            select(Tenant.id)
            .where(Tenant.is_active.is_(True))
            .order_by(Tenant.id)
        ).all()
    except Exception:
        logger.exception("Failed to retrieve active tenants for snapshots")
        return
    finally:
        discovery_db.close()

    logger.info(
        "Starting daily inventory snapshot job for %s active tenants",
        len(tenant_ids),
    )

    for tenant_id in tenant_ids:
        db = SessionLocal()

        try:
            result = capture_inventory_snapshots(
                db=db,
                tenant_id=tenant_id,
            )

            logger.info(
                "Inventory snapshots completed for tenant %s: "
                "created=%s, skipped=%s, total=%s",
                tenant_id,
                result["created"],
                result["skipped"],
                result["total"],
            )
        except Exception:
            logger.exception(
                "Inventory snapshot capture failed for tenant %s",
                tenant_id,
            )
        finally:
            db.close()

    logger.info("Daily inventory snapshot job finished")


def create_snapshot_scheduler() -> BackgroundScheduler:
    """Create the scheduler for daily inventory snapshots."""

    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        run_daily_inventory_snapshot_job,
        trigger=CronTrigger(
            hour=12,
            minute=5,
            timezone="UTC",
        ),
        id="daily_inventory_snapshot",
        name="Daily inventory snapshot capture",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    return scheduler
