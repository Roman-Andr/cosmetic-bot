export const loyaltyKeys = {
  all: ["loyalty"] as const,
  contactStatus: ["loyalty", "contact-status"] as const,
  profile: ["loyalty", "profile"] as const,
  purchases: (offset = 0) => ["loyalty", "purchases", { offset }] as const,
  transactions: (limit?: number, offset = 0) =>
    ["loyalty", "transactions", { limit: limit ?? null, offset }] as const,
};
