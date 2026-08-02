import { useCallback, useEffect, useState } from "react";

import type { AdminAccess, AdminRole, Profile } from "../entities/loyalty/model/types";
import { RegistrationPanel } from "../features/registration/ui/RegistrationPanel";
import { SaleWorkspace } from "../features/sale/ui/SaleWorkspace";
import { api, ApiError } from "../shared/api/client";
import { errorMessage } from "../shared/lib/format";
import { getTelegramApp, syncTelegramAppearance } from "../shared/lib/telegram";
import type { NoticeTone } from "../shared/model/notice";
import { Icon } from "../shared/ui/Icon";
import { SectionTile } from "../shared/ui/SectionTile";
import { OwnerDashboard } from "../widgets/admin/ui/OwnerDashboard";
import { ProfilePanel } from "../widgets/profile/ui/ProfilePanel";

type Tab = "profile" | "sale" | "admin";

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [contactReady, setContactReady] = useState(false);
  const [adminRole, setAdminRole] = useState<AdminRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ message: string; tone: NoticeTone } | null>(null);
  const [tab, setTab] = useState<Tab>("profile");
  const showNotice = useCallback((message: string | null, tone: NoticeTone = "error"): void => {
    setNotice(message ? { message, tone } : null);
  }, []);

  useEffect(() => {
    const telegram = getTelegramApp();
    telegram?.ready();
    telegram?.expand();
    const stopSyncingAppearance = syncTelegramAppearance();
    const load = async (): Promise<void> => {
      setLoading(true);
      const [profileResult, accessResult] = await Promise.allSettled([
        api.get<Profile>("/loyalty/me"),
        api.get<AdminAccess>("/admin/access"),
      ]);
      if (profileResult.status === "fulfilled") {
        setProfile(profileResult.value);
        setContactReady(true);
        if (profileResult.value.admin_role) setAdminRole(profileResult.value.admin_role);
      } else if (profileResult.reason instanceof ApiError && profileResult.reason.status === 404) {
        try { const contact = await api.get<{ is_available: boolean }>("/loyalty/contact-status"); setContactReady(contact.is_available); }
        catch (error) { showNotice(errorMessage(error)); }
      } else showNotice(errorMessage(profileResult.reason));

      if (accessResult.status === "fulfilled") {
        setAdminRole(accessResult.value.role);
        if (profileResult.status === "rejected") setTab(accessResult.value.role === "owner" ? "admin" : "sale");
      } else if (!(accessResult.reason instanceof ApiError && accessResult.reason.status === 403)) {
        showNotice(errorMessage(accessResult.reason));
      }
      setLoading(false);
    };
    void load();
    return stopSyncingAppearance;
  }, [showNotice]);

  useEffect(() => {
    if (notice?.tone !== "success") return;
    const timer = window.setTimeout(() => setNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const role = profile?.admin_role ?? adminRole;
  const isOwner = role === "owner";
  const canSell = role === "sales" || isOwner;
  if (loading) return <main className="screen loading-screen"><span className="loader" /><p>Открываем программу…</p></main>;

  return <main className="screen">
    {notice && <div className={`notice notice-${notice.tone}`} role={notice.tone === "error" ? "alert" : "status"}>
      <span className="notice-mark"><Icon name={notice.tone === "success" ? "check" : "close"} size={18} /></span>
      <span>{notice.message}</span>
      <button type="button" aria-label="Закрыть уведомление" onClick={() => setNotice(null)}><Icon name="close" size={18} /></button>
    </div>}
    {profile ? <>
      {canSell && <nav className="workspace-tabs" aria-label="Разделы кабинета">
        <SectionTile active={tab === "profile"} icon="account" title="Мой профиль" onClick={() => setTab("profile")} />
        <SectionTile active={tab === "sale"} icon="sale" title="Продажа" onClick={() => setTab("sale")} />
        {isOwner && <SectionTile active={tab === "admin"} icon="shield" title="Управление" onClick={() => setTab("admin")} />}
      </nav>}
      <div className="tab-content">
        {tab === "profile" && <ProfilePanel profile={profile} onProfile={setProfile} onNotice={showNotice} />}
        {tab === "sale" && canSell && <SaleWorkspace onNotice={showNotice} />}
        {tab === "admin" && isOwner && <OwnerDashboard onNotice={showNotice} />}
      </div>
    </> : canSell ? <><nav className="workspace-tabs" aria-label="Разделы кабинета"><SectionTile active={tab === "sale"} icon="sale" title="Продажа" onClick={() => setTab("sale")} />{isOwner && <SectionTile active={tab === "admin"} icon="shield" title="Управление" onClick={() => setTab("admin")} />}</nav>{tab === "admin" && isOwner ? <OwnerDashboard onNotice={showNotice} /> : <SaleWorkspace onNotice={showNotice} />}</> : <RegistrationPanel contactReady={contactReady} onContactReady={setContactReady} onProfile={setProfile} onNotice={showNotice} />}
  </main>;
}
