"""Transactional loyalty-programme operations."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
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

            amounts = calculate_purchase_amounts(
                current_balance=account.current_balance,
                total_amount=total,
                cashback_percent=cashback.percent,
            )
            redeemed = amounts.redeemed
            cash_paid = amounts.cash_paid
            accrued = amounts.accrued
            balance_after = amounts.balance_after
            balance_after_redemption = money(account.current_balance - redeemed)

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
                session.add(
                    BonusTransaction(
                        account_id=account.id,
                        purchase_id=purchase.id,
                        operation_type=BonusOperationType.REDEMPTION,
                        amount=-redeemed,
                        balance_after=balance_after_redemption,
                    )
                )
            if accrued:
                session.add(
                    BonusTransaction(
                        account_id=account.id,
                        purchase_id=purchase.id,
                        operation_type=BonusOperationType.ACCRUAL,
                        amount=accrued,
                        balance_after=balance_after,
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

            session.add(
                NotificationOutbox(
                    chat_id=customer_telegram_id,
                    body=(
                        f"Вам начислено {accrued} бонусов{promotion_text}. "
                        f"Текущий баланс: {balance_after} бонусов."
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
        if not buyer_code.isdigit() or len(buyer_code) != 6:
            raise InvalidCodeError("Buyer code must contain six digits")

        code = await session.scalar(
            select(LoyaltyCode).where(
                LoyaltyCode.code_digest
                == code_digest(buyer_code, self._settings.loyalty_code_pepper)
            )
        )
        if code is None or code.used_at is not None or code.expires_at <= datetime.now(UTC):
            raise InvalidCodeError("Buyer code is invalid, expired, or already used")
        account = await session.get(LoyaltyAccount, code.account_id)
        if account is None:
            raise LoyaltyError("Loyalty account does not exist")
        customer = await session.get(Customer, account.customer_id)
        if customer is None:
            raise LoyaltyError("Customer does not exist")
        tier = await self._current_tier(session, account.lifetime_turnover)
        cashback = self._effective_cashback(tier, customer.birth_date, datetime.now(UTC))
        amounts = calculate_purchase_amounts(
            current_balance=account.current_balance,
            total_amount=total,
            cashback_percent=cashback.percent,
        )
        return PurchasePreview(
            customer_name=customer.full_name,
            customer_phone=customer.phone,
            current_balance=account.current_balance,
            total_amount=total,
            redeemed=amounts.redeemed,
            cash_paid=amounts.cash_paid,
            accrued=amounts.accrued,
            cashback_percent=cashback.percent,
            cashback_source=cashback.source,
            tier_minimum_turnover=tier.minimum_turnover,
        )

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
        statement: Select[tuple[LoyaltyTierRule]] = (
            select(LoyaltyTierRule)
            .where(
                LoyaltyTierRule.is_active.is_(True),
                LoyaltyTierRule.minimum_turnover <= turnover,
            )
            .order_by(LoyaltyTierRule.minimum_turnover.desc())
            .limit(1)
        )
        tier = await session.scalar(statement)
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
