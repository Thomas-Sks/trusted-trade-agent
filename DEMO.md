# Demo script (5 minutes)

**Self-service option (jury hands-on):** share the console URL. *Get started* → organisation name + approver →
mandate limits (pre-filled) → scan the QR with the phone and press *Start* in Telegram (the screen turns to
"Phone paired" by itself) → *Watch the agent buy*. Asking for 3,000 L of milk sends the approval card to the
judge's own phone.

**Before:** gateway + console running, Telegram paired (`/start PAIR-HOTEL-A`), demo menu → *Reset demo data*.

0. **Watch the agent act (60 s) — open on this.** Agent live tab → *Run Claude agent (MCP)* with the free-text
   request. The centre column shows Claude calling the MCP tools one by one (interpret → create_request → lookup →
   place_order → explain_order) with what each returned; the right column, the **protocol wire**, shows every
   request hitting the gateway, tagged with the MCP tool that caused it, and the lookup's extra call to
   `/.well-known/ttap.json` = the buyer verifying the offer signature. The 4-step tracker lights up as it goes.
   Then *Run replenishment bot (REST)*: same protocol, no LLM, tagged `REST · replenishment-bot`.
1. **Request → auto-approved (45 s).** New request → scenario *Lactose-free milk*. Point at the tracker: Lookup turns
   green, *Signature verified* badge (checked in TypeScript, signed in Python). Recommended: the hotel's usual milk at
   €1.01/L, 128 products excluded with reasons. Place order → *Auto-approved within mandate*, Peppol `AP`.
2. **Exception → human (75 s).** Scenario *Cherry tomatoes 2,500 kg*: only 546 cases in stock → mixed plan with the
   official Valio substitute (origin changes MA → TN), Peppol `CA`. Place order → tracker waits on step 4.
   The card arrives on the phone: *why it needs you* (3 reasons), *×3 vs usual*. Approve on Telegram → the web tracker
   turns green by itself.
3. **Guardrails (60 s).** Mandate tab → per-order limit 2,000 → 5,000 → *Replay past decisions*: "3 of 10 past orders
   would have changed decision". Hit **Pause** → any new order is denied (`mandate_not_active`); Resume.
4. **Trust & audit (45 s).** Audit log → *Verify chain*: intact, every event signed. Mention offline verification
   with only the public key, and that a tampered line is detected.
5. **Attack (30 s).** Demo menu → *Prompt injection in catalogue*, then *Lactose-free milk*: the hostile text is shown
   as a product name, but price, quantity and decision are unchanged — the server recomputes everything.
6. **Openness (15 s).** Same protocol used by a Claude agent over MCP and a no-LLM replenishment bot; conformance kit
   10/10 MUST; spec + OpenAPI + ADRs in the repo.
