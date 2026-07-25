import { useEffect, type ReactNode } from "react";

import { Icon } from "./Icon";

export function Modal({ title, eyebrow, children, onClose, variant = "default" }: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  onClose: () => void;
  variant?: "default" | "success";
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", closeOnEscape);
    document.body.classList.add("modal-open");
    return () => { document.removeEventListener("keydown", closeOnEscape); document.body.classList.remove("modal-open"); };
  }, [onClose]);

  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
    <section className={`modal-card modal-${variant}`} role="dialog" aria-modal="true" aria-labelledby="modal-title" onMouseDown={(event) => event.stopPropagation()}>
      <div className="modal-topline">
        <div>{eyebrow && <p className="overline">{eyebrow}</p>}<h2 id="modal-title">{title}</h2></div>
        <button className="icon-button modal-close" type="button" aria-label="Закрыть" onClick={onClose}><Icon name="close" /></button>
      </div>
      {children}
    </section>
  </div>;
}
