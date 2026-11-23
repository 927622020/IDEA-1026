"""Supplier model for purchase order management."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "supplier_code",
            name="uq_suppliers_tenant_code",
        ),
        CheckConstraint(
            "default_lead_time_days >= 0",
            name="ck_suppliers_nonnegative_lead_time",
        ),
        Index("ix_suppliers_tenant_name", "tenant_id", "supplier_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    supplier_code: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    supplier_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    contact_person: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    default_lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
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

    tenant = relationship("Tenant")
