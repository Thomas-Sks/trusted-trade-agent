from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import pycountry

from ttap.domain.models import CatalogProduct

_TOKEN_RE = re.compile(r"[a-zåäöéü0-9]+")
_CLASSIFICATION_GROUPS = {"allergen", "nonAllergen", "nutritionalClaim", "packagingMarkedLabel"}


def _alpha2(numeric: str) -> str:
    country = pycountry.countries.get(numeric=numeric.zfill(3))
    return country.alpha_2.lower() if country else numeric


def _enum_ids(synkka: dict, group: str) -> frozenset[str]:
    return frozenset(
        v["id"]
        for g in synkka.get("classifications") or []
        if g.get("name") == group
        for v in g.get("values") or []
        if isinstance(v, dict) and "id" in v
    )


def parse_product(raw: dict) -> CatalogProduct:
    synkka = raw.get("synkkaData") or {}
    lot = Decimal(str(raw.get("allowedLotSize") or 1))
    if lot <= Decimal("0.01"):
        lot = Decimal("1")
    has_data = any(
        g.get("values") for g in synkka.get("classifications") or [] if g.get("name") in _CLASSIFICATION_GROUPS
    )
    return CatalogProduct(
        product_id=raw["id"],
        gtin=raw.get("salesUnitGtin"),
        names={n["language"]: n["value"] for n in synkka.get("names") or []},
        category=raw.get("category", ""),
        vendor=raw.get("vendorName", ""),
        brand=synkka.get("brand"),
        sales_unit=raw["salesUnit"],
        base_unit=raw["baseUnit"],
        units={u["unitId"]: Decimal(str(u["sizeInBaseUnits"])) for u in raw.get("units") or []},
        lot_size=lot,
        claims=_enum_ids(synkka, "nutritionalClaim"),
        labels=frozenset(x for x in _enum_ids(synkka, "packagingMarkedLabel") if not x.endswith("Temperature")),
        allergens_contained=_enum_ids(synkka, "allergen"),
        has_classification_data=has_data,
        origin_valio=raw.get("countryOfOrigin"),
        origin_manufacturer=tuple(sorted({_alpha2(c) for c in synkka.get("countriesOfOrigin") or []})),
        substitutes=tuple(s["substituteProduct"] for s in raw.get("substitutions") or []),
        variable_weight=bool(synkka.get("variableUnit")),
    )


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 3}


class JsonCatalog:
    def __init__(self, products: list[CatalogProduct], version: str):
        self._by_id = {p.product_id: p for p in products}
        self._version = version
        self._index = {p.product_id: _tokens(" ".join(p.names.values())) for p in products}

    @classmethod
    def from_file(cls, path: str | Path) -> JsonCatalog:
        raw = Path(path).read_bytes()
        version = "sha256:" + hashlib.sha256(raw).hexdigest()[:16]
        return cls([parse_product(r) for r in json.loads(raw)], version)

    @property
    def version(self) -> str:
        return self._version

    def get(self, product_id: str) -> CatalogProduct | None:
        return self._by_id.get(product_id)

    def search(self, text: str, limit: int = 200) -> list[CatalogProduct]:
        wanted = _tokens(text)
        scored = [(len(wanted & toks), pid) for pid, toks in self._index.items() if wanted & toks]
        scored.sort(key=lambda s: (-s[0], s[1]))
        return [self._by_id[pid] for _, pid in scored[:limit]]
