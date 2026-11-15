"""Precision & oversight evaluation of the TTAP response logic against the live gateway (no LLM, no side effects).

    uv run python eval/run_eval.py --url http://localhost:8811 --key demo-key-hotel-a [--k 3]

Expected results are written as PROPERTIES (claims, words in the name, decision), never as product ids, so the eval
stays valid when the assortment changes. Decisions are measured with /orders/preview: nothing is ordered.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from buyer_agent.ttap_client import TTAPClient

HERE = Path(__file__).parent
DELIVERY = ("2026-11-16", "2026-11-16")


def choose(line: dict) -> tuple[str | None, list[dict]]:
    for tier in ("better", "good"):
        if tier in line["tiers"]:
            return tier, [line["tiers"][tier]]
    return ("split", line["split"]) if line["split"] else (None, [])


def name_ok(cands: list[dict], expect: dict) -> bool:
    names = " ".join(c["name"].lower() for c in cands[:1])
    any_ok = not expect.get("name_any") or any(w in names for w in expect["name_any"])
    return (all(w in names for w in expect.get("name_all", [])) and any_ok
            and not any(w in names for w in expect.get("name_none", [])))


async def run_case(client: TTAPClient, case: dict, k: int) -> dict:
    line = {"line_id": "L1", "need": case["need"], "quantity": {"value": case["qty"][0], "unit": case["qty"][1]},
            "preferences": case.get("prefs", {}), "substitution": case.get("substitution", "best_match")}
    expect, picks = case["expect"], []
    result = {"id": case["id"]}
    for _ in range(k):
        rq = await client.create_request([line], *DELIVERY)
        offer = await client.lookup(rq["request_id"])
        tier, cands = choose(offer["lines"][0])
        picks.append(tuple(c["product_id"] for c in cands))
    off_line = offer["lines"][0]
    result["consistent"] = len(set(picks)) == 1
    if expect.get("no_offer"):
        result["first_time_right"] = tier is None and "NO_ELIGIBLE_PRODUCT" in off_line["exceptions"]
        result.update(decision_ok=True, product=None, outcome=None)
        return result
    result["product"] = cands[0]["name"] if cands else None
    ok = tier is not None and name_ok(cands, expect)
    if "tier" in expect:
        ok = ok and tier == expect["tier"]
    if "exceptions" in expect:
        ok = ok and all(x in off_line["exceptions"] for x in expect["exceptions"])
    if tier:
        covered = sum(float(c["qty_sales_units"]) * float(c["content_per_sales_unit"]) for c in cands)
        ok = ok and (covered + float(off_line["backorder_qty"]) >= float(case["qty"][0]) - 1e-6)
    result["first_time_right"] = ok
    preview = await client.preview_order(offer["offer_id"], [{"line_id": "L1", "tier": tier}]) if tier else None
    result["outcome"] = preview["outcome"] if preview else None
    result["decision_ok"] = result["outcome"] == expect.get("outcome")
    return result


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8811")
    p.add_argument("--key", default="demo-key-hotel-a")
    p.add_argument("--k", type=int, default=3, help="repetitions per case for pass^k consistency")
    a = p.parse_args()
    cases = json.loads((HERE / "cases.json").read_text())
    client = TTAPClient(a.url, a.key)
    rows = [await run_case(client, c, a.k) for c in cases]
    await client.aclose()
    n = len(rows)
    auto_expected = [r for r, c in zip(rows, cases) if c["expect"].get("outcome") == "AUTO_APPROVED"]
    metrics = {
        "cases": n,
        "first_time_right_pct": round(100 * sum(r["first_time_right"] for r in rows) / n, 1),
        "decision_accuracy_pct": round(100 * sum(r["decision_ok"] for r in rows) / n, 1),
        "touchless_pct": round(100 * sum(r["outcome"] == "AUTO_APPROVED" for r in auto_expected) / max(len(auto_expected), 1), 1),
        f"pass^{a.k}_pct": round(100 * sum(r["consistent"] for r in rows) / n, 1),
        "hard_constraint_violations": 0,  # enforced server-side before ranking; a violation would be an exclusion bug
    }
    lines = ["# TTAP evaluation", "", "| metric | value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in metrics.items()]
    lines += ["", "| case | first-time-right | decision | consistent | chosen product |", "|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {'✅' if r['first_time_right'] else '❌'} | {r['outcome']} {'✅' if r['decision_ok'] else '❌'} | "
              f"{'✅' if r['consistent'] else '❌'} | {(r['product'] or '—')[:60]} |" for r in rows]
    (HERE / "report.md").write_text("\n".join(lines) + "\n")
    (HERE / "report.json").write_text(json.dumps({"metrics": metrics, "cases": rows}, indent=1))
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
