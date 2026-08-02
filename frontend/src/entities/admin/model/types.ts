import type {
  AdminRole,
  CashbackSource,
  Gender,
} from "../../loyalty/model/types";

export interface Stats {
  registrations: number;
  purchase_count: number;
  turnover: string;
  accrued_bonuses: string;
  redeemed_bonuses: string;
  bonus_liability: string;
  tier_distribution: Record<string, number>;
}

export interface CustomerSearchResult {
  customer_id: string;
  full_name: string;
  phone: string;
  telegram_user_id: number;
  registered_at: string;
  current_balance: string;
  lifetime_turnover: string;
}

export interface CustomerDetail extends CustomerSearchResult {
  birth_date: string;
  gender: Gender;
}

export interface AdminAccess {
  role: AdminRole;
}

export interface BuyerLookup {
  customer_name: string;
  customer_phone_masked: string;
  registered_at: string;
  current_balance: string;
  cashback_percent: string;
  cashback_source: CashbackSource;
}

export interface SalePreview {
  customer_name: string;
  customer_phone_masked: string;
  current_balance: string;
  total_amount: string;
  bonus_redeemed: string;
  cash_paid: string;
  cashback_accrued: string;
  cashback_percent: string;
  cashback_source: CashbackSource;
}

export interface SaleRecord {
  purchase_id: string;
  bonus_redeemed: string;
  cash_paid: string;
  cashback_accrued: string;
  cashback_percent: string;
  cashback_source: CashbackSource;
  balance_after: string;
}

export interface Administrator {
  telegram_user_id: number;
  role: AdminRole;
  is_active: boolean;
  created_at: string;
}

export interface TierRuleInput {
  cashback_percent: string;
  minimum_turnover: string;
}

export interface SalePreviewInput {
  buyer_code: string;
  total_amount: string;
}

export interface SaleInput extends SalePreviewInput {
  product_external_ids: string[];
}
