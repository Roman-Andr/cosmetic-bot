export const adminKeys = {
  all: ["admin"] as const,
  access: ["admin", "access"] as const,
  administrators: ["admin", "administrators"] as const,
  customer: (customerId: string) => ["admin", "customers", "detail", customerId] as const,
  customerPurchases: (customerId: string) =>
    ["admin", "customers", "detail", customerId, "purchases"] as const,
  customers: ["admin", "customers"] as const,
  customerSearch: (query: string) => ["admin", "customers", "search", query] as const,
  stats: ["admin", "stats"] as const,
  tiers: ["admin", "tiers"] as const,
};
