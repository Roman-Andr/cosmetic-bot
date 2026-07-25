import { FormEvent, useCallback, useEffect, useState } from "react";

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

function formatByn(value: string): string {
  return `${Number(value).toFixed(2)} BYN`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ru-BY", { dateStyle: "medium" }).format(new Date(value));
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Произошла непредвиденная ошибка.";
}

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [contactReady, setContactReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [tab, setTab] = useState<"profile" | "purchases" | "admin">("profile");

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

  if (loading) return <main className="screen"><p>Загрузка…</p></main>;

  return (
    <main className="screen">
      <header className="hero">
        <p className="eyebrow">VELINA COSMETIC</p>
        <h1>Программа лояльности</h1>
      </header>
      {notice && <p className="notice" role="alert">{notice}</p>}
      {profile ? (
        <>
          <nav className="tabs" aria-label="Разделы">
            <button className={tab === "profile" ? "active" : ""} onClick={() => setTab("profile")}>Профиль</button>
            <button className={tab === "purchases" ? "active" : ""} onClick={() => setTab("purchases")}>Покупки</button>
            <button className={tab === "admin" ? "active" : ""} onClick={() => setTab("admin")}>Админ</button>
          </nav>
          {tab === "profile" && <ProfilePanel profile={profile} onProfile={setProfile} onNotice={setNotice} />}
          {tab === "purchases" && <PurchasesPanel onNotice={setNotice} />}
          {tab === "admin" && <AdminPanel onNotice={setNotice} />}
        </>
      ) : (
        <RegistrationPanel
          contactReady={contactReady}
          onContactReady={setContactReady}
          onProfile={setProfile}
          onNotice={setNotice}
        />
      )}
    </main>
  );
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
    const check = (): void => {
      window.setTimeout(() => {
        void api.get<{ is_available: boolean }>("/loyalty/contact-status")
          .then((result) => onContactReady(result.is_available))
          .catch((error: unknown) => onNotice(errorMessage(error)));
      }, 1000);
    };
    telegram.requestContact((shared) => {
      if (shared) check();
    });
  };

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!contactReady || !consent) return;
    setSubmitting(true);
    try {
      const profile = await api.post<Profile>("/loyalty/register", {
        full_name: fullName,
        birth_date: birthDate,
        gender,
      });
      onProfile(profile);
      onNotice("Регистрация завершена.");
    } catch (error) {
      onNotice(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="panel form" onSubmit={(event) => void submit(event)}>
      <h2>Регистрация</h2>
      <p>Поделитесь номером через защищённое окно Telegram, затем заполните профиль.</p>
      <button type="button" className="secondary" onClick={requestContact}>
        {contactReady ? "Номер получен" : "Поделиться номером"}
      </button>
      <label>ФИО<input required value={fullName} onChange={(event) => setFullName(event.target.value)} /></label>
      <label>Дата рождения<input required type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} /></label>
      <label>Пол
        <select value={gender} onChange={(event) => setGender(event.target.value as "male" | "female")}>
          <option value="female">Женский</option>
          <option value="male">Мужской</option>
        </select>
      </label>
      <label className="check"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
        <span>Согласен(на) с <a href={privacyUrl} target="_blank" rel="noreferrer">политикой конфиденциальности</a>.</span>
      </label>
      <button disabled={!contactReady || !consent || submitting} type="submit">Зарегистрироваться</button>
    </form>
  );
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
      <span>Ваш баланс</span><strong>{formatByn(profile.current_balance)}</strong>
      <p>Уровень {profile.tier.cashback_percent}% · накоплено {formatByn(profile.lifetime_turnover)}</p>
    </section>
    <section className="panel"><h2>Ваш код</h2>
      {code ? <><output className="code">{code.code}</output><p>Действует до {new Date(code.expires_at).toLocaleTimeString("ru-BY", { hour: "2-digit", minute: "2-digit" })}.</p></> : <p>Передайте код администратору при покупке.</p>}
      <button onClick={() => void getCode()}>Получить код</button>
    </section>
    <section className="panel"><h2>Профиль</h2><p>Телефон: {profile.phone}</p><p>В программе с {formatDate(profile.registered_at)}</p>
      <form className="form compact" onSubmit={(event) => void updateName(event)}><label>ФИО<input value={fullName} onChange={(event) => setFullName(event.target.value)} /></label><button>Сохранить ФИО</button></form>
    </section>
  </section>;
}

function PurchasesPanel({ onNotice }: { onNotice: (value: string | null) => void }) {
  const [purchases, setPurchases] = useState<PurchasePage | null>(null);
  useEffect(() => { void api.get<PurchasePage>("/loyalty/purchases").then(setPurchases).catch((error: unknown) => onNotice(errorMessage(error))); }, [onNotice]);
  if (!purchases) return <p>Загрузка покупок…</p>;
  return <section className="panel"><h2>Предыдущие покупки</h2>{purchases.items.length === 0 ? <p>Покупок пока нет.</p> : <ul className="history">{purchases.items.map((purchase) => <li key={purchase.id}><span>{formatDate(purchase.created_at)}</span><strong>{formatByn(purchase.total_amount)}</strong><small>Начислено: {formatByn(purchase.cashback_accrued)}</small></li>)}</ul>}</section>;
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
  if (allowed === null) return <p>Проверка доступа…</p>;
  if (!allowed) return <section className="panel"><h2>Кабинет администратора</h2><p>Этот раздел доступен главному администратору.</p></section>;

  const saveTiers = async (): Promise<void> => { try { setTiers(await api.put<Tier[]>("/admin/tiers", { rules: tiers.map(({ minimum_turnover, cashback_percent }) => ({ minimum_turnover, cashback_percent })) })); onNotice("Настройки уровней сохранены."); } catch (error) { onNotice(errorMessage(error)); } };
  const search = async (event: FormEvent): Promise<void> => { event.preventDefault(); try { setCustomers(await api.get<CustomerSearchResult[]>(`/admin/customers/search?query=${encodeURIComponent(query)}`)); } catch (error) { onNotice(errorMessage(error)); } };
  const openCustomer = async (customerId: string): Promise<void> => {
    try {
      const [customer, purchases] = await Promise.all([
        api.get<CustomerDetail>(`/admin/customers/${customerId}`),
        api.get<PurchasePage>(`/admin/customers/${customerId}/purchases`),
      ]);
      setSelectedCustomer(customer);
      setSelectedCustomerPurchases(purchases);
    } catch (error) { onNotice(errorMessage(error)); }
  };

  return <section className="stack">
    <section className="panel"><h2>Статистика</h2>{stats && <div className="stats"><span>Участники<strong>{stats.registrations}</strong></span><span>Покупки<strong>{stats.purchase_count}</strong></span><span>Оборот<strong>{formatByn(stats.turnover)}</strong></span><span>Бонусы<strong>{formatByn(stats.bonus_liability)}</strong></span></div>}</section>
    <section className="panel"><h2>Выгрузки</h2><div className="actions"><button onClick={() => void download("/admin/exports/customers", "customers.xlsx")}>Клиенты XLSX</button><button className="secondary" onClick={() => void download("/admin/exports/purchases", "purchases.xlsx")}>Покупки XLSX</button></div></section>
    <section className="panel"><h2>Поиск клиента</h2><form className="actions" onSubmit={(event) => void search(event)}><input placeholder="ФИО, телефон или код" value={query} onChange={(event) => setQuery(event.target.value)} /><button>Найти</button></form><ul className="history">{customers.map((customer) => <li key={customer.customer_id}><button className="history-button" type="button" onClick={() => void openCustomer(customer.customer_id)}><span>{customer.full_name}<small>{customer.phone}</small></span><strong>{formatByn(customer.current_balance)}</strong></button></li>)}</ul>{selectedCustomer && <section className="customer-card"><h3>{selectedCustomer.full_name}</h3><p>{selectedCustomer.phone} · в программе с {formatDate(selectedCustomer.registered_at)}</p><p>Баланс: {formatByn(selectedCustomer.current_balance)} · оборот: {formatByn(selectedCustomer.lifetime_turnover)}</p><h4>Покупки</h4><ul className="history">{selectedCustomerPurchases?.items.length ? selectedCustomerPurchases.items.map((purchase) => <li key={purchase.id}><span>{formatDate(purchase.created_at)}</span><strong>{formatByn(purchase.total_amount)}</strong></li>) : <li>Покупок пока нет.</li>}</ul></section>}</section>
    <section className="panel"><h2>Уровни кешбэка</h2>{tiers.map((tier, index) => <div className="tier-row" key={tier.id ?? index}><input aria-label="Порог" type="number" min="0" step="0.01" value={tier.minimum_turnover} onChange={(event) => setTiers(tiers.map((item, itemIndex) => itemIndex === index ? { ...item, minimum_turnover: event.target.value } : item))} /><span>BYN →</span><input aria-label="Кешбэк" type="number" min="0" max="100" step="0.01" value={tier.cashback_percent} onChange={(event) => setTiers(tiers.map((item, itemIndex) => itemIndex === index ? { ...item, cashback_percent: event.target.value } : item))} /><span>%</span></div>)}<button onClick={() => void saveTiers()}>Сохранить уровни</button></section>
  </section>;
}
