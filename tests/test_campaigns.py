"""Promotion campaign validation, customer message and picture upload rules."""

import base64
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.admin import CampaignCreateRequest
from app.services.campaigns import (
    MAX_CAMPAIGN_PHOTO_BYTES,
    PHOTO_CAPTION_LIMIT,
    TEXT_MESSAGE_LIMIT,
    CampaignDraft,
    CampaignError,
    campaign_message,
    decode_campaign_photo,
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
