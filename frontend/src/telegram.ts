export interface TelegramWebApp {
  initData: string;
  ready: () => void;
  expand: () => void;
  requestContact: (callback?: (shared: boolean) => void) => void;
  onEvent: (eventType: "contactRequested", callback: (event: { status: "sent" | "cancelled" }) => void) => void;
  offEvent: (eventType: "contactRequested", callback: (event: { status: "sent" | "cancelled" }) => void) => void;
  showAlert: (message: string) => void;
  themeParams: Record<string, string | undefined>;
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp };
  }
}

export function getTelegramApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}
