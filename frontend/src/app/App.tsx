import { useCallback, useEffect, useState } from "react";

import { useAdminAccessQuery } from "../entities/admin/api/queries";
import { useContactStatusQuery, useProfileQuery } from "../entities/loyalty/api/queries";
import { RegistrationPanel } from "../features/registration/ui/RegistrationPanel";
import { SaleWorkspace } from "../features/sale/ui/SaleWorkspace";
import { ApiError } from "../shared/api/client";
import { errorMessage } from "../shared/lib/format";
import { getTelegramApp, syncTelegramAppearance } from "../shared/lib/telegram";
import type { NoticeTone } from "../shared/model/notice";
import { Icon } from "../shared/ui/Icon";
import { SectionTile } from "../shared/ui/SectionTile";
import { ui } from "../shared/ui/classes";
import { OwnerDashboard } from "../widgets/admin/ui/OwnerDashboard";
import { ProfilePanel } from "../widgets/profile/ui/ProfilePanel";

type Tab = "profile" | "sale" | "admin";

export default function App() {
  const [notice, setNotice] = useState<{ message: string; tone: NoticeTone } | null>(null);
  const [tab, setTab] = useState<Tab>("profile");
  const profileQuery = useProfileQuery();
  const accessQuery = useAdminAccessQuery();
  const profileMissing = profileQuery.error instanceof ApiError && profileQuery.error.status === 404;
  const contactQuery = useContactStatusQuery(profileMissing);
  const showNotice = useCallback((message: string | null, tone: NoticeTone = "error"): void => {
    setNotice(message ? { message, tone } : null);
  }, []);

  useEffect(() => {
    const telegram = getTelegramApp();
    telegram?.ready();
    telegram?.expand();
    const stopSyncingAppearance = syncTelegramAppearance();
    return stopSyncingAppearance;
  }, []);

  useEffect(() => {
    if (profileQuery.error && !profileMissing) showNotice(errorMessage(profileQuery.error));
  }, [profileMissing, profileQuery.error, showNotice]);

  useEffect(() => {
    if (accessQuery.error && !(accessQuery.error instanceof ApiError && accessQuery.error.status === 403)) {
      showNotice(errorMessage(accessQuery.error));
    }
  }, [accessQuery.error, showNotice]);

  useEffect(() => {
    if (contactQuery.error) showNotice(errorMessage(contactQuery.error));
  }, [contactQuery.error, showNotice]);

  const profile = profileQuery.data ?? null;
  const adminRole = accessQuery.data?.role ?? null;

  useEffect(() => {
    if (!profile && adminRole && tab === "profile") {
      setTab(adminRole === "owner" ? "admin" : "sale");
    }
  }, [adminRole, profile, tab]);

  useEffect(() => {
    if (notice?.tone !== "success") return;
    const timer = window.setTimeout(() => setNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const role = profile?.admin_role ?? adminRole;
  const isOwner = role === "owner";
  const canSell = role === "sales" || isOwner;
  const contactReady = profile !== null || contactQuery.data?.is_available === true;
  const loading = profileQuery.isPending || accessQuery.isPending
    || (profileMissing && contactQuery.isPending);
  if (loading) return <main className={ui("screen", "loading-screen")}><span className={ui("loader")} /><p>Открываем программу…</p></main>;

  return <main className={ui("screen")}>
    {notice && <div className={ui("notice", notice.tone === "error" ? "notice-error" : "notice-success")} role={notice.tone === "error" ? "alert" : "status"}>
      <span className={ui("notice-mark", notice.tone === "error" ? "notice-mark-error" : "notice-mark-success")}><Icon name={notice.tone === "success" ? "check" : "close"} size={18} /></span>
      <span>{notice.message}</span>
      <button className={ui("notice-close")} type="button" aria-label="Закрыть уведомление" onClick={() => setNotice(null)}><Icon name="close" size={18} /></button>
    </div>}
    {profile ? <>
      {canSell && <nav className={ui("workspace-tabs")} aria-label="Разделы кабинета">
        <SectionTile active={tab === "profile"} icon="account" title="Мой профиль" onClick={() => setTab("profile")} />
        <SectionTile active={tab === "sale"} icon="sale" title="Продажа" onClick={() => setTab("sale")} />
        {isOwner && <SectionTile active={tab === "admin"} icon="shield" title="Управление" onClick={() => setTab("admin")} />}
      </nav>}
      <div className={ui("tab-content")}>
        {tab === "profile" && <ProfilePanel profile={profile} onNotice={showNotice} />}
        {tab === "sale" && canSell && <SaleWorkspace onNotice={showNotice} />}
        {tab === "admin" && isOwner && <OwnerDashboard onNotice={showNotice} />}
      </div>
    </> : canSell ? <><nav className={ui("workspace-tabs")} aria-label="Разделы кабинета"><SectionTile active={tab === "sale"} icon="sale" title="Продажа" onClick={() => setTab("sale")} />{isOwner && <SectionTile active={tab === "admin"} icon="shield" title="Управление" onClick={() => setTab("admin")} />}</nav>{tab === "admin" && isOwner ? <OwnerDashboard onNotice={showNotice} /> : <SaleWorkspace onNotice={showNotice} />}</> : <RegistrationPanel contactReady={contactReady} onNotice={showNotice} />}
  </main>;
}
