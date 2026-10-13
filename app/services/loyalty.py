"""Transactional loyalty-programme operations."""

from __future__ import annotations

import calendar
import hashlib
import hmac
import secrets
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    BonusAllocation,
    BonusOperationType,
    BonusTransaction,
    CashbackSource,
    Customer,
    LoyaltyAccount,
    LoyaltyCode,
    LoyaltyTierRule,
    NotificationOutbox,
    Product,
    Purchase,
    PurchaseItem,
)
from app.services.tier_rules import get_current_tier

MONEY_QUANTUM = Decimal("0.01")
MAX_BONUS_SHARE = Decimal("0.10")
MINSK_TIMEZONE = ZoneInfo("Europe/Minsk")


class LoyaltyError(Exception):
    """Base exception raised for an invalid loyalty operation."""


class InvalidCodeError(LoyaltyError):
    """The supplied buyer code is invalid, expired, or already used."""


class ProductNotFoundError(LoyaltyError):
    """An administrator selected a product absent from the local catalogue."""


@dataclass(frozen=True)
class ProductSelection:
    """Optional product selected by an administrator when recording a sale."""

    external_id: str


@dataclass(frozen=True)
class PurchaseResult:
    """Confirmed purchase data used by bot notifications and API responses."""

    purchase: Purchase
    customer_telegram_id: int
    redeemed: Decimal
    accrued: Decimal
    balance_after: Decimal
    cashback_percent: Decimal
    cashback_source: CashbackSource
    tier_minimum_turnover: Decimal


@dataclass(frozen=True)
class PurchasePreview:
    """Non-mutating calculation shown before a sales administrator confirms a purchase."""

    customer_name: str
    customer_phone: str
    current_balance: Decimal
    total_amount: Decimal
    redeemed: Decimal
    cash_paid: Decimal
    accrued: Decimal
    cashback_percent: Decimal
    cashback_source: CashbackSource
    tier_minimum_turnover: Decimal


@dataclass(frozen=True)
class BuyerLookup:
    """Privacy-minimised customer details resolved from a valid temporary code."""

    customer_name: str
    customer_phone: str
    registered_at: datetime
    current_balance: Decimal
    cashback_percent: Decimal
    cashback_source: CashbackSource
    tier_minimum_turnover: Decimal


@dataclass(frozen=True)
class PurchaseAmounts:
    """Pure monetary calculation shared by preview and confirmed sale paths."""

    redeemed: Decimal
    cash_paid: Decimal
    accrued: Decimal
    balance_after: Decimal


@dataclass(frozen=True)
class EffectiveCashback:
    """Cashback rate selected for one confirmed purchase."""

    percent: Decimal
    source: CashbackSource


@dataclass(frozen=True)
class BonusLot:
    """The unconsumed remainder of one credit (accrual or promotion) transaction."""

    transaction_id: uuid.UUID
    remaining: Decimal
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class BonusExpiration:
    """Bonuses whose last spendable Minsk calendar day is ``valid_until``."""

    amount: Decimal
    valid_until: date


def money(value: Decimal | int | str, *, rounding: str = ROUND_HALF_UP) -> Decimal:
    """Normalize monetary values to Belarusian-ruble precision."""
    normalized = Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=rounding)
    return normalized


def calculate_purchase_amounts(
    *,
    current_balance: Decimal,
    total_amount: Decimal | int | str,
    cashback_percent: Decimal,
) -> PurchaseAmounts:
    """Apply the 10% redemption cap and accrue only from the cash-paid remainder."""
    total = money(total_amount)
    if total <= 0:
        raise LoyaltyError("Purchase total must be greater than zero")
    maximum_bonus = money(total * MAX_BONUS_SHARE, rounding=ROUND_DOWN)
    redeemed = min(money(current_balance), maximum_bonus)
    cash_paid = money(total - redeemed)
    accrued = money(cash_paid * cashback_percent / Decimal("100"))
    balance_after = money(current_balance - redeemed + accrued)
    return PurchaseAmounts(
        redeemed=redeemed,
        cash_paid=cash_paid,
        accrued=accrued,
        balance_after=balance_after,
    )


def observed_birthday(birth_date: date, year: int) -> date:
    """Return the birthday observed in ``year``; 29 February is observed on 28 February."""
    if birth_date.month == 2 and birth_date.day == 29:
        try:
            return date(year, 2, 29)
        except ValueError:
            return date(year, 2, 28)
    return birth_date.replace(year=year)


def is_birthday_cashback_active(
    birth_date: date,
    purchase_date: date,
    *,
    window_days: int,
) -> bool:
    """Check the inclusive birthday window, including dates that cross a calendar year."""
    return any(
        abs((purchase_date - observed_birthday(birth_date, year)).days) <= window_days
        for year in (purchase_date.year - 1, purchase_date.year, purchase_date.year + 1)
    )


def effective_cashback(
    *,
    tier_percent: Decimal,
    birth_date: date,
    purchase_date: date,
    birthday_cashback_percent: Decimal,
    birthday_cashback_window_days: int,
) -> EffectiveCashback:
    """Apply the birthday promotion before the normal turnover-based tier."""
    if is_birthday_cashback_active(
        birth_date,
        purchase_date,
        window_days=birthday_cashback_window_days,
    ):
        return EffectiveCashback(
            percent=birthday_cashback_percent,
            source=CashbackSource.BIRTHDAY,
        )
    return EffectiveCashback(percent=tier_percent, source=CashbackSource.TIER)


def add_months(value: date, months: int) -> date:
    """Shift a date by calendar months, clamping to the last day of a shorter month."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def expiry_instant(valid_until: date) -> datetime:
    """Bonuses valid through ``valid_until`` (Minsk) expire at the following local midnight."""
    next_day = datetime.combine(valid_until + timedelta(days=1), time.min, tzinfo=MINSK_TIMEZONE)
    return next_day.astimezone(UTC)


def valid_until(expires_at: datetime) -> date:
    """Return the last Minsk calendar day on which a lot can still be spent."""
    return (expires_at.astimezone(MINSK_TIMEZONE) - timedelta(microseconds=1)).date()


def accrual_expires_at(accrued_at: datetime, *, lifetime_months: int) -> datetime:
    """A credit stays spendable through the same Minsk calendar day ``lifetime_months`` later."""
    accrual_day = accrued_at.astimezone(MINSK_TIMEZONE).date()
    return expiry_instant(add_months(accrual_day, lifetime_months))


def allocate_debit(lots: Sequence[BonusLot], amount: Decimal) -> list[tuple[uuid.UUID, Decimal]]:
    """Consume the soonest-expiring lots first and return ``(credit id, portion)`` pairs."""
    outstanding = money(amount)
    allocations: list[tuple[uuid.UUID, Decimal]] = []
    for lot in sorted(lots, key=lambda lot: (lot.expires_at, lot.created_at, lot.transaction_id)):
        if outstanding <= 0:
            break
        portion = min(lot.remaining, outstanding)
        if portion > 0:
            allocations.append((lot.transaction_id, portion))
            outstanding -= portion
    if outstanding > 0:
        raise LoyaltyError("Bonus lots do not cover the requested debit")
    return allocations


def usable_balance(current_balance: Decimal, lots: Sequence[BonusLot], now: datetime) -> Decimal:
    """Exclude lots past expiry that the background sweep has not debited yet."""
    overdue = sum((lot.remaining for lot in lots if lot.expires_at <= now), Decimal("0"))
    return money(max(Decimal("0"), current_balance - overdue))


def next_expiration(lots: Sequence[BonusLot], now: datetime) -> BonusExpiration | None:
    """Return the spendable bonuses that will expire first, grouped by their last valid day."""
    live = [lot for lot in lots if lot.expires_at > now]
    if not live:
        return None
    first_day = min(valid_until(lot.expires_at) for lot in live)
    amount = sum(
        (lot.remaining for lot in live if valid_until(lot.expires_at) == first_day),
        Decimal("0"),
    )
    return BonusExpiration(amount=money(amount), valid_until=first_day)


async def open_bonus_lots(session: AsyncSession, account_id: uuid.UUID) -> list[BonusLot]:
    """Load every credit lot of an account that still has an unconsumed remainder."""
    remaining = BonusTransaction.amount - func.coalesce(func.sum(BonusAllocation.amount), 0)
    rows = await session.execute(
        select(
            BonusTransaction.id,
            remaining,
            BonusTransaction.expires_at,
            BonusTransaction.created_at,
        )
        .outerjoin(BonusAllocation, BonusAllocation.credit_transaction_id == BonusTransaction.id)
        .where(BonusTransaction.account_id == account_id, BonusTransaction.amount > 0)
        .group_by(BonusTransaction.id)
        .having(remaining > 0)
    )
    lots = []
    for transaction_id, lot_remaining, expires_at, created_at in rows:
        if expires_at is None:
            raise LoyaltyError("A bonus credit has no expiry date")
        lots.append(
            BonusLot(
                transaction_id=transaction_id,
                remaining=money(lot_remaining),
                expires_at=expires_at,
                created_at=created_at,
            )
        )
    return lots


async def record_debit(
    session: AsyncSession,
    *,
    account: LoyaltyAccount,
    lots: Sequence[BonusLot],
    operation_type: BonusOperationType,
    amount: Decimal,
    purchase_id: uuid.UUID | None = None,
) -> BonusTransaction:
    """Append a debit and its lot allocations; the caller must hold the account row lock."""
    debit_amount = money(amount)
    allocations = allocate_debit(lots, debit_amount)
    balance_after = money(account.current_balance - debit_amount)
    debit = BonusTransaction(
        id=uuid.uuid4(),
        account_id=account.id,
        purchase_id=purchase_id,
        operation_type=operation_type,
        amount=-debit_amount,
        balance_after=balance_after,
    )
    session.add(debit)
    # The allocation rows reference the debit, so it must reach the database first.
    await session.flush()
    session.add_all(
        BonusAllocation(
            debit_transaction_id=debit.id,
            credit_transaction_id=credit_id,
            amount=portion,
        )
        for credit_id, portion in allocations
    )
    account.current_balance = balance_after
    return debit


async def expire_overdue_lots(
    session: AsyncSession,
    account: LoyaltyAccount,
    lots: Sequence[BonusLot],
    now: datetime,
) -> list[BonusLot]:
    """Debit every lot past expiry in one ledger entry and return the still-spendable lots."""
    overdue = [lot for lot in lots if lot.expires_at <= now]
    total = money(sum((lot.remaining for lot in overdue), Decimal("0")))
    if total > 0:
        await record_debit(
            session,
            account=account,
            lots=overdue,
            operation_type=BonusOperationType.EXPIRATION,
            amount=total,
        )
    return [lot for lot in lots if lot.expires_at > now]


def code_digest(code: str, pepper: SecretValue) -> str:
    """Return a deterministic HMAC; never persist the plaintext six-digit code."""
    return hmac.new(pepper.get_secret_value().encode(), code.encode(), hashlib.sha256).hexdigest()


class SecretValue(Protocol):
    """Protocol implemented by Pydantic's secret values."""

    def get_secret_value(self) -> str:
        raise NotImplementedError


class LoyaltyService:
    """Use row locks to make code redemption and bonus updates race-safe."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate_code(
        self,
        session: AsyncSession,
        account_id: uuid.UUID,
    ) -> tuple[str, datetime]:
        """Create the account's only active one-hour customer code."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=1)

        try:
            account = await session.scalar(
                select(LoyaltyAccount).where(LoyaltyAccount.id == account_id).with_for_update()
            )
            if account is None:
                raise LoyaltyError("Loyalty account does not exist")

            await session.execute(
                update(LoyaltyCode)
                .where(
                    LoyaltyCode.account_id == account.id,
                    LoyaltyCode.used_at.is_(None),
                    LoyaltyCode.expires_at > now,
                )
                .values(expires_at=now)
            )

            # A digest collision is extraordinarily unlikely; regenerate before inserting.
            while True:
                code = f"{secrets.randbelow(1_000_000):06d}"
                digest = code_digest(code, self._settings.loyalty_code_pepper)
                existing = await session.scalar(
                    select(LoyaltyCode.id).where(LoyaltyCode.code_digest == digest)
                )
                if existing is None:
                    break

            session.add(
                LoyaltyCode(account_id=account.id, code_digest=digest, expires_at=expires_at)
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        return code, expires_at

    async def record_purchase(
        self,
        session: AsyncSession,
        *,
        buyer_code: str,
        recorded_by_telegram_id: int,
        total_amount: Decimal | str | int,
        selected_products: Iterable[ProductSelection] = (),
    ) -> PurchaseResult:
        """Redeem the maximum permitted bonus balance and accrue cashback atomically."""
        total = money(total_amount)
        if total <= 0:
            raise LoyaltyError("Purchase total must be greater than zero")
        if not buyer_code.isdigit() or len(buyer_code) != 6:
            raise InvalidCodeError("Buyer code must contain six digits")

        now = datetime.now(UTC)
        digest = code_digest(buyer_code, self._settings.loyalty_code_pepper)

        try:
            code = await session.scalar(
                select(LoyaltyCode).where(LoyaltyCode.code_digest == digest).with_for_update()
            )
            if code is None or code.used_at is not None or code.expires_at <= now:
                raise InvalidCodeError("Buyer code is invalid, expired, or already used")

            account = await session.scalar(
                select(LoyaltyAccount).where(LoyaltyAccount.id == code.account_id).with_for_update()
            )
            if account is None:
                raise LoyaltyError("Loyalty account does not exist")

            tier = await self._current_tier(session, account.lifetime_turnover)
            customer = await session.get(Customer, account.customer_id)
            if customer is None:
                raise LoyaltyError("Customer does not exist")
            cashback = self._effective_cashback(tier, customer.birth_date, now)
            products = await self._selected_products(session, selected_products)

            # Expired lots must never be spent, even if the background sweep has not run yet.
            spendable_lots = await expire_overdue_lots(
                session, account, await open_bonus_lots(session, account.id), now
            )
            amounts = calculate_purchase_amounts(
                current_balance=account.current_balance,
                total_amount=total,
                cashback_percent=cashback.percent,
            )
            redeemed = amounts.redeemed
            cash_paid = amounts.cash_paid
            accrued = amounts.accrued
            balance_after = amounts.balance_after
            accrual_expiry = accrual_expires_at(
                now, lifetime_months=self._settings.bonus_lifetime_months
            )

            purchase = Purchase(
                customer_id=account.customer_id,
                account_id=account.id,
                recorded_by_telegram_id=recorded_by_telegram_id,
                total_amount=total,
                bonus_redeemed=redeemed,
                cash_paid=cash_paid,
                cashback_percent=cashback.percent,
                cashback_source=cashback.source,
                cashback_accrued=accrued,
                tier_minimum_turnover=tier.minimum_turnover,
            )
            session.add(purchase)
            await session.flush()

            for product in products:
                session.add(
                    PurchaseItem(
                        purchase_id=purchase.id,
                        product_id=product.id,
                        external_product_id=product.external_id,
                        title_snapshot=product.title,
                    )
                )

            if redeemed:
                await record_debit(
                    session,
                    account=account,
                    lots=spendable_lots,
                    operation_type=BonusOperationType.REDEMPTION,
                    amount=redeemed,
                    purchase_id=purchase.id,
                )
            if accrued:
                session.add(
                    BonusTransaction(
                        account_id=account.id,
                        purchase_id=purchase.id,
                        operation_type=BonusOperationType.ACCRUAL,
                        amount=accrued,
                        balance_after=balance_after,
                        expires_at=accrual_expiry,
                    )
                )

            account.current_balance = balance_after
            account.lifetime_turnover = money(account.lifetime_turnover + total)
            code.used_at = now
            code.used_by_telegram_id = recorded_by_telegram_id

            customer_telegram_id = customer.telegram_user_id

            promotion_text = (
                f" по акции ко дню рождения ({cashback.percent}%)"
                if cashback.source is CashbackSource.BIRTHDAY
                else ""
            )

            validity_text = (
                f" Начисленные бонусы действуют до "
                f"{valid_until(accrual_expiry):%d.%m.%Y} включительно."
                if accrued
                else ""
            )

            session.add(
                NotificationOutbox(
                    chat_id=customer_telegram_id,
                    body=(
                        f"Вам начислено {accrued} бонусов{promotion_text}. "
                        f"Текущий баланс: {balance_after} бонусов.{validity_text}"
                    ),
                )
            )

            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        return PurchaseResult(
            purchase=purchase,
            customer_telegram_id=customer_telegram_id,
            redeemed=redeemed,
            accrued=accrued,
            balance_after=balance_after,
            cashback_percent=cashback.percent,
            cashback_source=cashback.source,
            tier_minimum_turnover=tier.minimum_turnover,
        )

    async def preview_purchase(
        self,
        session: AsyncSession,
        *,
        buyer_code: str,
        total_amount: Decimal | str | int,
    ) -> PurchasePreview:
        """Calculate a sale without consuming the code or changing the balance."""
        total = money(total_amount)
        if total <= 0:
            raise LoyaltyError("Purchase total must be greater than zero")
        buyer = await self.lookup_buyer(session, buyer_code=buyer_code)
        amounts = calculate_purchase_amounts(
            current_balance=buyer.current_balance,
            total_amount=total,
            cashback_percent=buyer.cashback_percent,
        )
        return PurchasePreview(
            customer_name=buyer.customer_name,
            customer_phone=buyer.customer_phone,
            current_balance=buyer.current_balance,
            total_amount=total,
            redeemed=amounts.redeemed,
            cash_paid=amounts.cash_paid,
            accrued=amounts.accrued,
            cashback_percent=buyer.cashback_percent,
            cashback_source=buyer.cashback_source,
            tier_minimum_turnover=buyer.tier_minimum_turnover,
        )

    async def lookup_buyer(
        self,
        session: AsyncSession,
        *,
        buyer_code: str,
    ) -> BuyerLookup:
        """Resolve a valid, unused customer code without consuming it."""
        if not buyer_code.isdigit() or len(buyer_code) != 6:
            raise InvalidCodeError("Buyer code must contain six digits")

        now = datetime.now(UTC)
        row = (
            await session.execute(
                select(Customer, LoyaltyAccount)
                .join(LoyaltyAccount, LoyaltyAccount.customer_id == Customer.id)
                .join(LoyaltyCode, LoyaltyCode.account_id == LoyaltyAccount.id)
                .where(
                    LoyaltyCode.code_digest
                    == code_digest(buyer_code, self._settings.loyalty_code_pepper),
                    LoyaltyCode.used_at.is_(None),
                    LoyaltyCode.expires_at > now,
                )
            )
        ).one_or_none()
        if row is None:
            raise InvalidCodeError("Buyer code is invalid, expired, or already used")

        customer, account = row
        tier = await self._current_tier(session, account.lifetime_turnover)
        cashback = self._effective_cashback(tier, customer.birth_date, now)
        lots = await open_bonus_lots(session, account.id)
        return BuyerLookup(
            customer_name=customer.full_name,
            customer_phone=customer.phone,
            registered_at=customer.created_at,
            current_balance=usable_balance(account.current_balance, lots, now),
            cashback_percent=cashback.percent,
            cashback_source=cashback.source,
            tier_minimum_turnover=tier.minimum_turnover,
        )

    async def expire_account_bonuses(
        self,
        session: AsyncSession,
        account_id: uuid.UUID,
        now: datetime,
    ) -> None:
        """Debit an account's overdue lots under the same row lock used by purchases."""
        try:
            account = await session.scalar(
                select(LoyaltyAccount).where(LoyaltyAccount.id == account_id).with_for_update()
            )
            if account is None:
                raise LoyaltyError("Loyalty account does not exist")
            await expire_overdue_lots(
                session, account, await open_bonus_lots(session, account.id), now
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    def _effective_cashback(
        self,
        tier: LoyaltyTierRule,
        birth_date: date,
        now: datetime,
    ) -> EffectiveCashback:
        """Select the promotion using the Minsk calendar date of the purchase."""
        return effective_cashback(
            tier_percent=tier.cashback_percent,
            birth_date=birth_date,
            purchase_date=now.astimezone(MINSK_TIMEZONE).date(),
            birthday_cashback_percent=self._settings.birthday_cashback_percent,
            birthday_cashback_window_days=self._settings.birthday_cashback_window_days,
        )

    async def _current_tier(self, session: AsyncSession, turnover: Decimal) -> LoyaltyTierRule:
        tier = await get_current_tier(session, turnover)
        if tier is None:
            raise LoyaltyError("No active loyalty tier applies to this account")
        return tier

    async def _selected_products(
        self,
        session: AsyncSession,
        selections: Iterable[ProductSelection],
    ) -> list[Product]:
        external_ids = list(dict.fromkeys(selection.external_id for selection in selections))
        if not external_ids:
            return []

        products = list(
            (
                await session.scalars(
                    select(Product).where(
                        Product.external_id.in_(external_ids), Product.is_active.is_(True)
                    )
                )
            ).all()
        )
        found_ids = {product.external_id for product in products}
        missing_ids = set(external_ids) - found_ids
        if missing_ids:
            raise ProductNotFoundError(f"Products not found: {', '.join(sorted(missing_ids))}")
        return products
