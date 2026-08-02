import { queryOptions, useQuery } from "@tanstack/react-query";

import { api } from "../../../shared/api/client";
import type { BonusTransactionPage, Profile, PurchasePage } from "../model/types";
import { loyaltyKeys } from "./queryKeys";

interface ContactStatus {
  is_available: boolean;
}

export function profileQueryOptions() {
  return queryOptions({
    queryKey: loyaltyKeys.profile,
    queryFn: () => api.get<Profile>("/loyalty/me"),
  });
}

export function contactStatusQueryOptions() {
  return queryOptions({
    queryKey: loyaltyKeys.contactStatus,
    queryFn: () => api.get<ContactStatus>("/loyalty/contact-status"),
    staleTime: 0,
  });
}

export function useProfileQuery({ live = false }: { live?: boolean } = {}) {
  return useQuery({
    ...profileQueryOptions(),
    refetchInterval: live ? 5000 : false,
    refetchIntervalInBackground: false,
  });
}

export function useContactStatusQuery(enabled: boolean) {
  return useQuery({ ...contactStatusQueryOptions(), enabled });
}

export function useTransactionsQuery({
  limit,
  live = false,
  offset = 0,
}: {
  limit?: number;
  live?: boolean;
  offset?: number;
} = {}) {
  const parameters = new URLSearchParams();
  if (limit !== undefined) parameters.set("limit", String(limit));
  if (offset > 0) parameters.set("offset", String(offset));
  const suffix = parameters.size > 0 ? `?${parameters.toString()}` : "";

  return useQuery({
    queryKey: loyaltyKeys.transactions(limit, offset),
    queryFn: () => api.get<BonusTransactionPage>(`/loyalty/transactions${suffix}`),
    refetchInterval: live ? 5000 : false,
    refetchIntervalInBackground: false,
    staleTime: live ? 0 : 15 * 1000,
  });
}

export function usePurchasesQuery(offset = 0) {
  const suffix = offset > 0 ? `?offset=${offset}` : "";
  return useQuery({
    queryKey: loyaltyKeys.purchases(offset),
    queryFn: () => api.get<PurchasePage>(`/loyalty/purchases${suffix}`),
    staleTime: 15 * 1000,
  });
}
