import { useCallback, useEffect, useRef, useState } from "react";

import { useIssueLoyaltyCodeMutation } from "../../../entities/loyalty/api/mutations";
import { errorMessage, formatTime } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { ui } from "../../../shared/ui/classes";

export function LoyaltyCodeModal({ onClose, onNotice }: { onClose: () => void; onNotice: NoticeHandler }) {
  const [copied, setCopied] = useState(false);
  const requested = useRef(false);
  const issueCode = useIssueLoyaltyCodeMutation();
  const { data: code, isPending: loading, mutate } = issueCode;

  const getCode = useCallback((): void => {
    setCopied(false);
    mutate(undefined, {
      onSuccess: () => haptic("success"),
      onError: (error) => { haptic("error"); onNotice(errorMessage(error)); },
    });
  }, [mutate, onNotice]);

  useEffect(() => {
    if (requested.current) return;
    requested.current = true;
    getCode();
  }, [getCode]);

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
    <p className={ui("code-modal-copy")}>Покажите этот код администратору перед оплатой. Бонусы и кешбэк рассчитаются автоматически.</p>
    {loading ? <div className={ui("code-loading")}><span className={ui("loader")} />Готовим ваш код…</div> : code ? <section className={ui("code-sheet")}>
      <div className={ui("code-value")}><output>{code.code}</output><button className={ui("copy-code", copied && "copy-code-copied")} type="button" onClick={() => void copyCode()} aria-label="Скопировать код">{copied ? <Icon name="check" size={20} /> : <Icon name="copy" size={20} />}</button></div>
      <p>Код действует до <b>{formatTime(code.expires_at)}</b> и используется один раз.</p>
      <button className={ui("text-action")} type="button" onClick={getCode}>Обновить код <Icon name="arrow" size={16} /></button>
    </section> : <button className={ui("primary-action")} type="button" onClick={getCode}>Получить код <Icon name="arrow" /></button>}
  </Modal>;
}
