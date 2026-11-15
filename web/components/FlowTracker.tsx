import { Check, FileText, Loader2, Search, ShieldCheck, ShoppingCart, X } from "lucide-react";

export type StepState = "todo" | "active" | "done" | "waiting" | "blocked";
export interface FlowStep { key: string; label: string; detail?: string; state: StepState }

const ICONS = { request: FileText, lookup: Search, order: ShoppingCart, approval: ShieldCheck } as const;
const RING: Record<StepState, string> = {
  todo: "bg-white text-muted ring-line",
  active: "bg-accent text-white ring-accent shadow-[0_0_0_6px_rgba(91,76,240,0.12)]",
  done: "bg-ok text-white ring-ok",
  waiting: "bg-warn text-white ring-warn shadow-[0_0_0_6px_rgba(196,106,0,0.12)]",
  blocked: "bg-bad text-white ring-bad",
};

export function FlowTracker({ steps }: { steps: FlowStep[] }) {
  return (
    <ol className="flex items-start">
      {steps.map((s, i) => {
        const Icon = s.state === "done" ? Check : s.state === "blocked" ? X : s.state === "waiting" ? Loader2 : ICONS[s.key as keyof typeof ICONS];
        const next = steps[i + 1];
        return (
          <li key={s.key} className="relative flex flex-1 flex-col items-center text-center">
            {next && (
              <div className="absolute left-1/2 top-5 h-0.5 w-full -translate-y-1/2 bg-line">
                <div className={`h-full bg-ok transition-all duration-500 ${s.state === "done" ? "w-full" : "w-0"}`} />
              </div>
            )}
            <div className={`relative z-10 grid size-10 place-items-center rounded-full ring-2 transition-all duration-300 ${RING[s.state]}`}>
              <Icon className={`size-[18px] ${s.state === "waiting" ? "animate-spin [animation-duration:2.5s]" : ""}`} />
            </div>
            <div className="mt-2 text-[11px] font-medium uppercase tracking-wider text-muted">Step {i + 1}</div>
            <div className="text-sm font-semibold">{s.label}</div>
            {s.detail && <div className="mt-0.5 max-w-[11rem] text-xs text-muted">{s.detail}</div>}
          </li>
        );
      })}
    </ol>
  );
}
