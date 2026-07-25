import { useState } from "react";

import { api } from "../../../shared/api/client";
import { errorMessage, formatTime } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";

interface LoyaltyCode { code: string; expires_at: string; }

export function LoyaltyCodeCard({ onNotice }: { onNotice: (value: string | null) => void }) {
  const [code, setCode] = useState<LoyaltyCode | null>(null);
  const [showInfo, setShowInfo] = useState(false);
  const [loading, setLoading] = useState(false);

  const getCode = async (): Promise<void> => {
    setLoading(true);
    try {
      setCode(await api.post<LoyaltyCode>("/loyalty/code"));
      haptic("success");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
    finally { setLoading(false); }
  };

  return <>
    <section className="panel code-panel">
      <div className="panel-heading"><div><p className="overline">ПОКУПКА В МАГАЗИНЕ</p><h2>Ваш временный код</h2></div><span className="soft-icon"><Icon name="code" /></span></div>
      {code ? <div className="code-result"><output className="code">{code.code}</output><p>Покажите его администратору до <b>{formatTime(code.expires_at)}</b>. Код действует один час.</p></div> : <p className="muted">Код нужен, чтобы начислить бонусы и автоматически списать до 10% от суммы покупки.</p>}
      <div className="inline-actions"><button className="primary-action" disabled={loading} onClick={() => void getCode()}>{loading ? "Готовим код…" : code ? "Получить новый" : "Получить код"}<Icon name="arrow" /></button><button className="icon-button" type="button" aria-label="Как работает код" onClick={() => setShowInfo(true)}><span>?</span></button></div>
    </section>
    {showInfo && <Modal title="Как работает код" eyebrow="ПРОСТО И БЕЗОПАСНО" onClose={() => setShowInfo(false)}><div className="modal-copy"><p>Покажите шестизначный код администратору при покупке.</p><ol className="step-list"><li><i>1</i><span>Код действует 60 минут и используется только один раз.</span></li><li><i>2</i><span>Бонусы спишутся автоматически, но не больше 10% заказа.</span></li><li><i>3</i><span>Кешбэк поступит на баланс сразу после оформления.</span></li></ol></div><button className="primary-action" onClick={() => setShowInfo(false)}>Понятно</button></Modal>}
  </>;
}
