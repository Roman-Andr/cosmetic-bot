import type { Profile } from "../../../entities/loyalty/model/types";
import { formatDate } from "../../../shared/lib/format";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";

export function BirthdayInfoModal({ profile, onClose }: { profile: Profile; onClose: () => void }) {
  const active = profile.birthday_cashback_active;
  return <Modal title="День рождения" eyebrow="ОСОБЫЙ БОНУС" onClose={onClose}>
    <section className={`birthday-feature${active ? " active" : ""}`}>
      <span><Icon name="gift" size={25} /></span>
      <div><p>{active ? "Праздничный кешбэк активен" : "Ваш праздничный кешбэк"}</p><strong>{profile.birthday_cashback_percent}%</strong><small>{active ? "на покупки прямо сейчас" : "в период дня рождения"}</small></div>
    </section>
    <section className="birthday-explainer"><h3>{active ? "Сегодня действует особый процент" : "Празднуем вместе с вами"}</h3><p>{active ? `Он заменяет стандартный процент вашего уровня до конца праздничного периода.` : `За ${profile.birthday_cashback_window_days} дня до и ${profile.birthday_cashback_window_days} дня после даты рождения начисляем повышенный кешбэк.`}</p></section>
    <dl className="birthday-details"><div><dt>Дата рождения</dt><dd>{formatDate(profile.birth_date)}</dd></div><div><dt>Период акции</dt><dd>± {profile.birthday_cashback_window_days} дня</dd></div><div><dt>Кешбэк в этот период</dt><dd>{profile.birthday_cashback_percent}%</dd></div></dl>
  </Modal>;
}
