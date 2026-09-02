import { getTelegramApp } from "./telegram";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "velina.theme";
export const DEFAULT_THEME_PREFERENCE = "light" satisfies ThemePreference;

/** Canvas colour per theme, mirrored from `--color-canvas` in `app/styles.css`. */
export const THEME_CANVAS: Record<ResolvedTheme, string> = {
  light: "#f1f5f4",
  dark: "#000000",
};

const PREFERENCES: readonly ThemePreference[] = ["light", "dark", "system"];

export function isThemePreference(value: unknown): value is ThemePreference {
  return typeof value === "string" && PREFERENCES.includes(value as ThemePreference);
}

export function readStoredTheme(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemePreference(stored) ? stored : DEFAULT_THEME_PREFERENCE;
  } catch {
    return DEFAULT_THEME_PREFERENCE;
  }
}

function storeTheme(preference: ThemePreference): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Private-mode browsers reject writes; the choice then lasts for the session only.
  }
}

/** The theme to follow while the preference is `system`. */
export function clientTheme(): ResolvedTheme {
  const telegramScheme = getTelegramApp()?.colorScheme;
  if (telegramScheme === "light" || telegramScheme === "dark") return telegramScheme;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  return preference === "system" ? clientTheme() : preference;
}

export function applyTheme(theme: ResolvedTheme): void {
  const canvas = THEME_CANVAS[theme];
  const root = document.documentElement;
  root.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", canvas);
  const telegram = getTelegramApp();
  telegram?.setHeaderColor?.(canvas);
  telegram?.setBackgroundColor?.(canvas);
}

const listeners = new Set<() => void>();
let preference: ThemePreference = DEFAULT_THEME_PREFERENCE;
let resolved: ResolvedTheme = DEFAULT_THEME_PREFERENCE;
let initialized = false;

function publish(): void {
  applyTheme(resolved);
  for (const listener of listeners) listener();
}

function followClient(): void {
  const next = resolveTheme(preference);
  if (next === resolved) return;
  resolved = next;
  publish();
}

/**
 * Loads the stored preference and starts following the client theme. Safe to call
 * repeatedly — only the first call reads storage — and returns a teardown for the
 * client-theme subscriptions.
 */
export function initTheme(): () => void {
  if (!initialized) {
    initialized = true;
    preference = readStoredTheme();
    resolved = resolveTheme(preference);
  }
  publish();

  const media = window.matchMedia?.("(prefers-color-scheme: dark)");
  media?.addEventListener("change", followClient);
  const telegram = getTelegramApp();
  telegram?.onEvent("themeChanged", followClient);
  return () => {
    media?.removeEventListener("change", followClient);
    telegram?.offEvent("themeChanged", followClient);
  };
}

export function getThemePreference(): ThemePreference {
  return preference;
}

export function setThemePreference(next: ThemePreference): void {
  if (next === preference) return;
  preference = next;
  storeTheme(next);
  resolved = resolveTheme(next);
  publish();
}

export function subscribeToTheme(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
