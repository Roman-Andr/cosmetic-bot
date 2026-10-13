import { useEffect } from "react";

import { useTransactionsQuery } from "../../../entities/loyalty/api/queries";
import type { BonusExpiration, BonusTransaction } from "../../../entities/loyalty/model/types";
import { errorMessage, formatCalendarDate, formatDate } from "../../../shared/lib/format";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon, type IconName } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";
import { ui } from "../../../shared/ui/classes";

const operationIcons: Record<BonusTransaction["operation_type"], IconName> = {
  accrual: "plus",
  promotion: "gift",
  redemption: "arrow",
  expiration: "clock",
};

function operationTitle(transaction: BonusTransaction): string {
  switch (transaction.operation_type) {
    case "accrual": return "Начисление";
    case "promotion": return transaction.campaign_title ? `Подарок · ${transaction.campaign_title}` : "Подарок";
    case "redemption": return "Списание";
    case "expiration": return "Сгорание";
  }
}

export function BonusHistoryModal({ balance, nextExpiration, onClose, onNotice }: {
  balance: string;
  nextExpiration: BonusExpiration | null;
  onClose: () => void;
  onNotice: NoticeHandler;
}) {
  const transactionsQuery = useTransactionsQuery();
  const transactions = transactionsQuery.data;

  useEffect(() => {
    if (transactionsQuery.error) onNotice(errorMessage(transactionsQuery.error));
  }, [onNotice, transactionsQuery.error]);

  return <Modal title="История баллов" eyebrow="БОНУСНЫЙ СЧЁТ" onClose={onClose}>
    <section className={ui("balance-history-summary")}>
      <span className={ui("balance-history-icon")}><Icon name="gift" size={24} /></span>
      <div><span>Доступно сейчас</span><strong><Money value={balance} /></strong></div>
    </section>
    {nextExpiration && <p className={ui("expiry-note")}><Icon name="clock" size={18} /><span><b><Money value={nextExpiration.amount} /></b> сгорят после {formatCalendarDate(nextExpiration.valid_until)}. Потратьте их при следующей покупке.</span></p>}
    {transactionsQuery.isPending ? <div className={ui("modal-loader")}><span className={ui("loader")} />Загружаем историю…</div>
      : !transactions ? <div className={ui("empty-state", "compact-empty")}><span><Icon name="gift" /></span><h3>История недоступна</h3><p>Закройте окно и попробуйте ещё раз.</p></div>
      : transactions.items.length === 0
        ? <div className={ui("empty-state", "compact-empty")}><span><Icon name="gift" /></span><h3>Операций пока нет</h3><p>Здесь появятся начисления, подарки, списания и сгорания бонусов.</p></div>
        : <section className={ui("transaction-history")}><header><h3>Операции</h3><span>{transactions.items.length}</span></header><ul className={ui("transaction-list")}>{transactions.items.map((transaction) => {
          const isCredit = Number(transaction.amount) > 0;
          return <li key={transaction.id} className={isCredit ? ui("transaction-item-accrual") : undefined}>
            <div className={ui("transaction-main")}>
              <span className={ui("transaction-icon", isCredit ? "transaction-icon-accrual" : "transaction-icon-redemption")}><Icon name={operationIcons[transaction.operation_type]} size={18} /></span>
              <div className={ui("transaction-copy")}><strong>{operationTitle(transaction)}</strong><small>{formatDate(transaction.created_at)}</small></div>
              <em className={ui("transaction-amount", isCredit ? "transaction-amount-accrual" : "transaction-amount-redemption")}><Money prefix={isCredit ? "+" : "−"} value={Math.abs(Number(transaction.amount))} /></em>
            </div>
            <div className={ui("transaction-balance")}><span>Баланс после операции</span><b><Money value={transaction.balance_after} /></b></div>
          </li>;
        })}</ul></section>}
  </Modal>;
}
