"use client";
import { FileText } from "lucide-react";
import { useEffect, useState } from "react";
import {api, dateTime, euro, type OrgProfile } from "@/lib/api";
import type { Order } from "@/lib/types";
import { AuditLog } from "./AuditLog";
import { Badge, Card, Empty, RULE_LABEL, StatusBadge } from "./ui";

export function Requests({ org }: { org: OrgProfile }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    const tick = async () => { try { const o = await api<Order[]>(org.agent, "orders"); if (alive) setOrders(o); } catch { /* retry */ } };
    tick(); const id = setInterval(tick, 3000);
    return () => { alive = false; clearInterval(id); };
  }, [org]);

  return (
    <div className="space-y-5">
      <Card>
        {orders.length === 0 ? <Empty icon={<FileText className="size-5" />} title="No orders yet" text="Orders placed by agents for this organisation appear here." /> : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr className="border-b border-line"><th className="px-5 py-2 font-medium">Order</th><th className="py-2 font-medium">Decided</th><th className="py-2 font-medium">Status</th><th className="py-2 font-medium">Peppol</th><th className="py-2 font-medium">Rules</th><th className="py-2 pr-5 text-right font-medium">Total</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {orders.map((o) => (
                <tr key={o.order_id} onClick={() => setOpen(open === o.order_id ? null : o.order_id)}
                  className={`cursor-pointer hover:bg-page/60 ${open === o.order_id ? "bg-accent-soft/30" : ""}`}>
                  <td className="px-5 py-3 font-mono text-xs">{o.order_id}</td>
                  <td className="py-3 text-muted">{o.lock_until ? dateTime(o.lock_until) : "n/a"}</td>
                  <td className="py-3"><StatusBadge state={o.state} /></td>
                  <td className="py-3">{o.order_response && <Badge>{o.order_response.code}</Badge>}</td>
                  <td className="py-3"><div className="flex flex-wrap gap-1">{o.decision?.rules_fired.slice(0, 2).map((r) => <Badge key={r} tone="warn">{RULE_LABEL[r] ?? r}</Badge>)}</div></td>
                  <td className="py-3 pr-5 text-right font-medium">{euro(o.total_net)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {open && (
        <div className="animate-in">
          <div className="mb-2 text-sm font-semibold">Activity · {open}</div>
          <AuditLog org={org} filter={open} />
        </div>
      )}
    </div>
  );
}
