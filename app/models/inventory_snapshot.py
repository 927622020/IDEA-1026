from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "location_id",
            "product_id",
            "snapshot_date",
            name="uq_inventory_snapshot_daily",
        ),
        CheckConstraint(
            "on_hand >= 0",
            name="ck_inventory_snapshot_on_hand_nonnegative",
        ),
        CheckConstraint(
            "reserved >= 0",
            name="ck_inventory_snapshot_reserved_nonnegative",
        ),
        CheckConstraint(
            "available >= 0",
            name="ck_inventory_snapshot_available_nonnegative",
        ),
        CheckConstraint(
            "inbound >= 0",
            name="ck_inventory_snapshot_inbound_nonnegative",
        ),
        CheckConstraint(
            "reserved <= on_hand",
            name="ck_inventory_snapshot_reserved_lte_on_hand",
        ),
        CheckConstraint(
            "available = on_hand - reserved",
            name="ck_inventory_snapshot_available_matches",
        ),
        Index(
            "ix_inventory_snapshots_tenant_product_date",
            "tenant_id",
            "product_id",
            "snapshot_date",
        ),
        Index(
            "ix_inventory_snapshots_tenant_location_date",
            "tenant_id",
            "location_id",
            "snapshot_date",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    snapshot_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    on_hand: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )
    reserved: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )
    available: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )
    inbound: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    is_stockout: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    product = relationship("Product")
    location = relationship("Location")
