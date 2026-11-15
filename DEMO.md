# Demo script (6 minutes)

**Self-service option (jury hands-on):** share the console URL. *Get started* → organisation name + approver →
mandate limits (pre-filled) → choose *On my phone (Telegram)* and scan the QR, or *In the web console only* →
*Watch my agent buy*: the console opens Agent live with a request above the new limit already filled in. The approval
card goes to the judge's own phone (or the Approvals tab); once decided, the agent view turns green by itself.

**Fallbacks:** if the AI key runs out of credit the console says so explicitly; lookup, orders, approvals and the
replenishment bot (no AI) keep working. Each visitor gets 5 agent runs per 10 minutes.

**Before:** gateway + console running, Telegram paired (`/start PAIR-HOTEL-A`), demo menu → *Reset demo data*.

0. **The kitchen restocks itself (75 s) — open on this.** Org *Bistro Bruno*, tab *Kitchen* → *Reset*, then
   *Dinner service*: milk, cream, tomatoes, lettuce, chicken drop below their reorder points. *Restock with Claude*:
   the agent calls `check_inventory`, places **one order per supplier category**, and the mandate decides each:
   Produce and Meat & fish are **auto-approved**; Dairy waits for a human because the 10 L cooking cream is
   supplier-held stock Valio cannot verify (`unverified_stock_over_limit`, €622 > €200). Counter: *2 / 3 without a
   human*. Approve it (phone or Approvals tab) → the inventory shows it incoming. Say: **"The AI never decides. The
   mandate decides; the human only sees what the mandate does not cover."** *Rule-based (no AI)* gives the same
   orders and the same decisions to the cent.
1. **Watch the agent act (60 s).** Agent live tab → *Run Claude agent (MCP)* with the free-text
   request. The centre column shows Claude calling the MCP tools one by one (interpret → create_request → lookup →
   place_order → explain_order) with what each returned; the right column, the **protocol wire**, shows every
   request hitting the gateway, tagged with the MCP tool that caused it, and the lookup's extra call to
   `/.well-known/ttap.json` = the buyer verifying the offer signature. The 4-step tracker lights up as it goes.
   Then *Run replenishment bot (REST)*: same protocol, no LLM, tagged `REST · replenishment-bot`.
2. **Exception → human (60 s).** Org *Aurora Hotel*, Agent live → preset *Cherry tomatoes* (2,500 kg): only 546 cases
   in stock → mixed plan with the official Valio substitute (origin changes MA → TN), Peppol `CA`, tracker waits on
   step 4. The card arrives on the phone: *why it needs you* (reasons), *×3 vs usual*. Approve on Telegram → the web
   tracker turns green by itself. (Run *Reset demo data* afterwards: this order reserves the tomato stock.)
3. **Guardrails (30 s).** Show the reasons on the approval card (each rule with value and threshold). The kill switch
   and what-if replay exist in the protocol (`POST /mandate/pause`, `POST /mandate/simulate`: "3 of 10 past orders
   would have changed decision") — mention them, no UI needed.
4. **Trust & audit (45 s).** Audit log → *Verify chain*: intact, every event signed. Mention offline verification
   with only the public key, and that a tampered line is detected.
5. **Attack (30 s).** Show `eval/redteam/report.md`: 144 attacks in Finnish, Swedish and English, no filter, zero
   decision changed — the LLM never decides. Then live: Demo menu → *Prompt injection in catalogue*, then *Lactose-free milk*: the hostile text is shown
   as a product name, but price, quantity and decision are unchanged — the server recomputes everything.
6. **Openness (15 s).** Same protocol used by a Claude agent over MCP and a no-LLM replenishment bot; conformance kit
   10/10 MUST; spec + OpenAPI + ADRs in the repo.
