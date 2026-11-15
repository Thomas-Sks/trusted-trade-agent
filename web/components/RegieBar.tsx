"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const ACTIONS: { label: string; run: () => Promise<unknown> }[] = [
  { label: "🧪 Rupture lait (100 L)", run: () => api("admin", "admin/scenario", { method: "PUT", body: { stock_override: { "464306": 100 } } }) },
  { label: "📈 Tomates +15 %", run: () => api("admin", "admin/scenario", { method: "PUT", body: { price_increase_pct: { "462545": 15 } } }) },
  { label: "🔌 Panne Valio", run: () => api("admin", "admin/scenario", { method: "PUT", body: { outage: true } }) },
  { label: "♻️ Normal", run: () => api("admin", "admin/scenario", { method: "DELETE" }) },
  { label: "⏩ +3 jours", run: () => api("admin", "admin/clock/advance", { body: { minutes: 3 * 24 * 60 } }) },
  { label: "🧹 Reset démo", run: () => api("admin", "admin/reset", { method: "POST", body: {} }) },
];

export function RegieBar() {
  const [state, setState] = useState<{ now: string; scenario: string[] } | null>(null);
  const refresh = async () => { try { setState(await api("admin", "admin/state")); } catch { setState(null); } };
  useEffect(() => { refresh(); const id = setInterval(refresh, 5000); return () => clearInterval(id); }, []);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="chip bg-ink text-white">🎛️ Régie Valio</span>
      {state && <span className="chip bg-white text-ink ring-1 ring-grape-soft">🕐 {new Date(state.now).toLocaleString("fr-FR", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>}
      {state?.scenario.map((s) => <span key={s} className="chip bg-sun-soft text-[#b77400]">🧪 {s}</span>)}
      {ACTIONS.map((a) => (
        <button key={a.label} onClick={async () => { await a.run().catch(() => null); refresh(); }}
          className="btn bg-white/80 px-3 py-1 text-xs text-ink ring-1 ring-grape-soft hover:ring-grape">{a.label}</button>
      ))}
    </div>
  );
}
