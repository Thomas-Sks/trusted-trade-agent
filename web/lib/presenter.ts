// Shared demo organisations and demo controls are for the presenter only: visitors work in their own sandbox
// organisation, so nobody can change what the next visitor (or the jury) sees.
import type { NextRequest } from "next/server";

const CODE = process.env.PRESENTER_CODE;

export function isPresenter(req: NextRequest): boolean {
  return !CODE || req.headers.get("x-presenter-code") === CODE;
}

export function presenterOnly(): Response {
  return Response.json({ code: "PRESENTER_ONLY", detail: "Shared demo organisations and demo controls are reserved to the presenter. Use your own organisation." }, { status: 403 });
}
