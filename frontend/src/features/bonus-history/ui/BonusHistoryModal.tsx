import { useEffect } from "react";

import { useTransactionsQuery } from "../../../entities/loyalty/api/queries";
import { errorMessage, formatDate } from "../../../shared/lib/format";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";
import { ui } from "../../../shared/ui/classes";

export function BonusHistoryModal({ balance, onClose, onNotice }: {
  balance: string;
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
    {transactionsQuery.isPending ? <div className={ui("modal-loader")}><span className={ui("loader")} />Загружаем историю…</div>
      : !transactions ? <div className={ui("empty-state", "compact-empty")}><span><Icon name="gift" /></span><h3>История недоступна</h3><p>Закройте окно и попробуйте ещё раз.</p></div>
      : transactions.items.length === 0
        ? <div className={ui("empty-state", "compact-empty")}><span><Icon name="gift" /></span><h3>Операций пока нет</h3><p>Здесь появятся начисления и списания бонусов.</p></div>
        : <section className={ui("transaction-history")}><header><h3>Операции</h3><span>{transactions.items.length}</span></header><ul className={ui("transaction-list")}>{transactions.items.map((transaction) => {
          const isAccrual = transaction.operation_type === "accrual";
          return <li key={transaction.id} className={isAccrual ? ui("transaction-item-accrual") : undefined}>
            <div className={ui("transaction-main")}>
              <span className={ui("transaction-icon", isAccrual ? "transaction-icon-accrual" : "transaction-icon-redemption")}><Icon name={isAccrual ? "plus" : "arrow"} size={18} /></span>
              <div className={ui("transaction-copy")}><strong>{isAccrual ? "Начисление" : "Списание"}</strong><small>{formatDate(transaction.created_at)}</small></div>
              <em className={ui("transaction-amount", isAccrual ? "transaction-amount-accrual" : "transaction-amount-redemption")}><Money prefix={isAccrual ? "+" : "−"} value={Math.abs(Number(transaction.amount))} /></em>
            </div>
            <div className={ui("transaction-balance")}><span>Баланс после операции</span><b><Money value={transaction.balance_after} /></b></div>
          </li>;
        })}</ul></section>}
  </Modal>;
}
