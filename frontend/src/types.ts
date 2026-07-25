export type Gender = "male" | "female";

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
}

export interface Purchase {
  id: string;
  created_at: string;
  total_amount: string;
  bonus_redeemed: string;
  cashback_accrued: string;
}

export interface PurchasePage {
  items: Purchase[];
  next_offset: number | null;
}

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
