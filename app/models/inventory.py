
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InventoryBalance(Base):
    __tablename__ = "inventory_balances"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "location_id", "product_id",
            name="uq_inventory_tenant_location_product",
        ),
        CheckConstraint("on_hand >= 0", name="ck_inventory_on_hand_nonnegative"),
        CheckConstraint("reserved >= 0", name="ck_inventory_reserved_nonnegative"),
        CheckConstraint("inbound >= 0", name="ck_inventory_inbound_nonnegative"),
        CheckConstraint("reserved <= on_hand", name="ck_inventory_reserved_lte_on_hand"),
        Index("ix_inventory_tenant_product", "tenant_id", "product_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )

    on_hand: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal(0)
    )
    reserved: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal(0)
    )
    inbound: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal(0)
    )

    version: Mapped[int] = mapped_column(nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )

    product = relationship("Product")
    location = relationship("Location")

    @property
    def available(self) -> Decimal:
        return self.on_hand - self.reserved
