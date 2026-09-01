import type { ReactNode } from "react";

export type IconName =
  | "account" | "bag" | "chart" | "gift" | "shield" | "code" | "sale"
  | "search" | "close" | "check" | "plus" | "arrow" | "back" | "download" | "sparkle" | "copy" | "lock"
  | "sun" | "moon" | "contrast";

export function Icon({ name, size = 21 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    account: <><circle cx="12" cy="8" r="3.25" /><path d="M5.5 20c.75-3.25 3-5 6.5-5s5.75 1.75 6.5 5" /></>,
    bag: <><path d="M5 8.5h14l-1 11H6l-1-11Z" /><path d="M9 9V7a3 3 0 0 1 6 0v2" /></>,
    chart: <><path d="M5 19.5V11m7 8.5V5m7 14.5v-6" /><path d="M3.5 20.5h17" /></>,
    gift: <><path d="M4.5 10h15v10h-15zM3.5 7h17v3h-17zM12 7v13M12 7c-3.5 0-5-1.1-5-2.5C7 3.55 8 3 9 3c1.7 0 3 2 3 4Zm0 0c3.5 0 5-1.1 5-2.5 0-.95-1-1.5-2-1.5-1.7 0-3 2-3 4Z" /></>,
    shield: <><path d="M12 3.5 19 6v5c0 4.3-2.9 7.7-7 9.5-4.1-1.8-7-5.2-7-9.5V6l7-2.5Z" /><path d="m9 12 2 2 4-4" /></>,
    code: <><rect x="4" y="5" width="16" height="14" rx="2.5" /><path d="m9.5 10-2 2 2 2m5-4 2 2-2 2" /></>,
    sale: <><path d="M5 5.5h11l3 3v10H5z" /><path d="M16 5.5v3h3M8 11h8m-8 4h5" /></>,
    search: <><circle cx="10.7" cy="10.7" r="5.4" /><path d="m15 15 4.1 4.1" /></>,
    close: <><path d="m6.5 6.5 11 11m0-11-11 11" /></>,
    check: <path d="m5.5 12.5 4.1 4.1 8.9-9" />,
    plus: <path d="M12 5v14M5 12h14" />,
    arrow: <path d="M5 12h13m-5-5 5 5-5 5" />,
    back: <path d="M19 12H6m5 5-5-5 5-5" />,
    download: <><path d="M12 4v10m0 0 4-4m-4 4-4-4" /><path d="M5 18v2h14v-2" /></>,
    sparkle: <path d="m12 3 1.4 5.6L19 10l-5.6 1.4L12 17l-1.4-5.6L5 10l5.6-1.4L12 3Zm6 12 .7 2.3L21 18l-2.3.7L18 21l-.7-2.3L15 18l2.3-.7L18 15Z" />,
    copy: <><rect x="8" y="8" width="11" height="11" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2.5" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" /></>,
    moon: <path d="M20 14.3A8.2 8.2 0 0 1 9.7 4a8.5 8.5 0 1 0 10.3 10.3Z" />,
    contrast: <><circle cx="12" cy="12" r="8.2" /><path d="M12 3.8a8.2 8.2 0 0 1 0 16.4Z" fill="currentColor" stroke="none" /></>,
  };
  return <svg className={ui("icon")} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
import { ui } from "./classes";
