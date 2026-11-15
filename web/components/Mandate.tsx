"use client";
import { ArrowRight, History, Scale } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError, api, euro, ORGS, type Org } from "@/lib/api";
import { Badge, Button, Card, RULE_LABEL, StatusBadge } from "./ui";

interface MandateDoc { version: number; limit_per_order_net: string; max_unverified_value_net: string; period_budget_net: string | null; max_orders_per_hour: number | null }
interface Sim { replayed: number; changed: number; summary: string; note: string;
  changes: { order_id: string; total_net: string; before: string; after: string; rules_before: string[]; rules_after: string[] }[] }

const FIELDS = [
  { key: "limit_per_order_net", label: "Per-order limit", unit: "€" },
  { key: "max_unverified_value_net", label: "Max unverified stock", unit: "€" },
  { key: "period_budget_net", label: "Weekly budget", unit: "€" },
  { key: "max_orders_per_hour", label: "Max orders per hour", unit: "" },
] as const;

export function Mandate({ org }: { org: Org }) {
  const [current, setCurrent] = useState<MandateDoc | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [sim, setSim] = useState<Sim | null>(null);
  const [error, setError] = useState<string | null>(null);
  const role = ORGS[org].approver;

  useEffect(() => {
    setSim(null);
    api<MandateDoc>(role, "mandate").then((m) => {
      setCurrent(m);
      setDraft(Object.fromEntries(FIELDS.map((f) => [f.key, String(m[f.key] ?? "")])));
    }).catch(() => setCurrent(null));
  }, [role]);

  async function simulate() {
    setError(null);
    const body = Object.fromEntries(Object.entries(draft).filter(([k, v]) => v !== "" && v !== String(current?.[k as keyof MandateDoc] ?? "")));
    try { setSim(await api<Sim>(role, "mandate/simulate", { body })); }
    catch (e) { setError(e instanceof ApiError ? `${e.code}: ${e.message}` : String(e)); }
  }

  return (
    <div className="mx-auto grid max-w-5xl gap-5 lg:grid-cols-[360px_1fr]">
      <Card className="h-fit space-y-4 p-5">
        <div className="flex items-center gap-2">
          <Scale className="size-5 text-accent" />
          <div><div className="font-semibold">Mandate of {ORGS[org].label}</div>
            <div className="text-xs text-muted">Version {current?.version ?? "—"} · enforced by Cedar policies</div></div>
        </div>
        {FIELDS.map((f) => (
          <label key={f.key} className="block">
            <span className="text-xs font-medium text-muted">{f.label}</span>
            <div className="mt-1 flex items-center rounded-lg border border-line focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/10">
              {f.unit && <span className="pl-3 text-sm text-muted">{f.unit}</span>}
              <input value={draft[f.key] ?? ""} onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })} inputMode="decimal"
                className="w-full bg-transparent px-3 py-2 text-sm outline-none" />
              {current && String(current[f.key] ?? "") !== (draft[f.key] ?? "") && <span className="pr-3"><Badge tone="accent">changed</Badge></span>}
            </div>
          </label>
        ))}
        <Button className="w-full" onClick={simulate}><History className="size-4" />Replay past decisions</Button>
        <p className="text-xs text-muted">Read-only what-if. Nothing is changed until a human edits the mandate.</p>
      </Card>

      <Card className="p-6">
        {!sim ? (
          <div className="grid h-full place-items-center py-16 text-center">
            <div className="max-w-sm space-y-2">
              <History className="mx-auto size-8 text-muted" />
              <div className="font-semibold">What would a different mandate have done?</div>
              <div className="text-sm text-muted">Change a limit and replay every decision recorded in the signed audit log, with the same Cedar policies.</div>
            </div>
          </div>
        ) : (
          <div className="animate-in space-y-5">
            <div>
              <div className="text-5xl font-semibold tracking-tight">{sim.changed}<span className="text-2xl text-muted"> / {sim.replayed}</span></div>
              <div className="mt-1 text-lg font-medium">{sim.summary}</div>
              <p className="mt-1 text-xs text-muted">{sim.note}</p>
            </div>
            {sim.changes.length > 0 && (
              <div className="divide-y divide-line rounded-lg border border-line">
                {sim.changes.map((c) => (
                  <div key={c.order_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <span className="font-mono text-xs text-muted">{c.order_id}</span>
                    <span className="text-sm font-medium">{euro(c.total_net)}</span>
                    <div className="ml-auto flex items-center gap-2">
                      <StatusBadge state={c.before} /><ArrowRight className="size-4 text-muted" /><StatusBadge state={c.after} />
                    </div>
                    {c.rules_after.length > 0 && (
                      <div className="flex w-full flex-wrap gap-1">{c.rules_after.map((r) => <Badge key={r} tone="warn">{RULE_LABEL[r] ?? r}</Badge>)}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
            {error && <div className="text-sm text-bad">{error}</div>}
          </div>
        )}
      </Card>
    </div>
  );
}
