"use client";
import { useEffect, useState } from "react";
import { api, ORGS, time, type Org } from "@/lib/api";
import type { AuditEvent } from "@/lib/types";
import { Empty, PanelHeader, STEPS, stepTone } from "./ui";

const ACTOR = (a: string) => a.startsWith("agent") ? "🤖" : a.startsWith("policy") ? "⚖️" : a.startsWith("approver") ? "👩‍🍳" : a.startsWith("llm") ? "✨" : "⚙️";

export function AuditPanel({ org }: { org: Org }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [verify, setVerify] = useState<{ valid: boolean; events: number; problems: string[] } | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try { const ev = await api<AuditEvent[]>(ORGS[org].agent, "audit"); if (alive) setEvents(ev); } catch { /* gateway restarting */ }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => { alive = false; clearInterval(id); };
  }, [org]);

  const latest = events.at(-1);
  const flow = latest ? events.filter((e) => e.time >= (events.findLast((x) => x.step === "request")?.time ?? "")) : [];
  const reached = new Set(flow.map((e) => e.step));

  return (
    <section className="card flex min-h-0 flex-col">
      <PanelHeader emoji="📜" title="Journal vérifiable" subtitle="CloudEvents · chaîné SHA-256 · signé ES256" accent="bg-sky-soft"
        right={<button onClick={async () => setVerify(await api(ORGS[org].agent, "audit/verify"))} className="btn bg-sky text-white hover:bg-ink">🔐 Vérifier</button>} />
      <div className="px-5 pt-4">
        <div className="grid grid-cols-4 gap-2">
          {STEPS.map((s, i) => (
            <div key={s.key} className={`relative rounded-2xl p-2.5 text-center transition ${reached.has(s.key) ? `${s.tone} ring-2 ${s.ring}` : "bg-canvas text-muted"}`}>
              <div className="text-lg">{s.emoji}</div>
              <div className="text-[11px] font-extrabold">{i + 1}. {s.label}</div>
            </div>
          ))}
        </div>
        {verify && (
          <div className={`animate-pop mt-3 rounded-2xl p-3 text-sm font-semibold ${verify.valid ? "bg-mint-soft text-mint" : "bg-tomato-soft text-tomato"}`}>
            {verify.valid ? `✅ Chaîne intègre : ${verify.events} événements, signatures valides` : `❌ ${verify.problems.length} problème(s) : ${verify.problems[0]}`}
          </div>
        )}
      </div>
      <div className="scroll-soft min-h-0 flex-1 space-y-2 overflow-auto p-5">
        {events.length === 0 && <Empty emoji="🫙" text="Aucun événement pour l'instant." />}
        {[...events].reverse().map((e) => {
          const s = stepTone(e.step);
          return (
            <div key={e.id} className="animate-slide rounded-2xl bg-canvas/80 p-3">
              <div className="mb-1 flex items-center gap-2 text-[11px]">
                <span className={`chip ${s.tone}`}>{s.emoji} {s.label}</span>
                <span className="font-semibold">{ACTOR(e.actor)} {e.actor}</span>
                <span className="ml-auto font-mono text-muted">{time(e.time)}</span>
              </div>
              <div className="text-sm leading-snug">{e.explanation}</div>
              <div className="mt-1 truncate font-mono text-[10px] text-muted">{e.hash}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
