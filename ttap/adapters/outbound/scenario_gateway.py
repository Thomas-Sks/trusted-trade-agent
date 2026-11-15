"""Demo-only fault injection around the real supplier gateway. Every alteration is flagged as SIMULATED."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from ttap.domain.errors import UpstreamUnavailable
from ttap.domain.models import UpstreamAvailability, UpstreamPrice
from ttap.ports import SupplierGateway


class Scenario(BaseModel):
    stock_override: dict[str, Decimal] = {}
    price_increase_pct: dict[str, Decimal] = {}
    outage: bool = False

    def active(self) -> list[str]:
        out = [f"stock:{p}={v}" for p, v in self.stock_override.items()]
        out += [f"price:{p}+{v}%" for p, v in self.price_increase_pct.items()]
        return out + (["outage"] if self.outage else [])


class ScenarioGateway:
    def __init__(self, inner: SupplierGateway):
        self._inner = inner
        self.scenario = Scenario()

    def set(self, scenario: Scenario) -> None:
        self.scenario = scenario

    def clear(self) -> None:
        self.scenario = Scenario()

    async def prices(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamPrice]:
        if self.scenario.outage:
            raise UpstreamUnavailable("SIMULATED outage")
        out = await self._inner.prices(product_ids, delivery)
        for pid, pct in self.scenario.price_increase_pct.items():
            p = out.get(pid)
            if p and not p.error and p.unit_net is not None:
                factor = 1 + pct / 100
                out[pid] = p.model_copy(update={
                    "unit_net": (p.unit_net * factor).quantize(Decimal("0.01")),
                    "comparison_net": (p.comparison_net * factor).quantize(Decimal("0.01"))
                    if p.comparison_net is not None else None})
        return out

    async def availability(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamAvailability]:
        if self.scenario.outage:
            raise UpstreamUnavailable("SIMULATED outage")
        out = await self._inner.availability(product_ids, delivery)
        for pid, amount in self.scenario.stock_override.items():
            if pid in out:
                out[pid] = out[pid].model_copy(update={"available_amount": amount, "logistic_model": "Stock"})
        return out
