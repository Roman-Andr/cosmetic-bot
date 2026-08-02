import { useEffect, useState, type FormEvent } from "react";

import {
  useUpdateTiersMutation,
} from "../../../entities/admin/api/mutations";
import {
  useAdminStatsQuery,
  useAdminTiersQuery,
  useCustomerSearchQuery,
} from "../../../entities/admin/api/queries";
import { AdministratorsModal } from "../../../features/administrator-management/ui/AdministratorsModal";
import { CustomerModal } from "../../../features/customer-management/ui/CustomerModal";
import type { Tier } from "../../../entities/loyalty/model/types";
import { download } from "../../../shared/api/client";
import { errorMessage, formatDate } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import { useErrorNotice } from "../../../shared/lib/useErrorNotice";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { CurrencySymbol, Money } from "../../../shared/ui/Money";
import { ui } from "../../../shared/ui/classes";

type OwnerSection = "overview" | "customers" | "settings";

export function OwnerDashboard({ onNotice }: { onNotice: NoticeHandler }) {
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [tiersDirty, setTiersDirty] = useState(false);
  const [section, setSection] = useState<OwnerSection>("overview");
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const [showAdministrators, setShowAdministrators] = useState(false);
  const statsQuery = useAdminStatsQuery();
  const tiersQuery = useAdminTiersQuery();
  const customersQuery = useCustomerSearchQuery(submittedQuery);
  const updateTiersMutation = useUpdateTiersMutation();
  const stats = statsQuery.data;
  const customers = customersQuery.data ?? [];
  const hasSearched = submittedQuery.length >= 2;

  useEffect(() => {
    if (tiersQuery.data && !tiersDirty) setTiers(tiersQuery.data);
  }, [tiersDirty, tiersQuery.data]);

  useErrorNotice(onNotice, statsQuery.error, tiersQuery.error, customersQuery.error);

  const saveTiers = async (): Promise<void> => {
    try {
      const savedTiers = await updateTiersMutation.mutateAsync(
        tiers.map(({ minimum_turnover, cashback_percent }) => ({
          minimum_turnover,
          cashback_percent,
        })),
      );
      setTiers(savedTiers);
      setTiersDirty(false);
      haptic("success");
      onNotice("Правила кешбэка сохранены.", "success");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
  };

  const search = (event: FormEvent): void => {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (normalizedQuery.length < 2) { onNotice("Введите минимум два символа для поиска."); return; }
    if (normalizedQuery === submittedQuery) void customersQuery.refetch();
    else setSubmittedQuery(normalizedQuery);
  };

  const openCustomer = (customerId: string): void => {
    setSelectedCustomerId(customerId);
    haptic();
  };

  if (statsQuery.isPending || tiersQuery.isPending) return <section className={ui("owner-loading")}><span className={ui("loader")} />Загружаем управление…</section>;

  return <section className={ui("owner-workspace")}>
    <header className={ui("workspace-heading")}><p className={ui("eyebrow")}>УПРАВЛЕНИЕ ПРОГРАММОЙ</p><h1>Центр лояльности</h1><p>Главные показатели, база клиентов и правила — в отдельных рабочих разделах.</p></header>
    <nav className={ui("owner-tabs")} aria-label="Разделы управления">
      <OwnerTab active={section === "overview"} icon="chart" label="Обзор" onClick={() => setSection("overview")} />
      <OwnerTab active={section === "customers"} icon="search" label="Клиенты" onClick={() => setSection("customers")} />
      <OwnerTab active={section === "settings"} icon="gift" label="Настройки" onClick={() => setSection("settings")} />
    </nav>

    {section === "overview" && <div className={ui("owner-view")}>
      <section className={ui("metrics-board")}>{stats && <>
        <div><span className={ui("metric-icon")}><Icon name="account" size={18} /></span><small>Участники</small><strong>{stats.registrations}</strong></div>
        <div><span className={ui("metric-icon")}><Icon name="sale" size={18} /></span><small>Покупки</small><strong>{stats.purchase_count}</strong></div>
        <div><span className={ui("metric-icon")}><Icon name="chart" size={18} /></span><small>Оборот</small><strong><Money value={stats.turnover} /></strong></div>
        <div><span className={ui("metric-icon")}><Icon name="gift" size={18} /></span><small>Баланс бонусов</small><strong><Money value={stats.bonus_liability} /></strong></div>
      </>}</section>
      <section className={ui("owner-command-card")}><div><p className={ui("overline")} data-overline>БЫСТРЫЕ ДЕЙСТВИЯ</p><h2>Экспорт и команда</h2><p>Выгружайте данные или управляйте доступом Sales-администраторов.</p></div><div className={ui("command-actions")}><button type="button" onClick={() => void download("/admin/exports/customers", "customers.xlsx")}><Icon name="download" /><span>Клиенты</span><small>XLSX</small></button><button type="button" onClick={() => void download("/admin/exports/purchases", "purchases.xlsx")}><Icon name="download" /><span>Покупки</span><small>XLSX</small></button><button type="button" className={ui("command-team")} onClick={() => setShowAdministrators(true)}><Icon name="account" /><span>Команда</span><Icon name="arrow" size={16} /></button></div></section>
    </div>}

    {section === "customers" && <section className={ui("owner-view", "owner-card")}>
      <div className={ui("view-heading")}><div><p className={ui("overline")} data-overline>БАЗА КЛИЕНТОВ</p><h2>Найти клиента</h2><p>По ФИО, телефону или временному коду.</p></div><span className={ui("soft-icon")}><Icon name="search" /></span></div>
      <form className={ui("search-form")} onSubmit={search}><label className={ui("admin-search-field")}><Icon name="search" size={18} /><input className={ui("form-control")} aria-label="Поиск клиента" placeholder="Анна, телефон или код" value={query} onChange={(event) => setQuery(event.target.value)} /></label><button className={ui("primary-action", "auto-action")}>{customersQuery.isFetching ? "Ищем…" : "Найти"}</button></form>
      {hasSearched && <ul className={ui("customer-list")}>{customers.map((customer) => <li key={customer.customer_id}><button className={ui("customer-row")} type="button" onClick={() => openCustomer(customer.customer_id)}><span>{customer.full_name}<small>{customer.phone} · с {formatDate(customer.registered_at)}</small></span><strong><Money value={customer.current_balance} /><Icon name="arrow" size={15} /></strong></button></li>)}</ul>}
      {hasSearched && !customersQuery.isFetching && customers.length === 0 && <div className={ui("search-empty")}><Icon name="search" /><strong>Клиенты не найдены</strong><span>Проверьте запрос и попробуйте ещё раз.</span></div>}
    </section>}

    {section === "settings" && <section className={ui("owner-view", "owner-card")}>
      <div className={ui("view-heading")}><div><p className={ui("overline")} data-overline>ПРАВИЛА ЛОЯЛЬНОСТИ</p><h2>Уровни кешбэка</h2><p>Изменения применятся к следующим покупкам.</p></div><span className={ui("soft-icon")}><Icon name="gift" /></span></div>
      <div className={ui("tier-editor")}>{tiers.map((tier, index) => <section className={ui("tier-config-card")} key={tier.id ?? index}>
        <header><span className={ui("tier-index")}>{index + 1}</span><div><strong>Уровень {index + 1}</strong><small>Порог оборота и процент начисления</small></div></header>
        <div className={ui("tier-config-fields")}>
          <label><span>Оборот от</span><input className={ui("form-control", "number-input")} aria-label={`Порог уровня ${index + 1}`} type="number" min="0" step="0.01" value={tier.minimum_turnover} onChange={(event) => { setTiersDirty(true); setTiers(tiers.map((item, itemIndex) => itemIndex === index ? { ...item, minimum_turnover: event.target.value } : item)); }} /><em><CurrencySymbol /></em></label>
          <label><span>Кешбэк</span><input className={ui("form-control", "number-input")} aria-label={`Кешбэк уровня ${index + 1}`} type="number" min="0" max="100" step="0.01" value={tier.cashback_percent} onChange={(event) => { setTiersDirty(true); setTiers(tiers.map((item, itemIndex) => itemIndex === index ? { ...item, cashback_percent: event.target.value } : item)); }} /><em>%</em></label>
        </div>
      </section>)}</div>
      <button className={ui("primary-action")} disabled={updateTiersMutation.isPending} onClick={() => void saveTiers()}>{updateTiersMutation.isPending ? "Сохраняем…" : "Сохранить уровни"}<Icon name="check" /></button>
      <button className={ui("team-link")} type="button" onClick={() => setShowAdministrators(true)}><span><Icon name="account" />Sales-администраторы</span><Icon name="arrow" size={17} /></button>
    </section>}

    {selectedCustomerId && <CustomerModal customerId={selectedCustomerId} onClose={() => setSelectedCustomerId(null)} onNotice={onNotice} />}
    {showAdministrators && <AdministratorsModal onClose={() => setShowAdministrators(false)} onNotice={onNotice} />}
  </section>;
}

function OwnerTab({ active, icon, label, onClick }: { active: boolean; icon: "chart" | "search" | "gift"; label: string; onClick: () => void }) {
  return <button type="button" aria-pressed={active} onClick={onClick}><Icon name={icon} size={17} /><span>{label}</span></button>;
}
