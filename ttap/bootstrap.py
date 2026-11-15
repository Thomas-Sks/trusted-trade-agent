from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx

from ttap.adapters.inbound.rest_api import Services
from ttap.adapters.outbound.catalog_json import JsonCatalog
from ttap.adapters.outbound.cedar_engine import CedarPolicyEngine
from ttap.adapters.outbound.clocks import ShiftedClock
from ttap.adapters.outbound.jsonl_audit import JsonlAuditLog, MemoryAuditLog
from ttap.adapters.outbound.jws_signer import EcdsaSigner
from ttap.adapters.outbound.memory_mandates import InMemoryMandates
from ttap.adapters.outbound.sqlite_store import SqliteStore
from ttap.adapters.outbound.valio_gateway import ValioGateway
from ttap.application.auditing import AuditLog, Auditor
from ttap.application.lookup import LookupService
from ttap.application.orders import OrderService
from ttap.application.requests import RequestService
from ttap.domain.models import Mandate
from ttap.ports import CatalogRepository, Clock, MandateRepository, Signer, Store, SupplierGateway

ROOT = Path(__file__).resolve().parent.parent
POLICIES = ROOT / "policies" / "base.cedar"
DEMO_START = datetime.fromisoformat("2026-11-12T08:00:00+02:00")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def parse_agent_keys(raw: str) -> dict[str, str]:
    pairs = (item.strip().split(":", 1) for item in raw.split(",") if item.strip())
    return {key: org for key, org in pairs}


def demo_mandates() -> InMemoryMandates:
    until = DEMO_START + timedelta(days=60)
    return InMemoryMandates({
        "org_hotel_a": Mandate(org_id="org_hotel_a", version=1, valid_until=until,
                               limit_per_order_net=Decimal("2000"), max_unverified_value_net=Decimal("500")),
        "org_resto_b": Mandate(org_id="org_resto_b", version=1, valid_until=until,
                               limit_per_order_net=Decimal("800"), max_unverified_value_net=Decimal("200")),
    })


def build_services(catalog: CatalogRepository, gateway: SupplierGateway, clock: Clock,
                   store: Store | None = None, signer: Signer | None = None,
                   mandates: MandateRepository | None = None, audit: AuditLog | None = None) -> Services:
    store = store or SqliteStore()
    signer = signer or EcdsaSigner()
    mandates = mandates or demo_mandates()
    auditor = Auditor(audit or MemoryAuditLog(signer), clock, new_id)
    return Services(
        requests=RequestService(store, new_id, auditor),
        lookup=LookupService(catalog, gateway, signer, clock, store, new_id, auditor),
        orders=OrderService(store, signer, CedarPolicyEngine.from_file(POLICIES), mandates, clock, new_id, auditor),
        signer=signer,
    )


def build_live() -> tuple[Services, dict[str, str]]:
    catalog = JsonCatalog.from_file(ROOT / os.environ.get(
        "CATALOG_PATH", "resources/valio_aimo_junction26_product_data.json"))
    client = httpx.AsyncClient(base_url=os.environ.get("VALIO_BASE_URL", "https://junction26.valioaimo.fi"),
                               timeout=30.0)
    gateway = ValioGateway(client, os.environ["VALIO_API_KEY"])
    signer = EcdsaSigner.load_or_create(os.environ.get("TTAP_SIGNING_KEY", str(ROOT / "ttap_signing_key.json")))
    services = build_services(catalog, gateway, ShiftedClock(DEMO_START),
                              store=SqliteStore(os.environ.get("TTAP_DB", "ttap.db")), signer=signer,
                              audit=JsonlAuditLog(os.environ.get("TTAP_AUDIT", "audit.jsonl"), signer))
    keys = parse_agent_keys(os.environ.get("AGENT_KEYS", "demo-key-hotel-a:org_hotel_a,demo-key-resto-b:org_resto_b"))
    return services, keys
