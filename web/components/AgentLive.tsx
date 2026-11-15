"use client";
import { Bot, BrainCircuit, CheckCircle2, CircleAlert, Cpu, Play, Plug, Radio, Sparkles, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {api, euro, num, type OrgProfile } from "@/lib/api";
import { FlowTracker, type FlowStep } from "./FlowTracker";
import { Badge, Button, Card, RULE_LABEL, StatusBadge } from "./ui";

type Ev = { type: string; text?: string; tool?: string; input?: Record<string, unknown>; result?: unknown; model?: string; tools?: string[] };
type Wire = { id: number; time: number; method: string; path: string; status: number; ms: number; via: string };

const DEFAULT = "We need 1,000 litres of lactose-free milk for Monday, Finnish if possible.";
const STEP_OF: Record<string, string> = { interpret_request: "request", create_request: "request", lookup: "lookup", place_order: "order" };

/* ---------- human-readable tool inputs & results ---------- */
function describeCall(tool: string, input: Record<string, unknown> = {}) {
  if (tool === "interpret_request" || tool === "create_request") {
    if (tool === "interpret_request") return `“${String(input.text ?? "")}”`;
    const lines = (input.lines as { need?: { text?: string; product_id?: string; required_claims?: string[] }; quantity?: { value?: string; unit?: string } }[]) ?? [];
    return lines.map((l) => `${num(l.quantity?.value ?? 0)} ${l.quantity?.unit ?? ""} ${l.need?.product_id ? `product ${l.need.product_id}` : l.need?.text ?? ""}${l.need?.required_claims?.length ? ` · must be ${l.need.required_claims.join(", ").toLowerCase().replaceAll("_", " ")}` : ""}`).join(" + ") + ` · delivery ${String(input.requested_date ?? "")}`;
  }
  if (tool === "lookup") return `request ${String(input.request_id)}`;
  if (tool === "place_order") return `offer ${String(input.offer_id)} · ${Object.entries((input.line_choices as Record<string, string>) ?? {}).map(([l, t]) => `${l} → ${t}`).join(", ")}`;
  return String(input.order_id ?? JSON.stringify(input));
}

function ResultView({ tool, result }: { tool: string; result: unknown }) {
  const r = result as Record<string, unknown>;
  if (r && typeof r === "object" && "error" in r) return <Badge tone="bad">{String(r.error)}: {String(r.detail ?? "")}</Badge>;
  if (tool === "interpret_request") {
    const a = (r.assumptions as string[]) ?? [];
    return <div className="text-xs text-muted">Structured request · {a.length} assumption{a.length !== 1 ? "s" : ""}{a[0] ? ` — e.g. “${a[0]}”` : ""}</div>;
  }
  if (tool === "create_request") return <div className="text-xs text-muted">Request <span className="font-mono">{String(r.request_id)}</span> registered</div>;
  if (tool === "lookup") {
    const line = ((r.lines as Record<string, unknown>[]) ?? [])[0] ?? {};
    const tiers = (line.tiers as Record<string, Record<string, string>>) ?? {};
    const best = tiers.better ?? tiers.good;
    return (
      <div className="space-y-1.5">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone={r.signature_verified ? "ok" : "bad"}>{r.signature_verified ? "Signature verified by the buyer" : "Signature NOT verified"}</Badge>
          <Badge>{Object.keys(tiers).join(" · ") || "no tier"}{(line.split as unknown[])?.length ? " · split plan" : ""}</Badge>
          <Badge>{String(line.excluded_count ?? 0)} excluded</Badge>
          {((line.exceptions as string[]) ?? []).map((e) => <Badge key={e} tone="warn">{e.toLowerCase().replaceAll("_", " ")}</Badge>)}
        </div>
        {best && <div className="text-xs"><span className="font-medium">{best.name}</span> · {num(best.qty_sales_units)} × {euro(best.unit_net)} = <b>{euro(best.line_total_net)}</b></div>}
      </div>
    );
  }
  if (tool === "place_order") {
    const d = r.decision as { rules_fired?: string[] } | undefined;
    const resp = r.order_response as { code?: string } | undefined;
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge state={String(r.state)} />
        <Badge>{euro(String(r.total_net))}</Badge>
        {resp?.code && <Badge>Peppol {resp.code}</Badge>}
        {d?.rules_fired?.map((x) => <Badge key={x} tone="warn">{RULE_LABEL[x] ?? x}</Badge>)}
      </div>
    );
  }
  if (Array.isArray(result)) return <ul className="space-y-0.5 text-xs text-muted">{(result as string[]).map((x, i) => <li key={i}>{x}</li>)}</ul>;
  return <pre className="max-h-24 overflow-auto text-[11px] text-muted">{JSON.stringify(result, null, 1)}</pre>;
}

/* ---------- component ---------- */
export function AgentLive({ org }: { org: OrgProfile }) {
  const [text, setText] = useState(DEFAULT);
  const [events, setEvents] = useState<Ev[]>([]);
  const [running, setRunning] = useState<string | null>(null);
  const [wire, setWire] = useState<Wire[]>([]);
  const [showConsole, setShowConsole] = useState(false);
  const cursor = useRef(0);
  const feed = useRef<HTMLDivElement>(null);

  useEffect(() => {  // protocol wire: poll the gateway trace
    let alive = true;
    cursor.current = 0; setWire([]);
    const tick = async () => {
      try {
        const rows = await api<Wire[]>(org.agent, `trace?after=${cursor.current}`);
        if (alive && rows.length) { cursor.current = rows[rows.length - 1].id; setWire((w) => [...w, ...rows].slice(-120)); }
      } catch { /* gateway restarting */ }
    };
    tick(); const id = setInterval(tick, 700);
    return () => { alive = false; clearInterval(id); };
  }, [org]);

  useEffect(() => { feed.current?.scrollTo({ top: feed.current.scrollHeight, behavior: "smooth" }); }, [events]);

  async function run(kind: "claude" | "bot") {
    setEvents([]); setRunning(kind);
    try {
      const res = await fetch(`/api/agent/${kind}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ org: org.id, text, agent_key: typeof org.agent === "string" ? undefined : org.agent.key }) });
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n"); buf = lines.pop() ?? "";
        for (const l of lines) if (l.trim()) setEvents((e) => [...e, JSON.parse(l)]);
      }
    } catch (e) {
      setEvents((ev) => [...ev, { type: "error", text: String(e) }]);
    } finally { setRunning(null); }
  }

  // flow tracker from the agent's own actions
  const called = new Set(events.filter((e) => e.type === "tool_call").map((e) => STEP_OF[e.tool ?? ""]));
  const order = events.find((e) => e.type === "tool_result" && e.tool === "place_order")?.result as { state?: string } | undefined;
  const lookupDone = events.some((e) => e.type === "tool_result" && e.tool === "lookup");
  const state = (k: string, done: boolean): FlowStep["state"] => (done ? "done" : called.has(k) ? "active" : "todo");
  const approval: FlowStep["state"] = !order ? "todo" : ["AUTO_APPROVED", "APPROVED"].includes(order.state ?? "") ? "done" : order.state === "PENDING_HUMAN" ? "waiting" : "blocked";
  const steps: FlowStep[] = [
    { key: "request", label: "Request", state: state("request", called.has("lookup")), detail: "interpret · create_request" },
    { key: "lookup", label: "Lookup", state: state("lookup", lookupDone), detail: "signed offer" },
    { key: "order", label: "Order", state: state("order", !!order), detail: "place_order" },
    { key: "approval", label: "Approval", state: approval, detail: order?.state ? order.state.replaceAll("_", " ").toLowerCase() : "mandate · human" },
  ];
  const shownWire = wire.filter((w) => showConsole || !w.via.startsWith("web"));

  return (
    <div className="space-y-5">
      <Card className="px-6 py-5"><FlowTracker steps={steps} /></Card>
      <div className="grid gap-5 lg:grid-cols-[300px_1fr_380px]">
        <Card className="h-fit space-y-4 p-5">
          <div>
            <div className="font-semibold">Run a buying agent</div>
            <div className="text-xs text-muted">Buyer side · {org.label}</div>
          </div>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4}
            className="w-full resize-none rounded-lg border border-line p-3 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-accent/10" />
          <Button className="w-full" disabled={!!running} onClick={() => run("claude")}><Sparkles className="size-4" />{running === "claude" ? "Agent working…" : "Run Claude agent (MCP)"}</Button>
          <Button className="w-full" variant="secondary" disabled={!!running} onClick={() => run("bot")}><Cpu className="size-4" />{running === "bot" ? "Bot working…" : "Run replenishment bot (REST)"}</Button>
          <p className="text-xs text-muted">Same protocol, two very different clients: an LLM over MCP and a plain script over REST. Both are governed by the same mandate.</p>
        </Card>

        <Card className="flex min-h-[520px] flex-col">
          <div className="flex items-center gap-2 border-b border-line px-5 py-3 text-sm font-semibold"><Bot className="size-4 text-accent" />Agent
            {running && <span className="ml-auto flex items-center gap-1.5 text-xs font-normal text-accent"><span className="size-2 animate-ping rounded-full bg-accent" />live</span>}</div>
          <div ref={feed} className="flex-1 space-y-3 overflow-auto p-5" style={{ maxHeight: 560 }}>
            {events.length === 0 && <div className="grid h-full place-items-center text-sm text-muted">Press “Run” to watch the agent act.</div>}
            {events.map((e, i) => {
              if (e.type === "start") return <div key={i} className="animate-in flex items-center gap-2 text-xs text-muted"><Plug className="size-3.5" />{e.model} connected · tools: {e.tools?.join(", ")}</div>;
              if (e.type === "thinking") return <div key={i} className="animate-in flex gap-2 rounded-lg bg-page px-3 py-2 text-xs italic text-muted"><BrainCircuit className="mt-0.5 size-3.5 shrink-0" />{e.text}</div>;
              if (e.type === "tool_call") return (
                <div key={i} className="animate-in rounded-lg border border-accent/25 bg-accent-soft/30 px-3 py-2.5">
                  <div className="flex items-center gap-2 text-xs"><Wrench className="size-3.5 text-accent" /><Badge tone="accent">MCP tool</Badge><span className="font-mono font-semibold">{e.tool}</span></div>
                  <div className="mt-1 text-sm">{describeCall(e.tool ?? "", e.input)}</div>
                </div>
              );
              if (e.type === "tool_result") return (
                <div key={i} className="animate-in ml-5 border-l-2 border-ok/40 pl-3"><div className="mb-1 flex items-center gap-1 text-[11px] font-medium text-ok"><CheckCircle2 className="size-3" />{e.tool} returned</div><ResultView tool={e.tool ?? ""} result={e.result} /></div>
              );
              if (e.type === "error") return <div key={i} className="animate-in flex gap-2 rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad"><CircleAlert className="mt-0.5 size-4" />{e.text}</div>;
              if (e.type === "text") return <div key={i} className="animate-in whitespace-pre-wrap rounded-lg bg-white px-3 py-2.5 text-sm ring-1 ring-line">{e.text}</div>;
              return null;
            })}
          </div>
        </Card>

        <Card className="flex min-h-[520px] flex-col">
          <div className="flex items-center gap-2 border-b border-line px-5 py-3 text-sm font-semibold"><Radio className="size-4 text-info" />Protocol wire
            <label className="ml-auto flex items-center gap-1.5 text-xs font-normal text-muted"><input type="checkbox" checked={showConsole} onChange={(e) => setShowConsole(e.target.checked)} />console traffic</label></div>
          <div className="flex-1 space-y-1 overflow-auto p-3 font-mono text-[11px]" style={{ maxHeight: 560 }}>
            {shownWire.length === 0 && <div className="p-4 text-center font-sans text-sm text-muted">Gateway calls appear here as they happen.</div>}
            {[...shownWire].reverse().map((w) => (
              <div key={w.id} className="animate-in flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-page">
                <span className={`w-11 rounded px-1 text-center font-semibold ${w.method === "GET" ? "bg-info-soft text-info" : "bg-accent-soft text-accent"}`}>{w.method}</span>
                <span className="min-w-0 flex-1 truncate">{w.path}</span>
                <span className={w.status < 300 ? "text-ok" : w.status < 500 ? "text-warn" : "text-bad"}>{w.status}</span>
                <span className="w-12 text-right text-muted">{w.ms}ms</span>
                <span className={`max-w-[170px] shrink-0 truncate rounded px-1.5 py-0.5 ${w.via.startsWith("mcp") ? "bg-accent-soft text-accent" : w.via.startsWith("web") ? "bg-page text-muted" : "bg-warn-soft text-warn"}`}>
                  {w.via.startsWith("mcp:") ? `MCP · ${w.via.slice(4)}` : w.via.startsWith("rest:") ? `REST · ${w.via.slice(5)}` : w.via}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
