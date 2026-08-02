import { useEffect, useRef, useState, type FormEvent } from "react";

import type { BuyerLookup, Product, SalePreview, SaleRecord } from "../../../entities/loyalty/model/types";
import { api, ApiError } from "../../../shared/api/client";
import { errorMessage, formatDate } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { CurrencySymbol, Money } from "../../../shared/ui/Money";
import { ui } from "../../../shared/ui/classes";

export function SaleWorkspace({ onNotice }: { onNotice: NoticeHandler }) {
  const [buyerCode, setBuyerCode] = useState("");
  const [amount, setAmount] = useState("");
  const [query, setQuery] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<Product[]>([]);
  const [preview, setPreview] = useState<SalePreview | null>(null);
  const [success, setSuccess] = useState<SaleRecord | null>(null);
  const [searching, setSearching] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [recording, setRecording] = useState(false);
  const [productPickerOpen, setProductPickerOpen] = useState(false);
  const [buyer, setBuyer] = useState<BuyerLookup | null>(null);
  const [buyerLookupState, setBuyerLookupState] = useState<"idle" | "loading" | "found" | "not-found">("idle");
  const productRequestId = useRef(0);
  const buyerRequestId = useRef(0);
  const productPickerRef = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    if (buyerCode.length !== 6) {
      buyerRequestId.current += 1;
      setBuyer(null);
      setBuyerLookupState("idle");
      return;
    }

    const requestId = ++buyerRequestId.current;
    setBuyerLookupState("loading");
    const timer = window.setTimeout(() => {
      void api.get<BuyerLookup>(`/admin/purchases/customer?buyer_code=${buyerCode}`)
        .then((customer) => {
          if (requestId !== buyerRequestId.current) return;
          setBuyer(customer);
          setBuyerLookupState("found");
          haptic("light");
        })
        .catch((error: unknown) => {
          if (requestId !== buyerRequestId.current) return;
          setBuyer(null);
          if (error instanceof ApiError && error.status === 404) {
            setBuyerLookupState("not-found");
            haptic("warning");
          } else {
            setBuyerLookupState("idle");
            onNotice(errorMessage(error));
          }
        });
    }, 180);

    return () => window.clearTimeout(timer);
  }, [buyerCode, onNotice]);

  useEffect(() => {
    if (!productPickerOpen) {
      productRequestId.current += 1;
      setSearching(false);
      return;
    }

    const requestId = ++productRequestId.current;
    const timer = window.setTimeout(() => {
      setSearching(true);
      void api.get<Product[]>(`/admin/products?query=${encodeURIComponent(query.trim())}`)
        .then((items) => { if (requestId === productRequestId.current) setProducts(items); })
        .catch((error: unknown) => { if (requestId === productRequestId.current) onNotice(errorMessage(error)); })
        .finally(() => { if (requestId === productRequestId.current) setSearching(false); });
    }, query.trim() ? 180 : 0);

    return () => window.clearTimeout(timer);
  }, [onNotice, productPickerOpen, query]);

  const selectProduct = (product: Product): void => {
    if (selectedProducts.some((item) => item.external_id === product.external_id)) return;
    setSelectedProducts((items) => [...items, product]);
    haptic();
  };

  const removeProduct = (externalId: string): void => {
    setSelectedProducts((items) => items.filter((item) => item.external_id !== externalId));
    haptic();
  };

  const openPreview = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!/^\d{6}$/.test(buyerCode) || Number(amount) <= 0) {
      haptic("warning");
      onNotice("Введите шестизначный код и сумму покупки больше нуля.");
      return;
    }
    setPreviewing(true);
    try {
      setPreview(await api.post<SalePreview>("/admin/purchases/preview", { buyer_code: buyerCode, total_amount: amount }));
      haptic("light");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
    finally { setPreviewing(false); }
  };

  const recordSale = async (): Promise<void> => {
    setRecording(true);
    try {
      const result = await api.post<SaleRecord>("/admin/purchases", {
        buyer_code: buyerCode,
        total_amount: amount,
        product_external_ids: selectedProducts.map((item) => item.external_id),
      });
      setPreview(null);
      setSuccess(result);
      haptic("success");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
    finally { setRecording(false); }
  };

  const reset = (): void => {
    buyerRequestId.current += 1;
    setBuyerCode(""); setBuyer(null); setBuyerLookupState("idle"); setAmount(""); setQuery(""); setProducts([]); setSelectedProducts([]); setPreview(null); setSuccess(null);
    if (productPickerRef.current) productPickerRef.current.open = false;
    setProductPickerOpen(false);
  };
  const availableProducts = products.filter((product) => !selectedProducts.some((selected) => selected.external_id === product.external_id));

  return <section className={ui("sales-workspace")}>
    <header className={ui("workspace-heading")}><p className={ui("eyebrow")}>РАБОЧЕЕ МЕСТО</p><h1>Новая покупка</h1><p>Введите код клиента и сумму — система сама рассчитает списание и кешбэк.</p></header>
    <form className={ui("sale-composer")} onSubmit={(event) => void openPreview(event)}>
      <section className={ui("sale-primary-fields")}>
        <div className={ui("sale-section-heading")}><span>1</span><div><h2>Клиент и сумма</h2><p>Шестизначный код клиент получает в своём Mini App.</p></div></div>
        <div className={ui("sale-input-grid")}>
          <label className={ui("sale-field")}><span>Код клиента</span><span className={ui("sale-control", buyerLookupState === "found" && "sale-control-found")}>
            <Icon name="code" size={19} />
            <input aria-label="Код клиента" inputMode="numeric" pattern="[0-9]*" maxLength={6} value={buyerCode} onChange={(event) => setBuyerCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" />
            {buyerLookupState === "loading" && <i className={ui("field-loader")} aria-label="Ищем клиента" />}
            {buyerLookupState === "found" && <i className={ui("field-status")}><Icon name="check" size={16} /></i>}
          </span></label>
          <label className={ui("sale-field")}><span>Сумма заказа</span><span className={ui("sale-control")}>
            <Icon name="sale" size={19} />
            <input className={ui("number-input")} aria-label="Сумма заказа" inputMode="decimal" type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" />
            <i className={ui("input-suffix")}><CurrencySymbol /></i>
          </span></label>
          {buyerLookupState === "not-found" && <p className={ui("customer-lookup-error")}><Icon name="close" size={15} />Код не найден, истёк или уже был использован.</p>}
          {buyer && <section className={ui("identified-customer")}>
            <span className={ui("identified-avatar")}>{buyer.customer_name.slice(0, 1).toUpperCase()}</span>
            <div className={ui("identified-copy")}><small>Клиент найден</small><strong>{buyer.customer_name}</strong><span>{buyer.customer_phone_masked} · с {formatDate(buyer.registered_at)}</span></div>
            <dl><div><dt>Баланс</dt><dd><Money value={buyer.current_balance} /></dd></div><div><dt>Кешбэк</dt><dd>{buyer.cashback_percent}%</dd></div></dl>
          </section>}
        </div>
      </section>
      <details ref={productPickerRef} className={ui("product-picker")} onToggle={(event) => setProductPickerOpen(event.currentTarget.open)}>
        <summary className={ui("product-picker-summary")}><span className={ui("product-picker-icon")}><Icon name="bag" size={18} /></span><span><strong>Добавить товары</strong><small>Необязательно, для истории заказа</small></span><em>{selectedProducts.length ? `${selectedProducts.length} выбрано` : "Опционально"}</em></summary>
        <div className={ui("product-picker-content")}>
          {selectedProducts.length > 0 && <ul className={ui("selected-products")}>{selectedProducts.map((product) => <li key={product.external_id}><span><b>{product.title}</b>{product.current_price && <small><Money value={product.current_price} /></small>}</span><button type="button" aria-label={`Убрать ${product.title}`} onClick={() => removeProduct(product.external_id)}><Icon name="close" size={17} /></button></li>)}</ul>}
          <div className={ui("product-combobox")}>
            <div className={ui("product-search")}><Icon name="search" size={18} /><input className={ui("form-control")} role="combobox" aria-autocomplete="list" aria-expanded={productPickerOpen} aria-controls="product-options" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Начните вводить название" />{searching && <span className={ui("field-loader")} aria-label="Поиск" />}</div>
            <div className={ui("product-dropdown")}>
              {availableProducts.length > 0
                ? <ul id="product-options" className={ui("product-results")} role="listbox">{availableProducts.map((product) => <li key={product.external_id}><button type="button" role="option" aria-selected={false} onClick={() => selectProduct(product)}><span><b>{product.title}</b><small>{product.external_id}{product.current_price && <> · <Money value={product.current_price} /></>}</small></span><Icon name="plus" size={18} /></button></li>)}</ul>
                : <div className={ui("product-empty")}>{searching ? "Загружаем товары…" : query.trim() ? "По вашему запросу ничего не найдено." : "В каталоге пока нет доступных товаров."}</div>}
            </div>
          </div>
        </div>
      </details>
      <button className={ui("primary-action", "sale-submit")} disabled={previewing || buyerLookupState === "loading" || buyerLookupState === "not-found"} type="submit">{previewing ? "Считаем бонусы…" : "Рассчитать заказ"}<Icon name="arrow" /></button>
    </form>
    {preview && <SaleConfirmation preview={preview} products={selectedProducts} onCancel={() => setPreview(null)} onConfirm={() => void recordSale()} recording={recording} />}
    {success && <SaleSuccess result={success} onClose={reset} />}
  </section>;
}

function SaleConfirmation({ preview, products, onCancel, onConfirm, recording }: {
  preview: SalePreview;
  products: Product[];
  onCancel: () => void;
  onConfirm: () => void;
  recording: boolean;
}) {
  const isBirthday = preview.cashback_source === "birthday";
  return <Modal title="Проверьте заказ" eyebrow="ПЕРЕД ПОДТВЕРЖДЕНИЕМ" onClose={onCancel}>
    <div className={ui("receipt-customer")}><span>{preview.customer_name.slice(0, 1).toUpperCase()}</span><div><strong>{preview.customer_name}</strong><small>{preview.customer_phone_masked} · баланс <Money value={preview.current_balance} /></small></div></div>
    <dl className={ui("receipt-totals")}><div><dt>Сумма заказа</dt><dd><Money value={preview.total_amount} /></dd></div><div><dt>Спишется бонусов</dt><dd className={ui("negative")}><Money prefix="−" value={preview.bonus_redeemed} /></dd></div><div className={ui("receipt-total")}><dt>К оплате</dt><dd><Money value={preview.cash_paid} /></dd></div><div className={ui("receipt-cashback")}><dt>{isBirthday ? "Кешбэк в дни рождения" : "Кешбэк по уровню"} <small>{preview.cashback_percent}%</small></dt><dd><Money prefix="+" value={preview.cashback_accrued} /></dd></div></dl>
    {products.length > 0 && <p className={ui("modal-product-summary")}><Icon name="bag" size={17} />{products.length === 1 ? products[0].title : `Выбрано товаров: ${products.length}`}</p>}
    <p className={ui("modal-warning")}>После подтверждения покупку нельзя изменить или отменить.</p>
    <div className={ui("split-actions")}><button className={ui("secondary-action")} type="button" onClick={onCancel}>Назад</button><button className={ui("primary-action")} disabled={recording} type="button" onClick={onConfirm}>{recording ? "Оформляем…" : "Подтвердить"}<Icon name="check" /></button></div>
  </Modal>;
}

function SaleSuccess({ result, onClose }: { result: SaleRecord; onClose: () => void }) {
  return <Modal title="Покупка оформлена" eyebrow="ВСЁ ГОТОВО" variant="success" onClose={onClose}>
    <section className={ui("success-hero")}>
      <div className={ui("success-seal")}><Icon name="check" size={32} /></div>
      <p className={ui("success-kicker")}>ОПЕРАЦИЯ ПРОШЛА УСПЕШНО</p>
      <h3>Баллы уже на счёте</h3>
      <p className={ui("success-copy")}>Покупка сохранена, а клиент получит подтверждение в Telegram.</p>
    </section>
    <dl className={ui("success-summary")}>
      <div><dt>Начислено</dt><dd><Money prefix="+" value={result.cashback_accrued} /></dd></div>
      <div><dt>Новый баланс</dt><dd><Money value={result.balance_after} /></dd></div>
    </dl>
    <p className={ui("success-note")}><Icon name="check" size={18} />Можно переходить к следующему клиенту.</p>
    <button className={ui("primary-action")} onClick={onClose}>Оформить следующую покупку<Icon name="arrow" /></button>
  </Modal>;
}
