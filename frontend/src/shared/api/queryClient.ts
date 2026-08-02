import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./client";

function shouldRetry(failureCount: number, error: Error): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  return failureCount < 2;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        gcTime: 5 * 60 * 1000,
        refetchOnReconnect: true,
        refetchOnWindowFocus: true,
        retry: shouldRetry,
        staleTime: 30 * 1000,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export const queryClient = createQueryClient();
