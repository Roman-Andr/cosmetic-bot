import { Icon, type IconName } from "./Icon";

export function SectionTile({ active, icon, title, subtitle, badge, onClick }: {
  active: boolean;
  icon: IconName;
  title: string;
  subtitle: string;
  badge?: string;
  onClick: () => void;
}) {
  return <button type="button" className={`section-tile${active ? " active" : ""}`} onClick={onClick}>
    <span className="tile-icon"><Icon name={icon} /></span>
    <span className="tile-copy"><strong>{title}</strong><small>{subtitle}</small></span>
    {badge && <span className="tile-badge">{badge}</span>}
  </button>;
}
