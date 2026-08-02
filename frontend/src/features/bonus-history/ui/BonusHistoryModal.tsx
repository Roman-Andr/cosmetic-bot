import { useEffect, useState } from "react";

import type { BonusTransactionPage } from "../../../entities/loyalty/model/types";
import { api } from "../../../shared/api/client";
import { errorMessage, formatDate } from "../../../shared/lib/format";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";

export function BonusHistoryModal({ balance, onClose, onNotice }: {
  balance: string;
  onClose: () => void;
  onNotice: NoticeHandler;
}) {
  const [transactions, setTransactions] = useState<BonusTransactionPage | null>(null);

  useEffect(() => {
    void api.get<BonusTransactionPage>("/loyalty/transactions")
      .then(setTransactions)
      .catch((error: unknown) => onNotice(errorMessage(error)));
  }, [balance, onNotice]);

  return <Modal title="История баллов" eyebrow="БОНУСНЫЙ СЧЁТ" onClose={onClose}>
    <section className="balance-history-summary">
      <span className="balance-history-icon"><Icon name="gift" size={24} /></span>
      <div><span>Доступно сейчас</span><strong><Money value={balance} /></strong></div>
    </section>
    {!transactions ? <div className="modal-loader"><span className="loader" />Загружаем историю…</div>
      : transactions.items.length === 0
        ? <div className="empty-state compact-empty"><span><Icon name="gift" /></span><h3>Операций пока нет</h3><p>Здесь появятся начисления и списания бонусов.</p></div>
        : <section className="transaction-history"><header><h3>Операции</h3><span>{transactions.items.length}</span></header><ul className="transaction-list">{transactions.items.map((transaction) => {
          const isAccrual = transaction.operation_type === "accrual";
          return <li key={transaction.id} className={isAccrual ? "accrual" : "redemption"}>
            <div className="transaction-main">
              <span className={`transaction-icon ${isAccrual ? "accrual" : "redemption"}`}><Icon name={isAccrual ? "plus" : "arrow"} size={18} /></span>
              <div className="transaction-copy"><strong>{isAccrual ? "Начисление" : "Списание"}</strong><small>{formatDate(transaction.created_at)}</small></div>
              <em className={isAccrual ? "accrual" : "redemption"}><Money prefix={isAccrual ? "+" : "−"} value={Math.abs(Number(transaction.amount))} /></em>
            </div>
            <div className="transaction-balance"><span>Баланс после операции</span><b><Money value={transaction.balance_after} /></b></div>
          </li>;
        })}</ul></section>}
  </Modal>;
}
