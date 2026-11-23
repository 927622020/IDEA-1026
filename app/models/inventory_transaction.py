from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    __table_args__ = (
        Index(
            "ix_inventory_tx_tenant_product_created",
            "tenant_id",
            "product_id",
            "created_at",
        ),
        Index(
            "ix_inventory_tx_tenant_location_created",
            "tenant_id",
            "location_id",
            "created_at",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_inventory_tx_tenant_idempotency",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )

    reference: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
