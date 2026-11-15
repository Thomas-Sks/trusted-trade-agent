# ADR 0004 — Signed offers and a hash-chained audit log instead of a blockchain

**Status:** accepted · 2026-11-15

## Context
The trust protocol must let an agent rely on the wholesaler's claims (price, stock, origin) without a manual check,
and let both parties prove later what was said and decided.

## Decision
- Offers are ES256 JWS over the RFC 8785 (JCS) canonical JSON; the public key is in `/.well-known/ttap.json`.
  The buyer side verifies every offer (Python MCP client and an independent TypeScript verifier in the console).
- Every claim carries an assurance level (verified stock, unknown supplier stock, observed delivery reliability,
  category-average carbon, conflicting origin, missing data).
- The audit log is CloudEvents JSONL, SHA-256 hash-chained per organisation, each entry signed; `verify_audit.py`
  checks it offline with the public key only.

## Consequences
- Non-repudiation and tamper evidence with standard web crypto, no gas fees, no prices on a public chain.
- A signature proves *who said what, when* — not that stock exists. That is why assurance levels and the mandate rule
  on unverified stock exist.
