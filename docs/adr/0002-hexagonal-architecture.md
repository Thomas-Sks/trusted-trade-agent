# ADR 0002 — Lightweight hexagonal architecture

**Status:** accepted · 2026-11-15

## Context
Everything that is a prototype today must be swappable for production: the mock Valio API, SQLite, Telegram, the LLM,
the clock. Tests must run on fabricated products to avoid overfitting to the dataset.

## Decision
Pure domain (`ttap/domain`, no I/O), use cases behind `typing.Protocol` ports (`ttap/ports.py`), adapters in
`ttap/adapters`, wiring in `ttap/bootstrap.py`. No DI framework, no DDD ceremony, one process.

## Consequences
- Production path is adapter by adapter: SQLite → Postgres, mock → real Valio API, Telegram → WhatsApp/Teams.
- The scenario injector and the stale-data cache are decorators around the supplier port: simulated data is isolated
  and always flagged.
- The domain is deterministic, which makes the mandate what-if replay possible.
