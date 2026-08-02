import { useState, type FormEvent } from "react";

import { useAddAdministratorMutation } from "../../../entities/admin/api/mutations";
import { useAdministratorsQuery } from "../../../entities/admin/api/queries";
import { errorMessage } from "../../../shared/lib/format";
import { haptic } from "../../../shared/lib/telegram";
import { useErrorNotice } from "../../../shared/lib/useErrorNotice";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { ui } from "../../../shared/ui/classes";

interface AdministratorsModalProps {
  onClose: () => void;
  onNotice: NoticeHandler;
}

export function AdministratorsModal({ onClose, onNotice }: AdministratorsModalProps) {
  const [telegramId, setTelegramId] = useState("");
  const administratorsQuery = useAdministratorsQuery();
  const addAdministratorMutation = useAddAdministratorMutation();
  const administrators = administratorsQuery.data;

  useErrorNotice(onNotice, administratorsQuery.error);

  const add = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!/^\d+$/.test(telegramId)) { onNotice("Введите числовой Telegram ID."); return; }
    try {
      await addAdministratorMutation.mutateAsync(Number(telegramId));
      setTelegramId("");
      haptic("success");
      onNotice("Sales-администратор добавлен.", "success");
    } catch (error) { haptic("error"); onNotice(errorMessage(error)); }
  };

  return <Modal title="Команда" eyebrow="ДОСТУП К ПРОДАЖАМ" onClose={onClose}>
    <p className={ui("muted")}>Sales-администратор может оформлять покупки в боте и Mini App, но не видит данные клиентов и настройки.</p>
    <form className={ui("administrator-form")} onSubmit={(event) => void add(event)}><label className={ui("admin-search-field")}><Icon name="account" size={18} /><input className={ui("form-control")} aria-label="Telegram ID" inputMode="numeric" value={telegramId} onChange={(event) => setTelegramId(event.target.value.replace(/\D/g, ""))} placeholder="Telegram ID" /></label><button className={ui("primary-action", "auto-action")} disabled={addAdministratorMutation.isPending}>{addAdministratorMutation.isPending ? "Добавляем…" : "Добавить"}<Icon name="plus" /></button></form>
    <ul className={ui("administrator-list")}>{administrators?.map((admin) => <li key={admin.telegram_user_id}><span className={admin.role === "owner" ? ui("role-dot-owner") : ui("role-dot-sales")} /><div><strong>{admin.role === "owner" ? "Главный администратор" : "Sales-администратор"}</strong><small>{admin.telegram_user_id}</small></div><em>{admin.is_active ? "Активен" : "Выключен"}</em></li>)}</ul>
  </Modal>;
}
