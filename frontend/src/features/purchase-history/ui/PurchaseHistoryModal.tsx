import { useEffect, useState } from "react";

import type { PurchasePage } from "../../../entities/loyalty/model/types";
import { api } from "../../../shared/api/client";
import { errorMessage, formatDate } from "../../../shared/lib/format";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";
import { ui } from "../../../shared/ui/classes";

export function PurchaseHistoryModal({ onClose, onNotice }: { onClose: () => void; onNotice: NoticeHandler }) {
  const [purchases, setPurchases] = useState<PurchasePage | null>(null);
  useEffect(() => { void api.get<PurchasePage>("/loyalty/purchases").then(setPurchases).catch((error: unknown) => onNotice(errorMessage(error))); }, [onNotice]);
  return <Modal title="Ваши покупки" eyebrow="ИСТОРИЯ" onClose={onClose}>
    {!purchases ? <div className={ui("modal-loader")}><span className={ui("loader")} />Загружаем покупки…</div> : purchases.items.length === 0 ? <div className={ui("empty-state", "compact-empty")}><span><Icon name="bag" /></span><h3>Покупок пока нет</h3><p>После первой покупки здесь появятся начисленные бонусы.</p></div> : <ul className={ui("purchase-timeline")}>{purchases.items.map((purchase) => <li key={purchase.id}><span className={ui("purchase-dot")} /><div><small>{formatDate(purchase.created_at)}</small><strong><Money value={purchase.total_amount} /></strong><em>{purchase.cashback_source === "birthday" ? `День рождения · ${purchase.cashback_percent}%` : `Уровень · ${purchase.cashback_percent}%`}</em></div><b><Money prefix="+" value={purchase.cashback_accrued} /></b></li>)}</ul>}
  </Modal>;
}
