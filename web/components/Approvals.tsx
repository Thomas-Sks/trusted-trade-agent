"use client";
import { Check, Gauge, Inbox, Smartphone, X } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useCallback, useEffect, useState } from "react";
import { api, dateTime, euro, num, ORGS, type Org } from "@/lib/api";
import type { ApprovalCard, Order } from "@/lib/types";
import { Badge, Button, Card, Empty } from "./ui";

const BOT = process.env.NEXT_PUBLIC_TELEGRAM_BOT;

function cutoff(min: number | null) {
  if (min === null) return "—";
  if (min < 0) return "passed";
  const d = Math.floor(min / 1440), h = Math.floor((min % 1440) / 60), m = min % 60;
  return d ? `${d} d ${h} h` : h ? `${h} h ${m} min` : `${m} min`;
}

export function Approvals({ org, onCount }: { org: Org; onCount: (n: number) => void }) {
  const [items, setItems] = useState<{ order: Order; card: ApprovalCard }[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [stats, setStats] = useState<{ summary: string; rubber_stamp_risk: boolean; approved_under_5s_pct: number | null } | null>(null);
  const role = ORGS[org].approver;

  const load = useCallback(async () => {
    try {
      const pending = await api<Order[]>(role, "approvals");
      const rows = await Promise.all(pending.map(async (order) => ({ order, card: await api<ApprovalCard>(role, `orders/${order.order_id}/card`) })));
      setItems(rows); onCount(rows.length);
      setStats(await api(role, "approvals/stats"));
    } catch { /* gateway restarting */ }
  }, [role, onCount]);

  useEffect(() => { load(); const id = setInterval(load, 2500); return () => clearInterval(id); }, [load]);
  const current = items.find((i) => i.order.order_id === selected) ?? items[0];

  async function act(verb: "approve" | "reject") {
    if (!current) return;
    setBusy(true);
    try {
      await api(role, `orders/${current.order.order_id}/${verb}`, { body: verb === "approve"
        ? { expected_version: current.order.version } : { expected_version: current.order.version, reason: "Rejected from the web console" } });
    } finally { setBusy(false); setSelected(null); load(); }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
      <div className="space-y-3">
        <Card>
          <div className="border-b border-line px-4 py-3 text-sm font-semibold">Pending · {items.length}</div>
          {items.length === 0 ? <Empty icon={<Inbox className="size-5" />} title="Nothing to approve" text="The agent is acting within its mandate." /> : (
            <ul className="divide-y divide-line">
              {items.map(({ order, card }) => (
                <li key={order.order_id}>
                  <button onClick={() => setSelected(order.order_id)}
                    className={`w-full px-4 py-3 text-left hover:bg-page ${current?.order.order_id === order.order_id ? "bg-accent-soft/40" : ""}`}>
                    <div className="flex items-center justify-between">
                      <span className="truncate text-sm font-medium">{card.lines[0]?.name}</span>
                      <span className="ml-2 text-sm font-semibold">{euro(card.total_net)}</span>
                    </div>
                    <div className="mt-0.5 truncate text-xs text-muted">{card.reasons[0]}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        {stats && (
          <Card className={`flex gap-3 p-4 ${stats.rubber_stamp_risk ? "ring-2 ring-warn/40" : ""}`}>
            <Gauge className={`mt-0.5 size-5 shrink-0 ${stats.rubber_stamp_risk ? "text-warn" : "text-muted"}`} />
            <div className="text-xs text-muted">
              <div className="mb-0.5 text-sm font-semibold text-ink">Oversight quality</div>
              {stats.summary}. Approving in seconds usually means not reading — the card shows facts, never the agent&apos;s advocacy.
            </div>
          </Card>
        )}
        {BOT && (
          <Card className="flex items-center gap-4 p-4">
            <QRCodeSVG value={`https://t.me/${BOT}?start=${ORGS[org].pairing}`} size={72} fgColor="#17162b" />
            <div className="text-xs text-muted">
              <div className="mb-0.5 flex items-center gap-1 text-sm font-semibold text-ink"><Smartphone className="size-4" />Approve on your phone</div>
              Scan to pair {ORGS[org].approverName} with the Telegram bot. One-time signed buttons.
            </div>
          </Card>
        )}
      </div>

      {current && (
        <Card className="animate-in">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-6 py-5">
            <div>
              <div className="text-xs text-muted">Approval request · {current.order.order_id}</div>
              <div className="text-2xl font-semibold">{euro(current.card.total_net)} <span className="text-sm font-normal text-muted">excl. VAT · {euro(current.card.total_gross)} incl. VAT</span></div>
            </div>
            <div className="flex gap-2">
              <Button variant="bad" disabled={busy} onClick={() => act("reject")}><X className="size-4" />Reject</Button>
              <Button variant="ok" disabled={busy} onClick={() => act("approve")}><Check className="size-4" />Approve</Button>
            </div>
          </div>
          <div className="space-y-5 px-6 py-5">
            <section>
              <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">Why it needs you</div>
              <ul className="space-y-1.5">{current.card.reasons.map((r) => <li key={r} className="flex gap-2 text-sm"><span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-warn" />{r}</li>)}</ul>
            </section>
            <section>
              <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">What would be ordered</div>
              <div className="divide-y divide-line rounded-lg border border-line">
                {current.card.lines.map((l, i) => (
                  <div key={i} className="flex items-center gap-4 px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{l.name}</div>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {l.partial && <Badge tone="bad">Partial</Badge>}
                        {l.is_substitute && <Badge tone="warn">Substitute</Badge>}
                        {l.vs_usual && !l.is_substitute && <Badge tone="info">{l.vs_usual}</Badge>}
                        {l.changes.filter((c) => c.startsWith("origin")).map((c) => <Badge key={c} tone="warn">Origin {c.split(":")[1].toUpperCase()}</Badge>)}
                      </div>
                    </div>
                    <div className="text-right text-sm"><div className="font-medium">{euro(l.line_total_net)}</div><div className="text-xs text-muted">{num(l.qty_sales_units)} × {euro(l.unit_net)}</div></div>
                  </div>
                ))}
              </div>
            </section>
            {current.card.warnings.length > 0 && (
              <section className="rounded-lg bg-warn-soft px-4 py-3 text-sm text-warn">{current.card.warnings.map((w) => <div key={w}>{w}</div>)}</section>
            )}
            <dl className="grid grid-cols-3 gap-4 text-sm">
              <div><dt className="text-xs text-muted">Delivery</dt><dd className="font-medium">{current.card.delivery_date ? dateTime(current.card.delivery_date).split(",")[0] : "—"}</dd></div>
              <div><dt className="text-xs text-muted">Order cut-off in</dt><dd className="font-medium">{cutoff(current.card.minutes_to_cutoff)}</dd></div>
              <div><dt className="text-xs text-muted">Signed offer</dt><dd className="font-mono text-xs">{current.card.offer_hash_short}</dd></div>
            </dl>
          </div>
        </Card>
      )}
    </div>
  );
}
