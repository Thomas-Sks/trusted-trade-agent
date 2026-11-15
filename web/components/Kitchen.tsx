"use client";
import { Bot, BrainCircuit, ChefHat, CircleAlert, Cpu, RotateCcw, Sparkles, Utensils, Wrench } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { euro, num, type OrgProfile } from "@/lib/api";
import { describeCall, ResultView, type Ev } from "./AgentLive";
import { Badge, Button, Card, RULE_LABEL } from "./ui";

type OrderView = { order_id: string; state: string; total_net: string; rules_fired: string[]; approved_by?: string | null };
type Item = {
  key: string; label: string; category: string; product_id: string; unit: string;
  on_hand: number; reorder_point: number; par: number; low: boolean; order_quantity: number; order: OrderView | null;
};
type State = { items: Item[]; services: number; orders: OrderView[] };

const ident = (org: OrgProfile) => ({ org: org.id, agent_key: typeof org.agent === "string" ? undefined : org.agent.key });

async function kitchen<T>(org: OrgProfile, action: string): Promise<T> {
  const res = await fetch(`/api/kitchen/${action}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(ident(org)) });
  if (!res.ok) throw new Error(`kitchen ${action}: ${res.status}`);
  return res.json();
}

function status(it: Item): { tone: "ok" | "warn" | "bad" | "accent" | "neutral"; text: string } {
  const o = it.order;
  if (o?.state === "AUTO_APPROVED") return { tone: "ok", text: `Ordered ${num(it.order_quantity)} ${it.unit} · auto-approved` };
  if (o?.state === "APPROVED") return { tone: "ok", text: `Ordered · approved by ${o.approved_by ?? "a human"}` };
  if (o?.state === "PENDING_HUMAN") return { tone: "warn", text: `Waiting for approval · ${o.rules_fired.map((r) => RULE_LABEL[r] ?? r).join(", ")}` };
  if (o && ["REJECTED", "DENIED", "EXPIRED"].includes(o.state)) return { tone: "bad", text: `${o.state.toLowerCase()} — not coming` };
  if (it.low) return { tone: "bad", text: `Low · needs ${num(it.order_quantity)} ${it.unit}` };
  return { tone: "neutral", text: "OK" };
}

function StockBar({ it }: { it: Item }) {
  const max = Math.max(it.par, it.on_hand) || 1;
  const incoming = it.order && ["AUTO_APPROVED", "APPROVED"].includes(it.order.state) ? it.order_quantity : 0;
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-page ring-1 ring-line">
      <div className={`absolute inset-y-0 left-0 rounded-full ${it.low ? "bg-bad/70" : "bg-ok/70"}`} style={{ width: `${(it.on_hand / max) * 100}%` }} />
      {incoming > 0 && <div className="absolute inset-y-0 rounded-full bg-ok/25" style={{ left: `${(it.on_hand / max) * 100}%`, width: `${(incoming / max) * 100}%` }} />}
      <div className="absolute inset-y-0 w-0.5 bg-ink/40" style={{ left: `${(it.reorder_point / max) * 100}%` }} title="reorder point" />
    </div>
  );
}

export function Kitchen({ org }: { org: OrgProfile }) {
  const [state, setState] = useState<State | null>(null);
  const [events, setEvents] = useState<Ev[]>([]);
  const [running, setRunning] = useState<"claude" | "bot" | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const feed = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => { try { setState(await kitchen<State>(org, "state")); } catch { /* agent service restarting */ } }, [org]);
  useEffect(() => { refresh(); const id = setInterval(refresh, 2000); return () => clearInterval(id); }, [refresh]);
  useEffect(() => { feed.current?.scrollTo({ top: feed.current.scrollHeight, behavior: "smooth" }); }, [events]);

  async function service() {
    const r = await kitchen<{ used: string[] }>(org, "service");
    setNote(`Dinner service done: ${r.used.slice(0, 4).join(" · ")}…`);
    refresh();
  }
  async function reset() { await kitchen(org, "reset"); setEvents([]); setNote(null); refresh(); }

  async function restock(mode: "claude" | "bot") {
    setEvents([]); setNote(null); setRunning(mode);
    try {
      const res = await fetch("/api/agent/kitchen", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ ...ident(org), mode }) });
      if (!res.ok) { const e = await res.json().catch(() => ({})); setEvents([{ type: "error", text: e.detail ?? `Agent service error (${res.status})` }]); return; }
      const reader = res.body!.getReader(); const decoder = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await reader.read(); if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n"); buf = lines.pop() ?? "";
        for (const l of lines) if (l.trim()) { const e = JSON.parse(l) as Ev; if (e.type !== "done") setEvents((x) => [...x, e]); if (e.type === "tool_result") refresh(); }
      }
    } catch (e) { setEvents((x) => [...x, { type: "error", text: String(e) }]); } finally { setRunning(null); refresh(); }
  }

  const orders = state?.orders ?? [];
  const auto = orders.filter((o) => o.state === "AUTO_APPROVED").length;
  const waiting = orders.filter((o) => o.state === "PENDING_HUMAN");
  const approved = orders.filter((o) => o.state === "APPROVED").length;
  const cats = [...new Set((state?.items ?? []).map((i) => i.category))];

  return (
    <div className="space-y-5">
      <Card className="flex flex-wrap items-center gap-4 px-6 py-5">
        <div className="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent"><ChefHat className="size-6" /></div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold">{org.label.replace(" (demo)", "")} — kitchen</div>
          <div className="text-sm text-muted">The inventory belongs to the restaurant. Its agent restocks what runs low; Valio&apos;s mandate engine decides every order, and only the exceptions reach a human.</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={!!running} onClick={service}><Utensils className="size-4" />Dinner service</Button>
          <Button disabled={!!running} onClick={() => restock("claude")}><Sparkles className="size-4" />{running === "claude" ? "Claude is restocking…" : "Restock with Claude"}</Button>
          <Button variant="secondary" disabled={!!running} onClick={() => restock("bot")}><Cpu className="size-4" />{running === "bot" ? "Restocking…" : "Rule-based (no AI)"}</Button>
          <Button variant="ghost" disabled={!!running} onClick={reset}><RotateCcw className="size-4" />Reset</Button>
        </div>
      </Card>

      {orders.length > 0 && (
        <div className="animate-in grid gap-3 sm:grid-cols-3">
          <Card className="px-5 py-4"><div className="text-xs text-muted">Orders placed by the agent</div><div className="text-2xl font-semibold">{orders.length}</div></Card>
          <Card className="px-5 py-4"><div className="text-xs text-muted">Without a human</div><div className="text-2xl font-semibold text-ok">{auto}<span className="text-base font-normal text-muted"> / {orders.length}</span></div></Card>
          <Card className="px-5 py-4"><div className="text-xs text-muted">Needed a human</div>
            <div className="text-2xl font-semibold text-warn">{waiting.length + approved}</div>
            {waiting.length > 0 && <div className="text-xs text-warn">{waiting.length} waiting — Approvals tab{org.pairing ? " or Telegram" : ""}</div>}
          </Card>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[1fr_440px]">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-3 text-sm font-semibold">
            <span>Inventory</span>
            <span className="text-xs font-normal text-muted">{state ? `${state.items.filter((i) => i.low).length} low · ${state.services} service${state.services !== 1 ? "s" : ""} since reset` : "…"}</span>
          </div>
          {note && <div className="border-b border-line bg-page px-5 py-2 text-xs text-muted">{note}</div>}
          {cats.map((cat) => (
            <div key={cat}>
              <div className="bg-page/60 px-5 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">{cat}</div>
              {state!.items.filter((i) => i.category === cat).map((it) => {
                const s = status(it);
                return (
                  <div key={it.key} className={`grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 border-b border-line px-5 py-2.5 transition sm:grid-cols-[180px_1fr_auto] ${it.order ? "bg-accent-soft/20" : ""}`}>
                    <div className="text-sm font-medium">{it.label}<div className="text-[11px] font-normal text-muted">{num(it.on_hand)} / {num(it.par)} {it.unit} · reorder at {num(it.reorder_point)}</div></div>
                    <div className="order-3 col-span-2 sm:order-none sm:col-span-1"><StockBar it={it} /></div>
                    <Badge tone={s.tone}>{s.text}</Badge>
                  </div>
                );
              })}
            </div>
          ))}
        </Card>

        <Card className="flex min-h-[520px] flex-col">
          <div className="flex items-center gap-2 border-b border-line px-5 py-3 text-sm font-semibold"><Bot className="size-4 text-accent" />Restock agent
            {running && <span className="ml-auto flex items-center gap-1.5 text-xs font-normal text-accent"><span className="size-2 animate-ping rounded-full bg-accent" />live</span>}</div>
          <div ref={feed} className="flex-1 space-y-3 overflow-auto p-5" style={{ maxHeight: 640 }}>
            {events.length === 0 && <div className="grid h-full place-items-center text-center text-sm text-muted">Run a dinner service, then let the agent restock.<br />Every check and order appears here.</div>}
            {events.map((e, i) => {
              if (e.type === "start") return <div key={i} className="text-xs text-muted">{e.model} · tools: {e.tools?.join(", ")}</div>;
              if (e.type === "thinking") return <div key={i} className="animate-in flex gap-2 rounded-lg bg-page px-3 py-2 text-xs italic text-muted"><BrainCircuit className="mt-0.5 size-3.5 shrink-0" />{e.text}</div>;
              if (e.type === "tool_call") return (
                <div key={i} className="animate-in rounded-lg border border-accent/25 bg-accent-soft/30 px-3 py-2">
                  <div className="flex items-center gap-2 text-xs"><Wrench className="size-3.5 text-accent" /><span className="font-mono font-semibold">{e.tool}</span></div>
                  <div className="mt-0.5 text-xs">{describeCall(e.tool ?? "", e.input)}</div>
                </div>
              );
              if (e.type === "tool_result") return <div key={i} className="animate-in ml-4 border-l-2 border-ok/40 pl-3"><ResultView tool={e.tool ?? ""} result={e.result} /></div>;
              if (e.type === "error") return <div key={i} className="animate-in flex gap-2 rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad"><CircleAlert className="mt-0.5 size-4" />{e.text}</div>;
              if (e.type === "text") return <div key={i} className="animate-in whitespace-pre-wrap rounded-lg bg-white px-3 py-2 text-sm ring-1 ring-line">{e.text}</div>;
              return null;
            })}
          </div>
          {orders.length > 0 && (
            <div className="space-y-1 border-t border-line px-5 py-3 text-xs">
              {orders.map((o) => (
                <div key={o.order_id} className="flex items-center gap-2"><span className="font-mono text-muted">{o.order_id}</span><span className="ml-auto">{euro(o.total_net)}</span>
                  <Badge tone={o.state === "PENDING_HUMAN" ? "warn" : ["AUTO_APPROVED", "APPROVED"].includes(o.state) ? "ok" : "bad"}>{o.state.replaceAll("_", " ").toLowerCase()}</Badge></div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
