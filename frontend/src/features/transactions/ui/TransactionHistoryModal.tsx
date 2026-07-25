import { useEffect, useState } from "react";

import type { BonusTransactionPage } from "../../../entities/loyalty/model/types";
import { api } from "../../../shared/api/client";
import { errorMessage, formatByn, formatDate } from "../../../shared/lib/format";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";

export function TransactionHistoryModal({ onClose, onNotice }: { onClose: () => void; onNotice: (message: string | null) => void }) {
  const [transactions, setTransactions] = useState<BonusTransactionPage | null>(null);
  useEffect(() => { void api.get<BonusTransactionPage>("/loyalty/transactions").then(setTransactions).catch((error: unknown) => onNotice(errorMessage(error))); }, [onNotice]);
  return <Modal title="Движение бонусов" eyebrow="ВАШ БАЛАНС" onClose={onClose}>
    {!transactions ? <div className="modal-loader"><span className="loader" />Загружаем историю…</div> : transactions.items.length === 0 ? <div className="empty-state compact-empty"><span><Icon name="gift" /></span><h3>Операций пока нет</h3><p>Здесь появятся начисления и списания бонусов.</p></div> : <ul className="transaction-list">{transactions.items.map((transaction) => {
      const isAccrual = transaction.operation_type === "accrual";
      const displayAmount = formatByn(String(Math.abs(Number(transaction.amount))));
      return <li key={transaction.id}><span className={`transaction-icon ${isAccrual ? "accrual" : "redemption"}`}><Icon name={isAccrual ? "plus" : "arrow"} size={16} /></span><div><strong>{isAccrual ? "Начислено бонусов" : "Списано бонусов"}</strong><small>{formatDate(transaction.created_at)} · баланс {formatByn(transaction.balance_after)}</small></div><em className={isAccrual ? "accrual" : "redemption"}>{isAccrual ? "+" : "−"}{displayAmount}</em></li>;
    })}</ul>}
  </Modal>;
}
