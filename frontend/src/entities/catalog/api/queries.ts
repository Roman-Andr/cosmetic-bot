import { useQuery } from "@tanstack/react-query";

import { api } from "../../../shared/api/client";
import type { Product } from "../../loyalty/model/types";

export function useProductsQuery(query: string, enabled: boolean) {
  return useQuery({
    queryKey: ["catalog", "products", query],
    queryFn: () => api.get<Product[]>(`/admin/products?query=${encodeURIComponent(query)}`),
    enabled,
    staleTime: 60 * 1000,
  });
}
