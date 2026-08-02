import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useRegisterMutation } from "../../../entities/loyalty/api/mutations";
import { contactStatusQueryOptions } from "../../../entities/loyalty/api/queries";
import { errorMessage } from "../../../shared/lib/format";
import { getTelegramApp, haptic } from "../../../shared/lib/telegram";
import type { NoticeHandler } from "../../../shared/model/notice";
import { Icon } from "../../../shared/ui/Icon";
import { ui } from "../../../shared/ui/classes";

const privacyUrl = "https://velinacosmetic.by/privacy";

export function RegistrationPanel({
  contactReady,
  onNotice,
}: {
  contactReady: boolean;
  onNotice: NoticeHandler;
}) {
  const [fullName, setFullName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState<"male" | "female">("female");
  const [consent, setConsent] = useState(false);
  const queryClient = useQueryClient();
  const registerMutation = useRegisterMutation();

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
        void queryClient.fetchQuery(contactStatusQueryOptions())
          .then(() => haptic("success"))
          .catch((error: unknown) => onNotice(errorMessage(error)));
      }, 850);
    });
  };

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!contactReady || !consent) return;
    try {
      await registerMutation.mutateAsync({ full_name: fullName, birth_date: birthDate, gender });
      haptic("success");
      onNotice("Регистрация завершена. Бонусный счёт активирован.", "success");
    } catch (error) {
      haptic("error");
      onNotice(errorMessage(error));
    }
  };

  return <section className={ui("onboarding")}>
    <section className={ui("onboarding-intro")}>
      <span className={ui("onboarding-symbol")}><Icon name="sparkle" /></span>
      <p className={ui("eyebrow", "intro-eyebrow")}>ПРОГРАММА ЛОЯЛЬНОСТИ</p>
      <h1>Красота<br />возвращается.</h1>
      <p>Получайте кешбэк за покупки, повышайте уровень и забирайте 10% в праздничные дни.</p>
      <div className={ui("onboarding-perks")}><span>до <b>7%</b> по уровню</span><span><b>10%</b> ко дню рождения</span></div>
    </section>
    <form className={ui("onboarding-form")} onSubmit={(event) => void submit(event)}>
      <div className={ui("onboarding-steps")} aria-label="Этапы регистрации"><span className={ui("onboarding-step-active")}><i>1</i>Номер</span><span className={contactReady ? ui("onboarding-step-active") : undefined}><i>2</i>Профиль</span></div>
      {!contactReady ? <section className={ui("onboarding-step")}>
        <div><p className={ui("overline")} data-overline>ШАГ 1 ИЗ 2</p><h2>Подтвердим номер</h2><p>Telegram передаст номер напрямую — он нужен только для защиты вашего бонусного счёта.</p></div>
        <button type="button" className={ui("primary-action")} onClick={requestContact}>Поделиться номером <Icon name="shield" /></button>
      </section> : <section className={ui("onboarding-step")}>
        <div><p className={ui("overline")} data-overline>ШАГ 2 ИЗ 2</p><h2>Немного о вас</h2><p>Номер подтверждён. Заполним профиль и активируем ваш бонусный счёт.</p></div>
        <div className={ui("form-grid")}>
          <label>ФИО<input className={ui("form-control")} required autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Как к вам обращаться" /></label>
          <label>Дата рождения<input className={ui("form-control")} required type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} /></label>
        </div>
        <label>Пол<select className={ui("form-control")} value={gender} onChange={(event) => setGender(event.target.value as "male" | "female")}><option value="female">Женский</option><option value="male">Мужской</option></select></label>
        <label className={ui("check")}><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /><span>Соглашаюсь с <a href={privacyUrl} target="_blank" rel="noreferrer">политикой конфиденциальности</a>.</span></label>
        <button className={ui("primary-action")} disabled={!consent || registerMutation.isPending} type="submit">{registerMutation.isPending ? "Создаём профиль…" : "Активировать бонусный счёт"}<Icon name="arrow" /></button>
      </section>}
    </form>
  </section>;
}
