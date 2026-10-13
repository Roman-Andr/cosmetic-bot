"""Expire bonus lots, record debit allocations and add promotion campaigns.

Every existing credit receives a six-month validity counted from this migration, so no
customer loses bonuses at release. Historical redemptions are allocated to the credits
they consumed in chronological order, and the migration aborts if the resulting lot
remainders do not add up to each account's balance.

Revision ID: 20261013_0004
Revises: 20260726_0003
Create Date: 2026-10-13
"""

import uuid
from collections import deque
from collections.abc import Sequence
from decimal import Decimal

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261013_0004"
down_revision: str | Sequence[str] | None = "20260726_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


campaign_status = postgresql.ENUM(
    "scheduled", "completed", "cancelled", name="campaign_status", create_type=False
)


def upgrade() -> None:
    # New enum values are only added here; nothing below uses them in this transaction.
    op.execute("ALTER TYPE bonus_operation_type ADD VALUE IF NOT EXISTS 'expiration'")
    op.execute("ALTER TYPE bonus_operation_type ADD VALUE IF NOT EXISTS 'promotion'")

    campaign_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "promotion_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("photo_file_id", sa.String(length=255)),
        sa.Column("bonus_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("bonus_valid_until", sa.Date()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", campaign_status, nullable=False, server_default="scheduled"),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("recipients_count", sa.Integer()),
        sa.Column("launched_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("bonus_amount >= 0", name="campaign_bonus_nonnegative"),
        sa.CheckConstraint(
            "bonus_amount = 0 OR bonus_valid_until IS NOT NULL",
            name="campaign_bonus_has_validity",
        ),
    )
    op.create_index("ix_promotion_campaigns_starts_at", "promotion_campaigns", ["starts_at"])

    op.add_column("bonus_transactions", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.add_column("bonus_transactions", sa.Column("campaign_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "bonus_transactions_campaign_id_fkey",
        "bonus_transactions",
        "promotion_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_bonus_transactions_expires_at", "bonus_transactions", ["expires_at"])

    op.create_table(
        "bonus_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("debit_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credit_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name="bonus_allocation_positive"),
        sa.ForeignKeyConstraint(["debit_transaction_id"], ["bonus_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["credit_transaction_id"], ["bonus_transactions.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_bonus_allocations_debit_transaction_id", "bonus_allocations", ["debit_transaction_id"]
    )
    op.create_index(
        "ix_bonus_allocations_credit_transaction_id", "bonus_allocations", ["credit_transaction_id"]
    )

    op.add_column("notification_outbox", sa.Column("photo_file_id", sa.String(length=255)))
    op.add_column("notification_outbox", sa.Column("dedupe_key", sa.String(length=200)))
    op.create_unique_constraint(
        "notification_outbox_dedupe_key_key", "notification_outbox", ["dedupe_key"]
    )

    # Existing credits stay spendable through the same Minsk day six months from release.
    op.execute(
        """
        UPDATE bonus_transactions
        SET expires_at = (
            (((now() AT TIME ZONE 'Europe/Minsk')::date + interval '6 months')::date + 1)::timestamp
            AT TIME ZONE 'Europe/Minsk'
        )
        WHERE amount > 0
        """
    )
    _backfill_allocations(op.get_bind())
    _verify_lots_match_balances(op.get_bind())

    op.create_check_constraint(
        "bonus_transaction_credit_expiry",
        "bonus_transactions",
        "(amount > 0) = (expires_at IS NOT NULL)",
    )
    op.create_index(
        "uq_bonus_transaction_campaign_account",
        "bonus_transactions",
        ["campaign_id", "account_id"],
        unique=True,
        postgresql_where=sa.text("campaign_id IS NOT NULL"),
    )


def _backfill_allocations(bind: sa.Connection) -> None:
    """Replay each account's ledger, charging every debit to its oldest open credits."""
    rows = bind.execute(
        sa.text(
            """
            SELECT id, account_id, amount
            FROM bonus_transactions
            -- A purchase writes its redemption and accrual with one timestamp; the
            -- redemption was computed from the earlier balance, so debits go first.
            ORDER BY account_id, created_at, amount > 0, id
            """
        )
    ).all()
    open_lots: dict[uuid.UUID, deque[list[object]]] = {}
    allocations: list[dict[str, object]] = []
    for transaction_id, account_id, amount in rows:
        lots = open_lots.setdefault(account_id, deque())
        if amount > 0:
            lots.append([transaction_id, amount])
            continue
        outstanding: Decimal = -amount
        while outstanding > 0:
            if not lots:
                raise RuntimeError(
                    f"Account {account_id} debited more bonuses than it was credited"
                )
            lot = lots[0]
            lot_remaining: Decimal = lot[1]  # type: ignore[assignment]
            portion = min(lot_remaining, outstanding)
            allocations.append(
                {
                    "id": uuid.uuid4(),
                    "debit": transaction_id,
                    "credit": lot[0],
                    "amount": portion,
                }
            )
            lot[1] = lot_remaining - portion
            outstanding -= portion
            if lot[1] == 0:
                lots.popleft()
    if allocations:
        bind.execute(
            sa.text(
                """
                INSERT INTO bonus_allocations
                    (id, debit_transaction_id, credit_transaction_id, amount)
                VALUES (:id, :debit, :credit, :amount)
                """
            ),
            allocations,
        )


def _verify_lots_match_balances(bind: sa.Connection) -> None:
    """Abort the release if open lot remainders disagree with any account balance."""
    mismatched = bind.execute(
        sa.text(
            """
            SELECT account.id
            FROM loyalty_accounts AS account
            LEFT JOIN (
                SELECT credit.account_id,
                       credit.amount - COALESCE(SUM(allocation.amount), 0) AS remaining
                FROM bonus_transactions AS credit
                LEFT JOIN bonus_allocations AS allocation
                    ON allocation.credit_transaction_id = credit.id
                WHERE credit.amount > 0
                GROUP BY credit.id
            ) AS lot ON lot.account_id = account.id
            GROUP BY account.id, account.current_balance
            HAVING account.current_balance <> COALESCE(SUM(lot.remaining), 0)
            """
        )
    ).all()
    if mismatched:
        accounts = ", ".join(str(row[0]) for row in mismatched[:10])
        raise RuntimeError(
            f"{len(mismatched)} loyalty account balance(s) disagree with the bonus ledger: "
            f"{accounts}"
        )


def downgrade() -> None:
    op.drop_index("uq_bonus_transaction_campaign_account", table_name="bonus_transactions")
    op.drop_constraint("bonus_transaction_credit_expiry", "bonus_transactions", type_="check")
    op.drop_constraint("notification_outbox_dedupe_key_key", "notification_outbox", type_="unique")
    op.drop_column("notification_outbox", "dedupe_key")
    op.drop_column("notification_outbox", "photo_file_id")
    op.drop_index("ix_bonus_allocations_credit_transaction_id", table_name="bonus_allocations")
    op.drop_index("ix_bonus_allocations_debit_transaction_id", table_name="bonus_allocations")
    op.drop_table("bonus_allocations")
    op.drop_index("ix_bonus_transactions_expires_at", table_name="bonus_transactions")
    op.drop_constraint("bonus_transactions_campaign_id_fkey", "bonus_transactions", type_="foreignkey")
    op.drop_column("bonus_transactions", "campaign_id")
    op.drop_column("bonus_transactions", "expires_at")
    op.drop_index("ix_promotion_campaigns_starts_at", table_name="promotion_campaigns")
    op.drop_table("promotion_campaigns")
    campaign_status.drop(op.get_bind(), checkfirst=True)
    # PostgreSQL cannot drop enum values. Rebuilding the type fails, and so aborts the
    # downgrade, while expiration or promotion rows exist: ledger rows are never discarded.
    op.execute("ALTER TYPE bonus_operation_type RENAME TO bonus_operation_type_old")
    op.execute("CREATE TYPE bonus_operation_type AS ENUM ('accrual', 'redemption')")
    op.execute(
        "ALTER TABLE bonus_transactions ALTER COLUMN operation_type TYPE bonus_operation_type "
        "USING operation_type::text::bonus_operation_type"
    )
    op.execute("DROP TYPE bonus_operation_type_old")
