import { useState } from "react";

import { api } from "../../../shared/api/client";
import { errorMessage, formatTime } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";

interface LoyaltyCode { code: string; expires_at: string; }

export function LoyaltyCodeModal({ onClose, onNotice }: { onClose: () => void; onNotice: (value: string | null) => void }) {
  const [code, setCode] = useState<LoyaltyCode | null>(null);
  const [loading, setLoading] = useState(false);

  const getCode = async (): Promise<void> => {
    setLoading(true);
    try {
      setCode(await api.post<LoyaltyCode>("/loyalty/code"));
      haptic("success");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
    finally { setLoading(false); }
  };

  return <Modal title="Код для покупки" eyebrow="VELINA CLUB" onClose={onClose}>
    <section className={`code-modal-hero${code ? " ready" : ""}`}>
      <span><Icon name={code ? "check" : "code"} size={24} /></span>
      <div><strong>{code ? "Код готов" : "Покажите код на кассе"}</strong><p>{code ? "Он привязан только к вашему бонусному счёту." : "Администратор использует его для расчёта скидки и кешбэка."}</p></div>
    </section>
    {code ? <section className="code-display">
      <output>{code.code}</output>
      <p>Действует до <b>{formatTime(code.expires_at)}</b>. После использования или через час код станет недействительным.</p>
    </section> : <ul className="code-rules">
      <li><Icon name="check" size={16} /><span>Бонусы спишутся автоматически — до 10% от заказа.</span></li>
      <li><Icon name="check" size={16} /><span>Кешбэк вернётся на баланс сразу после покупки.</span></li>
    </ul>}
    <button className="primary-action" disabled={loading} onClick={() => void getCode()}>{loading ? "Готовим код…" : code ? "Получить новый код" : "Получить код"}<Icon name="arrow" /></button>
  </Modal>;
}
