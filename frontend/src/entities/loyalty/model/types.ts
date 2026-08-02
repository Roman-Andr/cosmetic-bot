export type Gender = "male" | "female";
export type AdminRole = "owner" | "sales";
export type CashbackSource = "tier" | "birthday";

export interface Tier {
  id?: number;
  minimum_turnover: string;
  cashback_percent: string;
}

export interface Profile {
  full_name: string;
  phone: string;
  birth_date: string;
  gender: Gender;
  registered_at: string;
  current_balance: string;
  lifetime_turnover: string;
  tier: { minimum_turnover: string; cashback_percent: string };
  tier_progress: TierProgress;
  birthday_cashback_active: boolean;
  birthday_cashback_percent: string;
  birthday_cashback_window_days: number;
  is_owner: boolean;
  admin_role: AdminRole | null;
}

export interface TierProgress {
  current_tier: Tier;
  next_tier: Tier | null;
  amount_to_next_tier: string;
  progress_percent: string;
  tiers: Tier[];
}

export interface Purchase {
  id: string;
  created_at: string;
  total_amount: string;
  bonus_redeemed: string;
  cashback_percent: string;
  cashback_source: CashbackSource;
  cashback_accrued: string;
}

export interface PurchasePage {
  items: Purchase[];
  next_offset: number | null;
}

export interface BonusTransaction {
  id: string;
  created_at: string;
  operation_type: "accrual" | "redemption";
  amount: string;
  balance_after: string;
  purchase_id: string | null;
}

export interface BonusTransactionPage {
  items: BonusTransaction[];
  next_offset: number | null;
}

export interface LoyaltyCode {
  code: string;
  expires_at: string;
}
