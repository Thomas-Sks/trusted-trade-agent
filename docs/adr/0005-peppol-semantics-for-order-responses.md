# ADR 0005 — Peppol BIS Ordering semantics for partial availability and substitution

**Status:** accepted · 2026-11-15

## Context
We needed a standard vocabulary for "accepted with changes", partial quantities and substitutes. The Finnish State
mandates Peppol Advanced Ordering for its suppliers; the Finnish retail Peppol guide leaves substitution out.

## Decision
Order responses use Peppol codes: header AP / CA / RE (CA must carry lines, AP and RE must not), line status
5 (accepted) / 3 (changed) / 1 (added) / 7 (not accepted), a substituted-for reference and a backorder quantity.

## Consequences
- Partial availability and official Valio substitutes map one-to-one onto an existing European standard.
- Export to UBL XML for an ERP is a mapping, not a redesign (roadmap).
