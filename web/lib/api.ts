export type Role = "agent-hotel" | "agent-resto" | "approver-hotel" | "approver-resto" | "admin" | "public";
/** A credential: a demo role mapped server-side, or the visitor's own key from onboarding. */
export type Cred = Role | { key: string };

export interface OrgProfile {
  id: string; label: string; agent: Cred; approver: Cred; approverName: string; pairing: string; limit: string;
  telegramLink?: string | null; custom?: boolean;
}

export const DEMO_ORGS: OrgProfile[] = [
  { id: "hotel", label: "Aurora Hotel (demo)", agent: "agent-hotel", approver: "approver-hotel", approverName: "chef_alice", pairing: "PAIR-HOTEL-A", limit: "€2,000 / order" },
  { id: "resto", label: "Bistro Bruno (demo)", agent: "agent-resto", approver: "approver-resto", approverName: "chef_bruno", pairing: "PAIR-RESTO-B", limit: "€800 / order" },
];

const STORAGE = "ttap.myOrgs";
export function loadMyOrgs(): OrgProfile[] {
  try { return JSON.parse(localStorage.getItem(STORAGE) ?? "[]"); } catch { return []; }
}
export function saveMyOrgs(orgs: OrgProfile[]) {
  try { localStorage.setItem(STORAGE, JSON.stringify(orgs)); } catch { /* private mode: org lives for this tab only */ }
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, detail: string) {
    super(detail);
  }
}

const PRESENTER = "ttap.presenter";
/** The presenter unlocks the shared demo organisations and demo controls once with ?presenter=<code>. */
export function presenterCode(): string | null {
  try {
    const q = new URLSearchParams(window.location.search).get("presenter");
    if (q !== null) { if (q) localStorage.setItem(PRESENTER, q); else localStorage.removeItem(PRESENTER); }
    return localStorage.getItem(PRESENTER);
  } catch { return null; }
}
export function presenterHeaders(): Record<string, string> {
  const c = typeof window === "undefined" ? null : presenterCode();
  return c ? { "x-presenter-code": c } : {};
}

export interface CreatedOrg { org_id: string; name: string; approver_name: string; agent_key: string; approver_key: string; pairing_code: string; telegram_link: string | null }
export function profileOf(org: CreatedOrg, limitPerOrder: number | string): OrgProfile {
  return { id: org.org_id, label: org.name, agent: { key: org.agent_key }, approver: { key: org.approver_key },
    approverName: org.approver_name, pairing: org.pairing_code, telegramLink: org.telegram_link,
    limit: `€${Number(limitPerOrder).toLocaleString("en-IE")} / order`, custom: true };
}
/** Every visitor gets a private copy of the bistro, so nobody changes what the next visitor sees. */
export const SANDBOX_LIMITS = { limit_per_order_net: "800", period_budget_net: "20000", max_unverified_value_net: "200", max_orders_per_hour: "12" };
export async function createSandbox(): Promise<OrgProfile> {
  const org = await api<CreatedOrg>("public", "onboarding/organisations", { body: { name: "My Bistro", approver_name: "chef", ...SANDBOX_LIMITS } });
  return profileOf(org, SANDBOX_LIMITS.limit_per_order_net);
}

export async function api<T = unknown>(who: Cred, path: string, init?: { method?: string; body?: unknown; idempotencyKey?: string }): Promise<T> {
  const headers: Record<string, string> = { "content-type": "application/json", ...presenterHeaders() };
  if (typeof who === "string") headers["x-demo-role"] = who; else headers["x-ttap-key"] = who.key;
  if (init?.idempotencyKey) headers["idempotency-key"] = init.idempotencyKey;
  const res = await fetch(`/api/ttap/${path.replace(/^\//, "")}`, {
    method: init?.method ?? (init?.body !== undefined ? "POST" : "GET"),
    headers,
    body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data.code ?? "ERROR", typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data));
  return data as T;
}

export const euro = (v: string | number | null | undefined) =>
  v === null || v === undefined ? "n/a" : new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" }).format(Number(v));
export const num = (v: string | number) => new Intl.NumberFormat("en-IE", { maximumFractionDigits: 2 }).format(Number(v));
export const time = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
