import { useEffect, useState } from "react";

import type { PurchasePage } from "../../../entities/loyalty/model/types";
import { api } from "../../../shared/api/client";
import { errorMessage, formatByn, formatDate } from "../../../shared/lib/format";
import { Icon } from "../../../shared/ui/Icon";

export function PurchasesPanel({ onNotice }: { onNotice: (value: string | null) => void }) {
  const [purchases, setPurchases] = useState<PurchasePage | null>(null);
  useEffect(() => { void api.get<PurchasePage>("/loyalty/purchases").then(setPurchases).catch((error: unknown) => onNotice(errorMessage(error))); }, [onNotice]);
  if (!purchases) return <section className="panel loading-panel"><span className="loader" />Загружаем покупки…</section>;
  return <section className="stack"><section className="panel purchases-panel"><div className="panel-heading"><div><p className="overline">ИСТОРИЯ</p><h2>Ваши покупки</h2></div><span className="soft-icon"><Icon name="bag" /></span></div>{purchases.items.length === 0 ? <div className="empty-state"><span><Icon name="bag" /></span><h3>Покупок пока нет</h3><p>После первой покупки здесь появятся начисленные бонусы.</p></div> : <ul className="purchase-list">{purchases.items.map((purchase) => <li key={purchase.id}><span className="purchase-date">{formatDate(purchase.created_at)}</span><div><strong>{formatByn(purchase.total_amount)}</strong><small>{purchase.cashback_source === "birthday" ? `День рождения · ${purchase.cashback_percent}%` : `Кешбэк уровня · ${purchase.cashback_percent}%`}</small></div><em>+{formatByn(purchase.cashback_accrued)}</em></li>)}</ul>}</section></section>;
}
