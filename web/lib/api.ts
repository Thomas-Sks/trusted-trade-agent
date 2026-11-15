export type Role = "agent-hotel" | "agent-resto" | "approver-hotel" | "approver-resto" | "admin" | "public";
export type Org = "hotel" | "resto";

export const ORGS: Record<Org, { label: string; emoji: string; agent: Role; approver: Role; approverName: string; pairing: string }> = {
  hotel: { label: "Hôtel Aurora", emoji: "🏨", agent: "agent-hotel", approver: "approver-hotel", approverName: "chef_alice", pairing: "PAIR-HOTEL-A" },
  resto: { label: "Bistro Bruno", emoji: "🍽️", agent: "agent-resto", approver: "approver-resto", approverName: "chef_bruno", pairing: "PAIR-RESTO-B" },
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, detail: string) {
    super(detail);
  }
}

export async function api<T = unknown>(role: Role, path: string, init?: { method?: string; body?: unknown; idempotencyKey?: string }): Promise<T> {
  const headers: Record<string, string> = { "x-demo-role": role, "content-type": "application/json" };
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
  v === null || v === undefined ? "—" : new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(Number(v));
export const num = (v: string | number) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(Number(v));
export const time = (iso: string) => new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
