"""Owner-scheduled promotion campaigns: a broadcast with optional expiring gift bonuses."""

from __future__ import annotations

import base64
import binascii
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Row, Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditEvent,
    BonusOperationType,
    BonusTransaction,
    CampaignStatus,
    Customer,
    LoyaltyAccount,
    NotificationOutbox,
    PromotionCampaign,
)
from app.services.loyalty import MAX_BONUS_SHARE, expiry_instant, money

TEXT_MESSAGE_LIMIT = 4096
PHOTO_CAPTION_LIMIT = 1024
MAX_CAMPAIGN_PHOTO_BYTES = 5 * 1024 * 1024
# "Start now" requests travel from the Mini App, so allow a little clock skew.
START_GRACE = timedelta(minutes=5)

_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class CampaignError(Exception):
    """An owner campaign request violates a campaign rule; the message is user-facing."""


class CampaignNotFoundError(CampaignError):
    """The requested campaign does not exist."""


class CampaignStateError(CampaignError):
    """The campaign has already launched or been cancelled, so it can no longer change."""


@dataclass(frozen=True)
class CampaignDraft:
    """Owner input for a new campaign before it is persisted."""

    title: str
    message_text: str
    photo_file_id: str | None
    bonus_amount: Decimal
    bonus_valid_until: date | None
    starts_at: datetime


def campaign_message(
    message_text: str,
    bonus_amount: Decimal,
    bonus_valid_until: date | None,
) -> str:
    """Append the exact gift terms so customers never depend on the owner's free text."""
    text = message_text.strip()
    if bonus_amount <= 0 or bonus_valid_until is None:
        return text
    return (
        f"{text}\n\n"
        f"🎁 Вам начислено {money(bonus_amount)} подарочных бонусов. "
        f"Они действуют до {bonus_valid_until:%d.%m.%Y} включительно. "
        f"Бонусами можно оплатить до {MAX_BONUS_SHARE:.0%} покупки."
    )


def validate_campaign(draft: CampaignDraft, now: datetime) -> None:
    """Reject drafts that would launch in the past, expire before launch, or not fit Telegram."""
    if draft.starts_at.tzinfo is None:
        raise CampaignError("Время старта должно содержать часовой пояс")
    if draft.starts_at < now - START_GRACE:
        raise CampaignError("Время старта уже прошло")
    if draft.bonus_amount > 0:
        if draft.bonus_valid_until is None:
            raise CampaignError("Укажите, до какого дня действуют подарочные бонусы")
        if expiry_instant(draft.bonus_valid_until) <= max(draft.starts_at, now):
            raise CampaignError("Подарочные бонусы должны действовать и после старта акции")
    limit = PHOTO_CAPTION_LIMIT if draft.photo_file_id else TEXT_MESSAGE_LIMIT
    length = len(campaign_message(draft.message_text, draft.bonus_amount, draft.bonus_valid_until))
    if length > limit:
        raise CampaignError(
            f"Сообщение вместе с условиями акции — {length} символов, а Telegram допускает "
            f"не больше {limit}{' с картинкой' if draft.photo_file_id else ''}"
        )


def decode_campaign_photo(image_base64: str) -> bytes:
    """Decode an uploaded JPEG or PNG and enforce the size limit before contacting Telegram."""
    try:
        data = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CampaignError("Не удалось прочитать картинку") from exc
    if not data:
        raise CampaignError("Картинка пустая")
    if len(data) > MAX_CAMPAIGN_PHOTO_BYTES:
        raise CampaignError("Картинка больше 5 МБ")
    if not (data.startswith(_JPEG_SIGNATURE) or data.startswith(_PNG_SIGNATURE)):
        raise CampaignError("Поддерживаются только картинки JPEG и PNG")
    return data


async def audience_size(session: AsyncSession) -> int:
    """Every registered customer receives a campaign."""
    return await session.scalar(select(func.count(Customer.id))) or 0


async def list_campaigns(session: AsyncSession, *, limit: int = 50) -> list[PromotionCampaign]:
    """Return the newest campaigns first."""
    return list(
        (
            await session.scalars(
                select(PromotionCampaign).order_by(PromotionCampaign.created_at.desc()).limit(limit)
            )
        ).all()
    )


async def create_campaign(
    session: AsyncSession,
    draft: CampaignDraft,
    *,
    actor_telegram_id: int,
    now: datetime,
) -> PromotionCampaign:
    """Persist a scheduled campaign and its audit record."""
    validate_campaign(draft, now)
    has_bonus = draft.bonus_amount > 0
    try:
        campaign = PromotionCampaign(
            id=uuid.uuid4(),
            title=draft.title.strip(),
            message_text=draft.message_text.strip(),
            photo_file_id=draft.photo_file_id,
            bonus_amount=money(draft.bonus_amount),
            bonus_valid_until=draft.bonus_valid_until if has_bonus else None,
            starts_at=draft.starts_at,
            status=CampaignStatus.SCHEDULED,
            created_by_telegram_id=actor_telegram_id,
        )
        session.add(campaign)
        session.add(
            AuditEvent(
                actor_telegram_id=actor_telegram_id,
                event_type="promotion_campaign_created",
                target_type="promotion_campaigns",
                target_id=str(campaign.id),
                payload={
                    "title": campaign.title,
                    "bonus_amount": str(campaign.bonus_amount),
                    "bonus_valid_until": (
                        campaign.bonus_valid_until.isoformat()
                        if campaign.bonus_valid_until
                        else None
                    ),
                    "starts_at": campaign.starts_at.isoformat(),
                },
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return campaign


def _audit_snapshot(campaign: PromotionCampaign) -> dict[str, str | bool | None]:
    """The owner-editable fields of a campaign, in a JSON-friendly form."""
    return {
        "title": campaign.title,
        "message_text": campaign.message_text,
        "has_photo": campaign.photo_file_id is not None,
        "bonus_amount": str(campaign.bonus_amount),
        "bonus_valid_until": (
            campaign.bonus_valid_until.isoformat() if campaign.bonus_valid_until else None
        ),
        "starts_at": campaign.starts_at.isoformat(),
    }


async def edited_campaign_draft(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    draft: CampaignDraft,
    *,
    keep_photo: bool,
    lock: bool = False,
) -> tuple[PromotionCampaign, CampaignDraft]:
    """Load a still-scheduled campaign and resolve ``keep_photo`` to its stored picture."""
    query = select(PromotionCampaign).where(PromotionCampaign.id == campaign_id)
    campaign = await session.scalar(query.with_for_update() if lock else query)
    if campaign is None:
        raise CampaignNotFoundError("Акция не найдена")
    if campaign.status is not CampaignStatus.SCHEDULED:
        raise CampaignStateError("Акция уже стартовала или отменена — изменить её нельзя")
    if keep_photo:
        draft = replace(draft, photo_file_id=campaign.photo_file_id)
    return campaign, draft


async def update_campaign(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    draft: CampaignDraft,
    *,
    keep_photo: bool,
    actor_telegram_id: int,
    now: datetime,
) -> PromotionCampaign:
    """Replace every owner field of a campaign that has not launched yet.

    The row lock serialises the edit with ``dispatch_due_campaigns``: the launcher skips a
    locked campaign until the next tick, and an edit that waited for a launch sees it completed.
    """
    try:
        campaign, draft = await edited_campaign_draft(
            session, campaign_id, draft, keep_photo=keep_photo, lock=True
        )
        validate_campaign(draft, now)
        before = _audit_snapshot(campaign)
        has_bonus = draft.bonus_amount > 0
        campaign.title = draft.title.strip()
        campaign.message_text = draft.message_text.strip()
        campaign.photo_file_id = draft.photo_file_id
        campaign.bonus_amount = money(draft.bonus_amount)
        campaign.bonus_valid_until = draft.bonus_valid_until if has_bonus else None
        campaign.starts_at = draft.starts_at
        session.add(
            AuditEvent(
                actor_telegram_id=actor_telegram_id,
                event_type="promotion_campaign_updated",
                target_type="promotion_campaigns",
                target_id=str(campaign.id),
                payload={"before": before, "after": _audit_snapshot(campaign)},
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return campaign


async def cancel_campaign(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    *,
    actor_telegram_id: int,
    now: datetime,
) -> PromotionCampaign:
    """Cancel a campaign that has not launched yet; launched gifts are immutable."""
    try:
        campaign = await session.scalar(
            select(PromotionCampaign).where(PromotionCampaign.id == campaign_id).with_for_update()
        )
        if campaign is None:
            raise CampaignNotFoundError("Акция не найдена")
        if campaign.status is not CampaignStatus.SCHEDULED:
            raise CampaignStateError("Отменить можно только запланированную акцию")
        campaign.status = CampaignStatus.CANCELLED
        campaign.cancelled_at = now
        session.add(
            AuditEvent(
                actor_telegram_id=actor_telegram_id,
                event_type="promotion_campaign_cancelled",
                target_type="promotion_campaigns",
                target_id=str(campaign.id),
                payload={"title": campaign.title},
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return campaign


async def dispatch_due_campaigns(session: AsyncSession, now: datetime) -> int:
    """Launch every scheduled campaign whose start has arrived, one transaction per campaign."""
    launched = 0
    while True:
        try:
            campaign = await session.scalar(
                select(PromotionCampaign)
                .where(
                    PromotionCampaign.status == CampaignStatus.SCHEDULED,
                    PromotionCampaign.starts_at <= now,
                )
                .order_by(PromotionCampaign.starts_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if campaign is None:
                await session.rollback()
                return launched
            await _launch_campaign(session, campaign, now)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        launched += 1


def _gift_expiry(campaign: PromotionCampaign) -> datetime | None:
    """The instant the campaign's gift lots expire, or ``None`` for a plain broadcast."""
    if campaign.bonus_amount > 0 and campaign.bonus_valid_until is not None:
        return expiry_instant(campaign.bonus_valid_until)
    return None


def _recipients_without_gift(
    campaign_id: uuid.UUID,
) -> Select[tuple[uuid.UUID, int, LoyaltyAccount]]:
    """Customers whose account holds no gift lot of this campaign yet, oldest account first."""
    return (
        select(Customer.id, Customer.telegram_user_id, LoyaltyAccount)
        .join(LoyaltyAccount, LoyaltyAccount.customer_id == Customer.id)
        .where(
            ~exists().where(
                BonusTransaction.campaign_id == campaign_id,
                BonusTransaction.account_id == LoyaltyAccount.id,
            )
        )
        .order_by(LoyaltyAccount.id)
    )


def accepts_late_recipients(campaign: PromotionCampaign, now: datetime) -> bool:
    """A launched gift campaign can still reach newcomers until its bonuses expire."""
    expires_at = _gift_expiry(campaign)
    return (
        campaign.status is CampaignStatus.COMPLETED and expires_at is not None and expires_at > now
    )


async def late_recipients_count(
    session: AsyncSession, campaign: PromotionCampaign, now: datetime
) -> int:
    """How many customers registered after the launch and have not received the gift yet."""
    if not accepts_late_recipients(campaign, now):
        return 0
    query = _recipients_without_gift(campaign.id).order_by(None).subquery()
    return await session.scalar(select(func.count()).select_from(query)) or 0


async def send_campaign_to_late_recipients(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    *,
    actor_telegram_id: int,
    now: datetime,
) -> int:
    """Give a launched campaign's gift and message to customers who joined after the launch.

    The campaign row lock serialises concurrent presses, and the unique campaign/account index
    on gift lots means a customer can never receive the same gift twice.
    """
    try:
        campaign = await session.scalar(
            select(PromotionCampaign).where(PromotionCampaign.id == campaign_id).with_for_update()
        )
        if campaign is None:
            raise CampaignNotFoundError("Акция не найдена")
        if not accepts_late_recipients(campaign, now):
            raise CampaignStateError(
                "Дослать можно только отправленную акцию с бонусами, пока они не сгорели"
            )
        rows = (
            await session.execute(
                _recipients_without_gift(campaign.id).with_for_update(of=LoyaltyAccount)
            )
        ).all()
        if rows:
            _deliver_campaign(session, campaign, rows)
            campaign.recipients_count = (campaign.recipients_count or 0) + len(rows)
            session.add(
                AuditEvent(
                    actor_telegram_id=actor_telegram_id,
                    event_type="promotion_campaign_sent_to_late_recipients",
                    target_type="promotion_campaigns",
                    target_id=str(campaign.id),
                    payload={"title": campaign.title, "recipients": len(rows)},
                )
            )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return len(rows)


def _deliver_campaign(
    session: AsyncSession,
    campaign: PromotionCampaign,
    rows: Sequence[Row[tuple[uuid.UUID, int, LoyaltyAccount]]],
) -> None:
    """Grant the gift lot (if any) and queue the message for each locked customer account."""
    expires_at = _gift_expiry(campaign)
    body = campaign_message(
        campaign.message_text, campaign.bonus_amount, campaign.bonus_valid_until
    )
    for customer_id, telegram_user_id, account in rows:
        if expires_at is not None:
            account.current_balance = money(account.current_balance + campaign.bonus_amount)
            session.add(
                BonusTransaction(
                    account_id=account.id,
                    operation_type=BonusOperationType.PROMOTION,
                    amount=campaign.bonus_amount,
                    balance_after=account.current_balance,
                    expires_at=expires_at,
                    campaign_id=campaign.id,
                )
            )
        session.add(
            NotificationOutbox(
                chat_id=telegram_user_id,
                body=body,
                photo_file_id=campaign.photo_file_id,
                dedupe_key=f"campaign:{campaign.id}:{customer_id}",
            )
        )


async def _launch_campaign(
    session: AsyncSession,
    campaign: PromotionCampaign,
    now: datetime,
) -> None:
    """Grant the gift lot and queue the broadcast for every customer in one transaction."""
    expires_at = _gift_expiry(campaign)
    if expires_at is not None and expires_at <= now:
        # The process was down for the whole validity period; never grant dead bonuses.
        campaign.status = CampaignStatus.CANCELLED
        campaign.cancelled_at = now
        session.add(
            AuditEvent(
                event_type="promotion_campaign_expired_before_launch",
                target_type="promotion_campaigns",
                target_id=str(campaign.id),
                payload={"title": campaign.title},
            )
        )
        return

    rows = (
        await session.execute(
            select(Customer.id, Customer.telegram_user_id, LoyaltyAccount)
            .join(LoyaltyAccount, LoyaltyAccount.customer_id == Customer.id)
            .order_by(LoyaltyAccount.id)
            .with_for_update(of=LoyaltyAccount)
        )
    ).all()
    _deliver_campaign(session, campaign, rows)
    campaign.status = CampaignStatus.COMPLETED
    campaign.launched_at = now
    campaign.recipients_count = len(rows)
