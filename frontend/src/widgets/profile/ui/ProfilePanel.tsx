import { useState, type FormEvent } from "react";

import type { Profile } from "../../../entities/loyalty/model/types";
import { LoyaltyCodeCard } from "../../../features/loyalty-code/ui/LoyaltyCodeCard";
import { TierProgressCard } from "../../../features/tier-progress/ui/TierProgressCard";
import { TransactionHistoryModal } from "../../../features/transactions/ui/TransactionHistoryModal";
import { api } from "../../../shared/api/client";
import { errorMessage, formatByn, formatDate } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import { Icon } from "../../../shared/ui/Icon";

export function ProfilePanel({ profile, onProfile, onNotice }: {
  profile: Profile;
  onProfile: (value: Profile) => void;
  onNotice: (value: string | null) => void;
}) {
  const [fullName, setFullName] = useState(profile.full_name);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showTransactions, setShowTransactions] = useState(false);

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
      <strong>{formatByn(profile.current_balance)}</strong>
      <div className="balance-meta"><span>Ваш уровень <b>{profile.tier.cashback_percent}%</b></span><span>Оборот {formatByn(profile.lifetime_turnover)}</span></div>
    </section>
    <TierProgressCard progress={profile.tier_progress} onHistory={() => setShowTransactions(true)} />
    <button type="button" className="transaction-tile" onClick={() => setShowTransactions(true)}><span className="transaction-tile-icon"><Icon name="chart" /></span><span><strong>Движение бонусов</strong><small>Начисления и списания по покупкам</small></span><Icon name="arrow" size={18} /></button>
    <section className={`birthday-card${profile.birthday_cashback_active ? " active" : ""}`}>
      <span className="birthday-icon"><Icon name="gift" /></span>
      <div><p className="overline">ОСОБЫЙ БОНУС</p><h2>{profile.birthday_cashback_active ? "День рождения уже рядом" : "Кешбэк ко дню рождения"}</h2><p>{profile.birthday_cashback_active ? `Сегодня действует повышенный кешбэк ${profile.birthday_cashback_percent}%.` : `Получите ${profile.birthday_cashback_percent}% за ${profile.birthday_cashback_window_days} дня до и после даты рождения.`}</p></div>
      <strong>{profile.birthday_cashback_percent}%</strong>
    </section>
    <LoyaltyCodeCard onNotice={onNotice} />
    <section className="panel profile-panel">
      <div className="panel-heading"><div><p className="overline">ВАШИ ДАННЫЕ</p><h2>Профиль</h2></div><button className="icon-button pale" type="button" aria-label="Редактировать ФИО" onClick={() => setEditing((value) => !value)}><Icon name="account" /></button></div>
      <div className="profile-facts"><span>Телефон<b>{profile.phone}</b></span><span>Участник с<b>{formatDate(profile.registered_at)}</b></span></div>
      {editing && <form className="form compact edit-profile" onSubmit={(event) => void updateName(event)}><label>ФИО<input value={fullName} onChange={(event) => setFullName(event.target.value)} /></label><div className="split-actions"><button className="secondary-action" type="button" onClick={() => { setFullName(profile.full_name); setEditing(false); }}>Отмена</button><button className="primary-action" disabled={saving}>{saving ? "Сохраняем…" : "Сохранить"}</button></div></form>}
    </section>
    {showTransactions && <TransactionHistoryModal onClose={() => setShowTransactions(false)} onNotice={onNotice} />}
  </section>;
}
