# ADR 0001 — An open protocol hosted by the wholesaler, not a feed to a platform

**Status:** accepted · 2026-11-15

## Context
Agentic commerce platforms (OpenAI product feeds, Google Merchant Center/UCP, Amazon) expose a supplier through a
platform-owned schema and a daily feed. The platform owns the buyer relationship and the data, and a feed only says
`in_stock / out_of_stock` once a day. Valio Aimo asked for an interface defined "before someone else's platform does".

## Decision
Valio Aimo hosts the interface itself: REST (OpenAPI 3.1) + a buyer-side MCP server, a discovery document at
`/.well-known/ttap.json`, signed offers, and a published conformance kit. Any agent (LLM or not) can implement it.

## Consequences
- Valio keeps the transaction and the relationship (merchant of record); agents are clients, not intermediaries.
- We must publish the spec, the schemas and a conformance kit, or nobody can implement it — done (`SPEC.md`, `docs/openapi.json`, `conformance/`).
- Two independent clients prove agent-agnosticism: a Claude agent over MCP and a deterministic replenishment bot over REST.
