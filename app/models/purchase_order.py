"""Purchase order and purchase order line models."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "po_number",
            name="uq_purchase_orders_tenant_number",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_purchase_orders_tenant_idempotency",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'APPROVED', 'SUBMITTED', "
            "'PARTIALLY_RECEIVED', 'RECEIVED')",
            name="ck_purchase_orders_valid_status",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_purchase_orders_nonnegative_total",
        ),
        Index(
            "ix_purchase_orders_tenant_supplier",
            "tenant_id",
            "supplier_id",
        ),
        Index(
            "ix_purchase_orders_tenant_status",
            "tenant_id",
            "status",
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

    location_id: Mapped[UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    po_number: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="DRAFT",
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(16, 4),
        nullable=False,
        default=Decimal(0),
    )

    expected_delivery_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    external_reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
    location = relationship("Location")
    lines = relationship(
        "PurchaseOrderLine",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    __table_args__ = (
        UniqueConstraint(
            "purchase_order_id",
            "product_id",
            name="uq_purchase_order_lines_order_product",
        ),
        CheckConstraint(
            "ordered_quantity > 0",
            name="ck_purchase_order_lines_positive_ordered_quantity",
        ),
        CheckConstraint(
            "received_quantity >= 0",
            name="ck_purchase_order_lines_nonnegative_received_quantity",
        ),
        CheckConstraint(
            "received_quantity <= ordered_quantity",
            name="ck_purchase_order_lines_received_not_exceed_ordered",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="ck_purchase_order_lines_nonnegative_unit_cost",
        ),
        CheckConstraint(
            "line_total >= 0",
            name="ck_purchase_order_lines_nonnegative_total",
        ),
        Index(
            "ix_purchase_order_lines_product",
            "product_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    supplier_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    supplier_sku: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    ordered_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    received_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal(0),
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(16, 4),
        nullable=False,
    )

    purchase_order = relationship(
        "PurchaseOrder",
        back_populates="lines",
    )
    product = relationship("Product")
    supplier_product = relationship("SupplierProduct")
