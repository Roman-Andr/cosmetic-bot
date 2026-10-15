"""Promotion campaign validation, customer message and picture upload rules."""

import base64
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.models import (
    AuditEvent,
    BonusOperationType,
    BonusTransaction,
    CampaignStatus,
    LoyaltyAccount,
    NotificationOutbox,
    PromotionCampaign,
)
from app.schemas.admin import CampaignCreateRequest, CampaignUpdateRequest
from app.services.campaigns import (
    MAX_CAMPAIGN_PHOTO_BYTES,
    PHOTO_CAPTION_LIMIT,
    TEXT_MESSAGE_LIMIT,
    CampaignDraft,
    CampaignError,
    CampaignNotFoundError,
    CampaignStateError,
    accepts_late_recipients,
    campaign_message,
    decode_campaign_photo,
    late_recipients_count,
    send_campaign_to_late_recipients,
    update_campaign,
    validate_campaign,
)

NOW = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)  # 10:00 in Minsk


def draft(**changes: object) -> CampaignDraft:
    values: dict[str, object] = {
        "title": "День матери",
        "message_text": "С Днём матери!",
        "photo_file_id": None,
        "bonus_amount": Decimal("10"),
        "bonus_valid_until": date(2026, 10, 16),
        "starts_at": NOW,
    }
    values.update(changes)
    return CampaignDraft(**values)  # type: ignore[arg-type]


def test_campaign_message_appends_the_exact_gift_terms() -> None:
    assert campaign_message(" С Днём матери! ", Decimal("10"), date(2026, 10, 16)) == (
        "С Днём матери!\n\n"
        "🎁 Вам начислено 10.00 подарочных бонусов. Они действуют до 16.10.2026 включительно. "
        "Бонусами можно оплатить до 10% покупки."
    )


def test_campaign_without_bonus_is_a_plain_broadcast() -> None:
    assert campaign_message("Новая коллекция", Decimal("0"), None) == "Новая коллекция"


def test_valid_campaign_starting_now_is_accepted() -> None:
    validate_campaign(draft(), NOW)
    validate_campaign(draft(starts_at=NOW - timedelta(minutes=4)), NOW)


def test_campaign_start_in_the_past_is_rejected() -> None:
    with pytest.raises(CampaignError, match="уже прошло"):
        validate_campaign(draft(starts_at=NOW - timedelta(minutes=6)), NOW)


def test_campaign_start_needs_a_timezone() -> None:
    with pytest.raises(CampaignError, match="часовой пояс"):
        validate_campaign(draft(starts_at=datetime(2026, 10, 14, 10, 0)), NOW)


def test_gift_bonuses_need_a_validity_date() -> None:
    with pytest.raises(CampaignError, match="до какого дня"):
        validate_campaign(draft(bonus_valid_until=None), NOW)


def test_gift_bonuses_must_outlive_the_campaign_start() -> None:
    later_start = datetime(2026, 10, 17, 7, 0, tzinfo=UTC)
    with pytest.raises(CampaignError, match="после старта"):
        validate_campaign(draft(starts_at=later_start), NOW)


def test_gift_valid_through_the_start_day_is_accepted() -> None:
    validate_campaign(draft(bonus_valid_until=date(2026, 10, 13)), NOW)


def test_photo_caption_limit_includes_the_appended_terms() -> None:
    terms = len(campaign_message("", Decimal("10"), date(2026, 10, 16)))
    fits = "a" * (PHOTO_CAPTION_LIMIT - terms)
    validate_campaign(draft(message_text=fits, photo_file_id="file"), NOW)

    with pytest.raises(CampaignError, match="1024 с картинкой"):
        validate_campaign(draft(message_text=fits + "a", photo_file_id="file"), NOW)


def test_text_only_campaign_uses_the_telegram_message_limit() -> None:
    validate_campaign(draft(message_text="a" * TEXT_MESSAGE_LIMIT, bonus_amount=Decimal("0")), NOW)

    with pytest.raises(CampaignError, match="4096"):
        validate_campaign(
            draft(message_text="a" * (TEXT_MESSAGE_LIMIT + 1), bonus_amount=Decimal("0")), NOW
        )


def test_campaign_photo_accepts_jpeg_and_png() -> None:
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 32
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32

    assert decode_campaign_photo(base64.b64encode(jpeg).decode()) == jpeg
    assert decode_campaign_photo(base64.b64encode(png).decode()) == png


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not base64!", "прочитать"),
        (base64.b64encode(b"GIF89a-not-allowed").decode(), "JPEG и PNG"),
        (
            base64.b64encode(b"\xff\xd8\xff" + b"0" * MAX_CAMPAIGN_PHOTO_BYTES).decode(),
            "больше 5 МБ",
        ),
    ],
)
def test_campaign_photo_rejects_unusable_uploads(payload: str, message: str) -> None:
    with pytest.raises(CampaignError, match=message):
        decode_campaign_photo(payload)


def test_campaign_request_strips_text_and_rejects_blank_or_excessive_values() -> None:
    request = CampaignCreateRequest(
        title="  День матери ",
        message_text=" Текст ",
        bonus_amount=Decimal("10"),
        bonus_valid_until=date(2026, 10, 16),
        starts_at=NOW,
    )
    assert (request.title, request.message_text) == ("День матери", "Текст")

    with pytest.raises(ValidationError):
        CampaignCreateRequest(
            title="   ", message_text="Текст", bonus_amount=Decimal("0"), starts_at=NOW
        )
    with pytest.raises(ValidationError):
        CampaignCreateRequest(
            title="Акция", message_text="Текст", bonus_amount=Decimal("1000.01"), starts_at=NOW
        )


class FakeResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[object, ...]]:
        return self.rows


class FakeSession:
    """Just enough of AsyncSession for the campaign edit and late-delivery transactions."""

    def __init__(
        self, campaign: PromotionCampaign | None, rows: list[tuple[object, ...]] | None = None
    ) -> None:
        self.campaign = campaign
        self.rows = rows or []
        self.added: list[object] = []
        self.statements: list[object] = []
        self.committed = False
        self.rolled_back = False

    async def scalar(self, statement: object) -> PromotionCampaign | None:
        self.statements.append(statement)
        return self.campaign

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return FakeResult(self.rows)

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def scheduled_campaign(**changes: object) -> PromotionCampaign:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "title": "День матери",
        "message_text": "С праздником!",
        "photo_file_id": "stored-photo",
        "bonus_amount": Decimal("15.00"),
        "bonus_valid_until": date(2026, 10, 16),
        "starts_at": NOW + timedelta(days=1),
        "status": CampaignStatus.SCHEDULED,
        "created_by_telegram_id": 1,
    }
    values.update(changes)
    return PromotionCampaign(**values)


async def edit(
    session: FakeSession, change: CampaignDraft, *, keep_photo: bool = False
) -> PromotionCampaign:
    return await update_campaign(
        session,  # type: ignore[arg-type]
        uuid.uuid4(),
        change,
        keep_photo=keep_photo,
        actor_telegram_id=42,
        now=NOW,
    )


async def test_scheduled_campaign_edit_replaces_every_owner_field() -> None:
    campaign = scheduled_campaign()
    session = FakeSession(campaign)
    starts_at = NOW + timedelta(hours=3)

    await edit(
        session,
        draft(
            title=" Мамин день ",
            message_text=" Новый текст ",
            photo_file_id="new-photo",
            bonus_amount=Decimal("20"),
            bonus_valid_until=date(2026, 10, 18),
            starts_at=starts_at,
        ),
    )

    assert (campaign.title, campaign.message_text, campaign.photo_file_id) == (
        "Мамин день",
        "Новый текст",
        "new-photo",
    )
    assert campaign.bonus_amount == Decimal("20.00")
    assert campaign.bonus_valid_until == date(2026, 10, 18)
    assert campaign.starts_at == starts_at
    assert campaign.status is CampaignStatus.SCHEDULED
    assert session.committed
    [audit] = session.added
    assert isinstance(audit, AuditEvent)
    assert audit.event_type == "promotion_campaign_updated"
    assert audit.actor_telegram_id == 42
    assert audit.payload["before"]["bonus_amount"] == "15.00"
    assert audit.payload["after"]["bonus_amount"] == "20.00"


async def test_campaign_edit_locks_the_row_against_a_concurrent_launch() -> None:
    session = FakeSession(scheduled_campaign())

    await edit(session, draft())

    [statement] = session.statements
    assert "FOR UPDATE" in str(statement.compile())  # type: ignore[attr-defined]


async def test_campaign_edit_can_keep_or_remove_the_stored_photo() -> None:
    kept = scheduled_campaign()
    await edit(FakeSession(kept), draft(photo_file_id=None), keep_photo=True)
    assert kept.photo_file_id == "stored-photo"

    removed = scheduled_campaign()
    await edit(FakeSession(removed), draft(photo_file_id=None))
    assert removed.photo_file_id is None


async def test_kept_photo_applies_the_caption_limit() -> None:
    session = FakeSession(scheduled_campaign())
    long_text = "а" * PHOTO_CAPTION_LIMIT

    with pytest.raises(CampaignError, match="1024"):
        await edit(session, draft(message_text=long_text), keep_photo=True)
    assert session.rolled_back and not session.committed


async def test_campaign_edit_to_no_bonus_clears_the_validity_date() -> None:
    campaign = scheduled_campaign()

    await edit(FakeSession(campaign), draft(bonus_amount=Decimal("0")))

    assert campaign.bonus_amount == Decimal("0.00")
    assert campaign.bonus_valid_until is None


async def test_campaign_edit_is_validated_like_a_new_campaign() -> None:
    campaign = scheduled_campaign()
    session = FakeSession(campaign)

    with pytest.raises(CampaignError, match="прошло"):
        await edit(session, draft(starts_at=NOW - timedelta(hours=1)))

    assert campaign.starts_at == NOW + timedelta(days=1)
    assert session.rolled_back and not session.added


@pytest.mark.parametrize("status", [CampaignStatus.COMPLETED, CampaignStatus.CANCELLED])
async def test_launched_or_cancelled_campaign_cannot_be_edited(status: CampaignStatus) -> None:
    campaign = scheduled_campaign(status=status)
    session = FakeSession(campaign)

    with pytest.raises(CampaignStateError):
        await edit(session, draft(title="Другое"))

    assert campaign.title == "День матери"
    assert session.rolled_back and not session.committed


async def test_editing_a_missing_campaign_is_reported() -> None:
    with pytest.raises(CampaignNotFoundError):
        await edit(FakeSession(None), draft())


def test_campaign_update_cannot_both_keep_and_replace_the_photo() -> None:
    values: dict[str, object] = {
        "title": "Акция",
        "message_text": "Текст",
        "bonus_amount": Decimal("0"),
        "starts_at": NOW,
    }
    assert CampaignUpdateRequest(**values, keep_photo=True).keep_photo  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        CampaignUpdateRequest(**values, keep_photo=True, photo_file_id="new")  # type: ignore[arg-type]


def launched_campaign(**changes: object) -> PromotionCampaign:
    values: dict[str, object] = {
        "starts_at": NOW - timedelta(days=1),
        "status": CampaignStatus.COMPLETED,
        "launched_at": NOW - timedelta(days=1),
        "recipients_count": 10,
    }
    values.update(changes)
    return scheduled_campaign(**values)


def newcomer(balance: str = "0.00") -> tuple[uuid.UUID, int, LoyaltyAccount]:
    account = LoyaltyAccount(id=uuid.uuid4(), current_balance=Decimal(balance))
    return uuid.uuid4(), 555, account


def test_only_launched_gift_campaigns_with_live_bonuses_accept_late_recipients() -> None:
    assert accepts_late_recipients(launched_campaign(), NOW)
    # Valid through 16 Oct in Minsk means spendable until 16 Oct 23:59 Minsk (20:59 UTC).
    assert accepts_late_recipients(launched_campaign(), datetime(2026, 10, 16, 20, 59, tzinfo=UTC))
    assert not accepts_late_recipients(launched_campaign(), datetime(2026, 10, 16, 21, tzinfo=UTC))
    assert not accepts_late_recipients(
        launched_campaign(bonus_amount=Decimal("0"), bonus_valid_until=None), NOW
    )
    assert not accepts_late_recipients(scheduled_campaign(), NOW)
    assert not accepts_late_recipients(launched_campaign(status=CampaignStatus.CANCELLED), NOW)


async def test_late_recipient_count_skips_the_query_for_closed_campaigns() -> None:
    session = FakeSession(None)

    assert await late_recipients_count(session, scheduled_campaign(), NOW) == 0  # type: ignore[arg-type]
    assert session.statements == []


async def send_late(session: FakeSession) -> int:
    return await send_campaign_to_late_recipients(
        session,  # type: ignore[arg-type]
        uuid.uuid4(),
        actor_telegram_id=42,
        now=NOW,
    )


async def test_late_recipients_get_the_same_gift_lot_and_message() -> None:
    campaign = launched_campaign()
    customer_id, chat_id, account = newcomer("3.00")
    session = FakeSession(campaign, [(customer_id, chat_id, account)])

    assert await send_late(session) == 1

    lot, message, audit = session.added
    assert isinstance(lot, BonusTransaction)
    assert lot.operation_type is BonusOperationType.PROMOTION
    assert (lot.amount, lot.balance_after) == (Decimal("15.00"), Decimal("18.00"))
    assert lot.expires_at == datetime(2026, 10, 16, 21, tzinfo=UTC)
    assert lot.campaign_id == campaign.id
    assert account.current_balance == Decimal("18.00")
    assert isinstance(message, NotificationOutbox)
    assert message.chat_id == chat_id
    assert message.photo_file_id == "stored-photo"
    assert message.dedupe_key == f"campaign:{campaign.id}:{customer_id}"
    assert "до 16.10.2026 включительно" in message.body
    assert isinstance(audit, AuditEvent)
    assert audit.payload == {"title": "День матери", "recipients": 1}
    assert campaign.recipients_count == 11
    assert session.committed


async def test_late_delivery_only_targets_locked_accounts_without_the_gift() -> None:
    session = FakeSession(launched_campaign(), [newcomer()])

    await send_late(session)

    sql = str(session.statements[-1].compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]
    assert "NOT (EXISTS" in sql
    assert "bonus_transactions.campaign_id" in sql
    assert "FOR UPDATE OF loyalty_accounts" in sql


async def test_late_delivery_with_nobody_missing_changes_nothing() -> None:
    campaign = launched_campaign()
    session = FakeSession(campaign)

    assert await send_late(session) == 0

    assert session.added == []
    assert campaign.recipients_count == 10


async def test_expired_gift_campaign_cannot_be_sent_late() -> None:
    session = FakeSession(launched_campaign(bonus_valid_until=date(2026, 10, 12)), [newcomer()])

    with pytest.raises(CampaignStateError, match="сгорели"):
        await send_late(session)

    assert session.added == []
    assert session.rolled_back and not session.committed
