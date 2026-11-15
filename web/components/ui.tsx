import type { ReactNode } from "react";

export const STEPS = [
  { key: "request", label: "Request", emoji: "📝", tone: "bg-grape-soft text-grape", ring: "ring-grape" },
  { key: "lookup", label: "Lookup", emoji: "🔎", tone: "bg-sky-soft text-sky", ring: "ring-sky" },
  { key: "order", label: "Order", emoji: "🧾", tone: "bg-bubble-soft text-bubble", ring: "ring-bubble" },
  { key: "approval", label: "Approval", emoji: "✅", tone: "bg-sun-soft text-[#b77400]", ring: "ring-sun" },
] as const;

export function stepTone(step: string) {
  return STEPS.find((s) => s.key === step) ?? STEPS[0];
}

export function PanelHeader({ emoji, title, subtitle, accent, right }: { emoji: string; title: string; subtitle: string; accent: string; right?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-5 pt-5">
      <div className="flex items-center gap-3">
        <div className={`grid size-11 place-items-center rounded-2xl text-xl ${accent}`}>{emoji}</div>
        <div>
          <h2 className="text-lg font-extrabold tracking-tight">{title}</h2>
          <p className="text-xs text-muted">{subtitle}</p>
        </div>
      </div>
      {right}
    </div>
  );
}

const STATE_STYLE: Record<string, [string, string]> = {
  AUTO_APPROVED: ["bg-mint-soft text-mint", "⚡ Approuvée automatiquement"],
  APPROVED: ["bg-mint-soft text-mint", "✅ Approuvée"],
  PENDING_HUMAN: ["bg-sun-soft text-[#b77400]", "⏳ En attente d'un humain"],
  DENIED: ["bg-tomato-soft text-tomato", "⛔ Refusée par le mandat"],
  REJECTED: ["bg-tomato-soft text-tomato", "❌ Refusée"],
  EXPIRED: ["bg-tomato-soft text-tomato", "⌛ Expirée (refus par défaut)"],
};

export function StateBadge({ state, big }: { state: string; big?: boolean }) {
  const [cls, label] = STATE_STYLE[state] ?? ["bg-grape-soft text-grape", state];
  return <span className={`chip ${cls} ${big ? "px-3.5 py-1.5 text-sm" : ""}`}>{label}</span>;
}

const STOCK: Record<string, [string, string]> = {
  VERIFIED_QTY: ["bg-mint-soft text-mint", "✅ stock vérifié"],
  VERIFIED_UNLIMITED: ["bg-mint-soft text-mint", "✅ stock vérifié"],
  UNKNOWN_SUPPLIER_STOCK: ["bg-sun-soft text-[#b77400]", "❔ stock fournisseur"],
  STALE: ["bg-tomato-soft text-tomato", "🕓 périmé"],
};

export function StockChip({ stock }: { stock: string }) {
  const [cls, label] = STOCK[stock] ?? ["bg-grape-soft text-grape", stock];
  return <span className={`chip ${cls}`}>{label}</span>;
}

export function ChangeChip({ change }: { change: string }) {
  const [kind, value] = change.split(":");
  const label = kind === "origin" ? `🌍 origine ${value.toUpperCase()}` : kind === "substitute" ? `🔁 substitut de ${value}` : kind === "brand" ? `🏷️ marque ${value}` : change;
  return <span className="chip bg-bubble-soft text-bubble">{label}</span>;
}

export function Empty({ emoji, text }: { emoji: string; text: string }) {
  return (
    <div className="grid place-items-center gap-2 rounded-2xl border-2 border-dashed border-grape-soft p-8 text-center text-sm text-muted">
      <span className="text-3xl">{emoji}</span>
      {text}
    </div>
  );
}
