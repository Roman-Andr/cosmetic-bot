import { useCallback, useEffect, useState, type FormEvent } from "react";

import type { Administrator, CustomerDetail, CustomerSearchResult, PurchasePage, Stats, Tier } from "../../../entities/loyalty/model/types";
import { api, download } from "../../../shared/api/client";
import { ApiError } from "../../../shared/api/client";
import { errorMessage, formatByn, formatDate } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";

export function OwnerDashboard({ onNotice }: { onNotice: (value: string | null) => void }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [query, setQuery] = useState("");
  const [customers, setCustomers] = useState<CustomerSearchResult[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerDetail | null>(null);
  const [selectedCustomerPurchases, setSelectedCustomerPurchases] = useState<PurchasePage | null>(null);
  const [showAdministrators, setShowAdministrators] = useState(false);
  const [savingTiers, setSavingTiers] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadDashboard = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      const [dashboard, configuredTiers] = await Promise.all([api.get<Stats>("/admin/stats"), api.get<Tier[]>("/admin/tiers")]);
      setStats(dashboard); setTiers(configuredTiers);
    } catch (error) { if (!(error instanceof ApiError && error.status === 403)) onNotice(errorMessage(error)); }
    finally { setLoading(false); }
  }, [onNotice]);

  useEffect(() => { void loadDashboard(); }, [loadDashboard]);

  const saveTiers = async (): Promise<void> => {
    setSavingTiers(true);
    try {
      setTiers(await api.put<Tier[]>("/admin/tiers", { rules: tiers.map(({ minimum_turnover, cashback_percent }) => ({ minimum_turnover, cashback_percent })) }));
      haptic("success"); onNotice("Правила кешбэка сохранены.");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
    finally { setSavingTiers(false); }
  };

  const search = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (query.trim().length < 2) { onNotice("Введите минимум два символа для поиска."); return; }
    try { setCustomers(await api.get<CustomerSearchResult[]>(`/admin/customers/search?query=${encodeURIComponent(query.trim())}`)); }
    catch (error) { onNotice(errorMessage(error)); }
  };

  const openCustomer = async (customerId: string): Promise<void> => {
    try {
      const [customer, purchases] = await Promise.all([api.get<CustomerDetail>(`/admin/customers/${customerId}`), api.get<PurchasePage>(`/admin/customers/${customerId}/purchases`)]);
      setSelectedCustomer(customer); setSelectedCustomerPurchases(purchases); haptic();
    } catch (error) { onNotice(errorMessage(error)); }
  };

  if (loading) return <section className="panel loading-panel"><span className="loader" />Загружаем управление…</section>;
  return <section className="stack owner-dashboard">
    <section className="owner-hero"><div><p className="eyebrow">УПРАВЛЕНИЕ ПРОГРАММОЙ</p><h2>Всё под контролем</h2><p>Показатели, клиенты и правила лояльности в одном месте.</p></div><span><Icon name="shield" size={25} /></span></section>
    <section className="panel"><div className="panel-heading"><div><p className="overline">ПОКАЗАТЕЛИ</p><h2>Обзор программы</h2></div><span className="soft-icon"><Icon name="chart" /></span></div>{stats && <div className="stats"><span>Участники<strong>{stats.registrations}</strong></span><span>Покупки<strong>{stats.purchase_count}</strong></span><span>Оборот<strong>{formatByn(stats.turnover)}</strong></span><span>Бонусы<strong>{formatByn(stats.bonus_liability)}</strong></span></div>}</section>
    <section className="panel owner-tools"><div className="panel-heading"><div><p className="overline">ИНСТРУМЕНТЫ</p><h2>Управление</h2></div></div><div className="tool-grid"><button className="tool-button" type="button" onClick={() => void download("/admin/exports/customers", "customers.xlsx")}><Icon name="download" /><span>Клиенты</span><small>XLSX</small></button><button className="tool-button" type="button" onClick={() => void download("/admin/exports/purchases", "purchases.xlsx")}><Icon name="download" /><span>Покупки</span><small>XLSX</small></button><button className="tool-button wide" type="button" onClick={() => setShowAdministrators(true)}><Icon name="account" /><span>Администраторы</span><Icon name="arrow" size={18} /></button></div></section>
    <section className="panel"><div className="panel-heading"><div><p className="overline">БАЗА КЛИЕНТОВ</p><h2>Найти клиента</h2></div><span className="soft-icon"><Icon name="search" /></span></div><form className="search-form" onSubmit={(event) => void search(event)}><input placeholder="ФИО, телефон или код" value={query} onChange={(event) => setQuery(event.target.value)} /><button className="primary-action">Найти</button></form><ul className="customer-list">{customers.map((customer) => <li key={customer.customer_id}><button className="customer-row" type="button" onClick={() => void openCustomer(customer.customer_id)}><span>{customer.full_name}<small>{customer.phone} · с {formatDate(customer.registered_at)}</small></span><strong>{formatByn(customer.current_balance)}<Icon name="arrow" size={15} /></strong></button></li>)}</ul>{customers.length === 0 && query && <p className="search-hint">Введите запрос и нажмите «Найти».</p>}</section>
    <section className="panel"><div className="panel-heading"><div><p className="overline">ПРАВИЛА ЛОЯЛЬНОСТИ</p><h2>Уровни кешбэка</h2></div><span className="soft-icon"><Icon name="gift" /></span></div><p className="muted tier-description">Уровень определяется по общему обороту клиента. Изменения применяются к следующим покупкам.</p>{tiers.map((tier, index) => <div className="tier-row" key={tier.id ?? index}><span className="tier-index">{index + 1}</span><label><small>Оборот от</small><input aria-label="Порог" type="number" min="0" step="0.01" value={tier.minimum_turnover} onChange={(event) => setTiers(tiers.map((item, itemIndex) => itemIndex === index ? { ...item, minimum_turnover: event.target.value } : item))} /><em>BYN</em></label><label><small>Кешбэк</small><input aria-label="Кешбэк" type="number" min="0" max="100" step="0.01" value={tier.cashback_percent} onChange={(event) => setTiers(tiers.map((item, itemIndex) => itemIndex === index ? { ...item, cashback_percent: event.target.value } : item))} /><em>%</em></label></div>)}<button className="primary-action" disabled={savingTiers} onClick={() => void saveTiers()}>{savingTiers ? "Сохраняем…" : "Сохранить уровни"}<Icon name="check" /></button></section>
    {selectedCustomer && <CustomerModal customer={selectedCustomer} purchases={selectedCustomerPurchases} onClose={() => setSelectedCustomer(null)} />}
    {showAdministrators && <AdministratorsModal onClose={() => setShowAdministrators(false)} onNotice={onNotice} />}
  </section>;
}

function CustomerModal({ customer, purchases, onClose }: { customer: CustomerDetail; purchases: PurchasePage | null; onClose: () => void }) {
  return <Modal title="Карточка клиента" eyebrow="VELINA CLUB" onClose={onClose}>
    <div className="customer-detail-head"><span>{customer.full_name.slice(0, 1).toUpperCase()}</span><div><strong>{customer.full_name}</strong><small>{customer.phone} · с {formatDate(customer.registered_at)}</small></div></div>
    <div className="customer-detail-metrics"><span>Баланс<b>{formatByn(customer.current_balance)}</b></span><span>Оборот<b>{formatByn(customer.lifetime_turnover)}</b></span></div>
    <h3 className="modal-section-title">Покупки</h3><ul className="purchase-list compact-list">{purchases?.items.length ? purchases.items.map((purchase) => <li key={purchase.id}><span className="purchase-date">{formatDate(purchase.created_at)}</span><strong>{formatByn(purchase.total_amount)}</strong><em>+{formatByn(purchase.cashback_accrued)}</em></li>) : <li className="empty-list">Покупок пока нет.</li>}</ul>
  </Modal>;
}

function AdministratorsModal({ onClose, onNotice }: { onClose: () => void; onNotice: (value: string | null) => void }) {
  const [administrators, setAdministrators] = useState<Administrator[] | null>(null);
  const [telegramId, setTelegramId] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async (): Promise<void> => { try { setAdministrators(await api.get<Administrator[]>("/admin/administrators")); } catch (error) { onNotice(errorMessage(error)); } }, [onNotice]);
  useEffect(() => { void load(); }, [load]);
  const add = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!/^\d+$/.test(telegramId)) { onNotice("Введите числовой Telegram ID."); return; }
    setAdding(true);
    try {
      await api.post<Administrator>("/admin/administrators", { telegram_user_id: Number(telegramId) });
      setTelegramId(""); await load(); haptic("success"); onNotice("Sales-администратор добавлен.");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
    finally { setAdding(false); }
  };
  return <Modal title="Администраторы" eyebrow="ДОСТУП К ПРОДАЖАМ" onClose={onClose}>
    <p className="muted">Sales-администратор может оформлять покупки в боте и Mini App, но не видит данные клиентов и настройки.</p>
    <form className="administrator-form" onSubmit={(event) => void add(event)}><input inputMode="numeric" value={telegramId} onChange={(event) => setTelegramId(event.target.value.replace(/\D/g, ""))} placeholder="Telegram ID" /><button className="primary-action" disabled={adding}>{adding ? "Добавляем…" : "Добавить"}<Icon name="plus" /></button></form>
    <ul className="administrator-list">{administrators?.map((admin) => <li key={admin.telegram_user_id}><span className={`role-dot ${admin.role}`} /><div><strong>{admin.role === "owner" ? "Главный администратор" : "Sales-администратор"}</strong><small>{admin.telegram_user_id}</small></div><em>{admin.is_active ? "Активен" : "Выключен"}</em></li>)}</ul>
  </Modal>;
}
