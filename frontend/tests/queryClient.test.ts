import { afterEach, describe, expect, test } from "bun:test";

import { profileQueryOptions } from "../src/entities/loyalty/api/queries";
import { createQueryClient } from "../src/shared/api/queryClient";

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;

function installTelegramWindow(): void {
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { Telegram: { WebApp: { initData: "signed-init-data" } } },
  });
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: originalWindow,
  });
});

describe("query client", () => {
  test("deduplicates simultaneous profile requests", async () => {
    installTelegramWindow();
    let requestCount = 0;
    globalThis.fetch = async () => {
      requestCount += 1;
      await Promise.resolve();
      return new Response(JSON.stringify({ full_name: "Анна" }), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    };
    const client = createQueryClient();

    const [first, second] = await Promise.all([
      client.fetchQuery(profileQueryOptions()),
      client.fetchQuery(profileQueryOptions()),
    ]);

    expect(first).toEqual(second);
    expect(requestCount).toBe(1);
    client.clear();
  });

  test("does not retry an expected client error", async () => {
    installTelegramWindow();
    let requestCount = 0;
    globalThis.fetch = async () => {
      requestCount += 1;
      return new Response(JSON.stringify({ detail: "Профиль не найден" }), {
        headers: { "Content-Type": "application/json" },
        status: 404,
      });
    };
    const client = createQueryClient();

    await expect(client.fetchQuery(profileQueryOptions())).rejects.toThrow("Профиль не найден");
    expect(requestCount).toBe(1);
    client.clear();
  });
});
