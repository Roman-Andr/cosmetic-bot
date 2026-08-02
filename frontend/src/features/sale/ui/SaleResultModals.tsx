import type { SalePreview, SaleRecord } from "../../../entities/admin/model/types";
import type { Product } from "../../../entities/catalog/model/types";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";
import { ui } from "../../../shared/ui/classes";

interface SaleConfirmationProps {
  preview: SalePreview;
  products: Product[];
  onCancel: () => void;
  onConfirm: () => void;
  recording: boolean;
}

export function SaleConfirmation({
  preview,
  products,
  onCancel,
  onConfirm,
  recording,
}: SaleConfirmationProps) {
  const isBirthday = preview.cashback_source === "birthday";
  return <Modal title="Проверьте заказ" eyebrow="ПЕРЕД ПОДТВЕРЖДЕНИЕМ" onClose={onCancel}>
    <div className={ui("receipt-customer")}><span>{preview.customer_name.slice(0, 1).toUpperCase()}</span><div><strong>{preview.customer_name}</strong><small>{preview.customer_phone_masked} · баланс <Money value={preview.current_balance} /></small></div></div>
    <dl className={ui("receipt-totals")}><div><dt>Сумма заказа</dt><dd><Money value={preview.total_amount} /></dd></div><div><dt>Спишется бонусов</dt><dd className={ui("negative")}><Money prefix="−" value={preview.bonus_redeemed} /></dd></div><div className={ui("receipt-total")}><dt>К оплате</dt><dd><Money value={preview.cash_paid} /></dd></div><div className={ui("receipt-cashback")}><dt>{isBirthday ? "Кешбэк в дни рождения" : "Кешбэк по уровню"} <small>{preview.cashback_percent}%</small></dt><dd><Money prefix="+" value={preview.cashback_accrued} /></dd></div></dl>
    {products.length > 0 && <p className={ui("modal-product-summary")}><Icon name="bag" size={17} />{products.length === 1 ? products[0].title : `Выбрано товаров: ${products.length}`}</p>}
    <p className={ui("modal-warning")}>После подтверждения покупку нельзя изменить или отменить.</p>
    <div className={ui("split-actions")}><button className={ui("secondary-action")} type="button" onClick={onCancel}>Назад</button><button className={ui("primary-action")} disabled={recording} type="button" onClick={onConfirm}>{recording ? "Оформляем…" : "Подтвердить"}<Icon name="check" /></button></div>
  </Modal>;
}

export function SaleSuccess({ result, onClose }: { result: SaleRecord; onClose: () => void }) {
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
