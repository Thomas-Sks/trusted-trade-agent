"use client";
import { useCallback, useEffect, useState } from "react";
import { Approvals } from "@/components/Approvals";
import { AuditLog } from "@/components/AuditLog";
import { DemoMenu } from "@/components/DemoMenu";
import { NewRequest } from "@/components/NewRequest";
import { Requests } from "@/components/Requests";
import { ORGS, type Org } from "@/lib/api";

const TABS = [
  { key: "new", label: "New request" },
  { key: "requests", label: "Orders" },
  { key: "approvals", label: "Approvals" },
  { key: "audit", label: "Audit log" },
] as const;
type Tab = (typeof TABS)[number]["key"];

export default function Home() {
  const [org, setOrg] = useState<Org>("hotel");
  const [tab, setTab] = useState<Tab>("new");
  const [pending, setPending] = useState(0);
  const onCount = useCallback((n: number) => setPending(n), []);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("tab");
    if (TABS.some((t) => t.key === q)) setTab(q as Tab);  // eslint-disable-line react-hooks/set-state-in-effect
  }, []);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-6">
          <div className="flex items-center gap-2.5">
            <div className="size-7 rounded-lg bg-gradient-to-br from-accent via-[#9b5cf6] to-[#ff7ab6]" />
            <span className="font-semibold tracking-tight">TTAP</span>
            <span className="hidden whitespace-nowrap text-sm text-muted xl:inline">Trusted Trade Agent Protocol</span>
          </div>
          <nav className="flex h-full items-stretch gap-1">
            {TABS.map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`relative flex items-center gap-1.5 whitespace-nowrap px-3 text-sm font-medium transition ${tab === t.key ? "text-ink" : "text-muted hover:text-ink"}`}>
                {t.label}
                {t.key === "approvals" && pending > 0 && <span className="rounded-full bg-warn px-1.5 text-[11px] font-semibold text-white">{pending}</span>}
                {tab === t.key && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent" />}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <DemoMenu />
            <select value={org} onChange={(e) => setOrg(e.target.value as Org)}
              className="rounded-lg bg-white px-2.5 py-1.5 text-sm font-medium ring-1 ring-line outline-none">
              {(Object.keys(ORGS) as Org[]).map((o) => <option key={o} value={o}>{ORGS[o].label} · {ORGS[o].limit}</option>)}
            </select>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className={tab === "new" ? "" : "hidden"}><NewRequest org={org} /></div>
        {tab === "requests" && <Requests org={org} />}
        <div className={tab === "approvals" ? "" : "hidden"}><Approvals org={org} onCount={onCount} /></div>
        {tab === "audit" && <AuditLog org={org} />}
      </main>
    </div>
  );
}
