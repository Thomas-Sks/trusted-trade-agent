"use client";
import { ArrowRight, CheckCircle2, Clock3, FileSignature, Lock, RotateCcw, Sparkles, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError, api, dateTime, euro, num, ORGS, type Org } from "@/lib/api";
import type { Draft, Offer, Order } from "@/lib/types";
import { FlowTracker, type FlowStep } from "./FlowTracker";
import { OfferLineView } from "./OfferCard";
import { Badge, Button, Card, RULE_LABEL, StatusBadge } from "./ui";

const MONDAY = { requested_date: "2026-11-16", latest_acceptable_date: "2026-11-16" };
const QUICK = [
  { title: "Lactose-free milk", text: "1,000 L for Monday, Finnish preferred", lines: [{ line_id: "L1", need: { text: "lactose free milk", required_claims: ["FREE_FROM_LACTOSE"] }, quantity: { value: "1000", unit: "L" }, preferences: { origin: ["fi"] } }] },
  { title: "Cherry tomatoes", text: "2,500 kg of our usual product", lines: [{ line_id: "L1", need: { text: "cherry tomatoes", product_id: "462545" }, quantity: { value: "2500", unit: "KG" } }] },
  { title: "Large milk order", text: "3,000 L, above the order limit", lines: [{ line_id: "L1", need: { text: "lactose free milk", required_claims: ["FREE_FROM_LACTOSE"] }, quantity: { value: "3000", unit: "L" } }] },
];
const PEPPOL: Record<string, string> = { AP: "Accepted as requested", CA: "Accepted with changes", RE: "Rejected", AB: "Acknowledged" };

type Line = { line_id: string; need: { text: string; product_id?: string | null; required_claims?: string[] }; quantity: { value: string; unit: string }; preferences?: { origin?: string[] } };

function describe(l: Line) {
  const parts = [`${num(l.quantity.value)} ${l.quantity.unit} · ${l.need.product_id ? `product ${l.need.product_id}` : l.need.text}`];
  if (l.need.required_claims?.length) parts.push(`must be ${l.need.required_claims.map((c) => c.toLowerCase().replaceAll("_", " ")).join(", ")}`);
  if (l.preferences?.origin?.length) parts.push(`prefers ${l.preferences.origin.join("/").toUpperCase()}`);
  return parts.join(" — ");
}

export function NewRequest({ org }: { org: Org }) {
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<{ lines: Line[]; delivery: typeof MONDAY; assumptions: string[]; questions: string[] } | null>(null);
  const [offer, setOffer] = useState<Offer | null>(null);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [order, setOrder] = useState<Order | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const role = ORGS[org].agent;

  useEffect(() => { reset(); }, [org]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (order?.state !== "PENDING_HUMAN") return;
    const id = setInterval(async () => { try { setOrder(await api<Order>(role, `orders/${order.order_id}`)); } catch { /* keep polling */ } }, 2000);
    return () => clearInterval(id);
  }, [order?.state, order?.order_id, role]);

  function reset() { setText(""); setDraft(null); setOffer(null); setOrder(null); setError(null); }
  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label); setError(null);
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? `${e.code}: ${e.message}` : String(e)); } finally { setBusy(null); }
  }
  const lookup = (lines: Line[], delivery = MONDAY) => run("Searching the catalogue and checking live price & stock…", async () => {
    const rq = await api<{ request_id: string }>(role, "requests", { body: { lines, delivery } });
    const o = await api<Offer>(role, `requests/${rq.request_id}/lookup`, { method: "POST" });
    setOffer(o);
    setChoices(Object.fromEntries(o.lines.map((l) => [l.line_id, l.tiers.better ? "better" : l.tiers.good ? "good" : "split"])));
  });
  const interpret = () => run("Claude is reading your request…", async () => setDraft(await api<Draft>(role, "interpret", { body: { text } }) as never));
  const place = () => run("Placing the order at the locked price…", async () => {
    const selected = Object.entries(choices).map(([line_id, tier]) => ({ line_id, tier }));
    setOrder(await api<Order>(role, "orders", { body: { offer_id: offer!.offer_id, selected }, idempotencyKey: `${offer!.offer_id}:${JSON.stringify(selected)}` }));
  });

  const phase = order ? "result" : offer ? "offer" : "compose";
  const total = order ? euro(order.total_net) : undefined;
  const approvalState = !order ? "todo" : ["AUTO_APPROVED", "APPROVED"].includes(order.state) ? "done" : order.state === "PENDING_HUMAN" ? "waiting" : "blocked";
  const steps: FlowStep[] = [
    { key: "request", label: "Request", state: phase === "compose" ? "active" : "done", detail: phase === "compose" ? "Describe the need" : "Structured need" },
    { key: "lookup", label: "Lookup", state: phase === "compose" ? "todo" : phase === "offer" ? "active" : "done", detail: offer ? (offer.ui_signature_verified ? "Signed offer verified" : "Signature NOT verified") : "Price & availability" },
    { key: "order", label: "Order", state: phase === "result" ? "done" : "todo", detail: total ? `${total} locked` : "Fixed price" },
    { key: "approval", label: "Approval", state: approvalState as FlowStep["state"],
      detail: !order ? "Mandate or human" : order.state === "PENDING_HUMAN" ? `Waiting for ${ORGS[org].approverName}` : order.approved_by ? `By ${order.approved_by}` : order.state === "AUTO_APPROVED" ? "Within mandate" : order.state.toLowerCase() },
  ];

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Card className="px-6 py-6"><FlowTracker steps={steps} /></Card>

      {error && <div className="animate-in rounded-lg bg-bad-soft px-4 py-3 text-sm text-bad">{error}</div>}
      {busy && <div className="flex animate-in items-center gap-2 text-sm text-muted"><span className="size-2 animate-ping rounded-full bg-accent" />{busy}</div>}

      {phase === "compose" && (
        <Card className="animate-in space-y-5 p-6">
          <div>
            <h2 className="text-lg font-semibold">What do you need?</h2>
            <p className="text-sm text-muted">Describe it in any language. The agent turns it into a structured request; the wholesaler&apos;s mandate decides.</p>
          </div>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3}
            placeholder="e.g. We need 1,000 litres of lactose-free milk by Monday, Finnish if possible."
            className="w-full resize-none rounded-lg border border-line p-3 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-accent/10" />
          {!draft ? (
            <div className="flex justify-end"><Button onClick={interpret} disabled={!text || !!busy}><Sparkles className="size-4" />Interpret request</Button></div>
          ) : (
            <div className="animate-in space-y-3 rounded-lg bg-page p-4">
              <div className="text-xs font-medium uppercase tracking-wider text-muted">Structured request</div>
              {draft.lines.map((l) => <div key={l.line_id} className="text-sm font-medium">{describe(l)}</div>)}
              {[...draft.assumptions, ...draft.questions].length > 0 && (
                <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted">
                  {draft.assumptions.map((a) => <li key={a}>{a}</li>)}
                  {draft.questions.map((q) => <li key={q} className="text-warn">{q}</li>)}
                </ul>
              )}
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setDraft(null)}>Edit</Button>
                <Button onClick={() => lookup(draft.lines, draft.delivery)} disabled={!!busy}>Find offers <ArrowRight className="size-4" /></Button>
              </div>
            </div>
          )}
          <div>
            <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">Or start from a scenario</div>
            <div className="grid gap-2 sm:grid-cols-3">
              {QUICK.map((q) => (
                <button key={q.title} onClick={() => lookup(q.lines as Line[])} disabled={!!busy}
                  className="rounded-lg border border-line p-3 text-left transition hover:border-accent hover:bg-accent-soft/30 disabled:opacity-40">
                  <div className="text-sm font-semibold">{q.title}</div>
                  <div className="text-xs text-muted">{q.text}</div>
                </button>
              ))}
            </div>
          </div>
        </Card>
      )}

      {phase === "offer" && offer && (
        <Card className="animate-in space-y-5 p-6">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold">Recommended offer</h2>
              <p className="text-sm text-muted">Fixed prices from Valio Aimo, signed by the wholesaler.</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Badge tone={offer.ui_signature_verified ? "ok" : "bad"} icon={<FileSignature className="size-3" />}>{offer.ui_signature_verified ? "Signature verified" : "Signature invalid"}</Badge>
              <Badge icon={<Clock3 className="size-3" />}>Valid until {dateTime(offer.valid_until)}</Badge>
              {offer.simulated.length > 0 && <Badge tone="warn">Simulated: {offer.simulated.join(", ")}</Badge>}
            </div>
          </div>
          {offer.lines.map((line) => (
            <OfferLineView key={line.line_id} line={line} choice={choices[line.line_id]} onChoose={(t) => setChoices({ ...choices, [line.line_id]: t })} />
          ))}
          <div className="flex items-center justify-between border-t border-line pt-4">
            <Button variant="ghost" onClick={reset}><RotateCcw className="size-4" />Start over</Button>
            <Button onClick={place} disabled={!!busy || !offer.ui_signature_verified}><Lock className="size-4" />Place order at this price</Button>
          </div>
        </Card>
      )}

      {phase === "result" && order && (
        <Card className="animate-in overflow-hidden">
          <div className={`flex items-center gap-4 px-6 py-5 ${approvalState === "done" ? "bg-ok-soft" : approvalState === "waiting" ? "bg-warn-soft" : "bg-bad-soft"}`}>
            {approvalState === "done" ? <CheckCircle2 className="size-8 text-ok" /> : approvalState === "waiting" ? <Clock3 className="size-8 text-warn" /> : <XCircle className="size-8 text-bad" />}
            <div>
              <div className="text-lg font-semibold">
                {order.state === "AUTO_APPROVED" ? "Order auto-approved" : order.state === "APPROVED" ? `Approved by ${order.approved_by}` :
                  order.state === "PENDING_HUMAN" ? `Waiting for ${ORGS[org].approverName}'s approval` : order.state === "DENIED" ? "Denied by the mandate" : `Order ${order.state.toLowerCase()}`}
              </div>
              <div className="text-sm text-muted">
                {order.state === "PENDING_HUMAN" ? "Sent to the web console and Telegram. The price stays locked meanwhile." :
                  approvalState === "done" ? "Ready to be transmitted to Valio Aimo." : order.rejection_reason ?? "No order will be transmitted."}
              </div>
            </div>
            <div className="ml-auto text-right">
              <div className="text-2xl font-semibold">{euro(order.total_net)}</div>
              <div className="text-xs text-muted">excl. VAT</div>
            </div>
          </div>
          <div className="grid gap-4 p-6 sm:grid-cols-3">
            <div><div className="text-xs text-muted">Status</div><StatusBadge state={order.state} /></div>
            <div><div className="text-xs text-muted">Order response (Peppol)</div>
              <div className="text-sm font-medium">{order.order_response ? `${order.order_response.code} · ${PEPPOL[order.order_response.code]}` : "—"}</div></div>
            <div><div className="text-xs text-muted">Price locked until</div><div className="text-sm font-medium">{order.lock_until ? dateTime(order.lock_until) : "—"}</div></div>
            {order.decision && order.decision.rules_fired.length > 0 && (
              <div className="sm:col-span-3">
                <div className="mb-1.5 text-xs text-muted">Why a human is needed</div>
                <div className="flex flex-wrap gap-1.5">{order.decision.rules_fired.map((r) => <Badge key={r} tone="warn">{RULE_LABEL[r] ?? r}</Badge>)}</div>
              </div>
            )}
          </div>
          <div className="flex justify-between border-t border-line px-6 py-4">
            <span className="font-mono text-xs text-muted">{order.order_id}</span>
            <Button variant="secondary" onClick={reset}><RotateCcw className="size-4" />New request</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
