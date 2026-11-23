from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SalesRecord(Base):
    __tablename__ = "sales_records"

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sales_records_quantity_positive"),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_sales_records_tenant_idempotency",
        ),
        Index(
            "ix_sales_tenant_product_sold",
            "tenant_id",
            "product_id",
            "sold_at",
        ),
        Index(
            "ix_sales_tenant_location_sold",
            "tenant_id",
            "location_id",
            "sold_at",
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

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    sold_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    external_reference: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
