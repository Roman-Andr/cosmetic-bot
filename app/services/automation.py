"""Background loyalty automation: campaign launches, bonus expiry and customer reminders.

Every customer message is written to ``NotificationOutbox`` with a ``dedupe_key``, so a
restart, a retried step or a second worker can never send the same reminder twice.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import (
    BonusAllocation,
    BonusTransaction,
    Customer,
    LoyaltyAccount,
    NotificationOutbox,
)
from app.services.campaigns import dispatch_due_campaigns
from app.services.loyalty import (
    MAX_BONUS_SHARE,
    MINSK_TIMEZONE,
    BonusExpiration,
    LoyaltyService,
    expiry_instant,
    money,
    observed_birthday,
    valid_until,
)

logger = logging.getLogger(__name__)

AUTOMATION_INTERVAL_SECONDS = 60
# Days before a lot burns; 1 means the morning of its last spendable day.
EXPIRY_WARNING_DAYS = (14, 7, 1)
MIN_EXPIRY_WARNING_AMOUNT = Decimal("1.00")
# Reminders are only sent during polite local hours, once per Minsk calendar day.
REMINDER_START = time(10, 0)
REMINDER_END = time(21, 0)

SessionFactory = async_sessionmaker[AsyncSession]


@dataclass(frozen=True)
class ExpiringLot:
    """A spendable credit remainder approaching its expiry, with its owner's chat."""

    account_id: uuid.UUID
    telegram_user_id: int
    remaining: Decimal
    expires_at: datetime


def days_until_expiry(expires_at: datetime, today: date) -> int:
    """Count Minsk calendar days until a lot burns; 1 means today is its last valid day."""
    return (valid_until(expires_at) - today).days + 1


def expiry_warnings(
    lots: Iterable[ExpiringLot],
    today: date,
    *,
    warning_days: Sequence[int] = EXPIRY_WARNING_DAYS,
    minimum_amount: Decimal = MIN_EXPIRY_WARNING_AMOUNT,
) -> dict[tuple[uuid.UUID, int], list[BonusExpiration]]:
    """Group today's due warnings into one message per account, totalled per expiry day."""
    per_account: defaultdict[tuple[uuid.UUID, int], defaultdict[date, Decimal]] = defaultdict(
        lambda: defaultdict(Decimal)
    )
    for lot in lots:
        if days_until_expiry(lot.expires_at, today) in warning_days:
            per_account[(lot.account_id, lot.telegram_user_id)][valid_until(lot.expires_at)] += (
                lot.remaining
            )
    warnings: dict[tuple[uuid.UUID, int], list[BonusExpiration]] = {}
    for key, per_day in per_account.items():
        if sum(per_day.values(), Decimal("0")) < minimum_amount:
            continue
        warnings[key] = [
            BonusExpiration(amount=money(amount), valid_until=day)
            for day, amount in sorted(per_day.items())
        ]
    return warnings


def expiry_warning_message(expirations: Sequence[BonusExpiration], today: date) -> str:
    """Tell the customer exactly how many bonuses burn and the last day to spend them."""
    if len(expirations) == 1:
        expiration = expirations[0]
        if expiration.valid_until == today:
            head = f"⏳ Сегодня последний день: {expiration.amount} бонусов сгорят в полночь."
        else:
            head = (
                f"⏳ {expiration.amount} бонусов действуют до "
                f"{expiration.valid_until:%d.%m.%Y} включительно, потом сгорят."
            )
    else:
        lines = "\n".join(
            f"• {expiration.amount} — до {expiration.valid_until:%d.%m.%Y} включительно"
            for expiration in expirations
        )
        head = f"⏳ Скоро сгорят бонусы:\n{lines}"
    return (
        f"{head}\n"
        f"Бонусами можно оплатить до {MAX_BONUS_SHARE:.0%} покупки — "
        "покажите продавцу код из приложения."
    )


def birthday_window(
    birth_date: date,
    today: date,
    *,
    window_days: int,
) -> tuple[date, date, date] | None:
    """Return ``(start, birthday, end)`` of the cashback window containing ``today``."""
    for year in (today.year - 1, today.year, today.year + 1):
        birthday = observed_birthday(birth_date, year)
        start = birthday - timedelta(days=window_days)
        end = birthday + timedelta(days=window_days)
        if start <= today <= end:
            return start, birthday, end
    return None


def format_percent(value: Decimal) -> str:
    """Render 10.00 as "10" and 7.50 as "7.5" for customer-facing text."""
    return f"{value.normalize():f}"


def birthday_message(
    *,
    today: date,
    start: date,
    birthday: date,
    end: date,
    percent: Decimal,
) -> str:
    """Announce the birthday cashback window; the greeting adapts if it is sent late."""
    if today < birthday:
        greeting = "🎂 Скоро ваш день рождения!"
    elif today == birthday:
        greeting = "🎂 С днём рождения!"
    else:
        greeting = "🎂 С прошедшим днём рождения!"
    return (
        f"{greeting} С {start:%d.%m} по {end:%d.%m} включительно действует праздничный "
        f"кешбэк {format_percent(percent)}% на покупки. Ждём вас!"
    )


async def enqueue_once(
    session: AsyncSession,
    *,
    chat_id: int,
    body: str,
    dedupe_key: str,
) -> bool:
    """Queue a notification unless one with the same key was ever queued before."""
    result = await session.execute(
        insert(NotificationOutbox)
        .values(id=uuid.uuid4(), chat_id=chat_id, body=body, dedupe_key=dedupe_key, attempts=0)
        .on_conflict_do_nothing(index_elements=[NotificationOutbox.dedupe_key])
        .returning(NotificationOutbox.id)
    )
    return result.scalar_one_or_none() is not None


async def accounts_with_overdue_lots(session: AsyncSession, now: datetime) -> list[uuid.UUID]:
    """Find accounts holding a credit remainder whose expiry has passed."""
    remaining = BonusTransaction.amount - func.coalesce(func.sum(BonusAllocation.amount), 0)
    overdue = (
        select(BonusTransaction.account_id)
        .outerjoin(BonusAllocation, BonusAllocation.credit_transaction_id == BonusTransaction.id)
        .where(BonusTransaction.amount > 0, BonusTransaction.expires_at <= now)
        .group_by(BonusTransaction.id)
        .having(remaining > 0)
        .subquery()
    )
    return list((await session.scalars(select(overdue.c.account_id).distinct())).all())


async def send_expiry_warnings(session: AsyncSession, now: datetime) -> int:
    """Queue today's 14/7/1-day expiry reminders."""
    today = now.astimezone(MINSK_TIMEZONE).date()
    horizon = expiry_instant(today + timedelta(days=max(EXPIRY_WARNING_DAYS)))
    remaining = BonusTransaction.amount - func.coalesce(func.sum(BonusAllocation.amount), 0)
    rows = await session.execute(
        select(
            BonusTransaction.account_id,
            Customer.telegram_user_id,
            remaining,
            BonusTransaction.expires_at,
        )
        .join(LoyaltyAccount, LoyaltyAccount.id == BonusTransaction.account_id)
        .join(Customer, Customer.id == LoyaltyAccount.customer_id)
        .outerjoin(BonusAllocation, BonusAllocation.credit_transaction_id == BonusTransaction.id)
        .where(
            BonusTransaction.amount > 0,
            BonusTransaction.expires_at > now,
            BonusTransaction.expires_at <= horizon,
        )
        .group_by(BonusTransaction.id, Customer.telegram_user_id)
        .having(remaining > 0)
    )
    lots = [
        ExpiringLot(
            account_id=account_id,
            telegram_user_id=telegram_user_id,
            remaining=money(lot_remaining),
            expires_at=expires_at,
        )
        for account_id, telegram_user_id, lot_remaining, expires_at in rows
        if expires_at is not None
    ]
    queued = 0
    try:
        for (account_id, telegram_user_id), expirations in expiry_warnings(lots, today).items():
            queued += await enqueue_once(
                session,
                chat_id=telegram_user_id,
                body=expiry_warning_message(expirations, today),
                dedupe_key=f"expiry-warning:{account_id}:{today.isoformat()}",
            )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return queued


async def send_birthday_reminders(
    session: AsyncSession,
    now: datetime,
    settings: Settings,
) -> int:
    """Queue one birthday-cashback announcement per customer and observed birthday."""
    percent = settings.birthday_cashback_percent
    if percent <= 0:
        return 0
    today = now.astimezone(MINSK_TIMEZONE).date()
    customers = (
        await session.execute(select(Customer.id, Customer.telegram_user_id, Customer.birth_date))
    ).all()
    queued = 0
    try:
        for customer_id, telegram_user_id, birth_date in customers:
            window = birthday_window(
                birth_date, today, window_days=settings.birthday_cashback_window_days
            )
            if window is None:
                continue
            start, birthday, end = window
            queued += await enqueue_once(
                session,
                chat_id=telegram_user_id,
                body=birthday_message(
                    today=today, start=start, birthday=birthday, end=end, percent=percent
                ),
                dedupe_key=f"birthday:{customer_id}:{birthday.isoformat()}",
            )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return queued


async def expire_overdue_bonuses(
    session_factory: SessionFactory,
    service: LoyaltyService,
    now: datetime,
) -> int:
    """Debit overdue lots account by account so one failure never blocks the others."""
    async with session_factory() as session:
        account_ids = await accounts_with_overdue_lots(session, now)
    for account_id in account_ids:
        async with session_factory() as session:
            await service.expire_account_bonuses(session, account_id, now)
    return len(account_ids)


AutomationStep = Callable[[datetime], Awaitable[object]]


async def _run_step(name: str, step: AutomationStep, now: datetime) -> bool:
    """Isolate step failures so one broken job never stops the others."""
    try:
        await step(now)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Loyalty automation step failed: %s", name)
        return False
    return True


async def loyalty_automation_loop(settings: Settings, session_factory: SessionFactory) -> None:
    """Launch campaigns and expire bonuses every minute; send reminders once per day."""
    service = LoyaltyService(settings)
    reminders_sent_on: date | None = None

    async def launch_campaigns(now: datetime) -> None:
        async with session_factory() as session:
            await dispatch_due_campaigns(session, now)

    async def expire_bonuses(now: datetime) -> None:
        await expire_overdue_bonuses(session_factory, service, now)

    async def warn_expiring(now: datetime) -> None:
        async with session_factory() as session:
            await send_expiry_warnings(session, now)

    async def announce_birthdays(now: datetime) -> None:
        async with session_factory() as session:
            await send_birthday_reminders(session, now, settings)

    while True:
        now = datetime.now(UTC)
        await _run_step("campaign launch", launch_campaigns, now)
        await _run_step("bonus expiry", expire_bonuses, now)
        local_now = now.astimezone(MINSK_TIMEZONE)
        if reminders_sent_on != local_now.date() and (
            REMINDER_START <= local_now.time() < REMINDER_END
        ):
            warned = await _run_step("expiry warnings", warn_expiring, now)
            announced = await _run_step("birthday reminders", announce_birthdays, now)
            if warned and announced:
                reminders_sent_on = local_now.date()
        await asyncio.sleep(AUTOMATION_INTERVAL_SECONDS)
