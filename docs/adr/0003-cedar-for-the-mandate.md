# ADR 0003 — The mandate is evaluated by Cedar, with three outcomes

**Status:** accepted · 2026-11-15

## Context
Guardrails must be readable by a buyer, auditable, deterministic, and impossible for the agent to talk its way around.
Options compared: Cedar, OPA/Rego, W3C ODRL, CEL, hand-written code.

## Decision
Cedar (`cedarpy`), embedded. Two evaluations (`submit_order`, `auto_approve`) give three outcomes: DENIED,
AUTO_APPROVED, PENDING_HUMAN (with every `forbid` that fired as reasons). Errors fail closed (DENIED). The context is
computed by the server only (totals, unverified value, substitutions, committed spend, order pace).

## Consequences
- Same choice as AWS Bedrock AgentCore Policy for agent guardrails; policies are short, named and analysable.
- No quantifiers in Cedar: per-line aggregates are pre-computed in Python.
- Rules never reference product ids: they act on generic facts, so they survive assortment changes.
- Recorded contexts make decisions replayable (`POST /mandate/simulate`).
