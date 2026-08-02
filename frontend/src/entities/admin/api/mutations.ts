import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../../shared/api/client";
import { loyaltyKeys } from "../../loyalty/api/queryKeys";
import type { Administrator, SalePreview, SaleRecord, Tier } from "../../loyalty/model/types";
import { adminKeys } from "./queryKeys";

interface TierRuleInput {
  cashback_percent: string;
  minimum_turnover: string;
}

interface SalePreviewInput {
  buyer_code: string;
  total_amount: string;
}

interface SaleInput extends SalePreviewInput {
  product_external_ids: string[];
}

export function useUpdateTiersMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rules: TierRuleInput[]) => api.put<Tier[]>("/admin/tiers", { rules }),
    onSuccess: async (tiers) => {
      queryClient.setQueryData(adminKeys.tiers, tiers);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: loyaltyKeys.profile }),
        queryClient.invalidateQueries({ queryKey: adminKeys.stats }),
      ]);
    },
  });
}

export function useAddAdministratorMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (telegramUserId: number) =>
      api.post<Administrator>("/admin/administrators", { telegram_user_id: telegramUserId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.administrators }),
  });
}

export function useSalePreviewMutation() {
  return useMutation({
    mutationFn: (payload: SalePreviewInput) =>
      api.post<SalePreview>("/admin/purchases/preview", payload),
  });
}

export function useRecordSaleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SaleInput) => api.post<SaleRecord>("/admin/purchases", payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: loyaltyKeys.all }),
        queryClient.invalidateQueries({ queryKey: adminKeys.stats }),
        queryClient.invalidateQueries({ queryKey: adminKeys.customers }),
      ]);
    },
  });
}
