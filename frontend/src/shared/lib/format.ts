export function formatAmount(value: string | number): string {
  return Number(value).toFixed(2);
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ru-BY", { dateStyle: "medium" }).format(new Date(value));
}

/** Formats an ISO calendar date (YYYY-MM-DD) without shifting it through a time zone. */
export function formatCalendarDate(value: string, { withYear = true } = {}): string {
  const [year, month, day] = value.split("-");
  return withYear ? `${day}.${month}.${year}` : `${day}.${month}`;
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("ru-BY", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Minsk",
  }).format(new Date(value));
}

/** Minsk wall-clock parts in the formats of `<input type="date">` and `type="time"`. */
export function minskDateTimeParts(value: Date): { date: string; time: string } {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Minsk",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(value);
  const part = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((item) => item.type === type)?.value ?? "";
  return {
    date: `${part("year")}-${part("month")}-${part("day")}`,
    time: `${part("hour")}:${part("minute")}`,
  };
}

export function formatTime(value: string): string {
  return new Intl.DateTimeFormat("ru-BY", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Произошла непредвиденная ошибка.";
}
