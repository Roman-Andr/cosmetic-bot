import { haptic } from "../../../shared/lib/telegram";
import { setThemePreference, type ThemePreference } from "../../../shared/lib/theme";
import { useThemePreference } from "../../../shared/lib/useTheme";
import { Icon } from "../../../shared/ui/Icon";
import type { IconName } from "../../../shared/ui/Icon";
import { ui } from "../../../shared/ui/classes";

const OPTIONS: ReadonlyArray<{ value: ThemePreference; label: string; icon: IconName }> = [
  { value: "light", label: "Светлая", icon: "sun" },
  { value: "dark", label: "Тёмная", icon: "moon" },
  { value: "system", label: "Как в Telegram", icon: "contrast" },
];

export function ThemeSwitcher() {
  const preference = useThemePreference();

  const choose = (value: ThemePreference): void => {
    if (value === preference) return;
    setThemePreference(value);
    haptic("light");
  };

  return <section className={ui("theme-switcher")} aria-label="Оформление">
    <p>ОФОРМЛЕНИЕ</p>
    <div className={ui("theme-options")} role="group">
      {OPTIONS.map((option) => <button
        key={option.value}
        className={ui("theme-option")}
        type="button"
        aria-pressed={option.value === preference}
        onClick={() => choose(option.value)}
      ><Icon name={option.icon} size={19} />{option.label}</button>)}
    </div>
  </section>;
}
