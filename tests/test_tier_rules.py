from decimal import Decimal

import pytest

from app.services.tier_rules import TierRuleValue, parse_tier_rules


def test_parse_tier_rules_returns_normalized_values() -> None:
    assert parse_tier_rules("0:3, 1000:5.5, 2000:7") == [
        TierRuleValue(Decimal("0.00"), Decimal("3.00")),
        TierRuleValue(Decimal("1000.00"), Decimal("5.50")),
        TierRuleValue(Decimal("2000.00"), Decimal("7.00")),
    ]


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("", "Количество уровней"),
        ("100:3", "Первый порог"),
        ("0:3, 0:5", "строго возрастать"),
        ("0:101", "процент"),
        ("0-three", "формат"),
        ("zero:3", "числами"),
        ("0:NaN", "процент"),
        ("NaN:3", "Порог"),
    ],
)
def test_parse_tier_rules_rejects_invalid_configurations(raw: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_tier_rules(raw)
