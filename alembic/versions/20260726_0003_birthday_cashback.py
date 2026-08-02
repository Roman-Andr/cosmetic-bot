"""Record the source of each historical cashback calculation.

Revision ID: 20260726_0003
Revises: 20260725_0002
Create Date: 2026-07-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260726_0003"
down_revision: str | Sequence[str] | None = "20260725_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


cashback_source = postgresql.ENUM("tier", "birthday", name="cashback_source", create_type=False)


def upgrade() -> None:
    cashback_source.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "purchases",
        sa.Column(
            "cashback_source",
            cashback_source,
            nullable=False,
            server_default="tier",
        ),
    )
    op.alter_column("purchases", "cashback_source", server_default=None)


def downgrade() -> None:
    op.drop_column("purchases", "cashback_source")
    cashback_source.drop(op.get_bind(), checkfirst=True)
