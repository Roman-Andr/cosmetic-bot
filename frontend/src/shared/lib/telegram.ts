export interface TelegramWebApp {
  initData: string;
  ready: () => void;
  expand: () => void;
  colorScheme?: "light" | "dark";
  requestContact: (callback?: (shared: boolean) => void) => void;
  onEvent: (eventType: "contactRequested" | "themeChanged", callback: (event?: { status: "sent" | "cancelled" }) => void) => void;
  offEvent: (eventType: "contactRequested" | "themeChanged", callback: (event?: { status: "sent" | "cancelled" }) => void) => void;
  showAlert: (message: string) => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  HapticFeedback?: {
    impactOccurred: (style: "light" | "medium" | "heavy") => void;
    notificationOccurred: (type: "error" | "success" | "warning") => void;
  };
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

export function syncTelegramAppearance(): () => void {
  const telegram = getTelegramApp();
  if (!telegram) return () => undefined;

  const apply = (): void => {
    const theme = telegram.themeParams;
    const headerColor = theme.header_bg_color ?? theme.secondary_bg_color ?? theme.bg_color;
    const backgroundColor = theme.secondary_bg_color ?? theme.bg_color;
    if (headerColor) telegram.setHeaderColor?.(headerColor);
    if (backgroundColor) telegram.setBackgroundColor?.(backgroundColor);
  };

  apply();
  telegram.onEvent("themeChanged", apply);
  return () => telegram.offEvent("themeChanged", apply);
}

export function haptic(type: "success" | "error" | "warning" | "light" = "light"): void {
  const feedback = getTelegramApp()?.HapticFeedback;
  if (!feedback) return;
  if (type === "light") feedback.impactOccurred("light");
  else feedback.notificationOccurred(type);
}
