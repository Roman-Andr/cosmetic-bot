"""Shared customer-data normalization and privacy helpers."""

from __future__ import annotations


class InvalidPhoneError(ValueError):
    """A Telegram contact did not contain a plausible international phone number."""


def normalize_phone(phone: str) -> str:
    """Normalize a Telegram phone number to the E.164-like form stored by the app."""
    digits = "".join(character for character in phone if character.isdigit())
    if not 7 <= len(digits) <= 15:
        raise InvalidPhoneError("Phone number must contain between 7 and 15 digits")
    return f"+{digits}"


def mask_phone(phone: str) -> str:
    """Keep enough digits for till identification without exposing the full number."""
    if len(phone) <= 5:
        return phone
    return f"{phone[:4]}{'*' * max(1, len(phone) - 6)}{phone[-2:]}"
