from app.models.domain import (
    AdminRole,
    BonusOperationType,
    CampaignStatus,
    CashbackSource,
    Gender,
    PurchaseStatus,
    SupportDialogStatus,
    enum_values,
)


def test_database_enums_use_stable_lowercase_values() -> None:
    assert enum_values(Gender) == ["male", "female"]
    assert enum_values(AdminRole) == ["owner", "sales"]
    assert enum_values(PurchaseStatus) == ["confirmed"]
    assert enum_values(CashbackSource) == ["tier", "birthday"]
    assert enum_values(BonusOperationType) == ["accrual", "redemption", "expiration", "promotion"]
    assert enum_values(CampaignStatus) == ["scheduled", "completed", "cancelled"]
    assert enum_values(SupportDialogStatus) == ["open", "closed"]
