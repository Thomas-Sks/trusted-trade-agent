"use client";
import { AlertTriangle, ChevronDown, Leaf, MapPin, PackageCheck, ShieldCheck, Truck } from "lucide-react";
import { useState } from "react";
import { euro, num } from "@/lib/api";
import type { Candidate, OfferLine } from "@/lib/types";
import { Badge } from "./ui";

const TIER: Record<string, { label: string; hint: string }> = {
  good: { label: "Good", hint: "Lowest price meeting your constraints" },
  better: { label: "Better", hint: "Also matches your preferences" },
  best: { label: "Best", hint: "Preferences + quality (labels, reliability, carbon)" },
  split: { label: "Mixed plan", hint: "Available stock + substitute + backorder" },
};
const EXCEPTION: Record<string, string> = {
  PARTIAL_AVAILABILITY: "Only part of the requested quantity is in stock.",
  SUBSTITUTED: "An official Valio substitute completes the order.",
  BACKORDER: "Part of the quantity cannot be delivered on time.",
  NO_ELIGIBLE_PRODUCT: "No product meets the hard constraints.",
  REQUESTED_PRODUCT_UNAVAILABLE: "The requested product is unavailable.",
};

function changeLabel(c: string) {
  const [k, v] = c.split(":");
  return k === "origin" ? `Origin ${v.toUpperCase()}` : k === "substitute" ? `Substitute for ${v}` : k === "brand" ? `Brand ${v}` : c;
}

function Trust({ c }: { c: Candidate }) {
  const verified = c.stock.startsWith("VERIFIED");
  return (
    <div className="flex flex-wrap gap-1.5">
      <Badge tone={verified ? "ok" : "warn"} icon={<PackageCheck className="size-3" />}>{verified ? "Stock verified" : "Supplier stock unverified"}</Badge>
      {c.partial && <Badge tone="bad">Partial</Badge>}
      {c.changes_vs_request.map((x) => <Badge key={x} tone="warn">{changeLabel(x)}</Badge>)}
      {c.origins.length > 0 && !c.changes_vs_request.some((x) => x.startsWith("origin")) &&
        <Badge icon={<MapPin className="size-3" />}>{c.origins.join("/").toUpperCase()}</Badge>}
      {c.reliability && <Badge icon={<Truck className="size-3" />}>{Math.round(Number(c.reliability) * 100)}% on time</Badge>}
      {c.carbon_kg_per_kg && <Badge icon={<Leaf className="size-3" />}>{num(c.carbon_kg_per_kg)} kg CO₂e/kg</Badge>}
    </div>
  );
}

function Option({ c }: { c: Candidate }) {
  return (
    <div className="space-y-3">
      <div className="text-base font-semibold leading-snug">{c.name}</div>
      <dl className="grid grid-cols-3 gap-3 text-sm">
        <div><dt className="text-xs text-muted">Quantity</dt><dd className="font-medium">{num(c.qty_sales_units)} × {c.sales_unit}</dd></div>
        <div><dt className="text-xs text-muted">Unit price</dt><dd className="font-medium">{euro(c.unit_net)}</dd></div>
        <div><dt className="text-xs text-muted">Line total</dt><dd className="font-semibold">{euro(c.line_total_net)}</dd></div>
      </dl>
      <Trust c={c} />
    </div>
  );
}

export function OfferLineView({ line, choice, onChoose }: { line: OfferLine; choice: string; onChoose: (t: string) => void }) {
  const [open, setOpen] = useState(false);
  const options = [...Object.keys(line.tiers), ...(line.split.length ? ["split"] : [])];
  const chosen = choice === "split" ? null : line.tiers[choice];
  return (
    <div className="space-y-3">
      {line.exceptions.length > 0 && (
        <div className="flex gap-2 rounded-lg bg-warn-soft p-3 text-sm text-warn">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div>{line.exceptions.map((e) => <div key={e}>{EXCEPTION[e] ?? e}</div>)}</div>
        </div>
      )}
      <div className="rounded-xl border-2 border-accent/30 bg-accent-soft/30 p-4">
        <div className="mb-3 flex items-center gap-2">
          <Badge tone="accent">{TIER[choice]?.label ?? choice}</Badge>
          <span className="text-xs text-muted">{TIER[choice]?.hint}</span>
        </div>
        {chosen ? <Option c={chosen} /> : (
          <div className="space-y-4">
            {line.split.map((c) => <Option key={c.product_id} c={c} />)}
            {Number(line.backorder_qty) > 0 && <Badge tone="warn">Backorder: {num(line.backorder_qty)} not covered</Badge>}
          </div>
        )}
      </div>
      {options.length > 1 && (
        <div>
          <button onClick={() => setOpen(!open)} className="flex items-center gap-1 text-sm font-medium text-muted hover:text-ink">
            <ChevronDown className={`size-4 transition ${open ? "rotate-180" : ""}`} /> Compare {options.length} options
          </button>
          {open && (
            <div className="mt-2 divide-y divide-line rounded-lg border border-line">
              {options.map((t) => {
                const c = t === "split" ? null : line.tiers[t];
                const total = c ? c.line_total_net : line.split.reduce((s, x) => s + Number(x.line_total_net), 0);
                return (
                  <button key={t} onClick={() => onChoose(t)}
                    className={`flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-page ${t === choice ? "bg-accent-soft/40" : ""}`}>
                    <span className={`size-3.5 rounded-full border-2 ${t === choice ? "border-accent bg-accent" : "border-line"}`} />
                    <span className="w-24 font-medium">{TIER[t].label}</span>
                    <span className="flex-1 truncate text-muted">{c ? c.name : `${line.split.length} products`}</span>
                    <span className="font-medium">{euro(total)}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
      {line.excluded.length > 0 && (
        <p className="flex items-center gap-1.5 text-xs text-muted"><ShieldCheck className="size-3.5" />
          {line.excluded.length} products excluded by hard constraints, unit or availability (see audit log).</p>
      )}
    </div>
  );
}
