import { afterEach, describe, expect, test } from "bun:test";

import {
  DEFAULT_THEME_PREFERENCE,
  THEME_CANVAS,
  THEME_STORAGE_KEY,
  applyTheme,
  clientTheme,
  isThemePreference,
  readStoredTheme,
  resolveTheme,
} from "../src/shared/lib/theme";

const originalWindow = globalThis.window;
const originalDocument = globalThis.document;

function define(name: "window" | "document", value: unknown): void {
  Object.defineProperty(globalThis, name, { configurable: true, value });
}

function installWindow(options: {
  stored?: string | null;
  telegramScheme?: "light" | "dark";
  prefersDark?: boolean;
} = {}): void {
  const store = new Map<string, string>();
  if (options.stored != null) store.set(THEME_STORAGE_KEY, options.stored);
  define("window", {
    localStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
    },
    matchMedia: () => ({ matches: options.prefersDark === true }),
    Telegram: options.telegramScheme
      ? { WebApp: { colorScheme: options.telegramScheme } }
      : undefined,
  });
}

function installDocument(): { root: { dataset: Record<string, string> }; meta: string } {
  const root = { dataset: {} as Record<string, string> };
  const meta = { content: "" };
  define("document", {
    documentElement: root,
    querySelector: () => ({
      setAttribute: (_name: string, value: string) => void (meta.content = value),
    }),
  });
  return { root, get meta() { return meta.content; } };
}

afterEach(() => {
  define("window", originalWindow);
  define("document", originalDocument);
});

describe("theme preference", () => {
  test("defaults to the light theme when nothing is stored", () => {
    installWindow();
    expect(DEFAULT_THEME_PREFERENCE).toBe("light");
    expect(readStoredTheme()).toBe("light");
  });

  test("reads a stored preference back", () => {
    installWindow({ stored: "dark" });
    expect(readStoredTheme()).toBe("dark");
  });

  test("falls back to light for an unrecognised stored value", () => {
    installWindow({ stored: "solarized" });
    expect(readStoredTheme()).toBe("light");
  });

  test("falls back to light when storage is unavailable", () => {
    define("window", {
      localStorage: {
        getItem: () => { throw new Error("blocked"); },
      },
    });
    expect(readStoredTheme()).toBe("light");
  });

  test("only accepts the three known preferences", () => {
    expect(isThemePreference("light")).toBe(true);
    expect(isThemePreference("dark")).toBe(true);
    expect(isThemePreference("system")).toBe(true);
    expect(isThemePreference("auto")).toBe(false);
    expect(isThemePreference(null)).toBe(false);
  });
});

describe("theme resolution", () => {
  test("explicit preferences ignore the client theme", () => {
    installWindow({ telegramScheme: "dark" });
    expect(resolveTheme("light")).toBe("light");
    installWindow({ telegramScheme: "light" });
    expect(resolveTheme("dark")).toBe("dark");
  });

  test("system follows the Telegram colour scheme", () => {
    installWindow({ telegramScheme: "dark", prefersDark: false });
    expect(clientTheme()).toBe("dark");
    expect(resolveTheme("system")).toBe("dark");
  });

  test("system falls back to the OS preference outside Telegram", () => {
    installWindow({ prefersDark: true });
    expect(resolveTheme("system")).toBe("dark");
    installWindow({ prefersDark: false });
    expect(resolveTheme("system")).toBe("light");
  });
});

describe("applyTheme", () => {
  test("stamps the theme on the root element and the theme-color meta", () => {
    installWindow();
    const dom = installDocument();
    applyTheme("dark");
    expect(dom.root.dataset.theme).toBe("dark");
    expect(dom.meta).toBe(THEME_CANVAS.dark);
    applyTheme("light");
    expect(dom.root.dataset.theme).toBe("light");
    expect(dom.meta).toBe(THEME_CANVAS.light);
  });
});
