// Server-side proxy to the TTAP gateway. Demo identities (agent / approver / Valio admin) are mapped to keys here,
// so no key ever reaches the browser. Offers returned by lookup are re-verified in TypeScript.
import type { NextRequest } from "next/server";
import type { JWK } from "jose";
import { verifyOffer } from "@/lib/verify";
import { limitLlm } from "@/lib/ratelimit";
import { isPresenter, presenterOnly } from "@/lib/presenter";

const KEYS: Record<string, string | undefined> = {
  "agent-hotel": process.env.KEY_AGENT_HOTEL,
  "agent-resto": process.env.KEY_AGENT_RESTO,
  "approver-hotel": process.env.KEY_APPROVER_HOTEL,
  "approver-resto": process.env.KEY_APPROVER_RESTO,
  admin: process.env.KEY_ADMIN,
};
const GATEWAY = process.env.GATEWAY_URL ?? "http://localhost:8811";

async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const target = `${GATEWAY}/${path.join("/")}${req.nextUrl.search}`;
  if (req.method === "POST" && path.at(-1) === "interpret") { const limited = limitLlm(req, "interpret"); if (limited) return limited; }
  const headers: Record<string, string> = { "content-type": "application/json", "x-ttap-via": "web:console" };
  // the visitor's own (onboarded) key wins over demo roles
  const role = req.headers.get("x-demo-role");
  if (!req.headers.get("x-ttap-key") && role && role !== "public" && !isPresenter(req)) return presenterOnly();
  const key = req.headers.get("x-ttap-key") ?? KEYS[role ?? ""];
  if (key) headers.authorization = `Bearer ${key}`;
  const idem = req.headers.get("idempotency-key");
  if (idem) headers["idempotency-key"] = idem;
  const body = ["GET", "HEAD"].includes(req.method) ? undefined : await req.text();
  let upstream: Response;
  try {
    upstream = await fetch(target, { method: req.method, headers, body, cache: "no-store" });
  } catch {
    return Response.json({ code: "GATEWAY_UNREACHABLE", detail: GATEWAY }, { status: 502 });
  }
  const text = await upstream.text();
  if (upstream.ok && path.at(-1) === "lookup") {
    const offer = JSON.parse(text);
    const wk = await (await fetch(`${GATEWAY}/.well-known/ttap.json`, { cache: "no-store" })).json();
    offer.ui_signature_verified = await verifyOffer(offer, wk.jwks.keys[0] as JWK);
    return Response.json(offer, { status: upstream.status });
  }
  return new Response(text, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
  });
}

export { forward as GET, forward as POST, forward as PUT, forward as DELETE };
