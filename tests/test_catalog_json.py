import json
from decimal import Decimal

from ttap.adapters.outbound.catalog_json import JsonCatalog, parse_product
from tests.factories import raw_product


def test_parse_extracts_claims_labels_and_drops_temperature_markers():
    p = parse_product(raw_product("1", "Milk 1 l", claims=("FREE_FROM_LACTOSE",), labels=("EU_ORGANIC_FARMING",)))
    assert p.claims == frozenset({"FREE_FROM_LACTOSE"})
    assert p.labels == frozenset({"EU_ORGANIC_FARMING"})
    assert p.has_classification_data is True


def test_lot_size_001_is_one_and_other_lots_kept():
    assert parse_product(raw_product("1", "x", lot=0.01)).lot_size == Decimal("1")
    assert parse_product(raw_product("2", "x", lot=1.5)).lot_size == Decimal("1.5")


def test_manufacturer_origin_numeric_codes_become_alpha2():
    p = parse_product(raw_product("1", "x", origin="gb", synkka_origins=("528",)))
    assert p.origin_valio == "gb"
    assert p.origin_manufacturer == ("nl",)


def test_missing_classification_is_flagged():
    p = parse_product(raw_product("1", "x", with_classification=False))
    assert p.has_classification_data is False


def test_search_ranks_by_matched_tokens(tmp_path):
    raws = [raw_product("1", "Orange juice 1 l"), raw_product("2", "Lactose free milk 1 l"),
            raw_product("3", "Milk chocolate")]
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(raws))
    cat = JsonCatalog.from_file(path)
    ids = [p.product_id for p in cat.search("lactose free milk")]
    assert ids[0] == "2"
    assert "1" not in ids
    assert cat.get("3").display_name() == "Milk chocolate"
    assert cat.version.startswith("sha256:")
