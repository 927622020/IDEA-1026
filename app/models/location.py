
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "location_code", name="uq_locations_tenant_code"),
        Index("ix_locations_tenant_name", "tenant_id", "location_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_code: Mapped[str] = mapped_column(String(50), nullable=False)
    location_name: Mapped[str] = mapped_column(String(160), nullable=False)
    location_type: Mapped[str] = mapped_column(String(30), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(
    String(64),
    nullable=False,
    default="UTC",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(UTC)
    )

    tenant = relationship("Tenant")
