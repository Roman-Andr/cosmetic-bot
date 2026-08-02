import { useCallback, useEffect, useId, useRef, type ReactNode } from "react";

import { getTelegramApp } from "../lib/telegram";
import { ui } from "./classes";
import { Icon } from "./Icon";

const PAGE_STATE_KEY = "__loyaltyPage";
let openPageCount = 0;

export function Modal({ title, eyebrow, children, onClose, variant = "default" }: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  onClose: () => void;
  variant?: "default" | "success";
}) {
  const titleId = useId();
  const pageId = useId();
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  const navigateBack = useCallback((): void => {
    if (window.history.state?.[PAGE_STATE_KEY] === pageId) window.history.back();
    else onCloseRef.current();
  }, [pageId]);

  useEffect(() => {
    const previousState = window.history.state;
    const previousUrl = window.location.href;
    const telegramBackButton = getTelegramApp()?.BackButton;
    const closeFromHistory = (): void => onCloseRef.current();
    const closeOnEscape = (event: KeyboardEvent): void => {
      if (event.key === "Escape") navigateBack();
    };

    window.history.pushState(
      { ...(previousState ?? {}), [PAGE_STATE_KEY]: pageId },
      "",
      previousUrl,
    );
    openPageCount += 1;
    telegramBackButton?.show();
    telegramBackButton?.onClick(navigateBack);
    window.addEventListener("popstate", closeFromHistory);
    document.addEventListener("keydown", closeOnEscape);
    document.body.classList.add("modal-open");
    return () => {
      window.removeEventListener("popstate", closeFromHistory);
      document.removeEventListener("keydown", closeOnEscape);
      telegramBackButton?.offClick(navigateBack);
      openPageCount = Math.max(0, openPageCount - 1);
      if (openPageCount === 0) {
        telegramBackButton?.hide();
        document.body.classList.remove("modal-open");
      }
      if (window.history.state?.[PAGE_STATE_KEY] === pageId) {
        window.history.replaceState(previousState, "", previousUrl);
      }
    };
  }, [navigateBack, pageId]);

  const variantClasses = { default: ui("modal-sheet"), success: ui("modal-sheet") } as const;

  return <div className={ui("modal-backdrop")} role="presentation">
    <section className={variantClasses[variant]} role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className={ui("modal-topline")}>
        <button className={ui("icon-button", "modal-close")} type="button" aria-label="Назад" onClick={navigateBack}><Icon name="back" /></button>
        <div>{eyebrow && <p className={ui("overline")} data-overline>{eyebrow}</p>}<h2 id={titleId}>{title}</h2></div>
      </div>
      <div className={ui("modal-page-content")}>{children}</div>
    </section>
  </div>;
}
