import { useState, type FormEvent } from "react";

import type { Profile } from "../../../entities/loyalty/model/types";
import { api } from "../../../shared/api/client";
import { errorMessage } from "../../../shared/lib/format";
import { getTelegramApp, haptic } from "../../../shared/lib/telegram";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";

const privacyUrl = "https://velinacosmetic.by/privacy";

export function RegistrationPanel({
  contactReady,
  onContactReady,
  onProfile,
  onNotice,
}: {
  contactReady: boolean;
  onContactReady: (value: boolean) => void;
  onProfile: (value: Profile) => void;
  onNotice: NoticeHandler;
}) {
  const [fullName, setFullName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState<"male" | "female">("female");
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const requestContact = (): void => {
    const telegram = getTelegramApp();
    if (!telegram) {
      onNotice("Регистрация доступна только внутри Telegram.");
      return;
    }
    haptic();
    telegram.requestContact((shared) => {
      if (!shared) return;
      window.setTimeout(() => {
        void api.get<{ is_available: boolean }>("/loyalty/contact-status")
          .then((result) => { onContactReady(result.is_available); haptic("success"); })
          .catch((error: unknown) => onNotice(errorMessage(error)));
      }, 850);
    });
  };

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!contactReady || !consent) return;
    setSubmitting(true);
    try {
      onProfile(await api.post<Profile>("/loyalty/register", { full_name: fullName, birth_date: birthDate, gender }));
      haptic("success");
      onNotice("Регистрация завершена. Бонусный счёт активирован.", "success");
    } catch (error) {
      haptic("error");
      onNotice(errorMessage(error));
    } finally { setSubmitting(false); }
  };

  return <section className="onboarding">
    <section className="onboarding-intro">
      <span className="onboarding-symbol"><Icon name="sparkle" /></span>
      <p className="eyebrow">ПРОГРАММА ЛОЯЛЬНОСТИ</p>
      <h1>Красота<br />возвращается.</h1>
      <p>Получайте кешбэк за покупки, повышайте уровень и забирайте 10% в праздничные дни.</p>
      <div className="onboarding-perks"><span>до <b>7%</b> по уровню</span><span><b>10%</b> ко дню рождения</span></div>
    </section>
    <form className="onboarding-form" onSubmit={(event) => void submit(event)}>
      <div className="onboarding-steps" aria-label="Этапы регистрации"><span className="active"><i>1</i>Номер</span><span className={contactReady ? "active" : ""}><i>2</i>Профиль</span></div>
      {!contactReady ? <section className="onboarding-step">
        <div><p className="overline">ШАГ 1 ИЗ 2</p><h2>Подтвердим номер</h2><p>Telegram передаст номер напрямую — он нужен только для защиты вашего бонусного счёта.</p></div>
        <button type="button" className="primary-action" onClick={requestContact}>Поделиться номером <Icon name="shield" /></button>
      </section> : <section className="onboarding-step">
        <div><p className="overline">ШАГ 2 ИЗ 2</p><h2>Немного о вас</h2><p>Номер подтверждён. Заполним профиль и активируем ваш бонусный счёт.</p></div>
        <div className="form-grid">
          <label>ФИО<input required autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Как к вам обращаться" /></label>
          <label>Дата рождения<input required type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} /></label>
        </div>
        <label>Пол<select value={gender} onChange={(event) => setGender(event.target.value as "male" | "female")}><option value="female">Женский</option><option value="male">Мужской</option></select></label>
        <label className="check"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /><span>Соглашаюсь с <a href={privacyUrl} target="_blank" rel="noreferrer">политикой конфиденциальности</a>.</span></label>
        <button className="primary-action" disabled={!consent || submitting} type="submit">{submitting ? "Создаём профиль…" : "Активировать бонусный счёт"}<Icon name="arrow" /></button>
      </section>}
    </form>
  </section>;
}
