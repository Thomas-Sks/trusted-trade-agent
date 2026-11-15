// The restaurant's inventory lives on the buyer side (agent service); this forwards the console's kitchen actions.
import type { NextRequest } from "next/server";

const AGENT = process.env.AGENT_URL ?? "http://localhost:8820";
const ACTIONS = ["state", "service", "reset", "receive"];

export async function POST(req: NextRequest, ctx: { params: Promise<{ action: string }> }): Promise<Response> {
  const { action } = await ctx.params;
  if (!ACTIONS.includes(action)) return Response.json({ code: "NOT_FOUND" }, { status: 404 });
  try {
    const upstream = await fetch(`${AGENT}/kitchen/${action}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: await req.text(), cache: "no-store",
    });
    return new Response(upstream.body, { status: upstream.status, headers: { "content-type": "application/json", "cache-control": "no-store" } });
  } catch {
    return Response.json({ code: "AGENT_UNREACHABLE", detail: AGENT }, { status: 502 });
  }
}
