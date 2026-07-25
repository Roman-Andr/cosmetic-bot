import { Icon, type IconName } from "./Icon";

export function SectionTile({ active, icon, title, onClick }: {
  active: boolean;
  icon: IconName;
  title: string;
  onClick: () => void;
}) {
  return <button type="button" className={`workspace-tab${active ? " active" : ""}`} aria-pressed={active} onClick={onClick}>
    <Icon name={icon} size={18} />
    <span>{title}</span>
  </button>;
}
