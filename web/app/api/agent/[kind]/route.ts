// Streams a buyer-side agent run (NDJSON) from the agent service to the browser, unbuffered.
import type { NextRequest } from "next/server";

const AGENT = process.env.AGENT_URL ?? "http://localhost:8820";

export async function POST(req: NextRequest, ctx: { params: Promise<{ kind: string }> }): Promise<Response> {
  const { kind } = await ctx.params;
  if (!["claude", "bot"].includes(kind)) return Response.json({ code: "NOT_FOUND" }, { status: 404 });
  try {
    const upstream = await fetch(`${AGENT}/run/${kind}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: await req.text(), cache: "no-store",
    });
    return new Response(upstream.body, { headers: { "content-type": "application/x-ndjson", "cache-control": "no-store" } });
  } catch {
    return Response.json({ code: "AGENT_UNREACHABLE", detail: AGENT }, { status: 502 });
  }
}
