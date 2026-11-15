# Trusted Trade Agent Protocol (TTAP) — Specification

*Version `2026-11-15` · draft · MUST / SHOULD / MAY per RFC 2119 · machine-readable contract: [`docs/openapi.json`](docs/openapi.json) · conformance kit: [`conformance/`](conformance/)*

TTAP is the interface through which an **external purchasing agent** buys from a food-service wholesaler: it gets
verifiable fixed-price offers, places orders, and has each order **decided by its mandate or signed off by a human**,
with a record both parties can verify.

## 1. Principles
1. **Four steps, in this order:** `request → lookup → order → approval`. Every object and audit event names its step.
2. **The LLM proposes, the deterministic core decides.** Free text is turned into a structured request (step 0, optional); prices, quantities, stock, signatures, decisions and explanations are computed deterministically.
3. **No product-specific rules.** Policies act on generic facts (claims, labels, amounts, assurance, origin, pace); product ids only appear in customer data (usual products).
4. **The server is authoritative.** Totals are recomputed from the signed offer; nothing the agent asserts is trusted.
5. **Every claim carries its assurance level.** Missing data never counts as a satisfied constraint.
6. **Fail closed.** Policy errors, stale data or expired locks lead to escalation or denial, never to execution.

## 2. Identity and isolation
| Role | Credential | Can |
|---|---|---|
| `agent` | agent key (OAuth 2.1 in production) | request, lookup, order, preview, read own orders and audit |
| `approver` | approver key / paired Telegram account | approve, reject, modify, pause/resume and simulate the mandate |
| `seller_admin` | admin key | demo controls only (scenarios, clock, reset) |
| *(public)* | none | self-service onboarding: create an organisation, which returns its agent and approver credentials |

- The organisation MUST be derived from the credential, never from the body; unknown body fields MUST be rejected.
- Cross-organisation access MUST return `404` (not `403`).
- An agent MUST NOT be able to modify its own mandate.

## 3. Operations
| Step | Endpoint | Notes |
|---|---|---|
| 0 | `POST /interpret` | free text → draft request + assumptions + questions (optional, LLM) |
| 1 Request | `POST /requests` | lines described by **properties**: `need {text, required_claims, excluded_allergens, required_labels, product_id?}`, `quantity {value, unit L|KG|PIECE}`, `preferences {origin, brands, labels}`, `substitution best_match|no_substitute`, delivery window |
| 2 Lookup | `POST /requests/{id}/lookup` | signed **Offer** with `good / better / best` tiers or a `split` plan |
| 3 Order | `POST /orders` (`Idempotency-Key` required) | order at the offer's locked price → `202` |
| 3′ Preview | `POST /orders/preview` | the decision the mandate would take; commits nothing |
| 4 Approval | `GET /approvals`, `GET /orders/{id}/card`, `POST /orders/{id}/approve|reject|modify` | humans; also via Telegram |
| Mandate | `GET /mandate`, `POST /mandate/pause|resume`, `POST /mandate/simulate` | kill switch and what-if replay |
| Audit | `GET /audit`, `GET /audit/verify`, `GET /approvals/stats` | signed chain, verification, oversight quality |
| Discovery | `GET /.well-known/ttap.json` | protocol, version, steps, JWKS |
| Onboarding | `POST /onboarding/organisations`, `GET /onboarding/status` | self-service: organisation + mandate limits → agent key, approver key, Telegram pairing link; status reports pairing |
| Observability | `GET /trace?after=` | the organisation's recent gateway calls, tagged with the client that made them (`X-TTAP-Via`: MCP tool, REST bot, console) |

## 4. Offers (trust protocol)
- An offer MUST be signed: ES256 JWS over the RFC 8785 (JCS) canonical JSON of the offer without `signature`, key in the discovery JWKS. Buyers SHOULD verify before acting (reference: `buyer_agent/ttap_client.py`, `web/lib/verify.ts`).
- `valid_until = min(now + TTL, price validTo, order cut-off)`. An offer is single-use.
- Each candidate states: `stock` (`VERIFIED_QTY`, `VERIFIED_UNLIMITED`, `UNKNOWN_SUPPLIER_STOCK`, `STALE`), `origin` (`CONSISTENT`, `CONFLICT`, `SINGLE_SOURCE`, `MISSING`), delivery reliability (observed history), carbon (category average), `changes_vs_request`, `partial`, `is_substitute`.
- Each line lists **excluded products with a reason** and its `exceptions` (`PARTIAL_AVAILABILITY`, `SUBSTITUTED`, `BACKORDER`, `NO_ELIGIBLE_PRODUCT`, `REQUESTED_PRODUCT_UNAVAILABLE`).
- Supplier free text (product names) is untrusted data and MUST NOT be interpreted as instructions.

## 5. Response logic
1. Candidates: the requested product + its official substitutes, or a catalogue search where hard constraints apply **before** truncation, full-word matches beat partial ones, and the buyer's usual products come first.
2. Hard filters: claims, allergens, labels, comparison unit, sales block, delivery date, order cut-off.
3. Quantities: requested unit → sales units (name content cross-checked with the API price per unit), rounded up to the lot size.
4. Tiers: **good** = cheapest meeting hard constraints; **better** = also meets preferences; **best** = better + quality (labels, stock certainty, delivery reliability, lower carbon).
5. Partial availability: **split** plan = all available stock of the requested product → official substitutes → other candidates by price → backorder. `no_substitute` keeps partial + backorder only.

## 6. Order state machine
`PENDING_DECISION → AUTO_APPROVED | PENDING_HUMAN | DENIED`; `PENDING_HUMAN → APPROVED | REJECTED | EXPIRED` (or `→ PENDING_DECISION` after a modification). Every transition MUST be compare-and-set on `(state, version)` (`409 CONFLICT` otherwise). The price is locked until `lock_until = min(decision + approval timeout, price validTo, cut-off)`; past it, approval is refused and the order expires (fail-closed). Reminders are sent half-way.

## 7. Mandate (Cedar)
Two evaluations (`submit_order`, `auto_approve`) → three outcomes. Built-in rules: per-order limit, period budget (reserved atomically), order velocity (anti-splitting), unverified stock value, origin conflict, deviation from request (substitute/origin/brand), partial fulfilment, stale data, mandate inactive. Every `forbid` that fired is returned as a reason. `POST /mandate/simulate` replays recorded decisions with modified parameters.

## 8. Human approval
The approval card MUST show facts, never the agent's advocacy: raw lines, each triggered rule with value and threshold, deviation from usual quantities, substitutions and origin changes, assurance warnings, cut-off countdown. Messaging approvals (Telegram) use pairing codes, one-time signed action tokens bound to the order version, a check of **who clicked**, idempotent actions, and step-up to the web console above a threshold.

## 9. Concurrency
Known stock and period budget are reserved atomically at order time (`HELD` → `FIRM` on approval, `RELEASED` on rejection/expiry); a race returns `409 STOCK_CHANGED`. `Idempotency-Key` makes retries safe; offers are single-use.

## 10. Order response (Peppol BIS Ordering 3)
Header `AP` (accepted, no lines) · `CA` (accepted with changes, lines required) · `RE` (rejected, no lines). Line status `5` accepted · `3` changed (partial) · `1` added (substitute, with `substituted_for`) · `7` not accepted; `backorder_qty` per line.

## 11. Audit
CloudEvents 1.0 JSONL; fields `step`, `actor`, `outcome`, `data`, template-generated `explanation`; `prev_hash = SHA-256(JCS(previous))` per organisation; each entry signed ES256; offline verification with `scripts/verify_audit.py`.

## 12. Errors
`application/problem+json` with stable `code`: `NOT_FOUND`, `UNAUTHORIZED`, `OFFER_EXPIRED`, `OFFER_ALREADY_USED`, `INVALID_OFFER_SIGNATURE`, `INVALID_SELECTION`, `IDEMPOTENCY_MISMATCH`, `CONFLICT`, `PRICE_LOCK_EXPIRED`, `STOCK_CHANGED`, `UPSTREAM_UNAVAILABLE`, `INTERPRETER_UNAVAILABLE`.
LLM failures on step 0 keep the protocol usable and name their cause: `AI_CREDITS_EXHAUSTED`, `AI_KEY_INVALID`,
`AI_RATE_LIMITED`, `AI_OVERLOADED`, `AI_UNAVAILABLE`.

## 12 bis. Onboarding (operating model)
A buyer organisation is created in one call: name, approver, mandate limits (per order, period budget, unverified
stock, velocity). The gateway returns an agent key (for the buying agent), an approver key and a single-use Telegram
pairing link. Pairing is optional: without it, approvals happen in the web console. A new organisation starts with no
usual products and the default Cedar policies; its limits apply from the first order.

## 13. Path to production
| Area | Prototype | Production |
|---|---|---|
| Processing | FastAPI async, one instance | stateless gateway on N instances, workers on Redis Streams / RabbitMQ, queue-depth autoscaling |
| State | SQLite (WAL) | Postgres, same atomic reservations and compare-and-set |
| Upstream | local throttle 8 req/s, batching, 60 s cache, stale fallback | shared throttle (Redis), shared cache, circuit breaker |
| Notifications | best-effort Telegram | transactional outbox, at-least-once + idempotent consumers; WhatsApp/Teams adapters |
| Stock | local reservation ledger | **reservation/commit endpoint at the wholesaler** |
| LLM cost & abuse | per-visitor and daily caps on LLM routes, input length caps, purchasing-only agent | per-organisation quotas and billing, spend alerts |
| Identity | static keys | OAuth 2.1 per organisation, RFC 9421 signed agent requests, verifiable agent mandates |
| ERP | order ready to transmit | Peppol UBL Order / OrderResponse export, EDI ORDERS/ORDRSP |
| Labels | supplier-declared | third-party attested (UN Transparency Protocol credentials, European Business Wallet) |
