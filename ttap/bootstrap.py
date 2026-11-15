from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx

from ttap.adapters.inbound.rest_api import DemoControls, Services
from ttap.adapters.outbound.caching_gateway import CachingGateway
from ttap.adapters.outbound.catalog_json import JsonCatalog
from ttap.adapters.outbound.cedar_engine import CedarPolicyEngine
from ttap.adapters.outbound.clocks import ShiftedClock
from ttap.adapters.outbound.jsonl_audit import JsonlAuditLog, MemoryAuditLog
from ttap.adapters.outbound.jws_signer import EcdsaSigner
from ttap.adapters.outbound.logging_notifier import LoggingNotifier
from ttap.adapters.outbound.memory_mandates import InMemoryMandates
from ttap.adapters.outbound.scenario_gateway import ScenarioCatalog, ScenarioGateway
from ttap.adapters.outbound.sqlite_store import SqliteStore
from ttap.adapters.outbound.valio_gateway import ValioGateway
from ttap.application.approvals import ApprovalService
from ttap.application.interpret import InterpretService
from ttap.application.auditing import AuditLog, Auditor
from ttap.application.lookup import LookupService
from ttap.application.mandates import MandateService
from ttap.application.onboarding import OnboardingService
from ttap.application.orders import OrderService
from ttap.application.requests import RequestService
from ttap.domain.models import Mandate, UsualItem
from ttap.ports import CatalogRepository, Clock, MandateRepository, Notifier, Signer, Store, SupplierGateway

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
        # usual_list is customer data (its order guide), not a rule: rules never reference product ids
        "org_hotel_a": Mandate(org_id="org_hotel_a", version=1, valid_until=until,
                               limit_per_order_net=Decimal("2000"), max_unverified_value_net=Decimal("500"),
                               period_budget_net=Decimal("20000"), max_orders_per_hour=5,
                               usual_list=[UsualItem(product_id="464306", median_qty=Decimal("1000")),
                                           UsualItem(product_id="462545", median_qty=Decimal("500"))]),
        "org_resto_b": Mandate(org_id="org_resto_b", version=1, valid_until=until,
                               limit_per_order_net=Decimal("800"), max_unverified_value_net=Decimal("200"),
                               period_budget_net=Decimal("20000"), max_orders_per_hour=12),
    })


def _usual_ids(mandates: MandateRepository, org_id: str) -> set[str]:
    mandate = mandates.get(org_id)
    return {u.product_id for u in mandate.usual_list} if mandate else set()


def build_services(catalog: CatalogRepository, gateway: SupplierGateway, clock: Clock,
                   store: Store | None = None, signer: Signer | None = None,
                   mandates: MandateRepository | None = None, audit: AuditLog | None = None,
                   notifier: Notifier | None = None, simulated=lambda: [], interpreter=None) -> Services:
    store = store or SqliteStore()
    signer = signer or EcdsaSigner()
    mandates = mandates or demo_mandates()
    auditor = Auditor(audit or MemoryAuditLog(signer), clock, new_id)
    policy = CedarPolicyEngine.from_file(POLICIES)
    return Services(
        requests=RequestService(store, new_id, auditor),
        lookup=LookupService(catalog, gateway, signer, clock, store, new_id, auditor, simulated=simulated,
                             usual=lambda org: _usual_ids(mandates, org)),
        orders=OrderService(store, signer, policy, mandates, clock, new_id, auditor),
        signer=signer,
        approvals=ApprovalService(store, policy, mandates, clock, auditor, notifier or LoggingNotifier()),
        auditor=auditor,
        interpret=InterpretService(interpreter, catalog, mandates, clock, auditor),
        mandates=MandateService(mandates, policy, auditor),
    )


def parse_approver_entries(raw: str) -> dict[str, tuple[str, str]]:
    """'secret:org:user,...' -> {secret: (org, user)} (used for approver API keys and Telegram pairing codes)."""
    out = {}
    for item in raw.split(","):
        if item.strip():
            secret, org, user = item.strip().split(":", 2)
            out[secret] = (org, user)
    return out


def _interpreter():
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return None
    from ttap.adapters.outbound.claude_interpreter import ClaudeInterpreter
    return ClaudeInterpreter()


@dataclass
class LiveApp:
    services: Services
    agent_keys: dict[str, str]
    approver_keys: dict[str, tuple[str, str]]
    lifecycle: object | None
    admin_key: str | None


def build_live() -> LiveApp:
    res = ROOT / "resources"
    catalog = JsonCatalog.from_files(
        ROOT / os.environ.get("CATALOG_PATH", "resources/valio_aimo_junction26_product_data.json"),
        res / "valio_aimo_junction26_delivery_reliability.csv", res / "valio_aimo_junction26_carbon_footprint.csv")
    client = httpx.AsyncClient(base_url=os.environ.get("VALIO_BASE_URL", "https://junction26.valioaimo.fi"),
                               timeout=30.0)
    scenario = ScenarioGateway(ValioGateway(client, os.environ["VALIO_API_KEY"]))
    gateway = CachingGateway(scenario)
    signer = EcdsaSigner.load_or_create(os.environ.get("TTAP_SIGNING_KEY", str(ROOT / "ttap_signing_key.json")))
    store = SqliteStore(os.environ.get("TTAP_DB", "ttap.db"), stock_scope=os.environ.get("TTAP_STOCK_SCOPE", "global"))
    clock = ShiftedClock(DEMO_START)
    telegram = None
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        from ttap.adapters.outbound.telegram_notifier import TelegramNotifier
        telegram = TelegramNotifier(os.environ["TELEGRAM_BOT_TOKEN"], store)
    catalog = ScenarioCatalog(catalog, scenario)
    services = build_services(catalog, gateway, clock, store=store, signer=signer,
                              audit=JsonlAuditLog(os.environ.get("TTAP_AUDIT", "audit.jsonl"), signer),
                              notifier=telegram, simulated=lambda: scenario.scenario.active(),
                              interpreter=_interpreter())
    services.demo = DemoControls(scenario=scenario, cache=gateway, clock=clock, store=store)
    pairing = parse_approver_entries(os.environ.get(
        "APPROVER_PAIRING", "PAIR-HOTEL-A:org_hotel_a:chef_alice,PAIR-RESTO-B:org_resto_b:chef_bruno"))
    if telegram:
        from ttap.adapters.inbound.telegram_logic import ApprovalBotLogic
        telegram.bind(ApprovalBotLogic(store, services.approvals, pairing, clock,
                                       web_base_url=os.environ.get("TTAP_PUBLIC_URL"), mandates=services.mandates))
    keys = parse_agent_keys(os.environ.get("AGENT_KEYS", "demo-key-hotel-a:org_hotel_a,demo-key-resto-b:org_resto_b"))
    approvers = parse_approver_entries(os.environ.get("APPROVER_KEYS", "approver-key-hotel-a:org_hotel_a:chef_alice,approver-key-resto-b:org_resto_b:chef_bruno"))
    services.onboarding = OnboardingService(store, services.mandates._mandates, clock, services.auditor, keys, approvers,
                                            pairing, telegram_bot=os.environ.get("TELEGRAM_BOT_USERNAME"))
    services.onboarding.load_all()
    return LiveApp(services, keys, approvers, telegram, os.environ.get("ADMIN_KEY", "admin-key-valio"))
