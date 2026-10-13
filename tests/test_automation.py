"""Pure decision logic behind expiry warnings and birthday reminders."""

import uuid
from datetime import date
from decimal import Decimal

from app.services.automation import (
    ExpiringLot,
    birthday_message,
    birthday_window,
    days_until_expiry,
    expiry_warning_message,
    expiry_warnings,
    format_percent,
)
from app.services.loyalty import BonusExpiration, expiry_instant

TODAY = date(2026, 10, 13)
ANNA = uuid.uuid4()
BORIS = uuid.uuid4()


def expiring(account: uuid.UUID, amount: str, valid_through: date, chat_id: int = 1) -> ExpiringLot:
    return ExpiringLot(
        account_id=account,
        telegram_user_id=chat_id,
        remaining=Decimal(amount),
        expires_at=expiry_instant(valid_through),
    )


def test_days_until_expiry_counts_the_last_valid_day_as_one() -> None:
    assert days_until_expiry(expiry_instant(TODAY), TODAY) == 1
    assert days_until_expiry(expiry_instant(date(2026, 10, 19)), TODAY) == 7
    assert days_until_expiry(expiry_instant(date(2026, 10, 26)), TODAY) == 14


def test_expiry_warnings_fire_only_fourteen_seven_and_one_day_ahead() -> None:
    lots = [
        expiring(ANNA, "3.00", date(2026, 10, 26)),  # 14 days
        expiring(ANNA, "2.00", date(2026, 10, 26)),  # same day, same account
        expiring(ANNA, "4.00", date(2026, 10, 20)),  # 8 days: no warning today
        expiring(BORIS, "10.00", TODAY, chat_id=2),  # last day
    ]

    assert expiry_warnings(lots, TODAY) == {
        (ANNA, 1): [BonusExpiration(amount=Decimal("5.00"), valid_until=date(2026, 10, 26))],
        (BORIS, 2): [BonusExpiration(amount=Decimal("10.00"), valid_until=TODAY)],
    }


def test_expiry_warnings_group_several_days_into_one_sorted_message() -> None:
    lots = [
        expiring(ANNA, "6.00", date(2026, 10, 26)),
        expiring(ANNA, "1.50", date(2026, 10, 19)),
    ]

    assert expiry_warnings(lots, TODAY)[(ANNA, 1)] == [
        BonusExpiration(amount=Decimal("1.50"), valid_until=date(2026, 10, 19)),
        BonusExpiration(amount=Decimal("6.00"), valid_until=date(2026, 10, 26)),
    ]


def test_expiry_warnings_skip_negligible_amounts() -> None:
    assert expiry_warnings([expiring(ANNA, "0.99", TODAY)], TODAY) == {}


def test_expiry_warning_message_variants() -> None:
    last_day = expiry_warning_message(
        [BonusExpiration(amount=Decimal("10.00"), valid_until=TODAY)], TODAY
    )
    assert last_day.startswith("⏳ Сегодня последний день: 10.00 бонусов сгорят в полночь.")
    assert "до 10% покупки" in last_day

    upcoming = expiry_warning_message(
        [BonusExpiration(amount=Decimal("5.00"), valid_until=date(2026, 10, 26))], TODAY
    )
    assert upcoming.startswith("⏳ 5.00 бонусов действуют до 26.10.2026 включительно")

    several = expiry_warning_message(
        [
            BonusExpiration(amount=Decimal("1.50"), valid_until=date(2026, 10, 19)),
            BonusExpiration(amount=Decimal("6.00"), valid_until=date(2026, 10, 26)),
        ],
        TODAY,
    )
    assert "• 1.50 — до 19.10.2026 включительно\n• 6.00 — до 26.10.2026" in several


def test_birthday_window_contains_today_including_its_inclusive_edges() -> None:
    birth = date(1990, 10, 15)

    assert birthday_window(birth, date(2026, 10, 12), window_days=3) == (
        date(2026, 10, 12),
        date(2026, 10, 15),
        date(2026, 10, 18),
    )
    assert birthday_window(birth, date(2026, 10, 18), window_days=3) is not None
    assert birthday_window(birth, date(2026, 10, 11), window_days=3) is None
    assert birthday_window(birth, date(2026, 10, 19), window_days=3) is None


def test_birthday_window_crosses_the_new_year() -> None:
    assert birthday_window(date(1992, 1, 1), date(2026, 12, 30), window_days=3) == (
        date(2026, 12, 29),
        date(2027, 1, 1),
        date(2027, 1, 4),
    )


def test_leap_day_birthday_window_uses_february_28_in_common_years() -> None:
    window = birthday_window(date(2000, 2, 29), date(2027, 2, 25), window_days=3)

    assert window is not None
    assert window[1] == date(2027, 2, 28)


def test_birthday_message_adapts_the_greeting_and_formats_the_rate() -> None:
    window = {
        "start": date(2026, 10, 12),
        "birthday": date(2026, 10, 15),
        "end": date(2026, 10, 18),
    }

    before = birthday_message(today=date(2026, 10, 12), percent=Decimal("10.00"), **window)
    assert before == (
        "🎂 Скоро ваш день рождения! С 12.10 по 18.10 включительно действует праздничный "
        "кешбэк 10% на покупки. Ждём вас!"
    )
    assert birthday_message(today=date(2026, 10, 15), percent=Decimal("10"), **window).startswith(
        "🎂 С днём рождения!"
    )
    assert birthday_message(today=date(2026, 10, 17), percent=Decimal("10"), **window).startswith(
        "🎂 С прошедшим днём рождения!"
    )


def test_format_percent_drops_insignificant_zeros() -> None:
    assert format_percent(Decimal("10.00")) == "10"
    assert format_percent(Decimal("7.50")) == "7.5"
