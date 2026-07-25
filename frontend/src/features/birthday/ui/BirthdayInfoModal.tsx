import type { Profile } from "../../../entities/loyalty/model/types";
import { formatDate } from "../../../shared/lib/format";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";

export function BirthdayInfoModal({ profile, onClose }: { profile: Profile; onClose: () => void }) {
  const active = profile.birthday_cashback_active;
  return <Modal title="День рождения" eyebrow="ОСОБЫЙ БОНУС" onClose={onClose}>
    <section className={`birthday-modal-hero${active ? " active" : ""}`}>
      <span><Icon name="gift" size={25} /></span>
      <div><strong>{active ? "Праздничный кешбэк уже действует" : "Праздничный кешбэк для вас"}</strong><p>{active ? `На покупки сейчас начисляется ${profile.birthday_cashback_percent}% вместо уровня лояльности.` : `В день рождения действует кешбэк ${profile.birthday_cashback_percent}%.`}</p></div>
    </section>
    <dl className="birthday-details">
      <div><dt>Дата рождения</dt><dd>{formatDate(profile.birth_date)}</dd></div>
      <div><dt>Период акции</dt><dd>{profile.birthday_cashback_window_days} дня до и {profile.birthday_cashback_window_days} дня после</dd></div>
      <div><dt>Кешбэк в этот период</dt><dd>{profile.birthday_cashback_percent}%</dd></div>
    </dl>
    <p className="birthday-note">В праздничный период повышенный кешбэк заменяет стандартный процент вашего уровня.</p>
  </Modal>;
}
