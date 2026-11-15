// In-memory limits for the routes that spend the Anthropic key (agent runs, request interpretation).
// The console is public for the jury; this keeps one visitor, or everyone together, from draining the key.
import type { NextRequest } from "next/server";

type Window = { count: number; resetAt: number };
const buckets = new Map<string, Window>();

function hit(key: string, limit: number, windowMs: number, now: number): boolean {
  const w = buckets.get(key);
  if (!w || w.resetAt <= now) { buckets.set(key, { count: 1, resetAt: now + windowMs }); return true; }
  if (w.count >= limit) return false;
  w.count += 1;
  return true;
}

export function clientIp(req: NextRequest): string {
  return req.headers.get("x-forwarded-for")?.split(",")[0].trim() || req.headers.get("x-real-ip") || "local";
}

const MIN = 60_000;
const RULES = {
  agent: { perIp: Number(process.env.LLM_AGENT_PER_IP ?? 5), perIpWindow: 10 * MIN, perDay: Number(process.env.LLM_AGENT_PER_DAY ?? 150) },
  interpret: { perIp: Number(process.env.LLM_INTERPRET_PER_IP ?? 20), perIpWindow: 10 * MIN, perDay: Number(process.env.LLM_INTERPRET_PER_DAY ?? 600) },
};

/** Returns a 429 response when the caller is over the limit, otherwise null. */
export function limitLlm(req: NextRequest, kind: keyof typeof RULES): Response | null {
  const r = RULES[kind];
  const now = Date.now();
  if (!hit(`${kind}:ip:${clientIp(req)}`, r.perIp, r.perIpWindow, now))
    return Response.json({ code: "RATE_LIMITED", detail: `Demo limit: ${r.perIp} runs per visitor every 10 minutes. Please wait a moment.` }, { status: 429 });
  if (!hit(`${kind}:day`, r.perDay, 24 * 60 * MIN, now))
    return Response.json({ code: "RATE_LIMITED", detail: "The demo's daily AI budget is used up. The replenishment bot (no AI) still works." }, { status: 429 });
  return null;
}
