# Assumptions

Everything the prototype assumes about the challenge environment, stated explicitly. Each one is visible in the
code, in an ADR, or flagged in the UI.

## About the Valio mock API (confirmed by a Valio developer during the event)
| # | Assumption | Where it shows |
|---|---|---|
| A1 | There is no order API: an order is produced for (human or mandate) approval and is "ready to transmit"; nothing is sent to Valio. | `CONFIRMED` state reserved for the ERP hand-off (roadmap) |
| A2 | `availableAmount ≥ 999999` means **unknown** supplier stock (Terminal products), orderable. It is never shown as "in stock". | assurance level `UNKNOWN_SUPPLIER_STOCK`, rule `unverified_stock_over_limit` |
| A3 | Very large values (9999999999, 666666666…) are treated as known, effectively unlimited stock. | `VERIFIED_UNLIMITED` / `VERIFIED_QTY` |
| A4 | Empty `scheduleLines` = not available. An unknown product id looks identical, so ids are validated against the catalogue first. | exclusion `UNAVAILABLE`, error `UNKNOWN_PRODUCT` |
| A5 | `allowedLotSize` 0.01 means 1. Other lot sizes (1.5, 2, 10…) are honoured. | `ttap/domain/quantities.py` |
| A6 | `closingTime` is the order cut-off for `availableDate`. The mock is frozen around **2026-11-12**, so the demo clock starts at 2026-11-12 08:00 Europe/Helsinki and can be fast-forwarded. | `ShiftedClock`, demo menu |
| A7 | Availability and prices do not depend on the requested date in the mock; price validity (`validTo`) is real and bounds offers. | `offer_valid_until`, `lock_until` |
| A8 | The `customer` parameter is ignored by the mock. The gateway never lets an agent choose it: the organisation comes from the credential. | `rest_api.py` auth |
| A9 | Rate limits: < 10 req/s, a 429 blocks for 30 s. The gateway throttles to 8 req/s, batches ≤ 1,000 ids, caches. | `valio_gateway.py`, `caching_gateway.py` |

## About the data
| # | Assumption |
|---|---|
| D1 | Deposit material codes have no price: totals including deposits are flagged incomplete (not computed). |
| D2 | Carbon values are product-group averages: they never rank products within the same category. |
| D3 | 463 products have a Valio origin that differs from the manufacturer origin (Synkka): both are exposed with a `CONFLICT` level. |
| D4 | Missing classification data is not evidence of absence ("no allergen declared" ≠ "allergen free"): hard constraints on missing data exclude the product. |
| D5 | Third-party attestation of labels (organic, MSC…) is not available in the dataset; labels are `SUPPLIER_DECLARED`. |

## About the prototype
| # | Assumption |
|---|---|
| P1 | Two demo organisations (Aurora Hotel, Bistro Bruno) with in-memory mandates; the hotel's usual products are customer data, not rules. |
| P2 | Demo credentials are static API keys; production uses OAuth 2.1 per organisation and RFC 9421 request signatures. |
| P3 | The stock reservation ledger protects only orders that go through this gateway; real protection needs a reservation endpoint on Valio's side. |
| P4 | Simulated scenarios (shortage, price rise, outage, prompt injection, clock) are visibly flagged `SIMULATED` in offers, cards and the UI. |
| P5 | The evaluation set (16 cases) is small and written by the team; it measures regressions, not market-wide accuracy. |
| P6 | The hosted demo is public: anyone with the link can onboard, order and approve. LLM spend is bounded by per-visitor and daily caps, input length caps and a purchasing-only agent; demo state can be reset. |
| P7 | Mandates are held in memory. Onboarded organisations are stored (SQLite) with the mandate set at onboarding, so a gateway restart restores those limits; a pause (kill switch) is not persisted and is lifted by a restart. Orders, reservations and the audit chain persist. |
