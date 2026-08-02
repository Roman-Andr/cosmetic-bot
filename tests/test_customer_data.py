import pytest

from app.services.customer_data import InvalidPhoneError, mask_phone, normalize_phone


def test_normalize_phone_keeps_only_digits_and_adds_prefix() -> None:
    assert normalize_phone("+375 (29) 123-45-67") == "+375291234567"


@pytest.mark.parametrize("phone", ["123456", "1" * 16, "not-a-number"])
def test_normalize_phone_rejects_implausible_values(phone: str) -> None:
    with pytest.raises(InvalidPhoneError):
        normalize_phone(phone)


def test_mask_phone_preserves_identifying_edges_only() -> None:
    assert mask_phone("+375291234567") == "+375*******67"
    assert mask_phone("12345") == "12345"
