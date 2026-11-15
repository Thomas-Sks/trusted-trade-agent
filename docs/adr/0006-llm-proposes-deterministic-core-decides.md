# ADR 0006 — The LLM proposes, the deterministic core decides

**Status:** accepted · 2026-11-15

## Context
Buyers write free text in Finnish, Swedish or English. LLMs are good at that and unreliable at money and permissions.

## Decision
The LLM is confined to step 0 (Claude Haiku 5.5 turns text into a structured request with explicit assumptions) and
to the reference agent (Claude Sonnet 5.5) choosing between offers. Prices, quantities, stock, signatures, the mandate
decision and the audit text are computed deterministically; explanations come from templates, never from the LLM.
Supplier text is flagged untrusted; a prompt-injection scenario is part of the test suite.

## Consequences
- The protocol works with no LLM at all (the replenishment bot proves it).
- An injected instruction cannot change a price, a quantity or an approval: the server recomputes everything.
