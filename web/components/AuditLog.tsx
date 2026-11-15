"use client";
import { ScrollText, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ORGS, time, type Org } from "@/lib/api";
import type { AuditEvent } from "@/lib/types";
import { Badge, Button, Card, Empty } from "./ui";

const STEP_TONE = { request: "accent", lookup: "info", order: "neutral", approval: "warn" } as const;
const ACTOR = (a: string) => a.startsWith("agent") ? "Agent" : a.startsWith("policy") ? "Policy engine" : a.startsWith("approver") ? a.split(":")[1] : a.startsWith("llm") ? "Interpreter (LLM)" : "Gateway";

export function AuditLog({ org, filter }: { org: Org; filter?: string }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [step, setStep] = useState<string>("all");
  const [report, setReport] = useState<{ valid: boolean; events: number; problems: string[] } | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => { try { const e = await api<AuditEvent[]>(ORGS[org].agent, "audit"); if (alive) setEvents(e); } catch { /* retry */ } };
    tick(); const id = setInterval(tick, 3000);
    return () => { alive = false; clearInterval(id); };
  }, [org]);

  const shown = [...events].reverse().filter((e) => (step === "all" || e.step === step) && (!filter || e.subject.includes(filter) || e.explanation.includes(filter)));
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3">
        {["all", "request", "lookup", "order", "approval"].map((s) => (
          <button key={s} onClick={() => setStep(s)}
            className={`rounded-md px-2.5 py-1 text-sm capitalize ${step === s ? "bg-ink text-white" : "text-muted hover:bg-page"}`}>{s}</button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          {report && <Badge tone={report.valid ? "ok" : "bad"}>{report.valid ? `Chain intact · ${report.events} signed events` : `${report.problems.length} problem(s)`}</Badge>}
          <Button variant="secondary" onClick={async () => setReport(await api(ORGS[org].agent, "audit/verify"))}><ShieldCheck className="size-4" />Verify chain</Button>
        </div>
      </div>
      {shown.length === 0 ? <Empty icon={<ScrollText className="size-5" />} title="No events yet" text="Every step of every order is recorded here, hash-chained and signed." /> : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted">
            <tr className="border-b border-line"><th className="px-5 py-2 font-medium">Time</th><th className="py-2 font-medium">Step</th><th className="py-2 font-medium">Actor</th><th className="py-2 pr-5 font-medium">What happened</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {shown.map((e) => (
              <tr key={e.id} className="align-top hover:bg-page/60">
                <td className="whitespace-nowrap px-5 py-3 font-mono text-xs text-muted">{time(e.time)}</td>
                <td className="py-3 pr-4"><Badge tone={STEP_TONE[e.step as keyof typeof STEP_TONE] ?? "neutral"}>{e.step}</Badge></td>
                <td className="whitespace-nowrap py-3 pr-4 text-muted">{ACTOR(e.actor)}</td>
                <td className="py-3 pr-5">{e.explanation}<div className="mt-0.5 font-mono text-[10px] text-muted/70">{e.hash.slice(0, 23)}…</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
