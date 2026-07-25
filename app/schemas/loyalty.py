"""Mini App request and response contracts."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AdminRole, BonusOperationType, CashbackSource, Gender


class RegistrationRequest(BaseModel):
    """Customer details collected after Telegram contact sharing."""

    full_name: str = Field(min_length=2, max_length=255)
    birth_date: date = Field(description="ISO date supplied by the Mini App")
    gender: Gender

    @field_validator("birth_date")
    @classmethod
    def birth_date_must_not_be_in_the_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Birth date cannot be in the future")
        return value


class FullNameUpdateRequest(BaseModel):
    """The only personal field a customer may edit after registration."""

    full_name: str = Field(min_length=2, max_length=255)


class TierResponse(BaseModel):
    """Current tier determined from all-time turnover."""

    minimum_turnover: Decimal
    cashback_percent: Decimal


class TierProgressResponse(BaseModel):
    """Gamification data for the customer's current and next lifetime-turnover tier."""

    current_tier: TierResponse
    next_tier: TierResponse | None
    amount_to_next_tier: Decimal
    progress_percent: Decimal
    tiers: list[TierResponse]


class PurchaseSummaryResponse(BaseModel):
    """Customer-visible purchase history row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    total_amount: Decimal
    bonus_redeemed: Decimal
    cashback_percent: Decimal
    cashback_source: CashbackSource
    cashback_accrued: Decimal


class BonusTransactionResponse(BaseModel):
    """One immutable balance movement visible to the loyalty customer."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    operation_type: BonusOperationType
    amount: Decimal
    balance_after: Decimal
    purchase_id: UUID | None


class ProfileResponse(BaseModel):
    """Loyalty profile returned to the Mini App."""

    full_name: str
    phone: str
    birth_date: date
    gender: Gender
    registered_at: datetime
    current_balance: Decimal
    lifetime_turnover: Decimal
    tier: TierResponse
    birthday_cashback_active: bool
    birthday_cashback_percent: Decimal
    birthday_cashback_window_days: int
    is_owner: bool
    admin_role: AdminRole | None
    tier_progress: TierProgressResponse


class ContactStatusResponse(BaseModel):
    """Whether a fresh Telegram contact share is ready for registration."""

    is_available: bool


class CodeResponse(BaseModel):
    """A plaintext code returned once to the authenticated customer."""

    code: str = Field(pattern=r"^\d{6}$")
    expires_at: datetime


class PurchasePageResponse(BaseModel):
    """Paginated customer purchase history."""

    items: list[PurchaseSummaryResponse]
    next_offset: int | None


class BonusTransactionPageResponse(BaseModel):
    """Paginated ledger entries with no hidden balance adjustment paths."""

    items: list[BonusTransactionResponse]
    next_offset: int | None
