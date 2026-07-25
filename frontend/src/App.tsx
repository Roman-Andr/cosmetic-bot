import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";

import { api, ApiError, download } from "./api";
import { getTelegramApp } from "./telegram";
import type {
  CustomerDetail,
  CustomerSearchResult,
  Profile,
  PurchasePage,
  Stats,
  Tier,
} from "./types";

const privacyUrl = "https://velinacosmetic.by/privacy";

type Tab = "profile" | "purchases" | "admin";
type IconName = "account" | "bag" | "chart" | "gift" | "shield" | "code";

function formatByn(value: string): string {
  return `${Number(value).toFixed(2)} BYN`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ru-BY", { dateStyle: "medium" }).format(new Date(value));
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Произошла непредвиденная ошибка.";
}

function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, ReactNode> = {
    account: <><circle cx="12" cy="8" r="3.25" /><path d="M5.5 20c.75-3.25 3-5 6.5-5s5.75 1.75 6.5 5" /></>,
    bag: <><path d="M5 8.5h14l-1 11H6l-1-11Z" /><path d="M9 9V7a3 3 0 0 1 6 0v2" /></>,
    chart: <><path d="M5 19.5V11m7 8.5V5m7 14.5v-6" /><path d="M3.5 20.5h17" /></>,
    gift: <><path d="M4.5 10h15v10h-15zM3.5 7h17v3h-17zM12 7v13M12 7c-3.5 0-5-1.1-5-2.5C7 3.55 8 3 9 3c1.7 0 3 2 3 4Zm0 0c3.5 0 5-1.1 5-2.5 0-.95-1-1.5-2-1.5-1.7 0-3 2-3 4Z" /></>,
    shield: <><path d="M12 3.5 19 6v5c0 4.3-2.9 7.7-7 9.5-4.1-1.8-7-5.2-7-9.5V6l7-2.5Z" /><path d="m9 12 2 2 4-4" /></>,
    code: <><rect x="4" y="5" width="16" height="14" rx="2.5" /><path d="m9.5 10-2 2 2 2m5-4 2 2-2 2" /></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function SectionTile({
  active,
  icon,
  title,
  subtitle,
  onClick,
}: {
  active: boolean;
  icon: IconName;
  title: string;
  subtitle: string;
  onClick: () => void;
}) {
  return <button type="button" className={`section-tile${active ? " active" : ""}`} onClick={onClick}>
    <span className="tile-icon"><Icon name={icon} /></span>
    <span className="tile-copy"><strong>{title}</strong><small>{subtitle}</small></span>
  </button>;
}

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [contactReady, setContactReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("profile");

  const load = async (): Promise<void> => {
    setLoading(true);
    try {
      const result = await api.get<Profile>("/loyalty/me");
      setProfile(result);
      setContactReady(true);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        const contact = await api.get<{ is_available: boolean }>("/loyalty/contact-status");
        setContactReady(contact.is_available);
      } else {
        setNotice(errorMessage(error));
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const telegram = getTelegramApp();
    telegram?.ready();
    telegram?.expand();
    void load();
  }, []);

  if (loading) return <main className="screen loading-screen"><span className="loader" /><p>Открываем ваш кабинет…</p></main>;

  return <main className="screen">
    <header className="hero">
      <div className="brand-mark">V</div>
      <div>
        <p className="eyebrow">VELINA COSMETIC</p>
        <h1>Красота с привилегиями</h1>
      </div>
    </header>
    {notice && <button type="button" className="notice" role="alert" onClick={() => setNotice(null)}>{notice}<span>×</span></button>}
    {profile ? <>
      <nav className="section-grid" aria-label="Разделы кабинета">
        <SectionTile active={tab === "profile"} icon="account" title="Мой профиль" subtitle="Баланс и код" onClick={() => setTab("profile")} />
        <SectionTile active={tab === "purchases"} icon="bag" title="Покупки" subtitle="История заказов" onClick={() => setTab("purchases")} />
        {profile.is_owner && <SectionTile active={tab === "admin"} icon="shield" title="Управление" subtitle="Только для владельца" onClick={() => setTab("admin")} />}
      </nav>
      <div className="tab-content">
        {tab === "profile" && <ProfilePanel profile={profile} onProfile={setProfile} onNotice={setNotice} />}
        {tab === "purchases" && <PurchasesPanel onNotice={setNotice} />}
        {tab === "admin" && profile.is_owner && <AdminPanel onNotice={setNotice} />}
      </div>
    </> : <RegistrationPanel contactReady={contactReady} onContactReady={setContactReady} onProfile={setProfile} onNotice={setNotice} />}
  </main>;
}

function RegistrationPanel({
  contactReady,
  onContactReady,
  onProfile,
  onNotice,
}: {
  contactReady: boolean;
  onContactReady: (value: boolean) => void;
  onProfile: (value: Profile) => void;
  onNotice: (value: string | null) => void;
}) {
  const [fullName, setFullName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState<"male" | "female">("female");
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const requestContact = (): void => {
    const telegram = getTelegramApp();
    if (!telegram) {
      onNotice("Регистрация доступна только внутри Telegram.");
      return;
    }
    telegram.requestContact((shared) => {
      if (!shared) return;
      window.setTimeout(() => {
        void api.get<{ is_available: boolean }>("/loyalty/contact-status")
          .then((result) => onContactReady(result.is_available))
          .catch((error: unknown) => onNotice(errorMessage(error)));
      }, 900);
    });
  };

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!contactReady || !consent) return;
    setSubmitting(true);
    try {
      onProfile(await api.post<Profile>("/loyalty/register", { full_name: fullName, birth_date: birthDate, gender }));
      onNotice("Добро пожаловать в программу лояльности!");
    } catch (error) {
      onNotice(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  return <section className="registration-layout">
    <section className="intro-card">
      <span className="intro-icon"><Icon name="gift" /></span>
      <p className="eyebrow">VELINA CLUB</p>
      <h2>Покупайте —<br />возвращайте бонусы</h2>
      <p>Сохраняйте бонусы, используйте до 10% от суммы покупки и получайте особый кешбэк ко дню рождения.</p>
    </section>
    <form className="panel form registration-form" onSubmit={(event) => void submit(event)}>
      <div className="panel-heading"><div><p className="overline">ШАГ 1 ИЗ 1</p><h2>Создать профиль</h2></div><span className={`phone-status${contactReady ? " ready" : ""}`}>{contactReady ? "Номер получен" : "Нужен номер"}</span></div>
      <p className="muted">Поделитесь номером через защищённое окно Telegram. Он нужен только для участия в программе.</p>
      <button type="button" className="contact-button" onClick={requestContact}>
        <span className="button-icon"><Icon name="shield" /></span>{contactReady ? "Номер подтверждён" : "Поделиться номером"}
      </button>
      <div className="form-grid">
        <label>ФИО<input required autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Как к вам обращаться" /></label>
        <label>Дата рождения<input required type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} /></label>
      </div>
      <label>Пол<select value={gender} onChange={(event) => setGender(event.target.value as "male" | "female")}><option value="female">Женский</option><option value="male">Мужской</option></select></label>
      <label className="check"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /><span>Согласен(на) с <a href={privacyUrl} target="_blank" rel="noreferrer">политикой конфиденциальности</a>.</span></label>
      <button className="primary-action" disabled={!contactReady || !consent || submitting} type="submit">{submitting ? "Сохраняем…" : "Стать участником"}</button>
    </form>
  </section>;
}

function ProfilePanel({ profile, onProfile, onNotice }: { profile: Profile; onProfile: (value: Profile) => void; onNotice: (value: string | null) => void }) {
  const [fullName, setFullName] = useState(profile.full_name);
  const [code, setCode] = useState<{ code: string; expires_at: string } | null>(null);

  const updateName = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    try {
      onProfile(await api.patch<Profile>("/loyalty/me", { full_name: fullName }));
      onNotice("ФИО обновлено.");
    } catch (error) { onNotice(errorMessage(error)); }
  };

  const getCode = async (): Promise<void> => {
    try { setCode(await api.post("/loyalty/code")); } catch (error) { onNotice(errorMessage(error)); }
  };

  return <section className="stack">
    <section className="balance-card">
      <div className="balance-top"><span>Ваш бонусный баланс</span><span className="balance-orb"><Icon name="gift" /></span></div>
      <strong>{formatByn(profile.current_balance)}</strong>
      <div className="balance-meta"><span>Ваш уровень <b>{profile.tier.cashback_percent}%</b></span><span>Оборот {formatByn(profile.lifetime_turnover)}</span></div>
    </section>
    <section className={`birthday-card${profile.birthday_cashback_active ? " active" : ""}`}>
      <span className="birthday-icon"><Icon name="gift" /></span>
      <div><p className="overline">ОСОБЫЙ БОНУС</p><h2>{profile.birthday_cashback_active ? "День рождения уже рядом" : "Кешбэк ко дню рождения"}</h2><p>{profile.birthday_cashback_active ? `Сегодня действует повышенный кешбэк ${profile.birthday_cashback_percent}%.` : `Получите ${profile.birthday_cashback_percent}% за ${profile.birthday_cashback_window_days} дня до и ${profile.birthday_cashback_window_days} дня после даты рождения.`}</p></div>
      <strong>{profile.birthday_cashback_percent}%</strong>
    </section>
    <section className="panel code-panel">
      <div className="panel-heading"><div><p className="overline">ПОКУПКА В МАГАЗИНЕ</p><h2>Ваш временный код</h2></div><span className="soft-icon"><Icon name="code" /></span></div>
      {code ? <div className="code-result"><output className="code">{code.code}</output><p>Покажите его администратору до {new Date(code.expires_at).toLocaleTimeString("ru-BY", { hour: "2-digit", minute: "2-digit" })}.</p></div> : <p className="muted">Передайте код администратору — бонусы спишутся автоматически, но не более 10% от суммы заказа.</p>}
      <button className="primary-action" onClick={() => void getCode()}>{code ? "Получить новый код" : "Получить код"}</button>
    </section>
    <section className="panel profile-panel">
      <div className="panel-heading"><div><p className="overline">ВАШИ ДАННЫЕ</p><h2>Профиль</h2></div><span className="soft-icon"><Icon name="account" /></span></div>
      <div className="profile-facts"><span>Телефон<b>{profile.phone}</b></span><span>Участник с<b>{formatDate(profile.registered_at)}</b></span></div>
      <form className="form compact" onSubmit={(event) => void updateName(event)}><label>ФИО<input value={fullName} onChange={(event) => setFullName(event.target.value)} /></label><button className="secondary-action">Сохранить изменения</button></form>
    </section>
  </section>;
}

function PurchasesPanel({ onNotice }: { onNotice: (value: string | null) => void }) {
  const [purchases, setPurchases] = useState<PurchasePage | null>(null);
  useEffect(() => { void api.get<PurchasePage>("/loyalty/purchases").then(setPurchases).catch((error: unknown) => onNotice(errorMessage(error))); }, [onNotice]);
  if (!purchases) return <section className="panel loading-panel"><span className="loader" />Загружаем покупки…</section>;
  return <section className="stack"><section className="panel purchases-panel"><div className="panel-heading"><div><p className="overline">ИСТОРИЯ</p><h2>Ваши покупки</h2></div><span className="soft-icon"><Icon name="bag" /></span></div>{purchases.items.length === 0 ? <div className="empty-state"><span><Icon name="bag" /></span><h3>Покупок пока нет</h3><p>После первой покупки здесь появятся начисленные бонусы.</p></div> : <ul className="purchase-list">{purchases.items.map((purchase) => <li key={purchase.id}><span className="purchase-date">{formatDate(purchase.created_at)}</span><div><strong>{formatByn(purchase.total_amount)}</strong><small>{purchase.cashback_source === "birthday" ? `День рождения · ${purchase.cashback_percent}%` : `Кешбэк уровня · ${purchase.cashback_percent}%`}</small></div><em>+{formatByn(purchase.cashback_accrued)}</em></li>)}</ul>}</section></section>;
}

function AdminPanel({ onNotice }: { onNotice: (value: string | null) => void }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [query, setQuery] = useState("");
  const [customers, setCustomers] = useState<CustomerSearchResult[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerDetail | null>(null);
  const [selectedCustomerPurchases, setSelectedCustomerPurchases] = useState<PurchasePage | null>(null);
  const [allowed, setAllowed] = useState<boolean | null>(null);

  const loadAdmin = useCallback(async (): Promise<void> => {
    try {
      const [dashboard, configuredTiers] = await Promise.all([api.get<Stats>("/admin/stats"), api.get<Tier[]>("/admin/tiers")]);
      setStats(dashboard); setTiers(configuredTiers); setAllowed(true);
    } catch (error) {
      setAllowed(false);
      if (!(error instanceof ApiError && error.status === 403)) onNotice(errorMessage(error));
    }
  }, [onNotice]);
  useEffect(() => { void loadAdmin(); }, [loadAdmin]);
  if (allowed === null) return <section className="panel loading-panel"><span className="loader" />Загружаем управление…</section>;
  if (!allowed) return null;

  const saveTiers = async (): Promise<void> => { try { setTiers(await api.put<Tier[]>("/admin/tiers", { rules: tiers.map(({ minimum_turnover, cashback_percent }) => ({ minimum_turnover, cashback_percent })) })); onNotice("Настройки уровней сохранены."); } catch (error) { onNotice(errorMessage(error)); } };
  const search = async (event: FormEvent): Promise<void> => { event.preventDefault(); try { setCustomers(await api.get<CustomerSearchResult[]>(`/admin/customers/search?query=${encodeURIComponent(query)}`)); } catch (error) { onNotice(errorMessage(error)); } };
  const openCustomer = async (customerId: string): Promise<void> => {
    try {
      const [customer, purchases] = await Promise.all([api.get<CustomerDetail>(`/admin/customers/${customerId}`), api.get<PurchasePage>(`/admin/customers/${customerId}/purchases`)]);
      setSelectedCustomer(customer); setSelectedCustomerPurchases(purchases);
    } catch (error) { onNotice(errorMessage(error)); }
  };

  return <section className="stack admin-panel">
    <section className="panel"><div className="panel-heading"><div><p className="overline">ВЛАДЕЛЕЦ</p><h2>Показатели</h2></div><span className="soft-icon"><Icon name="chart" /></span></div>{stats && <div className="stats"><span>Участники<strong>{stats.registrations}</strong></span><span>Покупки<strong>{stats.purchase_count}</strong></span><span>Оборот<strong>{formatByn(stats.turnover)}</strong></span><span>Бонусы<strong>{formatByn(stats.bonus_liability)}</strong></span></div>}</section>
    <section className="panel"><div className="panel-heading"><div><p className="overline">ВЫГРУЗКИ</p><h2>Отчёты</h2></div></div><div className="actions"><button className="secondary-action" onClick={() => void download("/admin/exports/customers", "customers.xlsx")}>Клиенты XLSX</button><button className="secondary-action" onClick={() => void download("/admin/exports/purchases", "purchases.xlsx")}>Покупки XLSX</button></div></section>
    <section className="panel"><div className="panel-heading"><div><p className="overline">БАЗА КЛИЕНТОВ</p><h2>Поиск</h2></div></div><form className="search-form" onSubmit={(event) => void search(event)}><input placeholder="ФИО, телефон или код" value={query} onChange={(event) => setQuery(event.target.value)} /><button className="primary-action">Найти</button></form><ul className="customer-list">{customers.map((customer) => <li key={customer.customer_id}><button className="customer-row" type="button" onClick={() => void openCustomer(customer.customer_id)}><span>{customer.full_name}<small>{customer.phone}</small></span><strong>{formatByn(customer.current_balance)}</strong></button></li>)}</ul>{selectedCustomer && <section className="customer-card"><h3>{selectedCustomer.full_name}</h3><p>{selectedCustomer.phone} · в программе с {formatDate(selectedCustomer.registered_at)}</p><p>Баланс {formatByn(selectedCustomer.current_balance)} · оборот {formatByn(selectedCustomer.lifetime_turnover)}</p><h4>Покупки</h4><ul className="purchase-list compact-list">{selectedCustomerPurchases?.items.length ? selectedCustomerPurchases.items.map((purchase) => <li key={purchase.id}><span className="purchase-date">{formatDate(purchase.created_at)}</span><strong>{formatByn(purchase.total_amount)}</strong><em>+{formatByn(purchase.cashback_accrued)}</em></li>) : <li>Покупок пока нет.</li>}</ul></section>}</section>
    <section className="panel"><div className="panel-heading"><div><p className="overline">ПРАВИЛА ЛОЯЛЬНОСТИ</p><h2>Уровни кешбэка</h2></div></div>{tiers.map((tier, index) => <div className="tier-row" key={tier.id ?? index}><input aria-label="Порог" type="number" min="0" step="0.01" value={tier.minimum_turnover} onChange={(event) => setTiers(tiers.map((item, itemIndex) => itemIndex === index ? { ...item, minimum_turnover: event.target.value } : item))} /><span>BYN</span><input aria-label="Кешбэк" type="number" min="0" max="100" step="0.01" value={tier.cashback_percent} onChange={(event) => setTiers(tiers.map((item, itemIndex) => itemIndex === index ? { ...item, cashback_percent: event.target.value } : item))} /><span>%</span></div>)}<button className="primary-action" onClick={() => void saveTiers()}>Сохранить уровни</button></section>
  </section>;
}
