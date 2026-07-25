import { getTelegramApp } from "../lib/telegram";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const initData = getTelegramApp()?.initData;
  if (!initData) throw new ApiError(401, "Откройте приложение внутри Telegram.");
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData,
      ...options.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(response.status, payload?.detail ?? "Не удалось выполнить запрос.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function download(path: string, filename: string): Promise<void> {
  const initData = getTelegramApp()?.initData;
  if (!initData) throw new ApiError(401, "Откройте приложение внутри Telegram.");
  const response = await fetch(`/api${path}`, { headers: { "X-Telegram-Init-Data": initData } });
  if (!response.ok) throw new ApiError(response.status, "Не удалось создать выгрузку.");
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, payload?: unknown) =>
    request<T>(path, { method: "POST", body: payload === undefined ? undefined : JSON.stringify(payload) }),
  patch: <T>(path: string, payload: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(payload) }),
  put: <T>(path: string, payload: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(payload) }),
};
