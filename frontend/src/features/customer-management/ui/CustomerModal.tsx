import {
  useCustomerPurchasesQuery,
  useCustomerQuery,
} from "../../../entities/admin/api/queries";
import { formatDate } from "../../../shared/lib/format";
import { useErrorNotice } from "../../../shared/lib/useErrorNotice";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";
import { ui } from "../../../shared/ui/classes";

interface CustomerModalProps {
  customerId: string;
  onClose: () => void;
  onNotice: NoticeHandler;
}

export function CustomerModal({ customerId, onClose, onNotice }: CustomerModalProps) {
  const customerQuery = useCustomerQuery(customerId);
  const purchasesQuery = useCustomerPurchasesQuery(customerId);
  const customer = customerQuery.data;
  const purchases = purchasesQuery.data;

  useErrorNotice(onNotice, customerQuery.error, purchasesQuery.error);

  return <Modal title="Карточка клиента" eyebrow="ПРОФИЛЬ" onClose={onClose}>
    {!customer ? <div className={ui("modal-loader")}><span className={ui("loader")} />Загружаем клиента…</div> : <>
      <div className={ui("customer-detail-head")}><span>{customer.full_name.slice(0, 1).toUpperCase()}</span><div><strong>{customer.full_name}</strong><small>{customer.phone} · с {formatDate(customer.registered_at)}</small></div></div>
      <div className={ui("customer-detail-metrics")}><span>Баланс<b><Money value={customer.current_balance} /></b></span><span>Оборот<b><Money value={customer.lifetime_turnover} /></b></span></div>
      <h3 className={ui("modal-section-title")}>Покупки</h3><ul className={ui("purchase-list")}>{purchasesQuery.isPending ? <li className={ui("empty-list")}>Загружаем покупки…</li> : purchases?.items.length ? purchases.items.map((purchase) => <li key={purchase.id}><span className={ui("purchase-date")}>{formatDate(purchase.created_at)}</span><strong><Money value={purchase.total_amount} /></strong><em><Money prefix="+" value={purchase.cashback_accrued} /></em></li>) : <li className={ui("empty-list")}>Покупок пока нет.</li>}</ul>
    </>}
  </Modal>;
}
