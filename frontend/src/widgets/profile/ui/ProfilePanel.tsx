import { useEffect, useRef, useState, type FormEvent } from "react";

import { useUpdateProfileMutation } from "../../../entities/loyalty/api/mutations";
import { useProfileQuery, useTransactionsQuery } from "../../../entities/loyalty/api/queries";
import type { Profile } from "../../../entities/loyalty/model/types";
import { BonusHistoryModal } from "../../../features/bonus-history/ui/BonusHistoryModal";
import { BirthdayInfoModal } from "../../../features/birthday/ui/BirthdayInfoModal";
import { LoyaltyCodeModal } from "../../../features/loyalty-code/ui/LoyaltyCodeCard";
import { LoyaltyProgramModal } from "../../../features/loyalty-program/ui/LoyaltyProgramModal";
import { PurchaseHistoryModal } from "../../../features/purchase-history/ui/PurchaseHistoryModal";
import { ThemeSwitcher } from "../../../features/theme/ui/ThemeSwitcher";
import { TierProgressCard } from "../../../features/tier-progress/ui/TierProgressCard";
import { errorMessage, formatAmount, formatDate } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";
import { ui } from "../../../shared/ui/classes";

export function ProfilePanel({ profile, onNotice }: {
  profile: Profile;
  onNotice: NoticeHandler;
}) {
  const [fullName, setFullName] = useState(profile.full_name);
  const [editing, setEditing] = useState(false);
  const [showProgram, setShowProgram] = useState(false);
  const [showPurchases, setShowPurchases] = useState(false);
  const [showBirthday, setShowBirthday] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [showBalanceHistory, setShowBalanceHistory] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const latestTransactionId = useRef<string | null>(null);
  const updateProfileMutation = useUpdateProfileMutation();
  useProfileQuery({ live: true });
  const transactionsQuery = useTransactionsQuery({ limit: 10, live: true });
  const firstName = profile.full_name.trim().split(/\s+/)[0] || "друг";

  useEffect(() => {
    const transactions = transactionsQuery.data?.items;
    if (!transactions) return;
    const newestId = transactions[0]?.id ?? null;
    if (latestTransactionId.current) {
      const previousIndex = transactions.findIndex(
        (transaction) => transaction.id === latestTransactionId.current,
      );
      const newTransactions = transactions.slice(
        0,
        previousIndex >= 0 ? previousIndex : transactions.length,
      );
      const accrued = newTransactions
        .filter((transaction) => transaction.operation_type === "accrual")
        .reduce((total, transaction) => total + Math.abs(Number(transaction.amount)), 0);
      if (accrued > 0) {
        haptic("success");
        onNotice(`Начислено баллов: +${formatAmount(accrued)}. Баланс обновлён.`, "success");
      }
    }
    latestTransactionId.current = newestId;
  }, [onNotice, transactionsQuery.data]);

  const updateName = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    try {
      await updateProfileMutation.mutateAsync({ full_name: fullName });
      setEditing(false);
      haptic("success");
      onNotice("ФИО обновлено.", "success");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
  };

  const openAccount = (): void => {
    setFullName(profile.full_name);
    setEditing(false);
    setShowAccount(true);
  };

  return <section className={ui("customer-dashboard")}>
    <section className={ui("loyalty-summary-grid")} aria-label="Лояльность">
      <button type="button" className={ui("loyalty-tile", "points-tile")} onClick={() => setShowBalanceHistory(true)}>
        <div className={ui("tile-title-row")}><p>Мои баллы</p></div>
        <strong><Money value={profile.current_balance} /></strong>
      </button>
      <button type="button" className={ui("loyalty-tile", "cashback-tile")} onClick={() => setShowCode(true)}>
        <span className={ui("cashback-code-mark")} aria-hidden="true"><i /><i /><i /><span><Icon name="sparkle" size={22} /></span></span>
        <span className={ui("cashback-copy")}><small>Ваш кешбэк</small><strong>{profile.tier.cashback_percent}%</strong><em>Получить код <Icon name="arrow" size={15} /></em></span>
      </button>
      <button type="button" className={ui("program-tile")} onClick={() => setShowProgram(true)}>
        <span className={ui("program-copy")}><strong>Бонусная<br />программа</strong></span>
        <i><Icon name="arrow" size={19} /></i>
      </button>
    </section>

    <section className={ui("benefit-carousel")} aria-label="Больше выгод">
      <TierProgressCard progress={profile.tier_progress} onProgram={() => setShowProgram(true)} />
      <button type="button" className={ui("benefit-card", "birthday-benefit-card", profile.birthday_cashback_active && "birthday-benefit-active")} onClick={() => setShowBirthday(true)}><div><p>Подарки на день рождения</p><strong>{profile.birthday_cashback_percent}% кешбэк</strong><small>{profile.birthday_cashback_active ? "Праздничный период уже активен" : "За 3 дня до и 3 дня после"}</small></div><img src="/birthday-cake.svg" alt="Праздничный торт" /></button>
    </section>

    <section className={ui("customer-utility-row")}><button type="button" onClick={() => setShowPurchases(true)}><span><Icon name="bag" size={18} />История покупок</span><Icon name="arrow" size={17} /></button><button className={ui("profile-utility-button")} type="button" aria-label="Открыть данные профиля" onClick={openAccount}><Icon name="account" size={18} /></button></section>
    <p className={ui("customer-member-note")}>В программе с {formatDate(profile.registered_at)}</p>

    {showCode && <LoyaltyCodeModal onClose={() => setShowCode(false)} onNotice={onNotice} />}
    {showProgram && <LoyaltyProgramModal profile={profile} onClose={() => setShowProgram(false)} />}
    {showBalanceHistory && <BonusHistoryModal balance={profile.current_balance} onClose={() => setShowBalanceHistory(false)} onNotice={onNotice} />}
    {showPurchases && <PurchaseHistoryModal onClose={() => setShowPurchases(false)} onNotice={onNotice} />}
    {showBirthday && <BirthdayInfoModal profile={profile} onClose={() => setShowBirthday(false)} />}
    {showAccount && <Modal title="Ваши данные" eyebrow="ПРОФИЛЬ" onClose={() => setShowAccount(false)}>
      <section className={ui("account-modal-head")}><span>{firstName.slice(0, 1).toUpperCase()}</span><div><strong>{profile.full_name}</strong><small>Участник программы лояльности</small></div></section>
      <ThemeSwitcher />
      <dl className={ui("detail-list", "account-details")}><div><dt>Телефон</dt><dd>{profile.phone}</dd></div><div><dt>Дата регистрации</dt><dd>{formatDate(profile.registered_at)}</dd></div><div><dt>Дата рождения</dt><dd>{formatDate(profile.birth_date)}</dd></div></dl>
      {editing ? <form className={ui("form", "compact")} onSubmit={(event) => void updateName(event)}><label>ФИО<input className={ui("form-control")} value={fullName} onChange={(event) => setFullName(event.target.value)} /></label><div className={ui("split-actions")}><button className={ui("secondary-action")} type="button" onClick={() => { setFullName(profile.full_name); setEditing(false); }}>Отмена</button><button className={ui("primary-action")} disabled={updateProfileMutation.isPending}>{updateProfileMutation.isPending ? "Сохраняем…" : "Сохранить"}</button></div></form> : <button className={ui("secondary-action", "account-edit")} type="button" onClick={() => setEditing(true)}>Изменить ФИО</button>}
    </Modal>}
  </section>;
}
