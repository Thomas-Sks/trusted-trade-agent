"use client";
import { useState } from "react";
import { euro, num } from "@/lib/api";
import type { Candidate, Offer } from "@/lib/types";
import { ChangeChip, StockChip } from "./ui";

const TIER_STYLE: Record<string, { label: string; cls: string; hint: string }> = {
  good: { label: "Good", cls: "bg-sky-soft text-sky", hint: "meilleur prix, contraintes respectées" },
  better: { label: "Better", cls: "bg-grape-soft text-grape", hint: "+ vos préférences" },
  best: { label: "Best", cls: "bg-mint-soft text-mint", hint: "+ qualité (labels, fiabilité, carbone)" },
  split: { label: "Plan mixte", cls: "bg-bubble-soft text-bubble", hint: "partiel + substitut + reliquat" },
};
const EXC: Record<string, string> = {
  PARTIAL_AVAILABILITY: "✂️ dispo partielle", SUBSTITUTED: "🔁 substitution", BACKORDER: "📦 reliquat",
  NO_ELIGIBLE_PRODUCT: "🚫 aucun produit éligible", REQUESTED_PRODUCT_UNAVAILABLE: "🚫 produit demandé indisponible",
};

function CandidateRow({ c }: { c: Candidate }) {
  return (
    <div className="space-y-1.5">
      <div className="text-sm font-bold leading-snug">{c.name}</div>
      <div className="text-xs text-muted">
        {num(c.qty_sales_units)} {c.sales_unit} × {euro(c.unit_net)} · <span className="font-semibold text-ink">{euro(c.line_total_net)} HT</span>
        <span className="ml-1">({euro(c.comparison_net)}/unité de comparaison)</span>
      </div>
      <div className="flex flex-wrap gap-1">
        <StockChip stock={c.stock} />
        {c.partial && <span className="chip bg-tomato-soft text-tomato">✂️ partiel</span>}
        {c.changes_vs_request.map((x) => <ChangeChip key={x} change={x} />)}
        {c.origins.length > 0 && !c.changes_vs_request.some((x) => x.startsWith("origin")) && (
          <span className="chip bg-canvas text-muted">🌍 {c.origins.join("/").toUpperCase()}</span>
        )}
        {c.reliability && <span className="chip bg-canvas text-muted">🚚 {Math.round(Number(c.reliability) * 100)} %</span>}
        {c.carbon_kg_per_kg && <span className="chip bg-canvas text-muted">🌱 {num(c.carbon_kg_per_kg)} kgCO₂e/kg</span>}
      </div>
    </div>
  );
}

export function OfferView({ offer, onOrder, busy }: { offer: Offer; onOrder: (choices: Record<string, string>) => void; busy: boolean }) {
  const initial = Object.fromEntries(offer.lines.map((l) => [l.line_id, l.tiers.better ? "better" : l.tiers.good ? "good" : l.split.length ? "split" : ""]));
  const [choices, setChoices] = useState<Record<string, string>>(initial);
  const [showExcluded, setShowExcluded] = useState(false);
  const ready = Object.values(choices).every(Boolean);
  return (
    <div className="animate-pop space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {offer.ui_signature_verified ? (
          <span className="chip bg-mint-soft text-mint">🔏 signature vérifiée (ES256 · JCS)</span>
        ) : (
          <span className="chip bg-tomato-soft text-tomato">⚠️ signature non vérifiée</span>
        )}
        <span className="chip bg-canvas text-muted">⏱️ valable jusqu&apos;à {new Date(offer.valid_until).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</span>
        {offer.simulated.length > 0 && <span className="chip bg-sun-soft text-[#b77400]">🧪 SIMULÉ : {offer.simulated.join(", ")}</span>}
      </div>
      {offer.lines.map((line) => (
        <div key={line.line_id} className="space-y-2">
          <div className="flex flex-wrap gap-1">{line.exceptions.map((e) => <span key={e} className="chip bg-tomato-soft text-tomato">{EXC[e] ?? e}</span>)}</div>
          {[...Object.entries(line.tiers), ...(line.split.length ? [["split", null] as const] : [])].map(([tier, cand]) => {
            const style = TIER_STYLE[tier];
            const active = choices[line.line_id] === tier;
            return (
              <button key={tier} onClick={() => setChoices({ ...choices, [line.line_id]: tier })}
                className={`w-full rounded-2xl border-2 p-3 text-left transition hover:-translate-y-0.5 ${active ? "border-grape bg-grape-soft/40" : "border-transparent bg-canvas/70"}`}>
                <div className="mb-1.5 flex items-center gap-2">
                  <span className={`chip ${style.cls}`}>{style.label}</span>
                  <span className="text-[11px] text-muted">{style.hint}</span>
                  {active && <span className="ml-auto text-grape">●</span>}
                </div>
                {cand ? <CandidateRow c={cand} /> : (
                  <div className="space-y-2">
                    {line.split.map((c) => <CandidateRow key={c.product_id} c={c} />)}
                    {Number(line.backorder_qty) > 0 && <div className="chip bg-sun-soft text-[#b77400]">📦 reliquat non couvert : {num(line.backorder_qty)}</div>}
                  </div>
                )}
              </button>
            );
          })}
          {line.excluded.length > 0 && (
            <button onClick={() => setShowExcluded(!showExcluded)} className="text-xs font-semibold text-muted hover:text-ink">
              {showExcluded ? "▾" : "▸"} {line.excluded.length} produits écartés, et pourquoi
            </button>
          )}
          {showExcluded && (
            <div className="scroll-soft max-h-36 space-y-0.5 overflow-auto rounded-xl bg-canvas p-2 font-mono text-[11px] text-muted">
              {line.excluded.map((x) => <div key={x.product_id}>{x.product_id} → {x.reason}</div>)}
            </div>
          )}
        </div>
      ))}
      <button disabled={!ready || busy} onClick={() => onOrder(choices)} className="btn w-full justify-center bg-ink py-3 text-white hover:bg-grape">
        🧾 Commander au prix fixe de l&apos;offre
      </button>
    </div>
  );
}
