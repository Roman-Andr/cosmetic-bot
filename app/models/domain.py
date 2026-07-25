"""Persistent domain entities for loyalty, catalogue, roles and audit logs."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin

MONEY = Numeric(12, 2)
PERCENT = Numeric(5, 2)


class Gender(StrEnum):
    """The two gender values requested by the loyalty programme."""

    MALE = "male"
    FEMALE = "female"


class AdminRole(StrEnum):
    """Roles allowed to use the administrative bot interface."""

    OWNER = "owner"
    SALES = "sales"


class PurchaseStatus(StrEnum):
    """A confirmed purchase is immutable in the first MVP."""

    CONFIRMED = "confirmed"


class BonusOperationType(StrEnum):
    """Ledger operation kinds used to derive the available bonus balance."""

    ACCRUAL = "accrual"
    REDEMPTION = "redemption"


class SupportDialogStatus(StrEnum):
    """Lifecycle of a customer support conversation."""

    OPEN = "open"
    CLOSED = "closed"


class Customer(Base, CreatedAtMixin):
    """A Telegram customer registered in the loyalty programme."""

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    telegram_username: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[Gender] = mapped_column(Enum(Gender, name="gender"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    loyalty_account: Mapped[LoyaltyAccount] = relationship(back_populates="customer", uselist=False)
    purchases: Mapped[list[Purchase]] = relationship(back_populates="customer")


class LoyaltyAccount(Base, CreatedAtMixin):
    """Current loyalty projection backed by the immutable transaction ledger."""

    __tablename__ = "loyalty_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    current_balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.00"))
    lifetime_turnover: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.00")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    customer: Mapped[Customer] = relationship(back_populates="loyalty_account")
    transactions: Mapped[list[BonusTransaction]] = relationship(back_populates="account")
    codes: Mapped[list[LoyaltyCode]] = relationship(back_populates="account")

    __table_args__ = (
        CheckConstraint("current_balance >= 0", name="loyalty_account_balance_nonnegative"),
        CheckConstraint("lifetime_turnover >= 0", name="loyalty_account_turnover_nonnegative"),
    )


class LoyaltyTierRule(Base, CreatedAtMixin):
    """Owner-managed tier thresholds and cashback rates."""

    __tablename__ = "loyalty_tier_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    minimum_turnover: Mapped[Decimal] = mapped_column(MONEY, unique=True, nullable=False)
    cashback_percent: Mapped[Decimal] = mapped_column(PERCENT, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("minimum_turnover >= 0", name="tier_rule_turnover_nonnegative"),
        CheckConstraint(
            "cashback_percent >= 0 AND cashback_percent <= 100",
            name="tier_rule_cashback_percent_range",
        ),
    )


class AdminUser(Base, CreatedAtMixin):
    """A bot user authorised as the owner or a sales administrator."""

    __tablename__ = "admin_users"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[AdminRole] = mapped_column(Enum(AdminRole, name="admin_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    added_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)


class Product(Base, CreatedAtMixin):
    """A searchable local snapshot of a product from Google Sheets."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    current_price: Mapped[Decimal | None] = mapped_column(MONEY)
    url: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Purchase(Base, CreatedAtMixin):
    """An immutable confirmed sale recorded by a sales administrator."""

    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loyalty_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    recorded_by_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus, name="purchase_status"),
        nullable=False,
        default=PurchaseStatus.CONFIRMED,
    )
    total_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    bonus_redeemed: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cash_paid: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cashback_percent: Mapped[Decimal] = mapped_column(PERCENT, nullable=False)
    cashback_accrued: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tier_minimum_turnover: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="purchases")
    items: Mapped[list[PurchaseItem]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan"
    )
    bonus_transactions: Mapped[list[BonusTransaction]] = relationship(back_populates="purchase")

    __table_args__ = (
        CheckConstraint("total_amount > 0", name="purchase_total_positive"),
        CheckConstraint("bonus_redeemed >= 0", name="purchase_bonus_nonnegative"),
        CheckConstraint("cash_paid >= 0", name="purchase_cash_nonnegative"),
        CheckConstraint("cashback_accrued >= 0", name="purchase_cashback_nonnegative"),
    )


class PurchaseItem(Base, CreatedAtMixin):
    """A selected optional catalogue product, captured as a historical snapshot."""

    __tablename__ = "purchase_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )
    external_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title_snapshot: Mapped[str] = mapped_column(String(500), nullable=False)

    purchase: Mapped[Purchase] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("purchase_id", "external_product_id", name="purchase_item_unique_product"),
    )


class BonusTransaction(Base, CreatedAtMixin):
    """An append-only positive or negative loyalty-balance movement."""

    __tablename__ = "bonus_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loyalty_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchases.id", ondelete="RESTRICT"), index=True
    )
    operation_type: Mapped[BonusOperationType] = mapped_column(
        Enum(BonusOperationType, name="bonus_operation_type"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    account: Mapped[LoyaltyAccount] = relationship(back_populates="transactions")
    purchase: Mapped[Purchase | None] = relationship(back_populates="bonus_transactions")

    __table_args__ = (CheckConstraint("amount <> 0", name="bonus_transaction_nonzero"),)


class LoyaltyCode(Base, CreatedAtMixin):
    """A one-hour code stored only as an HMAC digest."""

    __tablename__ = "loyalty_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loyalty_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    used_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)

    account: Mapped[LoyaltyAccount] = relationship(back_populates="codes")


class ContactShare(Base, CreatedAtMixin):
    """A short-lived phone number explicitly shared through Telegram."""

    __tablename__ = "contact_shares"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    shared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditEvent(Base, CreatedAtMixin):
    """Security-relevant and owner actions recorded for later investigation."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(100))
    target_id: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class SupportDialog(Base, CreatedAtMixin):
    """Persistent customer-to-owner support conversation state."""

    __tablename__ = "support_dialogs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_external_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[SupportDialogStatus] = mapped_column(
        Enum(SupportDialogStatus, name="support_dialog_status"),
        nullable=False,
        default=SupportDialogStatus.OPEN,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportForward(Base, CreatedAtMixin):
    """Maps an owner-facing copied Telegram message back to its support dialog."""

    __tablename__ = "support_forwards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dialog_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("support_dialogs.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_message_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    customer_message_id: Mapped[int] = mapped_column(Integer, nullable=False)


class BlockedUser(Base, CreatedAtMixin):
    """Owner-managed support blocklist independent from loyalty membership."""

    __tablename__ = "blocked_users"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    blocked_by_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class NotificationOutbox(Base, CreatedAtMixin):
    """Pending Telegram notifications persisted with the business transaction."""

    __tablename__ = "notification_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


Index("ix_purchase_created_at", Purchase.created_at)
Index("ix_bonus_transaction_created_at", BonusTransaction.created_at)
