import { Icon, type IconName } from "./Icon";
import { ui } from "./classes";

export function SectionTile({ active, icon, title, onClick }: {
  active: boolean;
  icon: IconName;
  title: string;
  onClick: () => void;
}) {
  return <button type="button" className={ui("workspace-tab")} aria-pressed={active} onClick={onClick}>
    <Icon name={icon} size={18} />
    <span>{title}</span>
  </button>;
}
