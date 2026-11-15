from ttap.adapters.outbound.catalog_json import JsonCatalog
from ttap.adapters.outbound.clocks import FixedClock
from ttap.bootstrap import DEMO_START, build_services, parse_agent_keys
from tests.factories import product
from tests.fakes import FakeGateway


def test_parse_agent_keys():
    assert parse_agent_keys("a:org_a, b:org_b") == {"a": "org_a", "b": "org_b"}


def test_build_services_wires_everything():
    s = build_services(JsonCatalog([product("1", "x")], "v"), FakeGateway({}, {}), FixedClock(DEMO_START))
    assert s.requests and s.lookup and s.orders and s.signer.public_jwk()["kty"] == "EC"
