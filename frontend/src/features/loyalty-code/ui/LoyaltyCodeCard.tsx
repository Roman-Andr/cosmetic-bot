import { useCallback, useEffect, useState } from "react";

import { api } from "../../../shared/api/client";
import { errorMessage, formatTime } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";

interface LoyaltyCode { code: string; expires_at: string; }

export function LoyaltyCodeModal({ onClose, onNotice }: { onClose: () => void; onNotice: NoticeHandler }) {
  const [code, setCode] = useState<LoyaltyCode | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  const getCode = useCallback(async (): Promise<void> => {
    setLoading(true);
    setCopied(false);
    try {
      setCode(await api.post<LoyaltyCode>("/loyalty/code"));
      haptic("success");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
    finally { setLoading(false); }
  }, [onNotice]);

  useEffect(() => { void getCode(); }, [getCode]);

  const copyCode = async (): Promise<void> => {
    if (!code) return;
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(code.code);
      else {
        const field = document.createElement("textarea");
        field.value = code.code;
        field.style.position = "fixed";
        field.style.opacity = "0";
        document.body.append(field);
        field.select();
        const didCopy = document.execCommand("copy");
        field.remove();
        if (!didCopy) throw new Error("Не удалось скопировать код.");
      }
      setCopied(true);
      haptic("success");
      window.setTimeout(() => setCopied(false), 1800);
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
  };

  return <Modal title="Код для покупки" eyebrow="ВАШ КЕШБЭК" onClose={onClose}>
    <p className="code-modal-copy">Покажите этот код администратору перед оплатой. Бонусы и кешбэк рассчитаются автоматически.</p>
    {loading ? <div className="code-loading"><span className="loader" />Готовим ваш код…</div> : code ? <section className="code-sheet">
      <div className="code-value"><output>{code.code}</output><button className={`copy-code${copied ? " copied" : ""}`} type="button" onClick={() => void copyCode()} aria-label="Скопировать код">{copied ? <Icon name="check" size={20} /> : <Icon name="copy" size={20} />}</button></div>
      <p>Код действует до <b>{formatTime(code.expires_at)}</b> и используется один раз.</p>
      <button className="text-action" type="button" onClick={() => void getCode()}>Обновить код <Icon name="arrow" size={16} /></button>
    </section> : <button className="primary-action" type="button" onClick={() => void getCode()}>Получить код <Icon name="arrow" /></button>}
  </Modal>;
}
