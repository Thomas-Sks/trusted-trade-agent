# TTAP — Trusted Trade Agent Protocol

**Junction 2026 · Valio Aimo challenge.** An open, verifiable interface through which external purchasing agents
buy from a food-service wholesaler: *request → lookup → order → approval*, with signed offers, a mandate enforced by
policy, human sign-off on Telegram or the web, and an audit trail both parties can verify.

> Not a chatbot over a webshop: the wholesaler publishes the protocol, any agent (LLM or plain script) can speak it,
> and nothing an agent says can change a price, a quantity or an approval.

**Live demo:** https://16-171-234-227.sslip.io (until 2026-11-18) — *Get started* to create your own organisation.

## What it does
| Challenge requirement | TTAP |
|---|---|
| Product, price & availability lookup | Catalogue search with hard constraints (GS1 claims, labels, allergens), live price & stock from Valio, good/better/best tiers |
| Fixed-price inquiry → order | Signed, single-use offers (ES256 + RFC 8785) → order at the locked price, idempotent |
| Permissions & human approval | Cedar mandate → auto-approved / human / denied with reasons; Telegram & web approval; kill switch; what-if replay |
| Trust protocol | Assurance level on every claim (verified vs unknown stock, origin conflicts, missing data); buyer-side signature verification in Python **and** TypeScript |
| Partial availability & substitution | Split plan: available stock + official substitute + backorder, Peppol `CA` order response |
| Delivery & sustainability | Delivery reliability, cut-offs, labels and category carbon in ranking |
| Audit trail | CloudEvents, hash-chained, signed, verifiable offline; human-readable explanations from templates |

## Architecture
```mermaid
flowchart LR
  subgraph Buyer side
    A[Claude agent<br/>Sonnet 5.5] -- MCP --> M[TTAP MCP server<br/>verifies offer signatures]
    B[Replenishment bot<br/>no LLM] -- REST --> G
    M -- REST --> G
    W[Web console<br/>Next.js, TS verifier] -- REST --> G
    T[Approver on Telegram] <--> G
  end
  subgraph Valio Aimo side
    G[TTAP gateway<br/>FastAPI] --> C[(Cedar mandate)]
    G --> L[(Signed audit chain)]
    G --> R[(Reservations / orders<br/>SQLite)]
    G -- throttled, cached --> V[Valio price & availability API]
    G --> K[Catalogue<br/>GS1 Synkka + reliability + carbon]
  end
```
Hexagonal core (`ttap/domain` pure, `ttap/ports.py`, `ttap/adapters`). Decisions: [`docs/adr/`](docs/adr). Spec: [`SPEC.md`](SPEC.md). Assumptions: [`ASSUMPTIONS.md`](ASSUMPTIONS.md).

## Quickstart
```bash
cp .env.example .env            # set VALIO_API_KEY (and optionally ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN)
# datasets from the challenge portal into resources/ (not committed)
uv sync
uv run --env-file .env uvicorn ttap.main:app --port 8811          # gateway
uv run --env-file .env uvicorn buyer_agent.agent_server:app --port 8820   # buyer-side agents (live view)
(cd web && npm install && npx next dev --port 3100)                 # console → http://localhost:3100
```
or `docker compose up --build`.

**Hosted (single VM):** `deploy/compose.yml` — Caddy (automatic HTTPS) is the only published service; gateway and
agent stay on the internal network with fresh random keys. Run from `deploy/` with
`docker compose --env-file ../.env up -d --build`. LLM routes are rate-limited (per visitor and per day), inputs are
length-capped, and the agent only handles purchasing requests.

| Try | Command |
|---|---|
| **Onboard yourself** | Console → *Get started*: create an organisation, set its mandate, pair your phone via QR, run the agent |
| **Watch an agent act** | Console → *Agent live*: Claude's tool calls, results, and every gateway request on the protocol wire (`MCP · lookup`, `REST · replenishment-bot`) |
| Claude agent over MCP | `uv run --env-file .env python -m buyer_agent.reference_agent "1000 L of lactose-free milk for Monday"` |
| Plug Claude Desktop / Code | MCP stdio server: `python -m buyer_agent.mcp_server` with `TTAP_URL`, `TTAP_AGENT_KEY` |
| Replenishment bot (no LLM) | `uv run python -m buyer_agent.replenishment_bot --key demo-key-resto-b --once` |
| Precision eval | `uv run python eval/run_eval.py` → `eval/report.md` |
| Red team (FI/SV/EN) | `uv run python eval/redteam/run_redteam.py --url http://localhost:8811 [--llm 3]` → `eval/redteam/report.md` (use a scratch gateway) |
| Conformance kit | `uv run pytest conformance --server-url http://localhost:8811` → `conformance/compatibility.json` |
| Verify the audit log offline | `uv run python scripts/verify_audit.py audit.jsonl jwk.json` |
| Unit tests | `uv run pytest` |

## Results (live mock API, 2026-11-15)
- **Evaluation** (16 property-based cases, no LLM, `/orders/preview`): first-time-right 81 % → **100 %** after the full-word relevance fix; decision accuracy **100 %**; touchless rate **100 %** of expected auto-approvals; pass^3 consistency **100 %**; hard-constraint violations **0**. Small, team-written set — a regression guard, not a market claim.
- **Conformance kit:** 10/10 MUST, 2/2 SHOULD.
- **Red team** ([`eval/redteam/report.md`](eval/redteam/report.md)): 18 hostile instructions (6 intents × Finnish, Swedish, English) through buyer text, supplier product names, HTTP headers and forged protocol fields — **144 / 144 decisions unchanged, with no input filter**; 126 privilege-escalation attempts with the agent's own key all refused; the real Claude agent reading the payloads still ends in `PENDING_HUMAN`.
- **Interpreter** (Claude Haiku 5.5): FR/FI/EN free text → constraints in ~3 s, asks before guessing.
- **What-if:** raising the per-order limit to €5,000 → "3 of 10 past orders would have changed decision".
- **Tests:** 117 unit/integration tests.

## Repository
```
ttap/            gateway: domain (pure), application (use cases), adapters (REST, Telegram, Valio, Cedar, SQLite, JWS, Claude)
buyer_agent/     buyer side: verifying client, MCP server, Claude reference agent, replenishment bot
web/             Next.js console (Agent live · New request · Orders · Approvals · Mandate · Audit log)
policies/        Cedar mandate policies
conformance/     protocol conformance kit
eval/            precision evaluation
docs/            OpenAPI, ADRs, research notes
```
