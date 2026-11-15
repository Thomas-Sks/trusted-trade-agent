from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from ttap.adapters.outbound.catalog_json import JsonCatalog
from ttap.adapters.outbound.cedar_engine import CedarPolicyEngine
from ttap.adapters.outbound.clocks import FixedClock
from ttap.adapters.outbound.jsonl_audit import MemoryAuditLog
from ttap.adapters.outbound.jws_signer import EcdsaSigner
from ttap.adapters.outbound.memory_mandates import InMemoryMandates
from ttap.adapters.outbound.sqlite_store import SqliteStore
from ttap.application.auditing import Auditor
from ttap.application.lookup import LookupService
from ttap.application.orders import OrderService
from ttap.application.requests import RequestService
from ttap.domain.models import Delivery, Mandate, Need, Quantity, RequestLine, SelectedLine, Unit
from tests.factories import DEMO_NOW, MONDAY, price, product, stock
from tests.fakes import FakeGateway

POLICIES = Path(__file__).resolve().parent.parent / "policies" / "base.cedar"


class Env:
    def __init__(self, limit: str = "2000"):
        self.clock = FixedClock(DEMO_NOW)
        self.store = SqliteStore()
        self.signer = EcdsaSigner()
        catalog = JsonCatalog([product("M1", "Lactose free milk 1 l", claims=("FREE_FROM_LACTOSE",))], "sha256:t")
        gateway = FakeGateway({"M1": price("M1", "1.01", "1.01")}, {"M1": stock("M1", "9999999999")})
        mandates = InMemoryMandates({"org_a": Mandate(
            org_id="org_a", version=1, valid_until=DEMO_NOW + timedelta(days=30),
            limit_per_order_net=Decimal(limit), max_unverified_value_net=Decimal("500"))})
        counter = iter(range(1, 10_000))
        new_id = lambda prefix: f"{prefix}_{next(counter)}"  # noqa: E731
        self.mandates = mandates
        self.policy = CedarPolicyEngine.from_file(POLICIES)
        self.audit = MemoryAuditLog(self.signer)
        self.auditor = Auditor(self.audit, self.clock, new_id)
        self.new_id = new_id
        self.requests = RequestService(self.store, new_id, self.auditor)
        self.lookup = LookupService(catalog, gateway, self.signer, self.clock, self.store, new_id, self.auditor,
                                    offer_ttl=timedelta(minutes=30))
        self.orders = OrderService(self.store, self.signer, self.policy, mandates, self.clock, new_id,
                                   self.auditor)

    async def offer(self, litres: str = "1000", org: str = "org_a"):
        req = self.requests.create(org, [RequestLine(
            line_id="L1", need=Need(text="lactose free milk", required_claims=["FREE_FROM_LACTOSE"]),
            quantity=Quantity(value=Decimal(litres), unit=Unit.L))],
            Delivery(requested_date=MONDAY, latest_acceptable_date=MONDAY))
        return await self.lookup.lookup(org, req.request_id)


GOOD = [SelectedLine(line_id="L1", tier="good")]
