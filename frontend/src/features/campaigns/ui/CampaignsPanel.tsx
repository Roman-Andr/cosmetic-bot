import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";

import {
  useCampaignPreviewMutation,
  useCancelCampaignMutation,
  useCreateCampaignMutation,
  useUploadCampaignPhotoMutation,
} from "../../../entities/admin/api/mutations";
import { useCampaignsQuery } from "../../../entities/admin/api/queries";
import type {
  Campaign,
  CampaignInput,
  CampaignPreview,
  CampaignStatus,
} from "../../../entities/admin/model/types";
import {
  errorMessage,
  formatCalendarDate,
  formatDateTime,
  minskDateTimeParts,
} from "../../../shared/lib/format";
import { imageToJpegBase64 } from "../../../shared/lib/image";
import { haptic } from "../../../shared/lib/telegram";
import { useErrorNotice } from "../../../shared/lib/useErrorNotice";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { Modal } from "../../../shared/ui/Modal";
import { Money } from "../../../shared/ui/Money";
import { ui, type UiClass } from "../../../shared/ui/classes";

const TEXT_LIMIT = 4096;
const CAPTION_LIMIT = 1024;
const MAX_GIFT = 1000;
// Belarus has stayed on UTC+3 all year round since 2011.
const MINSK_OFFSET = "+03:00";

const statusLabels: Record<CampaignStatus, string> = {
  scheduled: "Запланирована",
  completed: "Отправлена",
  cancelled: "Отменена",
};

const statusClasses: Record<CampaignStatus, UiClass> = {
  scheduled: "campaign-status-scheduled",
  completed: "campaign-status-completed",
  cancelled: "campaign-status-cancelled",
};

type StartMode = "now" | "scheduled";

interface CampaignForm {
  title: string;
  message: string;
  bonus: string;
  validUntil: string;
  startMode: StartMode;
  startAt: string;
}

const emptyForm: CampaignForm = {
  title: "",
  message: "",
  bonus: "0",
  validUntil: "",
  startMode: "now",
  startAt: "",
};

function tomorrowMorning(): string {
  const tomorrow = minskDateTimeParts(new Date(Date.now() + 24 * 60 * 60 * 1000));
  return `${tomorrow.date}T10:00`;
}

function scheduledInstant(startAt: string): string {
  return `${startAt}:00${MINSK_OFFSET}`;
}

export function CampaignsPanel({ onNotice }: { onNotice: NoticeHandler }) {
  const campaignsQuery = useCampaignsQuery();
  const [composing, setComposing] = useState(false);
  const campaigns = campaignsQuery.data?.items ?? [];
  const audienceSize = campaignsQuery.data?.audience_size ?? 0;

  useErrorNotice(onNotice, campaignsQuery.error);

  return <div className={ui("owner-view")}>
    <section className={ui("owner-card")}>
      <div className={ui("view-heading")}><div><p className={ui("overline")} data-overline>АКЦИИ И РАССЫЛКИ</p><h2>Порадуйте клиентов</h2><p>Сообщение всем участникам программы и, по желанию, подарочные бонусы со своим сроком действия. Получателей сейчас: {audienceSize}.</p></div><span className={ui("soft-icon")}><Icon name="sparkle" /></span></div>
      <button className={ui("primary-action")} type="button" onClick={() => { haptic(); setComposing(true); }}>Новая акция<Icon name="plus" /></button>
    </section>

    <section className={ui("owner-card")}>
      <div className={ui("view-heading")}><div><p className={ui("overline")} data-overline>ИСТОРИЯ</p><h2>Акции</h2><p>Запланированную акцию можно отменить до старта.</p></div></div>
      {campaignsQuery.isPending ? <div className={ui("modal-loader")}><span className={ui("loader")} />Загружаем акции…</div>
        : campaigns.length === 0 ? <div className={ui("empty-state", "compact-empty")}><span><Icon name="gift" /></span><h3>Акций пока нет</h3><p>Создайте первую — например, подарок ко Дню матери.</p></div>
        : <ul className={ui("campaign-list")}>{campaigns.map((campaign) => <CampaignCard key={campaign.id} campaign={campaign} onNotice={onNotice} />)}</ul>}
    </section>

    {composing && <CampaignComposer onClose={() => setComposing(false)} onNotice={onNotice} />}
  </div>;
}

function CampaignCard({ campaign, onNotice }: { campaign: Campaign; onNotice: NoticeHandler }) {
  const cancelMutation = useCancelCampaignMutation();
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const hasBonus = Number(campaign.bonus_amount) > 0 && campaign.bonus_valid_until !== null;

  const cancel = async (): Promise<void> => {
    try {
      await cancelMutation.mutateAsync(campaign.id);
      haptic("success");
      onNotice("Акция отменена.", "success");
    } catch (error) {
      haptic("error");
      onNotice(errorMessage(error));
    } finally {
      setConfirmingCancel(false);
    }
  };

  const timing = campaign.status === "completed" && campaign.launched_at
    ? `Отправлена ${formatDateTime(campaign.launched_at)}`
    : campaign.status === "cancelled" && campaign.cancelled_at
      ? `Отменена ${formatDateTime(campaign.cancelled_at)}`
      : `Старт ${formatDateTime(campaign.starts_at)}`;

  return <li className={ui("campaign-card")}>
    <header><h3>{campaign.title}</h3><span className={ui("campaign-status", statusClasses[campaign.status])}>{statusLabels[campaign.status]}</span></header>
    <ul className={ui("campaign-meta")}>
      <li><Icon name="clock" size={16} />{timing}</li>
      <li><Icon name="gift" size={16} />{hasBonus && campaign.bonus_valid_until ? <span><Money value={campaign.bonus_amount} /> каждому · до {formatCalendarDate(campaign.bonus_valid_until)} включительно</span> : "Без бонусов — только сообщение"}</li>
      {campaign.recipients_count !== null && <li><Icon name="account" size={16} />Получателей: {campaign.recipients_count}</li>}
      {campaign.has_photo && <li><Icon name="image" size={16} />С картинкой</li>}
    </ul>
    <div className={ui("campaign-message")}><p>{campaign.message_text}</p></div>
    {campaign.status === "scheduled" && (confirmingCancel
      ? <div className={ui("split-actions")}><button className={ui("secondary-action")} type="button" onClick={() => setConfirmingCancel(false)}>Не отменять</button><button className={ui("primary-action")} type="button" disabled={cancelMutation.isPending} onClick={() => void cancel()}>{cancelMutation.isPending ? "Отменяем…" : "Отменить акцию"}</button></div>
      : <button className={ui("secondary-action")} type="button" onClick={() => setConfirmingCancel(true)}>Отменить</button>)}
  </li>;
}

function CampaignComposer({ onClose, onNotice }: { onClose: () => void; onNotice: NoticeHandler }) {
  const [form, setForm] = useState<CampaignForm>(emptyForm);
  const [photo, setPhoto] = useState<{ fileId: string; previewUrl: string } | null>(null);
  const [preview, setPreview] = useState<CampaignPreview | null>(null);
  const uploadMutation = useUploadCampaignPhotoMutation();
  const previewMutation = useCampaignPreviewMutation();
  const createMutation = useCreateCampaignMutation();
  const hasBonus = Number(form.bonus) > 0;
  const limit = photo ? CAPTION_LIMIT : TEXT_LIMIT;
  const today = minskDateTimeParts(new Date());
  const startDate = form.startMode === "scheduled" && form.startAt ? form.startAt.slice(0, 10) : today.date;

  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.previewUrl); }, [photo]);

  const update = (changes: Partial<CampaignForm>): void => {
    setForm((current) => ({ ...current, ...changes }));
  };

  const pickPhoto = async (event: ChangeEvent<HTMLInputElement>): Promise<void> => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const uploaded = await uploadMutation.mutateAsync(await imageToJpegBase64(file));
      setPhoto({ fileId: uploaded.photo_file_id, previewUrl: URL.createObjectURL(file) });
      haptic("success");
      onNotice("Картинка загружена — бот прислал её вам в чат для проверки.", "success");
    } catch (error) {
      haptic("error");
      onNotice(errorMessage(error));
    }
  };

  // "Start now" is stamped on every request so a slow review never lands in the past.
  const payload = (): CampaignInput => ({
    title: form.title.trim(),
    message_text: form.message.trim(),
    photo_file_id: photo?.fileId ?? null,
    bonus_amount: hasBonus ? Number(form.bonus).toFixed(2) : "0",
    bonus_valid_until: hasBonus ? form.validUntil : null,
    starts_at: form.startMode === "now" ? new Date().toISOString() : scheduledInstant(form.startAt),
  });

  const problem = (): string | null => {
    const bonus = Number(form.bonus);
    if (form.title.trim().length < 2) return "Укажите название акции.";
    if (!form.message.trim()) return "Напишите текст сообщения.";
    if (form.message.trim().length > limit) return `Сократите текст до ${limit} символов.`;
    if (!Number.isFinite(bonus) || bonus < 0 || bonus > MAX_GIFT) return `Подарочные бонусы — от 0 до ${MAX_GIFT}.`;
    if (hasBonus && !form.validUntil) return "Укажите, до какого дня действуют бонусы.";
    if (form.startMode === "scheduled" && !form.startAt) return "Укажите дату и время старта.";
    return null;
  };

  const review = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    const issue = problem();
    if (issue) { haptic("error"); onNotice(issue); return; }
    try {
      setPreview(await previewMutation.mutateAsync(payload()));
      haptic();
    } catch (error) {
      haptic("error");
      onNotice(errorMessage(error));
    }
  };

  const launch = async (): Promise<void> => {
    try {
      await createMutation.mutateAsync(payload());
      haptic("success");
      onNotice(form.startMode === "now" ? "Акция запущена — рассылка начнётся в течение минуты." : "Акция запланирована.", "success");
      onClose();
    } catch (error) {
      haptic("error");
      onNotice(errorMessage(error));
    }
  };

  return <><Modal title="Новая акция" eyebrow="АКЦИИ И РАССЫЛКИ" onClose={onClose}>
    <form className={ui("form")} onSubmit={(event) => void review(event)}>
      <label>Название акции<input className={ui("form-control")} maxLength={100} value={form.title} placeholder="День матери" onChange={(event) => update({ title: event.target.value })} /><span className={ui("field-hint")}>Клиенты увидят его в истории бонусов.</span></label>

      <label>Текст сообщения<textarea className={ui("form-control", "form-textarea")} value={form.message} placeholder="Дорогие мамы, поздравляем вас с праздником!" onChange={(event) => update({ message: event.target.value })} /><span className={ui(form.message.trim().length > limit ? "field-error" : "field-hint")}>{form.message.trim().length} / {limit}{hasBonus ? " · сумму и срок подарка бот допишет сам" : ""}</span></label>

      <div className={ui("field-group")}>
        <span>Картинка — необязательно</span>
        {photo
          ? <div className={ui("photo-preview")}><img src={photo.previewUrl} alt="Картинка акции" /><button className={ui("icon-button")} type="button" aria-label="Убрать картинку" onClick={() => setPhoto(null)}><Icon name="close" size={18} /></button></div>
          : <label className={ui("photo-picker-button")}><input className={ui("visually-hidden")} type="file" accept="image/jpeg,image/png,image/webp" disabled={uploadMutation.isPending} onChange={(event) => void pickPhoto(event)} />{uploadMutation.isPending ? <><span className={ui("loader")} />Загружаем…</> : <><Icon name="image" size={18} />Добавить картинку</>}</label>}
        <span className={ui("field-hint")}>С картинкой Telegram ограничивает текст 1024 символами.</span>
      </div>

      <div className={ui("form-grid")}>
        <label>Подарочные бонусы<input className={ui("form-control", "number-input")} type="number" inputMode="decimal" min="0" max={MAX_GIFT} step="0.01" value={form.bonus} onChange={(event) => update({ bonus: event.target.value })} /><span className={ui("field-hint")}>0 — просто сообщение без бонусов.</span></label>
        {hasBonus && <label>Действуют до (включительно)<input className={ui("form-control")} type="date" min={startDate} value={form.validUntil} onChange={(event) => update({ validUntil: event.target.value })} /><span className={ui("field-hint")}>В полночь после этой даты остаток сгорит.</span></label>}
      </div>

      <div className={ui("field-group")}>
        <span>Старт акции</span>
        <div className={ui("segmented")} role="group" aria-label="Старт акции">
          <button type="button" aria-pressed={form.startMode === "now"} onClick={() => update({ startMode: "now" })}>Сразу</button>
          <button type="button" aria-pressed={form.startMode === "scheduled"} onClick={() => update({ startMode: "scheduled", startAt: form.startAt || tomorrowMorning() })}>Запланировать</button>
        </div>
        {form.startMode === "scheduled" && <label>Дата и время по Минску<input className={ui("form-control")} type="datetime-local" min={`${today.date}T${today.time}`} value={form.startAt} onChange={(event) => update({ startAt: event.target.value })} /></label>}
      </div>

      <button className={ui("primary-action")} type="submit" disabled={previewMutation.isPending || uploadMutation.isPending}>{previewMutation.isPending ? "Проверяем…" : "Проверить и запустить"}<Icon name="arrow" /></button>
    </form>
  </Modal>
  {preview && <Modal title="Проверьте акцию" eyebrow="ПЕРЕД ЗАПУСКОМ" onClose={() => setPreview(null)}>
    <section className={ui("campaign-preview")}>
      {photo && <img src={photo.previewUrl} alt="Картинка акции" />}
      <p className={ui("campaign-message-full")}>{preview.message_text}</p>
    </section>
    <dl className={ui("receipt-totals")}>
      <div><dt>Получателей</dt><dd>{preview.audience_size}</dd></div>
      {hasBonus && <div><dt>Подарок каждому</dt><dd><Money value={form.bonus} /></dd></div>}
      {hasBonus && <div><dt>Всего бонусов</dt><dd><Money value={preview.total_bonus} /></dd></div>}
      {hasBonus && <div><dt>Действуют до</dt><dd>{formatCalendarDate(form.validUntil)} включительно</dd></div>}
      <div><dt>Старт</dt><dd>{form.startMode === "now" ? "Сразу после подтверждения" : formatDateTime(scheduledInstant(form.startAt))}</dd></div>
    </dl>
    <p className={ui("modal-warning")}>{hasBonus ? "После старта бонусы сразу начисляются всем клиентам — отменить их будет нельзя." : "После старта сообщение уйдёт всем клиентам — отменить рассылку будет нельзя."}</p>
    <div className={ui("split-actions")}>
      <button className={ui("secondary-action")} type="button" onClick={() => setPreview(null)}>Изменить</button>
      <button className={ui("primary-action")} type="button" disabled={createMutation.isPending} onClick={() => void launch()}>{createMutation.isPending ? "Сохраняем…" : form.startMode === "now" ? "Запустить" : "Запланировать"}<Icon name="check" /></button>
    </div>
  </Modal>}
  </>;
}
