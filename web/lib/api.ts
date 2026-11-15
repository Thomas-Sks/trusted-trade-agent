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

export async function api<T = unknown>(who: Cred, path: string, init?: { method?: string; body?: unknown; idempotencyKey?: string }): Promise<T> {
  const headers: Record<string, string> = { "content-type": "application/json" };
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
  v === null || v === undefined ? "—" : new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" }).format(Number(v));
export const num = (v: string | number) => new Intl.NumberFormat("en-IE", { maximumFractionDigits: 2 }).format(Number(v));
export const time = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
