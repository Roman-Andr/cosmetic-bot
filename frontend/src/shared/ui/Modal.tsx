import { useEffect, useId, type ReactNode } from "react";

import { Icon } from "./Icon";

export function Modal({ title, eyebrow, children, onClose, variant = "default" }: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  onClose: () => void;
  variant?: "default" | "success";
}) {
  const titleId = useId();
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", closeOnEscape);
    document.body.classList.add("modal-open");
    return () => { document.removeEventListener("keydown", closeOnEscape); document.body.classList.remove("modal-open"); };
  }, [onClose]);

  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
    <section className={`modal-sheet modal-${variant}`} role="dialog" aria-modal="true" aria-labelledby={titleId} onMouseDown={(event) => event.stopPropagation()}>
      <span className="modal-handle" aria-hidden="true" />
      <div className="modal-topline">
        <div>{eyebrow && <p className="overline">{eyebrow}</p>}<h2 id={titleId}>{title}</h2></div>
        <button className="icon-button modal-close" type="button" aria-label="Закрыть" onClick={onClose}><Icon name="close" /></button>
      </div>
      {children}
    </section>
  </div>;
}
