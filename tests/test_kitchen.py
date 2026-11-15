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
             "result": {"request_id": "rq1", "lines": [{"need": {"product_id": k.items[0].product_id},
                                                        "quantity": {"value": "66", "unit": "L"}}]}})
    k.track({"type": "tool_result", "tool": "create_request",
             "result": {"request_id": "rq2", "lines": [{"need": {"product_id": k.items[3].product_id},
                                                        "quantity": {"value": "21", "unit": "KG"}}]}})
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
    # items on order are not reported as low again (no double ordering)
    assert k.items[0].label not in {r["item"] for r in k.report()["low"]}
    # delivery: only the approved order goes into stock, and only once
    before = k.items[0].on_hand
    assert k.receive(orders) and k.items[0].on_hand == before + 66
    assert k.receive(orders) == []
    assert items[k.items[3].key]["order"]["state"] == "PENDING_HUMAN" and k.items[3].on_hand == 3
    k.reset()
    assert all(i["order"] is None for i in k.state(orders)["items"])


def test_kitchen_state_survives_a_restart(tmp_path, monkeypatch):
    import buyer_agent.kitchen as kitchen
    monkeypatch.setattr(kitchen, "STATE_FILE", str(tmp_path / "kitchen.json"))
    monkeypatch.setattr(kitchen, "KITCHENS", {})
    k = kitchen.kitchen_for("key-a")
    k.dinner_service()
    k.track({"type": "tool_result", "tool": "create_request",
             "result": {"request_id": "rq1", "lines": [{"need": {"product_id": k.items[0].product_id},
                                                        "quantity": {"value": "5", "unit": "L"}}]}})
    monkeypatch.setattr(kitchen, "KITCHENS", {})
    kitchen.load()
    again = kitchen.kitchen_for("key-a")
    assert again.services == 1 and again.items[0].on_hand == k.items[0].on_hand
    assert again.request_lines == {"rq1": {k.items[0].product_id: 5.0}}
