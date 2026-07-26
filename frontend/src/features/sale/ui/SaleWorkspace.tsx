import { useEffect, useRef, useState, type FormEvent } from "react";

import type { Product, SalePreview, SaleRecord } from "../../../entities/loyalty/model/types";
import { api } from "../../../shared/api/client";
import { errorMessage } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { CurrencySymbol, Money } from "../../../shared/ui/Money";

export function SaleWorkspace({ onNotice }: { onNotice: (value: string | null) => void }) {
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
  const productRequestId = useRef(0);
  const productPickerRef = useRef<HTMLDetailsElement>(null);

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
    setBuyerCode(""); setAmount(""); setQuery(""); setProducts([]); setSelectedProducts([]); setSuccess(null);
    if (productPickerRef.current) productPickerRef.current.open = false;
    setProductPickerOpen(false);
  };
  const availableProducts = products.filter((product) => !selectedProducts.some((selected) => selected.external_id === product.external_id));

  return <section className="sales-workspace">
    <header className="workspace-heading"><p className="eyebrow">РАБОЧЕЕ МЕСТО</p><h1>Новая покупка</h1><p>Введите код клиента и сумму — система сама рассчитает списание и кешбэк.</p></header>
    <form className="sale-composer" onSubmit={(event) => void openPreview(event)}>
      <section className="sale-primary-fields">
        <div className="sale-section-heading"><span>1</span><div><h2>Клиент и сумма</h2><p>Шестизначный код клиент получает в своём Mini App.</p></div></div>
        <div className="sale-input-grid"><label>Код клиента<input inputMode="numeric" pattern="[0-9]*" maxLength={6} value={buyerCode} onChange={(event) => setBuyerCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" /></label><label>Сумма заказа<input inputMode="decimal" type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" /><span className="input-suffix"><CurrencySymbol /></span></label></div>
      </section>
      <details ref={productPickerRef} className="product-picker" onToggle={(event) => setProductPickerOpen(event.currentTarget.open)}>
        <summary><span className="product-picker-icon"><Icon name="bag" size={18} /></span><span><strong>Добавить товары</strong><small>Необязательно, для истории заказа</small></span><em>{selectedProducts.length ? `${selectedProducts.length} выбрано` : "Опционально"}</em></summary>
        <div className="product-picker-content">
          {selectedProducts.length > 0 && <ul className="selected-products">{selectedProducts.map((product) => <li key={product.external_id}><span><b>{product.title}</b>{product.current_price && <small><Money value={product.current_price} /></small>}</span><button type="button" aria-label={`Убрать ${product.title}`} onClick={() => removeProduct(product.external_id)}><Icon name="close" size={17} /></button></li>)}</ul>}
          <div className="product-combobox">
            <div className="product-search"><Icon name="search" size={18} /><input role="combobox" aria-autocomplete="list" aria-expanded={productPickerOpen} aria-controls="product-options" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Начните вводить название" />{searching && <span className="field-loader" aria-label="Поиск" />}</div>
            <div className="product-dropdown">
              {availableProducts.length > 0
                ? <ul id="product-options" className="product-results" role="listbox">{availableProducts.map((product) => <li key={product.external_id}><button type="button" role="option" aria-selected={false} onClick={() => selectProduct(product)}><span><b>{product.title}</b><small>{product.external_id}{product.current_price && <> · <Money value={product.current_price} /></>}</small></span><Icon name="plus" size={18} /></button></li>)}</ul>
                : <div className="product-empty">{searching ? "Загружаем товары…" : query.trim() ? "По вашему запросу ничего не найдено." : "В каталоге пока нет доступных товаров."}</div>}
            </div>
          </div>
        </div>
      </details>
      <button className="primary-action sale-submit" disabled={previewing} type="submit">{previewing ? "Считаем бонусы…" : "Рассчитать заказ"}<Icon name="arrow" /></button>
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
    <div className="receipt-customer"><span>{preview.customer_name.slice(0, 1).toUpperCase()}</span><div><strong>{preview.customer_name}</strong><small>{preview.customer_phone_masked} · баланс <Money value={preview.current_balance} /></small></div></div>
    <dl className="receipt-totals"><div><dt>Сумма заказа</dt><dd><Money value={preview.total_amount} /></dd></div><div><dt>Спишется бонусов</dt><dd className="negative"><Money prefix="−" value={preview.bonus_redeemed} /></dd></div><div className="receipt-total"><dt>К оплате</dt><dd><Money value={preview.cash_paid} /></dd></div><div className="receipt-cashback"><dt>{isBirthday ? "Кешбэк в дни рождения" : "Кешбэк по уровню"} <small>{preview.cashback_percent}%</small></dt><dd><Money prefix="+" value={preview.cashback_accrued} /></dd></div></dl>
    {products.length > 0 && <p className="modal-product-summary"><Icon name="bag" size={17} />{products.length === 1 ? products[0].title : `Выбрано товаров: ${products.length}`}</p>}
    <p className="modal-warning">После подтверждения покупку нельзя изменить или отменить.</p>
    <div className="split-actions"><button className="secondary-action" type="button" onClick={onCancel}>Назад</button><button className="primary-action" disabled={recording} type="button" onClick={onConfirm}>{recording ? "Оформляем…" : "Подтвердить"}<Icon name="check" /></button></div>
  </Modal>;
}

function SaleSuccess({ result, onClose }: { result: SaleRecord; onClose: () => void }) {
  return <Modal title="Покупка оформлена" eyebrow="ВСЁ ГОТОВО" variant="success" onClose={onClose}>
    <div className="success-seal"><Icon name="check" size={28} /></div>
    <p className="success-copy">Кешбэк <b><Money value={result.cashback_accrued} /></b> начислен. Клиент получит уведомление в Telegram.</p>
    <div className="success-balance"><span>Баланс клиента теперь</span><strong><Money value={result.balance_after} /></strong></div>
    <button className="primary-action" onClick={onClose}>Оформить следующую покупку<Icon name="arrow" /></button>
  </Modal>;
}
