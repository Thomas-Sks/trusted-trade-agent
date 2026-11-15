from buyer_agent.kitchen import Kitchen


def test_report_lists_low_items_with_quantity_back_to_par():
    k = Kitchen()
    low = {r["item"]: r for r in k.report()["low"]}
    milk = next(it for it in k.items if it.key == "milk")
    assert milk.label in low
    assert low[milk.label]["order_quantity"] == milk.par - milk.on_hand
    assert all(r["order_quantity"] > 0 for r in low.values())
    assert not any(it.label in low for it in k.items if not it.low())


def test_dinner_service_consumes_stock_and_never_goes_negative():
    k = Kitchen()
    for _ in range(20):
        k.dinner_service()
    assert all(it.on_hand >= 0 for it in k.items)
    assert all(it.low() for it in k.items)


def test_order_status_follows_request_offer_order_chain_even_when_interleaved():
    k = Kitchen()
    k.track({"type": "tool_result", "tool": "create_request",
             "result": {"request_id": "rq1", "lines": [{"need": {"product_id": k.items[0].product_id}}]}})
    k.track({"type": "tool_result", "tool": "create_request",
             "result": {"request_id": "rq2", "lines": [{"need": {"product_id": k.items[3].product_id}}]}})
    k.track({"type": "tool_result", "tool": "lookup", "result": {"offer_id": "of2", "request_id": "rq2"}})
    k.track({"type": "tool_result", "tool": "lookup", "result": {"offer_id": "of1", "request_id": "rq1"}})
    k.track({"type": "tool_result", "tool": "place_order", "result": {"order_id": "or1", "offer_id": "of1"}})
    k.track({"type": "tool_result", "tool": "place_order", "result": {"order_id": "or2", "offer_id": "of2"}})
    orders = [{"order_id": "or1", "state": "AUTO_APPROVED", "total_net": "10", "decision": {"rules_fired": []}},
              {"order_id": "or2", "state": "PENDING_HUMAN", "total_net": "900",
               "decision": {"rules_fired": ["unverified_stock_over_limit"]}}]
    items = {i["key"]: i for i in k.state(orders)["items"]}
    assert items[k.items[0].key]["order"]["state"] == "AUTO_APPROVED"
    assert items[k.items[3].key]["order"]["rules_fired"] == ["unverified_stock_over_limit"]
    assert items[k.items[1].key]["order"] is None
    k.reset()
    assert all(i["order"] is None for i in k.state(orders)["items"])
