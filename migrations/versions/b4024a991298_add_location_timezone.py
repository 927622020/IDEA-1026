
"""add location timezone

Revision ID: b4024a991298
Revises: d653c9942b30
Create Date: 2026-11-20 22:09:07.206781
"""

import sqlalchemy as sa
from alembic import op

revision = "b4024a991298"
down_revision = "d653c9942b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the column as nullable first for existing records.
    op.add_column(
        "locations",
        sa.Column("timezone", sa.String(length=64), nullable=True),
    )

    # Give all existing locations a safe default timezone.
    op.execute(
        "UPDATE locations SET timezone = 'UTC' WHERE timezone IS NULL"
    )

    # Enforce the non-null constraint.
    op.alter_column(
        "locations",
        "timezone",
        existing_type=sa.String(length=64),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("locations", "timezone")
