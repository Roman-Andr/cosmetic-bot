import { useEffect, useMemo, useState } from "react";

import type { BonusTransactionPage, Profile } from "../../../entities/loyalty/model/types";
import { api } from "../../../shared/api/client";
import { errorMessage, formatDate } from "../../../shared/lib/format";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";

export function LoyaltyProgramModal({ profile, onClose, onNotice }: {
  profile: Profile;
  onClose: () => void;
  onNotice: (message: string | null) => void;
}) {
  const [transactions, setTransactions] = useState<BonusTransactionPage | null>(null);
  const progress = profile.tier_progress;
  const isMaxLevel = progress.next_tier === null;
  const percent = Math.min(100, Math.max(0, Number(progress.progress_percent)));
  const currentTierLabel = `${profile.tier.cashback_percent}%`;

  useEffect(() => {
    void api.get<BonusTransactionPage>("/loyalty/transactions").then(setTransactions).catch((error: unknown) => onNotice(errorMessage(error)));
  }, [onNotice]);

  const activeTierText = useMemo(() => isMaxLevel
    ? "Вы достигли максимального уровня."
    : <>До следующего уровня осталось <Money value={progress.amount_to_next_tier} />.</>, [isMaxLevel, progress.amount_to_next_tier]);

  return <Modal title="Про программу лояльности" eyebrow="VELINA CLUB" onClose={onClose}>
    <section className="program-overview">
      <span className="program-overview-icon"><Icon name="gift" /></span>
      <div><span>Ваш уровень сейчас</span><strong>{currentTierLabel} кешбэка</strong><p>{activeTierText}</p></div>
    </section>
    <section className="program-section">
      <div className="program-section-heading"><div><p className="overline">ВАШ ПУТЬ</p><h3>Уровни кешбэка</h3></div><span>{isMaxLevel ? "MAX" : `${percent.toFixed(0)}%`}</span></div>
      <ul className="tier-ladder modal-tier-ladder">{progress.tiers.map((tier) => {
        const isCurrent = tier.minimum_turnover === progress.current_tier.minimum_turnover && tier.cashback_percent === progress.current_tier.cashback_percent;
        const isReached = Number(tier.minimum_turnover) <= Number(progress.current_tier.minimum_turnover);
        return <li className={`${isCurrent ? "current" : ""}${isReached ? " reached" : ""}`} key={`${tier.minimum_turnover}-${tier.cashback_percent}`}><i>{isReached ? <Icon name="check" size={13} /> : null}</i><span>от <Money value={tier.minimum_turnover} /></span><b>{tier.cashback_percent}%</b></li>;
      })}</ul>
    </section>
    <section className="program-rules">
      <span><Icon name="sparkle" size={16} />Оборот учитывается полностью</span>
      <span><Icon name="gift" size={16} />Бонусы не сгорают</span>
      <span><Icon name="check" size={16} />Списываем до 10% заказа</span>
    </section>
    <section className="program-section bonus-history-section">
      <div className="program-section-heading"><div><p className="overline">ВАШ БАЛАНС</p><h3>История баллов</h3></div><span className="soft-icon"><Icon name="chart" size={18} /></span></div>
      {!transactions ? <div className="modal-loader"><span className="loader" />Загружаем историю…</div> : transactions.items.length === 0 ? <div className="empty-state compact-empty"><span><Icon name="gift" /></span><h3>Операций пока нет</h3><p>Здесь появятся начисления и списания бонусов.</p></div> : <ul className="transaction-list">{transactions.items.map((transaction) => {
        const isAccrual = transaction.operation_type === "accrual";
        return <li key={transaction.id}><span className={`transaction-icon ${isAccrual ? "accrual" : "redemption"}`}><Icon name={isAccrual ? "plus" : "arrow"} size={16} /></span><div><strong>{isAccrual ? "Начислено бонусов" : "Списано бонусов"}</strong><small>{formatDate(transaction.created_at)} · баланс <Money value={transaction.balance_after} /></small></div><em className={isAccrual ? "accrual" : "redemption"}><Money prefix={isAccrual ? "+" : "−"} value={Math.abs(Number(transaction.amount))} /></em></li>;
      })}</ul>}
    </section>
  </Modal>;
}
