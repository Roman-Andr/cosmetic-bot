import { describe, expect, test } from "bun:test";

import { formatCalendarDate, minskDateTimeParts } from "../src/shared/lib/format";

describe("formatCalendarDate", () => {
  test("keeps the calendar day of an ISO date regardless of the device time zone", () => {
    expect(formatCalendarDate("2026-10-16")).toBe("16.10.2026");
    expect(formatCalendarDate("2027-01-01", { withYear: false })).toBe("01.01");
  });
});

describe("minskDateTimeParts", () => {
  test("returns Minsk wall-clock values in date and time input formats", () => {
    // 21:30 UTC is already the next day in Minsk (UTC+3).
    expect(minskDateTimeParts(new Date("2026-10-13T21:30:00Z"))).toEqual({
      date: "2026-10-14",
      time: "00:30",
    });
  });
});
