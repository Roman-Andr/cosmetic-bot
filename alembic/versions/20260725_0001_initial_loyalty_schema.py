"""Create loyalty programme schema.

Revision ID: 20260725_0001
Revises:
Create Date: 2026-07-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260725_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


gender = sa.Enum("male", "female", name="gender")
admin_role = sa.Enum("owner", "sales", name="admin_role")
purchase_status = sa.Enum("confirmed", name="purchase_status")
bonus_operation_type = sa.Enum("accrual", "redemption", name="bonus_operation_type")


def upgrade() -> None:
    gender.create(op.get_bind(), checkfirst=True)
    admin_role.create(op.get_bind(), checkfirst=True)
    purchase_status.create(op.get_bind(), checkfirst=True)
    bonus_operation_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(length=255)),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("gender", gender, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("telegram_user_id"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index("ix_customers_telegram_user_id", "customers", ["telegram_user_id"])
    op.create_index("ix_customers_phone", "customers", ["phone"])

    op.create_table(
        "loyalty_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("lifetime_turnover", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("current_balance >= 0", name="loyalty_account_balance_nonnegative"),
        sa.CheckConstraint("lifetime_turnover >= 0", name="loyalty_account_turnover_nonnegative"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("customer_id"),
    )

    op.create_table(
        "loyalty_tier_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("minimum_turnover", sa.Numeric(12, 2), nullable=False),
        sa.Column("cashback_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by_telegram_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("minimum_turnover >= 0", name="tier_rule_turnover_nonnegative"),
        sa.CheckConstraint(
            "cashback_percent >= 0 AND cashback_percent <= 100",
            name="tier_rule_cashback_percent_range",
        ),
        sa.UniqueConstraint("minimum_turnover"),
    )

    op.create_table(
        "admin_users",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("role", admin_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("added_by_telegram_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("current_price", sa.Numeric(12, 2)),
        sa.Column("url", sa.Text()),
        sa.Column("photo_url", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_products_external_id", "products", ["external_id"])
    op.create_index("ix_products_title", "products", ["title"])

    op.create_table(
        "purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recorded_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("status", purchase_status, nullable=False, server_default="confirmed"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("bonus_redeemed", sa.Numeric(12, 2), nullable=False),
        sa.Column("cash_paid", sa.Numeric(12, 2), nullable=False),
        sa.Column("cashback_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("cashback_accrued", sa.Numeric(12, 2), nullable=False),
        sa.Column("tier_minimum_turnover", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("total_amount > 0", name="purchase_total_positive"),
        sa.CheckConstraint("bonus_redeemed >= 0", name="purchase_bonus_nonnegative"),
        sa.CheckConstraint("cash_paid >= 0", name="purchase_cash_nonnegative"),
        sa.CheckConstraint("cashback_accrued >= 0", name="purchase_cashback_nonnegative"),
        sa.ForeignKeyConstraint(["account_id"], ["loyalty_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_purchases_customer_id", "purchases", ["customer_id"])
    op.create_index("ix_purchases_recorded_by_telegram_id", "purchases", ["recorded_by_telegram_id"])
    op.create_index("ix_purchase_created_at", "purchases", ["created_at"])

    op.create_table(
        "purchase_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True)),
        sa.Column("external_product_id", sa.String(length=128), nullable=False),
        sa.Column("title_snapshot", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("purchase_id", "external_product_id", name="purchase_item_unique_product"),
    )

    op.create_table(
        "bonus_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True)),
        sa.Column("operation_type", bonus_operation_type, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount <> 0", name="bonus_transaction_nonzero"),
        sa.ForeignKeyConstraint(["account_id"], ["loyalty_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_bonus_transactions_account_id", "bonus_transactions", ["account_id"])
    op.create_index("ix_bonus_transactions_purchase_id", "bonus_transactions", ["purchase_id"])
    op.create_index("ix_bonus_transaction_created_at", "bonus_transactions", ["created_at"])

    op.create_table(
        "loyalty_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("used_by_telegram_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["loyalty_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("code_digest"),
    )
    op.create_index("ix_loyalty_codes_account_id", "loyalty_codes", ["account_id"])
    op.create_index("ix_loyalty_codes_expires_at", "loyalty_codes", ["expires_at"])
    op.create_index("ix_loyalty_codes_used_at", "loyalty_codes", ["used_at"])

    op.create_table(
        "contact_shares",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("shared_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_telegram_id", sa.BigInteger()),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100)),
        sa.Column("target_id", sa.String(length=100)),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_events_actor_telegram_id", "audit_events", ["actor_telegram_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_telegram_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("contact_shares")
    op.drop_index("ix_loyalty_codes_used_at", table_name="loyalty_codes")
    op.drop_index("ix_loyalty_codes_expires_at", table_name="loyalty_codes")
    op.drop_index("ix_loyalty_codes_account_id", table_name="loyalty_codes")
    op.drop_table("loyalty_codes")
    op.drop_index("ix_bonus_transaction_created_at", table_name="bonus_transactions")
    op.drop_index("ix_bonus_transactions_purchase_id", table_name="bonus_transactions")
    op.drop_index("ix_bonus_transactions_account_id", table_name="bonus_transactions")
    op.drop_table("bonus_transactions")
    op.drop_table("purchase_items")
    op.drop_index("ix_purchase_created_at", table_name="purchases")
    op.drop_index("ix_purchases_recorded_by_telegram_id", table_name="purchases")
    op.drop_index("ix_purchases_customer_id", table_name="purchases")
    op.drop_table("purchases")
    op.drop_index("ix_products_title", table_name="products")
    op.drop_index("ix_products_external_id", table_name="products")
    op.drop_table("products")
    op.drop_table("admin_users")
    op.drop_table("loyalty_tier_rules")
    op.drop_table("loyalty_accounts")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_index("ix_customers_telegram_user_id", table_name="customers")
    op.drop_table("customers")
    bonus_operation_type.drop(op.get_bind(), checkfirst=True)
    purchase_status.drop(op.get_bind(), checkfirst=True)
    admin_role.drop(op.get_bind(), checkfirst=True)
    gender.drop(op.get_bind(), checkfirst=True)
