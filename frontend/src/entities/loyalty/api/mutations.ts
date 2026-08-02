import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../../../shared/api/client";
import type { Gender, LoyaltyCode, Profile } from "../model/types";
import { loyaltyKeys } from "./queryKeys";

interface RegistrationInput {
  birth_date: string;
  full_name: string;
  gender: Gender;
}

export function useRegisterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RegistrationInput) => api.post<Profile>("/loyalty/register", payload),
    onSuccess: (profile) => {
      queryClient.setQueryData(loyaltyKeys.profile, profile);
      queryClient.setQueryData(loyaltyKeys.contactStatus, { is_available: true });
    },
  });
}

export function useUpdateProfileMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { full_name: string }) => api.patch<Profile>("/loyalty/me", payload),
    onSuccess: (profile) => queryClient.setQueryData(loyaltyKeys.profile, profile),
  });
}

export function useIssueLoyaltyCodeMutation() {
  return useMutation({
    mutationFn: () => api.post<LoyaltyCode>("/loyalty/code"),
    gcTime: 0,
  });
}
