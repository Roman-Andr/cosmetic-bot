import { useState, type FormEvent } from "react";

import type { Profile } from "../../../entities/loyalty/model/types";
import { BirthdayInfoModal } from "../../../features/birthday/ui/BirthdayInfoModal";
import { LoyaltyCodeCard } from "../../../features/loyalty-code/ui/LoyaltyCodeCard";
import { LoyaltyProgramModal } from "../../../features/loyalty-program/ui/LoyaltyProgramModal";
import { PurchaseHistoryModal } from "../../../features/purchase-history/ui/PurchaseHistoryModal";
import { TierProgressCard } from "../../../features/tier-progress/ui/TierProgressCard";
import { api } from "../../../shared/api/client";
import { errorMessage, formatDate } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import { Icon } from "../../../shared/ui/Icon";
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

  return <section className="stack">
    <section className="balance-card">
      <div className="balance-glow" />
      <div className="balance-top"><span>Ваш бонусный баланс</span><span className="balance-orb"><Icon name="gift" /></span></div>
      <strong><Money value={profile.current_balance} /></strong>
      <div className="balance-meta"><span>Ваш уровень <b>{profile.tier.cashback_percent}%</b></span><span>Оборот <Money value={profile.lifetime_turnover} /></span></div>
    </section>
    <TierProgressCard progress={profile.tier_progress} onProgram={() => setShowProgram(true)} />
    <div className="profile-info-grid">
      <button type="button" className="quick-info-tile" onClick={() => setShowPurchases(true)}><span className="quick-info-icon"><Icon name="bag" /></span><span><strong>История покупок</strong><small>Дата, сумма и кешбэк</small></span><Icon name="arrow" size={18} /></button>
      <button type="button" className={`quick-info-tile birthday-tile${profile.birthday_cashback_active ? " active" : ""}`} onClick={() => setShowBirthday(true)}><span className="quick-info-icon"><Icon name="gift" /></span><span><strong>День рождения</strong><small>{profile.birthday_cashback_active ? `${profile.birthday_cashback_percent}% уже действует` : "Праздничный кешбэк"}</small></span><Icon name="arrow" size={18} /></button>
    </div>
    <LoyaltyCodeCard onNotice={onNotice} />
    <section className="panel profile-panel">
      <div className="panel-heading"><div><p className="overline">ВАШИ ДАННЫЕ</p><h2>Профиль</h2></div><button className="icon-button pale" type="button" aria-label="Редактировать ФИО" onClick={() => setEditing((value) => !value)}><Icon name="account" /></button></div>
      <div className="profile-facts"><span>Телефон<b>{profile.phone}</b></span><span>Участник с<b>{formatDate(profile.registered_at)}</b></span></div>
      {editing && <form className="form compact edit-profile" onSubmit={(event) => void updateName(event)}><label>ФИО<input value={fullName} onChange={(event) => setFullName(event.target.value)} /></label><div className="split-actions"><button className="secondary-action" type="button" onClick={() => { setFullName(profile.full_name); setEditing(false); }}>Отмена</button><button className="primary-action" disabled={saving}>{saving ? "Сохраняем…" : "Сохранить"}</button></div></form>}
    </section>
    {showProgram && <LoyaltyProgramModal profile={profile} onClose={() => setShowProgram(false)} onNotice={onNotice} />}
    {showPurchases && <PurchaseHistoryModal onClose={() => setShowPurchases(false)} onNotice={onNotice} />}
    {showBirthday && <BirthdayInfoModal profile={profile} onClose={() => setShowBirthday(false)} />}
  </section>;
}
