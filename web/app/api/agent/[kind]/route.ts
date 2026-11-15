// Streams a buyer-side agent run (NDJSON) from the agent service to the browser, unbuffered.
import type { NextRequest } from "next/server";
import { isPresenter, presenterOnly } from "@/lib/presenter";
import { limitLlm } from "@/lib/ratelimit";

const AGENT = process.env.AGENT_URL ?? "http://localhost:8820";

export async function POST(req: NextRequest, ctx: { params: Promise<{ kind: string }> }): Promise<Response> {
  const { kind } = await ctx.params;
  if (!["claude", "bot", "kitchen"].includes(kind)) return Response.json({ code: "NOT_FOUND" }, { status: 404 });
  const body = await req.text();
  const ownKey = (() => { try { return !!JSON.parse(body).agent_key; } catch { return false; } })();
  if (!ownKey && !isPresenter(req)) return presenterOnly();
  if (kind === "kitchen" && (() => { try { return JSON.parse(body).mode === "claude"; } catch { return false; } })()) {
    const limited = limitLlm(req, "agent"); if (limited) return limited;
  }
  if (kind === "claude") {
    const text = (() => { try { return String(JSON.parse(body).text ?? ""); } catch { return ""; } })();
    if (text.length > 400) return Response.json({ code: "TOO_LONG", detail: "Please keep the purchasing request under 400 characters." }, { status: 413 });
    const limited = limitLlm(req, "agent"); if (limited) return limited;
  }
  try {
    const upstream = await fetch(`${AGENT}/run/${kind}`, {
      method: "POST", headers: { "content-type": "application/json" }, body, cache: "no-store",
    });
    return new Response(upstream.body, { status: upstream.status, headers: { "content-type": "application/x-ndjson", "cache-control": "no-store" } });
  } catch {
    return Response.json({ code: "AGENT_UNREACHABLE", detail: AGENT }, { status: 502 });
  }
}
