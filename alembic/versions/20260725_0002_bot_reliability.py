"""Add persistent support and notification delivery state.

Revision ID: 20260725_0002
Revises: 20260725_0001
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260725_0002"
down_revision: str | Sequence[str] | None = "20260725_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


support_dialog_status = postgresql.ENUM(
    "open", "closed", name="support_dialog_status", create_type=False
)


def upgrade() -> None:
    support_dialog_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "support_dialogs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("product_external_id", sa.String(length=128)),
        sa.Column("status", support_dialog_status, nullable=False, server_default="open"),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_support_dialogs_customer_telegram_id", "support_dialogs", ["customer_telegram_id"])
    op.create_table(
        "support_forwards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dialog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_message_id", sa.Integer(), nullable=False),
        sa.Column("customer_message_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["dialog_id"], ["support_dialogs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_message_id"),
    )
    op.create_table(
        "blocked_users",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("blocked_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "notification_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_notification_outbox_chat_id", "notification_outbox", ["chat_id"])
    op.create_index("ix_notification_outbox_sent_at", "notification_outbox", ["sent_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_sent_at", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_chat_id", table_name="notification_outbox")
    op.drop_table("notification_outbox")
    op.drop_table("blocked_users")
    op.drop_table("support_forwards")
    op.drop_index("ix_support_dialogs_customer_telegram_id", table_name="support_dialogs")
    op.drop_table("support_dialogs")
    support_dialog_status.drop(op.get_bind(), checkfirst=True)
