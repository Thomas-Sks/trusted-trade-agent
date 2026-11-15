"use client";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useState } from "react";
import { api, euro, num, ORGS, type Org } from "@/lib/api";
import type { ApprovalCard, Order } from "@/lib/types";
import { ChangeChip, Empty, PanelHeader, StockChip } from "./ui";

const BOT = process.env.NEXT_PUBLIC_TELEGRAM_BOT;

function duration(min: number | null) {
  if (min === null) return null;
  if (min < 0) return "dépassée";
  const d = Math.floor(min / 1440), h = Math.floor((min % 1440) / 60), m = min % 60;
  return d ? `${d} j ${h} h` : h ? `${h} h ${String(m).padStart(2, "0")}` : `${m} min`;
}

function Card({ order, card, org, onDone }: { order: Order; card: ApprovalCard; org: Org; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const act = async (verb: "approve" | "reject") => {
    setBusy(true);
    try {
      await api(ORGS[org].approver, `orders/${order.order_id}/${verb}`,
        { body: verb === "approve" ? { expected_version: order.version } : { expected_version: order.version, reason: "Refusée depuis la console web" } });
    } finally { setBusy(false); onDone(); }
  };
  return (
    <div className="animate-pop space-y-3 rounded-3xl bg-gradient-to-br from-sun-soft to-bubble-soft p-4 ring-1 ring-sun/30">
      <div className="flex items-center justify-between">
        <div className="text-sm font-extrabold">🟠 Validation requise</div>
        <code className="font-mono text-[11px] text-muted">{order.order_id}</code>
      </div>
      <div>
        <div className="mb-1 text-[11px] font-bold uppercase tracking-wide text-muted">Pourquoi</div>
        {card.reasons.map((r) => <div key={r} className="text-sm font-semibold">⛔ {r}</div>)}
      </div>
      <div className="space-y-2">
        {card.lines.map((l, i) => (
          <div key={i} className="rounded-2xl bg-white/80 p-2.5">
            <div className="text-sm font-bold leading-snug">📦 {l.name}</div>
            <div className="text-xs text-muted">{num(l.qty_sales_units)} {l.sales_unit} × {euro(l.unit_net)} → <b className="text-ink">{euro(l.line_total_net)}</b></div>
            <div className="mt-1 flex flex-wrap gap-1">
              <StockChip stock={l.stock} />
              {l.partial && <span className="chip bg-tomato-soft text-tomato">✂️ partiel</span>}
              {l.vs_usual && <span className="chip bg-grape-soft text-grape">📈 {l.vs_usual}</span>}
              {l.changes.map((c) => <ChangeChip key={c} change={c} />)}
            </div>
          </div>
        ))}
      </div>
      {card.warnings.map((w) => <div key={w} className="text-xs font-semibold text-[#b77400]">⚠️ {w}</div>)}
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <div className="text-xl font-extrabold">{euro(card.total_net)} <span className="text-xs text-muted">HT · {euro(card.total_gross)} TTC</span></div>
          <div className="text-xs text-muted">🚚 {card.delivery_date} · ⏰ {duration(card.minutes_to_cutoff)} · 🔏 {card.offer_hash_short}</div>
        </div>
        <div className="flex gap-2">
          <button disabled={busy} onClick={() => act("reject")} className="btn bg-white text-tomato ring-1 ring-tomato/30 hover:bg-tomato-soft">❌ Refuser</button>
          <button disabled={busy} onClick={() => act("approve")} className="btn bg-mint text-white hover:bg-ink">✅ Approuver</button>
        </div>
      </div>
      {card.step_up_required && <div className="text-xs font-semibold text-grape">🔐 Montant élevé : la console web est le canal de validation renforcée.</div>}
    </div>
  );
}

export function ApprovalsPanel({ org }: { org: Org }) {
  const [items, setItems] = useState<{ order: Order; card: ApprovalCard }[]>([]);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const pending = await api<Order[]>(ORGS[org].approver, "approvals");
        const withCards = await Promise.all(pending.map(async (order) =>
          ({ order, card: await api<ApprovalCard>(ORGS[org].approver, `orders/${order.order_id}/card`) })));
        if (alive) setItems(withCards);
      } catch { /* gateway restarting */ }
    };
    load();
    const id = setInterval(load, 2500);
    return () => { alive = false; clearInterval(id); };
  }, [org, tick]);

  const pairing = `https://t.me/${BOT}?start=${ORGS[org].pairing}`;
  return (
    <section className="card flex min-h-0 flex-col">
      <PanelHeader emoji="👩‍🍳" title="Approbations" subtitle={`Étape 4 · ${ORGS[org].approverName} · mandat Cedar`} accent="bg-sun-soft"
        right={<span className="chip bg-sun-soft text-[#b77400]">{items.length} en attente</span>} />
      <div className="scroll-soft min-h-0 flex-1 space-y-3 overflow-auto p-5">
        {items.length === 0 && <Empty emoji="🌤️" text="Rien à valider : l'agent reste dans son mandat." />}
        {items.map(({ order, card }) => <Card key={`${order.order_id}-${order.version}`} order={order} card={card} org={org} onDone={() => setTick((t) => t + 1)} />)}
        {BOT && (
          <div className="flex items-center gap-4 rounded-3xl bg-sky-soft/70 p-4">
            <div className="rounded-2xl bg-white p-2"><QRCodeSVG value={pairing} size={84} fgColor="#1e1b3a" /></div>
            <div className="text-sm">
              <div className="font-extrabold">📱 Valider depuis Telegram</div>
              <div className="text-xs text-muted">Scannez pour appairer {ORGS[org].approverName} à @{BOT}. Les cartes arrivent avec des boutons signés à usage unique.</div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
