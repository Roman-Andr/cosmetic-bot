"""Owner and sales-administration API contracts."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProductResponse(BaseModel):
    """Product search result available while recording a purchase."""

    external_id: str
    title: str
    current_price: Decimal | None


class CustomerSearchResponse(BaseModel):
    """Owner-visible customer search result."""

    customer_id: UUID
    full_name: str
    phone: str
    telegram_user_id: int
    registered_at: datetime
    current_balance: Decimal
    lifetime_turnover: Decimal


class CustomerDetailResponse(CustomerSearchResponse):
    """Expanded owner-visible customer card."""

    birth_date: date
    gender: str


class AdminStatsResponse(BaseModel):
    """Dashboard aggregates for an optional date range."""

    registrations: int
    purchase_count: int
    turnover: Decimal
    accrued_bonuses: Decimal
    redeemed_bonuses: Decimal
    bonus_liability: Decimal
    tier_distribution: dict[str, int]


class TierRuleInput(BaseModel):
    """One owner-editable cashback threshold."""

    minimum_turnover: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    cashback_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)


class TierRulesUpdateRequest(BaseModel):
    """The complete sorted tier table submitted by the owner."""

    rules: list[TierRuleInput] = Field(min_length=1, max_length=10)

    @field_validator("rules")
    @classmethod
    def rules_start_at_zero_and_are_unique(cls, rules: list[TierRuleInput]) -> list[TierRuleInput]:
        thresholds = [rule.minimum_turnover for rule in rules]
        if thresholds[0] != 0:
            raise ValueError("The first tier must start at 0 BYN")
        if thresholds != sorted(thresholds) or len(set(thresholds)) != len(thresholds):
            raise ValueError("Tier thresholds must be strictly increasing")
        return rules


class TierRuleResponse(TierRuleInput):
    """A persisted active tier rule."""

    id: int


class AddSalesAdminRequest(BaseModel):
    """Owner request to grant sales-only access to a Telegram account."""

    telegram_user_id: int = Field(gt=0)


class AdminUserResponse(BaseModel):
    """Administrator role record."""

    telegram_user_id: int
    role: str
    is_active: bool
    created_at: datetime
