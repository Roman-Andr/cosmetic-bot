export function formatAmount(value: string | number): string {
  return Number(value).toFixed(2);
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ru-BY", { dateStyle: "medium" }).format(new Date(value));
}

export function formatTime(value: string): string {
  return new Intl.DateTimeFormat("ru-BY", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Произошла непредвиденная ошибка.";
}
