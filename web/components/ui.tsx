import type { ButtonHTMLAttributes, ReactNode } from "react";

type Tone = "neutral" | "accent" | "ok" | "warn" | "bad" | "info";
const TONE: Record<Tone, string> = {
  neutral: "bg-page text-muted ring-line",
  accent: "bg-accent-soft text-accent ring-accent/15",
  ok: "bg-ok-soft text-ok ring-ok/15",
  warn: "bg-warn-soft text-warn ring-warn/15",
  bad: "bg-bad-soft text-bad ring-bad/15",
  info: "bg-info-soft text-info ring-info/15",
};

export function Badge({ tone = "neutral", children, icon }: { tone?: Tone; children: ReactNode; icon?: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE[tone]}`}>
      {icon}{children}
    </span>
  );
}

const BTN = {
  primary: "bg-accent text-white hover:bg-accent/90 shadow-sm",
  secondary: "bg-white text-ink ring-1 ring-line hover:bg-page",
  ghost: "text-muted hover:text-ink hover:bg-page",
  ok: "bg-ok text-white hover:bg-ok/90 shadow-sm",
  bad: "bg-white text-bad ring-1 ring-bad/30 hover:bg-bad-soft",
};

export function Button({ variant = "primary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof BTN }) {
  return (
    <button {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:pointer-events-none disabled:opacity-40 ${BTN[variant]} ${className}`} />
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-line bg-white shadow-[0_1px_2px_rgba(23,22,43,0.04)] ${className}`}>{children}</div>;
}

const STATE: Record<string, [Tone, string]> = {
  AUTO_APPROVED: ["ok", "Auto-approved"],
  APPROVED: ["ok", "Approved"],
  PENDING_HUMAN: ["warn", "Awaiting approval"],
  DENIED: ["bad", "Denied"],
  REJECTED: ["bad", "Rejected"],
  EXPIRED: ["bad", "Expired"],
};

export function StatusBadge({ state }: { state: string }) {
  const [tone, label] = STATE[state] ?? ["neutral", state];
  return <Badge tone={tone}><span className="size-1.5 rounded-full bg-current" />{label}</Badge>;
}

export function Empty({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <div className="grid place-items-center gap-2 px-6 py-16 text-center">
      <div className="grid size-10 place-items-center rounded-full bg-page text-muted">{icon}</div>
      <div className="font-semibold">{title}</div>
      <div className="max-w-sm text-sm text-muted">{text}</div>
    </div>
  );
}

export const RULE_LABEL: Record<string, string> = {
  total_over_order_limit: "Over per-order limit",
  unverified_stock_over_limit: "Unverified stock",
  origin_conflict: "Origin conflict",
  deviates_from_request: "Deviates from request",
  partial_fulfilment: "Partial availability",
  period_budget_exceeded: "Budget exceeded",
  order_velocity_exceeded: "Unusual order pace",
  stale_data: "Stale supplier data",
  mandate_not_active: "Mandate inactive",
};
