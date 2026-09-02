import { useSyncExternalStore } from "react";

import {
  DEFAULT_THEME_PREFERENCE,
  getThemePreference,
  subscribeToTheme,
  type ThemePreference,
} from "./theme";

export function useThemePreference(): ThemePreference {
  return useSyncExternalStore(
    subscribeToTheme,
    getThemePreference,
    () => DEFAULT_THEME_PREFERENCE,
  );
}
