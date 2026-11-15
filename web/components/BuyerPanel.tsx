"use client";
import { useState } from "react";
import { ApiError, api, euro, ORGS, type Org } from "@/lib/api";
import type { Draft, Offer, Order } from "@/lib/types";
import { OfferView } from "./OfferView";
import { Empty, PanelHeader, StateBadge } from "./ui";

const MONDAY = { requested_date: "2026-11-16", latest_acceptable_date: "2026-11-16" };
const SCENARIOS: { emoji: string; label: string; text: string; lines: unknown[] }[] = [
  { emoji: "🥛", label: "Lait 1 000 L", text: "1000 L de lait sans lactose pour lundi, de préférence finlandais",
    lines: [{ line_id: "L1", need: { text: "lactose free milk", required_claims: ["FREE_FROM_LACTOSE"] }, quantity: { value: "1000", unit: "L" }, preferences: { origin: ["fi"] } }] },
  { emoji: "🍅", label: "Tomates 2 500 kg", text: "2500 kg de nos tomates cerises habituelles pour lundi",
    lines: [{ line_id: "L1", need: { text: "cherry tomatoes", product_id: "462545" }, quantity: { value: "2500", unit: "KG" } }] },
  { emoji: "🚨", label: "Lait 3 000 L", text: "3000 L de lait sans lactose pour lundi",
    lines: [{ line_id: "L1", need: { text: "lactose free milk", required_claims: ["FREE_FROM_LACTOSE"] }, quantity: { value: "3000", unit: "L" } }] },
];

export function BuyerPanel({ org, onOrg }: { org: Org; onOrg: (o: Org) => void }) {
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [offer, setOffer] = useState<Offer | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const role = ORGS[org].agent;

  async function guard(label: string, fn: () => Promise<void>) {
    setBusy(label); setError(null);
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? `${e.code} · ${e.message}` : String(e)); }
    finally { setBusy(null); }
  }

  const sendRequest = (lines: unknown[], delivery = MONDAY) => guard("Lookup…", async () => {
    setOffer(null); setOrder(null);
    const rq = await api<{ request_id: string }>(role, "requests", { body: { lines, delivery } });
    setOffer(await api<Offer>(role, `requests/${rq.request_id}/lookup`, { method: "POST" }));
  });

  const interpret = () => guard("Claude lit votre demande…", async () => {
    setDraft(await api<Draft>(role, "interpret", { body: { text } }));
  });

  const place = (choices: Record<string, string>) => guard("Commande…", async () => {
    const selected = Object.entries(choices).map(([line_id, tier]) => ({ line_id, tier }));
    setOrder(await api<Order>(role, "orders", { body: { offer_id: offer!.offer_id, selected }, idempotencyKey: `${offer!.offer_id}-${JSON.stringify(selected)}` }));
  });

  return (
    <section className="card flex min-h-0 flex-col">
      <PanelHeader emoji="🛒" title="Agent acheteur" subtitle="Étapes 1 → 3 · Request, Lookup, Order" accent="bg-grape-soft"
        right={
          <div className="flex rounded-full bg-canvas p-1">
            {(Object.keys(ORGS) as Org[]).map((o) => (
              <button key={o} onClick={() => { onOrg(o); setOffer(null); setOrder(null); setDraft(null); }}
                className={`rounded-full px-3 py-1 text-xs font-bold transition ${org === o ? "bg-white shadow text-ink" : "text-muted"}`}>
                {ORGS[o].emoji} {ORGS[o].label}
              </button>
            ))}
          </div>
        } />
      <div className="scroll-soft min-h-0 flex-1 space-y-4 overflow-auto p-5">
        <div className="flex flex-wrap gap-2">
          {SCENARIOS.map((s) => (
            <button key={s.label} onClick={() => { setText(s.text); setDraft(null); sendRequest(s.lines); }} disabled={!!busy}
              className="btn bg-white text-ink ring-1 ring-grape-soft hover:-translate-y-0.5 hover:ring-grape">
              {s.emoji} {s.label}
            </button>
          ))}
        </div>
        <div className="rounded-2xl bg-canvas p-3">
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2}
            placeholder="« Il me faut 1000 L de lait sans lactose pour lundi… » (fr · en · fi)"
            className="w-full resize-none bg-transparent text-sm outline-none placeholder:text-muted" />
          <div className="flex justify-end">
            <button onClick={interpret} disabled={!text || !!busy} className="btn bg-grape text-white hover:bg-ink">✨ Interpréter avec Claude</button>
          </div>
        </div>

        {busy && <div className="animate-pulse text-sm font-semibold text-grape">⏳ {busy}</div>}
        {error && <div className="animate-pop rounded-2xl bg-tomato-soft p-3 text-sm font-semibold text-tomato">⚠️ {error}</div>}

        {draft && !offer && (
          <div className="animate-pop space-y-2 rounded-2xl bg-sun-soft/60 p-3">
            <div className="text-xs font-bold uppercase tracking-wide text-[#b77400]">Brouillon de demande · hypothèses explicites</div>
            {draft.assumptions.map((a) => <div key={a} className="text-sm">💡 {a}</div>)}
            {draft.questions.map((q) => <div key={q} className="text-sm font-semibold">❓ {q}</div>)}
            <pre className="scroll-soft max-h-28 overflow-auto rounded-xl bg-white/70 p-2 font-mono text-[11px]">{JSON.stringify(draft.lines, null, 1)}</pre>
            <button onClick={() => sendRequest(draft.lines, draft.delivery)} className="btn bg-ink text-white hover:bg-grape">📝 Envoyer la demande</button>
          </div>
        )}

        {offer && !order && <OfferView offer={offer} onOrder={place} busy={!!busy} />}

        {order && (
          <div className="animate-pop space-y-3 rounded-2xl bg-canvas p-4">
            <div className="flex flex-wrap items-center gap-2">
              <StateBadge state={order.state} big />
              {order.order_response && <span className="chip bg-white text-ink ring-1 ring-grape-soft">Peppol {order.order_response.code}</span>}
            </div>
            <div className="text-2xl font-extrabold">{euro(order.total_net)} <span className="text-sm font-semibold text-muted">HT</span></div>
            {order.decision?.rules_fired.map((r) => <div key={r} className="text-sm">⛔ <code className="font-mono text-xs">{r}</code></div>)}
            <div className="font-mono text-[11px] text-muted">{order.order_id}</div>
            <button onClick={() => { setOffer(null); setOrder(null); }} className="btn bg-white text-ink ring-1 ring-grape-soft">↺ Nouvelle demande</button>
          </div>
        )}

        {!offer && !order && !draft && !busy && <Empty emoji="🧺" text="Choisissez un scénario ou écrivez une demande." />}
      </div>
    </section>
  );
}
