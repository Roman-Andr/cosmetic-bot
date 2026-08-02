import { useQuery } from "@tanstack/react-query";

import { api } from "../../../shared/api/client";
import type { PurchasePage, Tier } from "../../loyalty/model/types";
import type {
  Administrator,
  AdminAccess,
  BuyerLookup,
  CustomerDetail,
  CustomerSearchResult,
  Stats,
} from "../model/types";
import { adminKeys } from "./queryKeys";

export function useAdminAccessQuery() {
  return useQuery({
    queryKey: adminKeys.access,
    queryFn: () => api.get<AdminAccess>("/admin/access"),
    staleTime: 60 * 1000,
  });
}

export function useAdminStatsQuery() {
  return useQuery({
    queryKey: adminKeys.stats,
    queryFn: () => api.get<Stats>("/admin/stats"),
    staleTime: 30 * 1000,
  });
}

export function useAdminTiersQuery() {
  return useQuery({
    queryKey: adminKeys.tiers,
    queryFn: () => api.get<Tier[]>("/admin/tiers"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useCustomerSearchQuery(query: string) {
  return useQuery({
    queryKey: adminKeys.customerSearch(query),
    queryFn: () =>
      api.get<CustomerSearchResult[]>(
        `/admin/customers/search?query=${encodeURIComponent(query)}`,
      ),
    enabled: query.length >= 2,
  });
}

export function useCustomerQuery(customerId: string | null) {
  return useQuery({
    queryKey: adminKeys.customer(customerId ?? ""),
    queryFn: () => api.get<CustomerDetail>(`/admin/customers/${customerId}`),
    enabled: customerId !== null,
  });
}

export function useCustomerPurchasesQuery(customerId: string | null) {
  return useQuery({
    queryKey: adminKeys.customerPurchases(customerId ?? ""),
    queryFn: () => api.get<PurchasePage>(`/admin/customers/${customerId}/purchases`),
    enabled: customerId !== null,
    staleTime: 15 * 1000,
  });
}

export function useAdministratorsQuery(enabled = true) {
  return useQuery({
    queryKey: adminKeys.administrators,
    queryFn: () => api.get<Administrator[]>("/admin/administrators"),
    enabled,
  });
}

export function useBuyerQuery(buyerCode: string) {
  return useQuery({
    queryKey: ["sale", "buyer", buyerCode],
    queryFn: () =>
      api.get<BuyerLookup>(`/admin/purchases/customer?buyer_code=${buyerCode}`),
    enabled: /^\d{6}$/.test(buyerCode),
    gcTime: 0,
    refetchOnMount: "always",
    staleTime: 0,
  });
}
