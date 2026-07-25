import { useState, type FormEvent } from "react";

import type { Profile } from "../../../entities/loyalty/model/types";
import { BirthdayInfoModal } from "../../../features/birthday/ui/BirthdayInfoModal";
import { LoyaltyCodeModal } from "../../../features/loyalty-code/ui/LoyaltyCodeCard";
import { LoyaltyProgramModal } from "../../../features/loyalty-program/ui/LoyaltyProgramModal";
import { PurchaseHistoryModal } from "../../../features/purchase-history/ui/PurchaseHistoryModal";
import { TierProgressCard } from "../../../features/tier-progress/ui/TierProgressCard";
import { api } from "../../../shared/api/client";
import { errorMessage, formatDate } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";

export function ProfilePanel({ profile, onProfile, onNotice }: {
  profile: Profile;
  onProfile: (value: Profile) => void;
  onNotice: (value: string | null) => void;
}) {
  const [fullName, setFullName] = useState(profile.full_name);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showProgram, setShowProgram] = useState(false);
  const [showPurchases, setShowPurchases] = useState(false);
  const [showBirthday, setShowBirthday] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const firstName = profile.full_name.trim().split(/\s+/)[0] || "друг";

  const updateName = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    setSaving(true);
    try {
      onProfile(await api.patch<Profile>("/loyalty/me", { full_name: fullName }));
      setEditing(false);
      haptic("success");
      onNotice("ФИО обновлено.");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
    finally { setSaving(false); }
  };

  const openAccount = (): void => {
    setFullName(profile.full_name);
    setEditing(false);
    setShowAccount(true);
  };

  return <section className="customer-dashboard">
    <header className="customer-greeting">
      <div><p className="eyebrow">VELINA CLUB</p><h1>Здравствуйте,<br />{firstName}</h1><p>С вами с {formatDate(profile.registered_at)}</p></div>
      <button className="account-trigger" type="button" aria-label="Открыть данные профиля" onClick={openAccount}><Icon name="account" /></button>
    </header>

    <section className="wallet-card">
      <div className="wallet-card-top"><span>Бонусный баланс</span><span className="tier-chip">{profile.tier.cashback_percent}% кешбэк</span></div>
      <strong><Money value={profile.current_balance} /></strong>
      <div className="wallet-card-footer"><span>Оборот <Money value={profile.lifetime_turnover} /></span><button type="button" onClick={() => setShowCode(true)}>Получить код <Icon name="arrow" size={17} /></button></div>
    </section>

    <TierProgressCard progress={profile.tier_progress} onProgram={() => setShowProgram(true)} />

    <section className="dashboard-actions" aria-label="Быстрые действия">
      <button type="button" className="dashboard-action" onClick={() => setShowPurchases(true)}><span className="dashboard-action-icon"><Icon name="bag" /></span><span><strong>Покупки</strong><small>История заказов</small></span><Icon name="arrow" size={17} /></button>
      <button type="button" className={`dashboard-action${profile.birthday_cashback_active ? " birthday-active" : ""}`} onClick={() => setShowBirthday(true)}><span className="dashboard-action-icon"><Icon name="gift" /></span><span><strong>День рождения</strong><small>{profile.birthday_cashback_active ? `${profile.birthday_cashback_percent}% уже действует` : "Праздничный кешбэк"}</small></span><Icon name="arrow" size={17} /></button>
    </section>

    {showCode && <LoyaltyCodeModal onClose={() => setShowCode(false)} onNotice={onNotice} />}
    {showProgram && <LoyaltyProgramModal profile={profile} onClose={() => setShowProgram(false)} onNotice={onNotice} />}
    {showPurchases && <PurchaseHistoryModal onClose={() => setShowPurchases(false)} onNotice={onNotice} />}
    {showBirthday && <BirthdayInfoModal profile={profile} onClose={() => setShowBirthday(false)} />}
    {showAccount && <Modal title="Ваши данные" eyebrow="ПРОФИЛЬ" onClose={() => setShowAccount(false)}>
      <section className="account-modal-head"><span>{firstName.slice(0, 1).toUpperCase()}</span><div><strong>{profile.full_name}</strong><small>Участник Velina Club</small></div></section>
      <dl className="account-details"><div><dt>Телефон</dt><dd>{profile.phone}</dd></div><div><dt>Дата регистрации</dt><dd>{formatDate(profile.registered_at)}</dd></div><div><dt>Дата рождения</dt><dd>{formatDate(profile.birth_date)}</dd></div></dl>
      {editing ? <form className="form compact edit-profile" onSubmit={(event) => void updateName(event)}><label>ФИО<input value={fullName} onChange={(event) => setFullName(event.target.value)} /></label><div className="split-actions"><button className="secondary-action" type="button" onClick={() => { setFullName(profile.full_name); setEditing(false); }}>Отмена</button><button className="primary-action" disabled={saving}>{saving ? "Сохраняем…" : "Сохранить"}</button></div></form> : <button className="secondary-action account-edit" type="button" onClick={() => setEditing(true)}>Изменить ФИО</button>}
    </Modal>}
  </section>;
}
