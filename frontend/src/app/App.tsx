import { useEffect, useState } from "react";

import type { AdminAccess, AdminRole, Profile } from "../entities/loyalty/model/types";
import { RegistrationPanel } from "../features/registration/ui/RegistrationPanel";
import { SaleWorkspace } from "../features/sale/ui/SaleWorkspace";
import { api, ApiError } from "../shared/api/client";
import { errorMessage } from "../shared/lib/format";
import { getTelegramApp, syncTelegramAppearance } from "../shared/lib/telegram";
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
  const [notice, setNotice] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("profile");

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
        catch (error) { setNotice(errorMessage(error)); }
      } else setNotice(errorMessage(profileResult.reason));

      if (accessResult.status === "fulfilled") {
        setAdminRole(accessResult.value.role);
        if (profileResult.status === "rejected") setTab(accessResult.value.role === "owner" ? "admin" : "sale");
      } else if (!(accessResult.reason instanceof ApiError && accessResult.reason.status === 403)) {
        setNotice(errorMessage(accessResult.reason));
      }
      setLoading(false);
    };
    void load();
    return stopSyncingAppearance;
  }, []);

  const role = profile?.admin_role ?? adminRole;
  const isOwner = role === "owner";
  const canSell = role === "sales" || isOwner;
  if (loading) return <main className="screen loading-screen"><span className="loader" /><p>Открываем программу…</p></main>;

  return <main className="screen">
    {canSell && <header className="app-header admin-header"><span className="access-chip"><Icon name="shield" size={14} />{isOwner ? "Владелец" : "Sales"}</span></header>}
    {notice && <button type="button" className="notice" role="alert" onClick={() => setNotice(null)}><span>{notice}</span><Icon name="close" size={18} /></button>}
    {profile ? <>
      {canSell && <nav className="workspace-tabs" aria-label="Разделы кабинета">
        <SectionTile active={tab === "profile"} icon="account" title="Мой профиль" onClick={() => setTab("profile")} />
        <SectionTile active={tab === "sale"} icon="sale" title="Продажа" onClick={() => setTab("sale")} />
        {isOwner && <SectionTile active={tab === "admin"} icon="shield" title="Управление" onClick={() => setTab("admin")} />}
      </nav>}
      <div className="tab-content">
        {tab === "profile" && <ProfilePanel profile={profile} onProfile={setProfile} onNotice={setNotice} />}
        {tab === "sale" && canSell && <SaleWorkspace onNotice={setNotice} />}
        {tab === "admin" && isOwner && <OwnerDashboard onNotice={setNotice} />}
      </div>
    </> : canSell ? <><nav className="workspace-tabs" aria-label="Разделы кабинета"><SectionTile active={tab === "sale"} icon="sale" title="Продажа" onClick={() => setTab("sale")} />{isOwner && <SectionTile active={tab === "admin"} icon="shield" title="Управление" onClick={() => setTab("admin")} />}</nav>{tab === "admin" && isOwner ? <OwnerDashboard onNotice={setNotice} /> : <SaleWorkspace onNotice={setNotice} />}</> : <RegistrationPanel contactReady={contactReady} onContactReady={setContactReady} onProfile={setProfile} onNotice={setNotice} />}
  </main>;
}
