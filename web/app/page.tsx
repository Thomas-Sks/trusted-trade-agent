"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AgentLive, type Launch } from "@/components/AgentLive";
import { Approvals } from "@/components/Approvals";
import { AuditLog } from "@/components/AuditLog";
import { DemoMenu } from "@/components/DemoMenu";
import { Kitchen } from "@/components/Kitchen";
import { Onboarding } from "@/components/Onboarding";
import { Requests } from "@/components/Requests";
import { DEMO_ORGS, loadMyOrgs, saveMyOrgs, type OrgProfile } from "@/lib/api";

const TABS = [
  { key: "kitchen", label: "Kitchen" },
  { key: "start", label: "Get started" },
  { key: "live", label: "Agent live" },
  { key: "requests", label: "Orders" },
  { key: "approvals", label: "Approvals" },
  { key: "audit", label: "Audit log" },
] as const;
type Tab = (typeof TABS)[number]["key"];

export default function Home() {
  const [mine, setMine] = useState<OrgProfile[]>([]);
  const [orgId, setOrgId] = useState("resto");
  const [tab, setTab] = useState<Tab>("kitchen");
  const orgs = useMemo(() => [...mine, ...DEMO_ORGS], [mine]);
  const org = orgs.find((o) => o.id === orgId) ?? DEMO_ORGS[0];
  useEffect(() => {
    const saved = loadMyOrgs();
    if (saved.length) { setMine(saved); setOrgId(saved[0].id); }  // eslint-disable-line react-hooks/set-state-in-effect
  }, []);
  const [launch, setLaunch] = useState<Launch | null>(null);
  const onReady = useCallback((limit: number, paired: boolean) => {
    // a request deliberately above the new mandate's per-order limit: the approval path shows up on the phone
    const litres = Math.max(1000, Math.ceil((limit * 1.6) / 1.01 / 100) * 100);
    setLaunch({
      text: `We need ${litres.toLocaleString("en-IE")} litres of lactose-free milk for Monday, Finnish if possible.`,
      welcome: `Your agent will buy within €${limit.toLocaleString("en-IE")} per order; this request is above it, so ${paired ? "the approval will arrive on your phone" : "you will approve it in the Approvals tab"}. Press “Run my agent” and watch each step.`,
      nonce: Date.now(),
    });
    setTab("live");
  }, []);
  const addOrg = useCallback((o: OrgProfile) => {
    setMine((prev) => { const next = [o, ...prev.filter((p) => p.id !== o.id)]; saveMyOrgs(next); return next; });
    setOrgId(o.id);
  }, []);
  const [pending, setPending] = useState(0);
  const onCount = useCallback((n: number) => setPending(n), []);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("tab");
    if (TABS.some((t) => t.key === q)) setTab(q as Tab);  // eslint-disable-line react-hooks/set-state-in-effect
  }, []);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-6">
          <div className="flex items-center gap-2.5">
            <div className="size-7 rounded-lg bg-gradient-to-br from-accent via-[#9b5cf6] to-[#ff7ab6]" />
            <span className="font-semibold tracking-tight">TTAP</span>
            <span className="hidden whitespace-nowrap text-sm text-muted 2xl:inline">Trusted Trade Agent Protocol</span>
          </div>
          <nav className="flex h-full items-stretch gap-1">
            {TABS.map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`relative flex items-center gap-1.5 whitespace-nowrap px-2.5 text-sm font-medium transition ${tab === t.key ? "text-ink" : "text-muted hover:text-ink"}`}>
                {t.label}
                {t.key === "approvals" && pending > 0 && <span className="rounded-full bg-warn px-1.5 text-[11px] font-semibold text-white">{pending}</span>}
                {tab === t.key && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent" />}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <DemoMenu />
            <select value={org.id} onChange={(e) => setOrgId(e.target.value)}
              className="w-[190px] truncate rounded-lg bg-white px-2.5 py-1.5 text-sm font-medium ring-1 ring-line outline-none">
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.label} · {o.limit}</option>)}
            </select>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">
        <div className={tab === "start" ? "" : "hidden"}><Onboarding onCreated={addOrg} onReady={onReady} /></div>
        {tab === "kitchen" && <Kitchen key={org.id} org={org} />}
        <div className={tab === "live" ? "" : "hidden"}><AgentLive key={org.id} org={org} launch={launch} /></div>
        {tab === "requests" && <Requests key={org.id} org={org} />}
        <div className={tab === "approvals" ? "" : "hidden"}><Approvals key={org.id} org={org} onCount={onCount} /></div>
        {tab === "audit" && <AuditLog key={org.id} org={org} />}
      </main>
    </div>
  );
}
