"""Self-service onboarding (demo): an organisation registers, sets its mandate and gets agent/approver credentials
plus a one-time Telegram pairing code. Registries are shared dicts read by the REST and Telegram adapters."""
from __future__ import annotations

import re
import secrets
from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ttap.application.auditing import Auditor
from ttap.application.errors import TTAPError
from ttap.domain.models import Mandate
from ttap.ports import Clock, MandateRepository

MAX_ORGS = 500


class OrganisationLimitReached(TTAPError):
    code, status = "ONBOARDING_CLOSED", 429


class NewOrganisation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=60)
    approver_name: str = Field(min_length=2, max_length=40)
    limit_per_order_net: Decimal = Field(default=Decimal("2000"), gt=0)
    period_budget_net: Decimal = Field(default=Decimal("10000"), gt=0)
    max_unverified_value_net: Decimal = Field(default=Decimal("500"), ge=0)
    max_orders_per_hour: int = Field(default=5, gt=0, le=100)


class Organisation(BaseModel):
    org_id: str
    name: str
    approver_name: str
    agent_key: str
    approver_key: str
    pairing_code: str
    mandate: Mandate


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:24] or "org"


class OnboardingService:
    def __init__(self, store, mandates: MandateRepository, clock: Clock, auditor: Auditor,
                 agent_keys: dict[str, str], approver_keys: dict[str, tuple[str, str]],
                 pairing_codes: dict[str, tuple[str, str]], telegram_bot: str | None = None):
        self._store, self._mandates, self._clock, self._auditor = store, mandates, clock, auditor
        self._agent_keys, self._approver_keys, self._pairing = agent_keys, approver_keys, pairing_codes
        self._bot = telegram_bot

    def register(self, org: Organisation) -> None:
        """Make an organisation live in every registry (used at creation and when reloading at startup)."""
        self._mandates.save(org.mandate)
        self._agent_keys[org.agent_key] = org.org_id
        self._approver_keys[org.approver_key] = (org.org_id, org.approver_name)
        self._pairing[org.pairing_code] = (org.org_id, org.approver_name)

    def load_all(self) -> int:
        orgs = [Organisation.model_validate_json(b) for b in self._store.list_organisations()]
        for org in orgs:
            self.register(org)
        return len(orgs)

    def create(self, data: NewOrganisation) -> dict:
        if self._store.count_organisations() >= MAX_ORGS:
            raise OrganisationLimitReached("demo onboarding is full")
        org_id = f"org_{_slug(data.name)}_{secrets.token_hex(3)}"
        approver = _slug(data.approver_name)
        mandate = Mandate(org_id=org_id, version=1, valid_until=self._clock.now() + timedelta(days=60),
                          limit_per_order_net=data.limit_per_order_net, period_budget_net=data.period_budget_net,
                          max_unverified_value_net=data.max_unverified_value_net,
                          max_orders_per_hour=data.max_orders_per_hour)
        org = Organisation(org_id=org_id, name=data.name, approver_name=approver,
                           agent_key=f"agt_{secrets.token_urlsafe(18)}", approver_key=f"apr_{secrets.token_urlsafe(18)}",
                           pairing_code=f"PAIR-{secrets.token_hex(4).upper()}", mandate=mandate)
        self._store.save_organisation(org.org_id, org.model_dump_json())
        self.register(org)
        self._auditor.record(org_id=org_id, step="request", action="organisation_onboarded", subject=f"org/{org_id}",
                             actor=f"approver:{approver}", outcome="active",
                             explanation=f"{data.name} onboarded: per-order limit €{data.limit_per_order_net}, "
                                         f"weekly budget €{data.period_budget_net}, approver {approver}")
        return {**org.model_dump(mode="json", exclude={"mandate"}), "mandate": mandate.model_dump(mode="json"),
                "telegram_link": f"https://t.me/{self._bot}?start={org.pairing_code}" if self._bot else None}

    def status(self, org_id: str) -> dict:
        chats = self._store.approver_chats(org_id)
        return {"org_id": org_id, "telegram_paired": bool(chats), "paired_devices": len(chats)}
