import { useEffect, useState } from "react";

import type { BonusTransactionPage, Profile } from "../../../entities/loyalty/model/types";
import { api } from "../../../shared/api/client";
import { errorMessage, formatDate } from "../../../shared/lib/format";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";

type ProgramView = "levels" | "history";

export function LoyaltyProgramModal({ profile, onClose, onNotice }: {
  profile: Profile;
  onClose: () => void;
  onNotice: (message: string | null) => void;
}) {
  const [view, setView] = useState<ProgramView>("levels");
  const [transactions, setTransactions] = useState<BonusTransactionPage | null>(null);
  const progress = profile.tier_progress;
  const isMaxLevel = progress.next_tier === null;

  useEffect(() => {
    void api.get<BonusTransactionPage>("/loyalty/transactions").then(setTransactions).catch((error: unknown) => onNotice(errorMessage(error)));
  }, [onNotice]);

  return <Modal title="Программа лояльности" eyebrow="VELINA CLUB" onClose={onClose}>
    <section className="program-summary">
      <span className="program-summary-icon"><Icon name="gift" /></span>
      <div><span>Ваш активный уровень</span><strong>{profile.tier.cashback_percent}% кешбэка</strong><p>{isMaxLevel ? "Вы достигли максимального уровня." : <>До следующего уровня осталось <Money value={progress.amount_to_next_tier} />.</>}</p></div>
    </section>

    <div className="modal-tabs" role="tablist" aria-label="Разделы программы лояльности">
      <button className={view === "levels" ? "active" : ""} type="button" role="tab" aria-selected={view === "levels"} onClick={() => setView("levels")}>Уровни</button>
      <button className={view === "history" ? "active" : ""} type="button" role="tab" aria-selected={view === "history"} onClick={() => setView("history")}>Баллы</button>
    </div>

    {view === "levels" ? <section className="program-pane" role="tabpanel">
      <div className="program-pane-heading"><div><p className="overline">ВАШ ПУТЬ</p><h3>Как растёт кешбэк</h3></div><span>{isMaxLevel ? "MAX" : `до ${progress.next_tier?.cashback_percent}%`}</span></div>
      <ul className="tier-ladder modal-tier-ladder">{progress.tiers.map((tier) => {
        const isCurrent = tier.minimum_turnover === progress.current_tier.minimum_turnover && tier.cashback_percent === progress.current_tier.cashback_percent;
        const isReached = Number(tier.minimum_turnover) <= Number(progress.current_tier.minimum_turnover);
        return <li className={`${isCurrent ? "current" : ""}${isReached ? " reached" : ""}`} key={`${tier.minimum_turnover}-${tier.cashback_percent}`}><i>{isReached ? <Icon name="check" size={13} /> : null}</i><span>от <Money value={tier.minimum_turnover} /></span><b>{tier.cashback_percent}%</b></li>;
      })}</ul>
      <div className="program-rules"><span><Icon name="chart" size={16} />Уровень зависит от общего оборота.</span><span><Icon name="gift" size={16} />Бонусы не сгорают.</span><span><Icon name="check" size={16} />Списываем до 10% заказа.</span></div>
    </section> : <section className="program-pane" role="tabpanel">
      <div className="program-pane-heading"><div><p className="overline">ВАШ БАЛАНС</p><h3>История баллов</h3></div><span className="soft-icon"><Icon name="chart" size={18} /></span></div>
      {!transactions ? <div className="modal-loader"><span className="loader" />Загружаем историю…</div> : transactions.items.length === 0 ? <div className="empty-state compact-empty"><span><Icon name="gift" /></span><h3>Операций пока нет</h3><p>Здесь появятся начисления и списания бонусов.</p></div> : <ul className="transaction-list">{transactions.items.map((transaction) => {
        const isAccrual = transaction.operation_type === "accrual";
        return <li key={transaction.id}><span className={`transaction-icon ${isAccrual ? "accrual" : "redemption"}`}><Icon name={isAccrual ? "plus" : "arrow"} size={16} /></span><div><strong>{isAccrual ? "Начислено бонусов" : "Списано бонусов"}</strong><small>{formatDate(transaction.created_at)} · баланс <Money value={transaction.balance_after} /></small></div><em className={isAccrual ? "accrual" : "redemption"}><Money prefix={isAccrual ? "+" : "−"} value={Math.abs(Number(transaction.amount))} /></em></li>;
      })}</ul>}
    </section>}
  </Modal>;
}
