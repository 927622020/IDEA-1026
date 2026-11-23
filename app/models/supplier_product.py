
"""Supplier-specific purchasing details for products."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SupplierProduct(Base):
    __tablename__ = "supplier_products"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "supplier_id",
            "product_id",
            name="uq_supplier_products_tenant_supplier_product",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_supplier_products_nonnegative_cost",
        ),
        CheckConstraint(
            "lead_time_days >= 0",
            name="ck_supplier_products_nonnegative_lead_time",
        ),
        CheckConstraint(
            "minimum_order_quantity > 0",
            name="ck_supplier_products_positive_moq",
        ),
        CheckConstraint(
            "pack_size > 0",
            name="ck_supplier_products_positive_pack_size",
        ),
        Index(
            "uq_supplier_products_preferred",
            "tenant_id",
            "product_id",
            unique=True,
            postgresql_where=text("is_preferred = true AND is_active = true"),
            sqlite_where=text("is_preferred = 1 AND is_active = 1"),
        ),
        Index(
            "ix_supplier_products_tenant_product",
            "tenant_id",
            "product_id",
        ),
        Index(
            "ix_supplier_products_tenant_supplier",
            "tenant_id",
            "supplier_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    supplier_sku: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    lead_time_days: Mapped[int] = mapped_column(
        nullable=False,
    )

    minimum_order_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    pack_size: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    is_preferred: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    supplier = relationship("Supplier")
    product = relationship("Product")
