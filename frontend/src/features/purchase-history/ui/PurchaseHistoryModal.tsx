import { useEffect, useState } from "react";

import type { PurchasePage } from "../../../entities/loyalty/model/types";
import { api } from "../../../shared/api/client";
import { errorMessage, formatDate } from "../../../shared/lib/format";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";

export function PurchaseHistoryModal({ onClose, onNotice }: { onClose: () => void; onNotice: (value: string | null) => void }) {
  const [purchases, setPurchases] = useState<PurchasePage | null>(null);
  useEffect(() => { void api.get<PurchasePage>("/loyalty/purchases").then(setPurchases).catch((error: unknown) => onNotice(errorMessage(error))); }, [onNotice]);
  return <Modal title="Ваши покупки" eyebrow="ИСТОРИЯ" onClose={onClose}>
    {!purchases ? <div className="modal-loader"><span className="loader" />Загружаем покупки…</div> : purchases.items.length === 0 ? <div className="empty-state compact-empty"><span><Icon name="bag" /></span><h3>Покупок пока нет</h3><p>После первой покупки здесь появятся начисленные бонусы.</p></div> : <ul className="purchase-list">{purchases.items.map((purchase) => <li key={purchase.id}><span className="purchase-date">{formatDate(purchase.created_at)}</span><div><strong><Money value={purchase.total_amount} /></strong><small>{purchase.cashback_source === "birthday" ? `День рождения · ${purchase.cashback_percent}%` : `Кешбэк уровня · ${purchase.cashback_percent}%`}</small></div><em><Money prefix="+" value={purchase.cashback_accrued} /></em></li>)}</ul>}
  </Modal>;
}
