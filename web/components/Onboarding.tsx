"use client";
import { ArrowRight, Building2, Check, Loader2, Scale, Smartphone, Sparkles } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useState } from "react";
import { ApiError, api, type OrgProfile } from "@/lib/api";
import { Badge, Button, Card } from "./ui";

const LIMITS = [
  { key: "limit_per_order_net", label: "Per-order limit", unit: "€", value: "2000", hint: "Above this amount, a human must approve." },
  { key: "period_budget_net", label: "Weekly budget", unit: "€", value: "10000", hint: "Total the agent may commit per 7 days." },
  { key: "max_unverified_value_net", label: "Unverified stock allowance", unit: "€", value: "500", hint: "Supplier-held stock Valio cannot verify." },
  { key: "max_orders_per_hour", label: "Max orders per hour", unit: "", value: "10", hint: "Catches an agent splitting orders under the limit." },
] as const;

interface Created { org_id: string; name: string; approver_name: string; agent_key: string; approver_key: string; pairing_code: string; telegram_link: string | null }

function Steps({ step }: { step: number }) {
  const labels = ["Organisation", "Mandate", "Phone", "Watch your agent"];
  return (
    <ol className="flex items-center gap-2">
      {labels.map((l, i) => (
        <li key={l} className="flex flex-1 items-center gap-2">
          <span className={`grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold transition ${i < step ? "bg-ok text-white" : i === step ? "bg-accent text-white" : "bg-page text-muted ring-1 ring-line"}`}>
            {i < step ? <Check className="size-3.5" /> : i + 1}
          </span>
          <span className={`text-sm ${i === step ? "font-semibold" : "text-muted"}`}>{l}</span>
          {i < labels.length - 1 && <span className={`h-px flex-1 ${i < step ? "bg-ok" : "bg-line"}`} />}
        </li>
      ))}
    </ol>
  );
}

export function Onboarding({ onCreated, onReady }: { onCreated: (o: OrgProfile) => void; onReady: (limitPerOrder: number, paired: boolean) => void }) {
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [approver, setApprover] = useState("");
  const [limits, setLimits] = useState<Record<string, string>>(Object.fromEntries(LIMITS.map((l) => [l.key, l.value])));
  const [created, setCreated] = useState<Created | null>(null);
  const [paired, setPaired] = useState(false);
  const [useTelegram, setUseTelegram] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (step !== 2 || !created || paired || !useTelegram) return;
    const id = setInterval(async () => {
      try { const s = await api<{ telegram_paired: boolean }>({ key: created.approver_key }, "onboarding/status"); if (s.telegram_paired) setPaired(true); } catch { /* retry */ }
    }, 1500);
    return () => clearInterval(id);
  }, [step, created, paired, useTelegram]);

  async function create() {
    setBusy(true); setError(null);
    try {
      const org = await api<Created>("public", "onboarding/organisations", { body: { name, approver_name: approver, ...limits } });
      setCreated(org); setUseTelegram(!!org.telegram_link);
      onCreated({ id: org.org_id, label: org.name, agent: { key: org.agent_key }, approver: { key: org.approver_key },
        approverName: org.approver_name, pairing: org.pairing_code, telegramLink: org.telegram_link,
        limit: `€${Number(limits.limit_per_order_net).toLocaleString("en-IE")} / order`, custom: true });
      setStep(2);
    } catch (e) { setError(e instanceof ApiError ? `${e.code}: ${e.message}` : String(e)); } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Let an agent buy for you — safely</h1>
        <p className="mt-1 text-sm text-muted">Set up your organisation in one minute. Your agent will buy from Valio Aimo within the limits you set, and ask you on your phone when it must not decide alone.</p>
      </div>
      <Card className="p-6"><Steps step={step} /></Card>

      {step === 0 && (
        <Card className="animate-in space-y-4 p-6">
          <div className="flex items-center gap-2 font-semibold"><Building2 className="size-5 text-accent" />Your organisation</div>
          <label className="block"><span className="text-xs font-medium text-muted">Organisation name</span>
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Helsinki Harbour Hotel"
              className="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-accent/10" /></label>
          <label className="block"><span className="text-xs font-medium text-muted">Who approves orders?</span>
            <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name"
              className="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-accent focus:ring-4 focus:ring-accent/10" /></label>
          <div className="flex justify-end"><Button disabled={name.trim().length < 2 || approver.trim().length < 2} onClick={() => setStep(1)}>Continue <ArrowRight className="size-4" /></Button></div>
        </Card>
      )}

      {step === 1 && (
        <Card className="animate-in space-y-4 p-6">
          <div className="flex items-center gap-2 font-semibold"><Scale className="size-5 text-accent" />Your agent&apos;s mandate</div>
          <p className="text-sm text-muted">These limits are enforced by the wholesaler&apos;s policy engine — the agent cannot talk its way around them.</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {LIMITS.map((l) => (
              <label key={l.key} className="block">
                <span className="text-xs font-medium text-muted">{l.label}</span>
                <div className="mt-1 flex items-center rounded-lg border border-line focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/10">
                  {l.unit && <span className="pl-3 text-sm text-muted">{l.unit}</span>}
                  <input value={limits[l.key]} inputMode="decimal" onChange={(e) => setLimits({ ...limits, [l.key]: e.target.value })}
                    className="w-full bg-transparent px-3 py-2 text-sm outline-none" />
                </div>
                <span className="mt-1 block text-xs text-muted">{l.hint}</span>
              </label>
            ))}
          </div>
          {error && <div className="rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad">{error}</div>}
          <div className="flex justify-between">
            <Button variant="ghost" onClick={() => setStep(0)}>Back</Button>
            <Button disabled={busy} onClick={create}>{busy ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}Create organisation</Button>
          </div>
        </Card>
      )}

      {step === 2 && created && (
        <Card className="animate-in space-y-5 p-6">
          <div className="flex items-center gap-2 font-semibold"><Smartphone className="size-5 text-accent" />How do you want to approve orders?</div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              { on: true, title: "On my phone (Telegram)", hint: "Approval cards with signed one-tap buttons", disabled: !created.telegram_link },
              { on: false, title: "In the web console only", hint: "No phone needed — use the Approvals tab", disabled: false },
            ].map((o) => (
              <button key={o.title} disabled={o.disabled} onClick={() => setUseTelegram(o.on)}
                className={`rounded-xl border px-4 py-3 text-left transition disabled:opacity-40 ${useTelegram === o.on ? "border-accent bg-accent-soft/40 ring-4 ring-accent/10" : "border-line hover:border-accent/50"}`}>
                <div className="text-sm font-semibold">{o.title}</div>
                <div className="text-xs text-muted">{o.disabled ? "Telegram is not configured on this server" : o.hint}</div>
              </button>
            ))}
          </div>
          {useTelegram && created.telegram_link && (
            <div className="animate-in flex flex-col items-center gap-5 sm:flex-row">
              <div className="rounded-xl bg-white p-3 ring-1 ring-line"><QRCodeSVG value={created.telegram_link} size={150} fgColor="#17162b" /></div>
              <div className="space-y-3 text-sm">
                <p>Scan with your phone camera (or tap the button on mobile), then press <b>Start</b> in Telegram. Approval requests will arrive there with one-time signed buttons.</p>
                <a href={created.telegram_link} target="_blank" rel="noreferrer"><Button variant="secondary"><Smartphone className="size-4" />Open Telegram</Button></a>
                <div className={`flex items-center gap-2 rounded-lg px-3 py-2 ${paired ? "bg-ok-soft text-ok" : "bg-page text-muted"}`}>
                  {paired ? <><Check className="size-4" /><b>Phone paired</b> — you will be asked here when needed.</> : <><Loader2 className="size-4 animate-spin" />Waiting for your phone… (you can also continue and pair later)</>}
                </div>
              </div>
            </div>
          )}
          <div className="flex justify-end">
            <Button onClick={() => onReady(Number(limits.limit_per_order_net), useTelegram && paired)}>
              <Sparkles className="size-4" />Watch my agent buy <ArrowRight className="size-4" /></Button>
          </div>
        </Card>
      )}

    </div>
  );
}
