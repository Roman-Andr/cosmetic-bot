import { useState, type FormEvent } from "react";

import { api } from "../../../shared/api/client";
import { errorMessage } from "../../../shared/lib/format";
import { getTelegramApp, haptic } from "../../../shared/lib/telegram";
import { Icon } from "../../../shared/ui/Icon";
import type { Profile } from "../../../entities/loyalty/model/types";

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
  onNotice: (value: string | null) => void;
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
      onNotice("Добро пожаловать в Velina Club!");
    } catch (error) {
      haptic("error");
      onNotice(errorMessage(error));
    } finally { setSubmitting(false); }
  };

  return <section className="registration-layout">
    <section className="intro-card">
      <span className="intro-icon"><Icon name="sparkle" /></span>
      <p className="eyebrow">VELINA CLUB</p>
      <h2>Красота,<br /><em>которая</em> возвращается</h2>
      <p>Возвращаем бонусы за покупки, бережно храним их на вашем балансе и дарим 10% в дни рождения.</p>
      <div className="intro-perks"><span><b>до 7%</b> по уровню</span><span><b>10%</b> ко дню рождения</span></div>
    </section>
    <form className="panel form registration-form" onSubmit={(event) => void submit(event)}>
      <div className="panel-heading"><div><p className="overline">VELINA CLUB</p><h2>Создать профиль</h2></div><span className={`phone-status${contactReady ? " ready" : ""}`}><i />{contactReady ? "Номер получен" : "Шаг 1 из 2"}</span></div>
      <p className="muted">Сначала подтвердите номер через защищённое окно Telegram — так мы защитим ваш баланс.</p>
      <button type="button" className={`contact-button${contactReady ? " is-ready" : ""}`} onClick={requestContact}>
        <span className="button-icon"><Icon name={contactReady ? "check" : "shield"} /></span>{contactReady ? "Номер подтверждён" : "Поделиться номером"}
      </button>
      <div className="form-grid">
        <label>ФИО<input required autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Как к вам обращаться" /></label>
        <label>Дата рождения<input required type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} /></label>
      </div>
      <label>Пол<select value={gender} onChange={(event) => setGender(event.target.value as "male" | "female")}><option value="female">Женский</option><option value="male">Мужской</option></select></label>
      <label className="check"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /><span>Соглашаюсь с <a href={privacyUrl} target="_blank" rel="noreferrer">политикой конфиденциальности</a>.</span></label>
      <button className="primary-action" disabled={!contactReady || !consent || submitting} type="submit">{submitting ? "Создаём профиль…" : "Стать участником"}<Icon name="arrow" /></button>
    </form>
  </section>;
}
