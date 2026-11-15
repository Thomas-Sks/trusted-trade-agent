# TTAP Phase 1 : fil complet — plan d'implémentation

> **Pour les agents qui exécutent :** SOUS-SKILL REQUIS : superpowers:subagent-driven-development (recommandé) ou superpowers:executing-plans, tâche par tâche. Les étapes sont des cases à cocher (`- [ ]`).

**Objectif :** une requête d'achat structurée traverse `Request → Lookup → Order → Approval (décision)` contre l'API mock Valio Aimo et ressort en `AUTO_APPROVED`, `PENDING_HUMAN` ou `DENIED`, via une API REST multi-organisations.

**Architecture :** hexagonale légère. `ttap/domain` est pur, `ttap/application` orchestre via `ttap/ports.py`, et `ttap/adapters` contient l'API Valio, le catalogue JSON, Cedar, SQLite, la signature JWS, les horloges et l'API REST FastAPI. L'assemblage se fait dans `ttap/bootstrap.py`.

**Stack technique :** Python 3.12, uv, fastapi 0.163, pydantic 2.14, httpx 0.28, cedarpy 4.12.2, joserfc 1.8, rfc8785 0.1.4, pycountry, pytest 9.2, pytest-asyncio 1.5, respx 0.23.

**Spec :** `SPEC.md` §0–§7, §10 (idempotence, compare-and-set), §14. Plan maître : `docs/superpowers/plans/2026-11-15-ttap-master-plan.md`.

## Contraintes globales
- Aucun identifiant produit, nom ou code catégorie dans le code ni dans les règles. Les tests utilisent des produits **fabriqués** (`tests/factories.py`).
- Tous les montants en `Decimal`. `float` n'est autorisé que pour `score`.
- `org_id` est toujours déduit du jeton `Authorization: Bearer <agent_key>`, jamais du corps. Un corps qui contient des champs inconnus est rejeté (`extra="forbid"`).
- `VALIO_API_KEY` vient de l'environnement. **Les jeux de données (`resources/*.json`, `*.csv`) ne sont jamais commités** : ils sont synthétiques et réservés au challenge.
- Appels amont : ≤ 8 req/s (`min_interval=0.125`), pause de 30 s sur un 429, au plus 1 000 ids par appel, `customer` amont constant (`"ttap-gateway"`).
- Horloge de démo : `2026-11-12T08:00:00+02:00`.
- Les commits se terminent par la ligne `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Fichiers de cette phase
| Fichier | Rôle |
|---|---|
| `pyproject.toml`, `.gitignore`, `.env.example` | projet, dépendances, secrets exclus |
| `ttap/domain/models.py` | tous les modèles pydantic (demande, catalogue, amont, offre, commande, mandat, décision) |
| `ttap/domain/quantities.py` | quantité extraite du nom, contenu par unité de vente, arrondi au lot |
| `ttap/domain/assurance.py` | niveaux de stock et d'origine, vérification des contraintes obligatoires |
| `ttap/domain/ranking.py` | évaluation d'un candidat, good / better / best |
| `ttap/domain/offer.py` | charge utile canonique, hash, validité de l'offre |
| `ttap/domain/decision.py` | contexte Cedar calculé par le serveur |
| `ttap/ports.py` | Protocols |
| `ttap/adapters/outbound/catalog_json.py` | lecture du fichier Synkka et recherche simple |
| `ttap/adapters/outbound/valio_gateway.py` | client amont (régulateur, 429, lots) |
| `ttap/adapters/outbound/jws_signer.py` | ES256 + JCS |
| `ttap/adapters/outbound/sqlite_store.py` | stockage, offre à usage unique, idempotence, compare-and-set |
| `ttap/adapters/outbound/cedar_engine.py` + `policies/base.cedar` | décision à 3 issues |
| `ttap/adapters/outbound/clocks.py`, `memory_mandates.py` | horloges, mandats en mémoire |
| `ttap/application/errors.py`, `requests.py`, `lookup.py`, `orders.py` | cas d'usage |
| `ttap/adapters/inbound/rest_api.py` | FastAPI |
| `ttap/bootstrap.py`, `ttap/main.py`, `scripts/smoke_milk.py` | assemblage, point d'entrée, test réel |
| `tests/…` | un fichier de test par module |

---

### Tâche 1 : squelette du projet et modèles du domaine

**Fichiers :**
- Créer : `pyproject.toml`, `.gitignore`, `.env.example`, `ttap/__init__.py`, `ttap/domain/__init__.py`, `ttap/application/__init__.py`, `ttap/adapters/__init__.py`, `ttap/adapters/inbound/__init__.py`, `ttap/adapters/outbound/__init__.py`, `ttap/domain/models.py`, `tests/__init__.py`, `tests/test_models.py`

**Interfaces :**
- Produit : tous les types de `ttap.domain.models` utilisés par les tâches 2 à 12 (`Unit`, `Quantity`, `Need`, `Preferences`, `RequestLine`, `Delivery`, `PurchaseRequest`, `CatalogProduct`, `StockStatus`, `OriginAssurance`, `UpstreamPrice`, `UpstreamAvailability`, `Candidate`, `Exclusion`, `OfferLine`, `Offer`, `OrderState`, `SelectedLine`, `Decision`, `Order`, `Mandate`).

- [ ] **Étape 1 : initialiser le dépôt et les fichiers du projet**

```bash
cd /home/weaver/Documents/30-hackathons/trusted_trade_agent
git init
mkdir -p ttap/domain ttap/application ttap/adapters/inbound ttap/adapters/outbound tests policies scripts
touch ttap/__init__.py ttap/domain/__init__.py ttap/application/__init__.py ttap/adapters/__init__.py \
      ttap/adapters/inbound/__init__.py ttap/adapters/outbound/__init__.py tests/__init__.py
```

`pyproject.toml` :
```toml
[project]
name = "ttap"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.163",
  "uvicorn>=0.54",
  "pydantic>=2.14",
  "httpx>=0.28",
  "cedarpy>=4.12.2",
  "joserfc>=1.8",
  "rfc8785>=0.1.4",
  "pycountry>=24.6",
]

[dependency-groups]
dev = ["pytest>=9.2", "pytest-asyncio>=1.5", "respx>=0.23"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["ttap"]
```

`.gitignore` :
```
.venv/
__pycache__/
*.db
*.db-wal
*.db-shm
.env
resources/*.json
resources/*.csv
```

`.env.example` :
```
VALIO_API_KEY=replace-me
VALIO_BASE_URL=https://junction26.valioaimo.fi
CATALOG_PATH=resources/valio_aimo_junction26_product_data.json
AGENT_KEYS=demo-key-hotel-a:org_hotel_a,demo-key-resto-b:org_resto_b
```

Lancer : `uv sync` → attendu : `.venv` créé, dépendances installées.

- [ ] **Étape 2 : écrire le test qui échoue**

`tests/test_models.py` :
```python
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ttap.domain.models import Delivery, Need, PurchaseRequest, Quantity, RequestLine, Unit


def test_purchase_request_requires_at_least_one_line():
    with pytest.raises(ValidationError):
        PurchaseRequest(request_id="rq_1", org_id="org_a", lines=[],
                        delivery=Delivery(requested_date=date(2026, 11, 16),
                                          latest_acceptable_date=date(2026, 11, 16)))


def test_quantity_must_be_positive():
    with pytest.raises(ValidationError):
        Quantity(value=Decimal("0"), unit=Unit.L)


def test_request_line_defaults():
    line = RequestLine(line_id="L1", need=Need(text="milk"),
                       quantity=Quantity(value=Decimal("1000"), unit=Unit.L))
    assert line.substitution == "best_match"
    assert line.preferences.origin == []
```

- [ ] **Étape 3 : lancer le test et vérifier qu'il échoue**

Lancer : `uv run pytest tests/test_models.py -v`
Attendu : ÉCHEC avec `ModuleNotFoundError: No module named 'ttap.domain.models'`

- [ ] **Étape 4 : écrire `ttap/domain/models.py`**

```python
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Unit(StrEnum):
    L = "L"
    KG = "KG"
    PIECE = "PIECE"


class Quantity(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: Decimal = Field(gt=0)
    unit: Unit


class Need(BaseModel):
    text: str
    required_claims: list[str] = []
    excluded_allergens: list[str] = []
    required_labels: list[str] = []
    product_id: str | None = None


class Preferences(BaseModel):
    origin: list[str] = []
    brands: list[str] = []
    labels: list[str] = []


SubstitutionPref = Literal["best_match", "no_substitute"]


class RequestLine(BaseModel):
    line_id: str
    need: Need
    quantity: Quantity
    preferences: Preferences = Preferences()
    substitution: SubstitutionPref = "best_match"


class Delivery(BaseModel):
    requested_date: date
    latest_acceptable_date: date


class PurchaseRequest(BaseModel):
    request_id: str
    org_id: str
    lines: list[RequestLine] = Field(min_length=1)
    delivery: Delivery


class CatalogProduct(BaseModel):
    model_config = ConfigDict(frozen=True)
    product_id: str
    gtin: str | None
    names: dict[str, str]
    category: str
    vendor: str
    brand: str | None
    sales_unit: str
    base_unit: str
    units: dict[str, Decimal]
    lot_size: Decimal
    claims: frozenset[str]
    labels: frozenset[str]
    allergens_contained: frozenset[str]
    has_classification_data: bool
    origin_valio: str | None
    origin_manufacturer: tuple[str, ...]
    substitutes: tuple[str, ...]
    variable_weight: bool

    def display_name(self, lang: str = "en") -> str:
        return self.names.get(lang) or next(iter(self.names.values()), self.product_id)


class StockStatus(StrEnum):
    VERIFIED_QTY = "VERIFIED_QTY"
    VERIFIED_UNLIMITED = "VERIFIED_UNLIMITED"
    UNKNOWN_SUPPLIER_STOCK = "UNKNOWN_SUPPLIER_STOCK"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"


class OriginAssurance(StrEnum):
    CONSISTENT = "CONSISTENT"
    CONFLICT = "CONFLICT"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    MISSING = "MISSING"


class UpstreamPrice(BaseModel):
    product_id: str
    error: bool
    unit_net: Decimal | None = None
    vat_rate: Decimal | None = None
    comparison_net: Decimal | None = None
    comparison_unit: str | None = None
    list_net: Decimal | None = None
    valid_to: datetime | None = None
    net_price_found: bool = False


class UpstreamAvailability(BaseModel):
    product_id: str
    sales_block: bool
    logistic_model: str | None = None
    available_amount: Decimal | None = None
    available_date: date | None = None
    sales_unit: str | None = None
    closing_time: datetime | None = None


Tier = Literal["good", "better", "best"]


class Candidate(BaseModel):
    product_id: str
    name: str
    qty_sales_units: Decimal
    sales_unit: str
    content_per_sales_unit: Decimal
    content_source: Literal["name", "price_ratio"]
    surplus: Decimal
    unit_net: Decimal
    line_total_net: Decimal
    vat_rate: Decimal
    comparison_net: Decimal
    price_valid_to: datetime | None
    stock: StockStatus
    available_amount: Decimal | None
    delivery_date: date
    order_cutoff: datetime | None
    origin: OriginAssurance
    origins: list[str]
    changes_vs_request: list[str]
    score: float


class Exclusion(BaseModel):
    product_id: str
    reason: str


class OfferLine(BaseModel):
    line_id: str
    tiers: dict[str, Candidate]
    excluded: list[Exclusion]
    exceptions: list[str]


class Offer(BaseModel):
    offer_id: str
    request_id: str
    org_id: str
    issued_at: datetime
    valid_until: datetime
    catalog_version: str
    lines: list[OfferLine]
    signature: str | None = None


class OrderState(StrEnum):
    PENDING_DECISION = "PENDING_DECISION"
    AUTO_APPROVED = "AUTO_APPROVED"
    PENDING_HUMAN = "PENDING_HUMAN"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    CONFIRMED = "CONFIRMED"


class SelectedLine(BaseModel):
    line_id: str
    tier: Tier


class Decision(BaseModel):
    outcome: Literal["AUTO_APPROVED", "PENDING_HUMAN", "DENIED"]
    rules_fired: list[str]
    context: dict[str, Any]


class Order(BaseModel):
    order_id: str
    org_id: str
    offer_id: str
    offer_hash: str
    selected: list[SelectedLine]
    state: OrderState
    version: int = 1
    total_net: Decimal
    decision: Decision | None = None
    idempotency_key: str


class Mandate(BaseModel):
    org_id: str
    version: int
    status: Literal["active", "suspended"] = "active"
    valid_until: datetime
    limit_per_order_net: Decimal
    max_unverified_value_net: Decimal
```

- [ ] **Étape 5 : lancer le test et vérifier qu'il passe**

Lancer : `uv run pytest tests/test_models.py -v` → attendu : 3 PASS

- [ ] **Étape 6 : commit**

```bash
git add pyproject.toml uv.lock .gitignore .env.example ttap tests
git commit -m "feat: project scaffold and domain models" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 2 : fabrique de produits de test et adaptateur catalogue

**Fichiers :**
- Créer : `tests/factories.py`, `ttap/adapters/outbound/catalog_json.py`, `tests/test_catalog_json.py`

**Interfaces :**
- Utilise : `CatalogProduct` (tâche 1).
- Produit : `parse_product(raw: dict) -> CatalogProduct` ; `JsonCatalog(products: list[CatalogProduct], version: str)` avec `.version: str`, `.get(product_id) -> CatalogProduct | None`, `.search(text: str, limit: int = 200) -> list[CatalogProduct]`, et `JsonCatalog.from_file(path: str | Path) -> JsonCatalog`. `tests.factories.raw_product(...)` est utilisé par toutes les tâches suivantes.

- [ ] **Étape 1 : écrire la fabrique (ce n'est pas un test, c'est un utilitaire)**

`tests/factories.py` :
```python
from datetime import date, datetime
from decimal import Decimal

from ttap.adapters.outbound.catalog_json import parse_product
from ttap.domain.models import CatalogProduct, UpstreamAvailability, UpstreamPrice

DEMO_NOW = datetime.fromisoformat("2026-11-12T08:00:00+02:00")
MONDAY = date(2026, 11, 16)


def raw_product(pid: str, name_en: str, *, sales_unit: str = "ST", base_unit: str = "ST",
                units: dict[str, float] | None = None, lot: float = 0.01,
                claims: tuple[str, ...] = (), labels: tuple[str, ...] = (),
                allergens: tuple[str, ...] = (), category: str = "C1", origin: str = "fi",
                synkka_origins: tuple[str, ...] = ("246",), substitutes: tuple[str, ...] = (),
                with_classification: bool = True, brand: str = "BrandA") -> dict:
    classifications = []
    if with_classification:
        classifications = [
            {"type": "ENUM", "name": "nutritionalClaim", "values": [{"id": c} for c in claims]},
            {"type": "ENUM", "name": "packagingMarkedLabel",
             "values": [{"id": label} for label in labels] + [{"id": "coolTemperature"}]},
            {"type": "ENUM", "name": "allergen", "values": [{"id": a} for a in allergens]},
            {"type": "ENUM", "name": "nonAllergen", "values": [{"id": "AC"}]},
        ]
    return {
        "id": pid, "salesUnitGtin": "64" + pid.zfill(11), "salesUnit": sales_unit, "baseUnit": base_unit,
        "category": category, "allowedLotSize": lot, "deleted": False, "vendorName": "VENDOR",
        "countryOfOrigin": origin,
        "units": [{"unitId": u, "sizeInBaseUnits": s} for u, s in (units or {sales_unit: 1.0}).items()],
        "deposits": [],
        "substitutions": [{"product": pid, "substituteProduct": s} for s in substitutes],
        "synkkaData": {"gtin": "64" + pid.zfill(11), "brand": brand,
                       "names": [{"value": name_en, "language": "en"}],
                       "countriesOfOrigin": list(synkka_origins),
                       "classifications": classifications, "variableUnit": False},
    }


def product(*args, **kwargs) -> CatalogProduct:
    return parse_product(raw_product(*args, **kwargs))


def price(pid: str, unit_net: str, comparison_net: str | None, comparison_unit: str | None = "L",
          vat: str = "13.5", valid_to: str = "2026-12-31T00:00:00+02:00") -> UpstreamPrice:
    return UpstreamPrice(product_id=pid, error=False, unit_net=Decimal(unit_net), vat_rate=Decimal(vat),
                         comparison_net=Decimal(comparison_net) if comparison_net else None,
                         comparison_unit=comparison_unit, list_net=Decimal(unit_net), valid_to=valid_to)


def stock(pid: str, amount: str, *, available_date: date = MONDAY,
          cutoff: str = "2026-11-15T17:00:00+02:00", model: str = "Stock") -> UpstreamAvailability:
    return UpstreamAvailability(product_id=pid, sales_block=False, logistic_model=model,
                                available_amount=Decimal(amount), available_date=available_date,
                                sales_unit="ST", closing_time=cutoff)
```

- [ ] **Étape 2 : écrire les tests qui échouent**

`tests/test_catalog_json.py` :
```python
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
```

- [ ] **Étape 3 : lancer les tests et vérifier qu'ils échouent**

Lancer : `uv run pytest tests/test_catalog_json.py -v` → attendu : ÉCHEC, `ModuleNotFoundError ... catalog_json`

- [ ] **Étape 4 : écrire `ttap/adapters/outbound/catalog_json.py`**

```python
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
```

- [ ] **Étape 5 : lancer les tests**

Lancer : `uv run pytest tests/test_catalog_json.py -v` → attendu : 5 PASS

- [ ] **Étape 6 : commit**

```bash
git add tests/factories.py tests/test_catalog_json.py ttap/adapters/outbound/catalog_json.py
git commit -m "feat: Synkka catalog adapter with token search" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 3 : quantités et unités

**Fichiers :**
- Créer : `ttap/domain/quantities.py`, `tests/test_quantities.py`

**Interfaces :**
- Utilise : `CatalogProduct`, `Unit`.
- Produit : `parse_name_quantity(name: str) -> tuple[Decimal, Unit] | None` ; `content_per_sales_unit(product, requested_unit: Unit, unit_net: Decimal | None, comparison_net: Decimal | None) -> tuple[Decimal, str] | None` (la source vaut `"name"` ou `"price_ratio"`) ; `sales_units_needed(requested: Decimal, content: Decimal, lot_size: Decimal) -> Decimal`.

- [ ] **Étape 1 : écrire les tests qui échouent**

`tests/test_quantities.py` :
```python
from decimal import Decimal

from ttap.domain.models import Unit
from ttap.domain.quantities import content_per_sales_unit, parse_name_quantity, sales_units_needed
from tests.factories import product


def test_parse_name_quantity_handles_units_and_commas():
    assert parse_name_quantity("Milk drink 1,75 l lactose free") == (Decimal("1.75"), Unit.L)
    assert parse_name_quantity("Cream 2,5 dl") == (Decimal("0.25"), Unit.L)
    assert parse_name_quantity("Salad 400g") == (Decimal("0.4"), Unit.KG)
    assert parse_name_quantity("Steak ca2kg") == (Decimal("2"), Unit.KG)
    assert parse_name_quantity("Milk 1 lactose free") is None


def test_content_uses_case_multiplier_confirmed_by_price_ratio():
    # 2 x 10 l per case; API: 31.31 EUR per case, 1.57 EUR per litre -> ratio 19.94
    p = product("9", "Milk drink 10 l box", sales_unit="KI", base_unit="ST", units={"KI": 2.0, "ST": 1.0})
    assert content_per_sales_unit(p, Unit.L, Decimal("31.31"), Decimal("1.57")) == (Decimal("20"), "name")


def test_content_falls_back_to_price_ratio_when_name_is_inconsistent():
    p = product("9", "Milk drink 3 l", sales_unit="KI", base_unit="ST", units={"KI": 1.0, "ST": 1.0})
    assert content_per_sales_unit(p, Unit.L, Decimal("10.00"), Decimal("1.00")) == (Decimal("10.00"), "price_ratio")


def test_content_unknown_without_name_or_ratio():
    p = product("9", "Mystery product")
    assert content_per_sales_unit(p, Unit.L, Decimal("5"), None) is None


def test_sales_units_rounded_up_to_lot():
    assert sales_units_needed(Decimal("1000"), Decimal("20"), Decimal("1")) == 50
    assert sales_units_needed(Decimal("1001"), Decimal("20"), Decimal("1")) == 51
    assert sales_units_needed(Decimal("4"), Decimal("1"), Decimal("1.5")) == Decimal("4.5")
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

Lancer : `uv run pytest tests/test_quantities.py -v` → attendu : ÉCHEC, `ModuleNotFoundError`

- [ ] **Étape 3 : écrire `ttap/domain/quantities.py`**

```python
from __future__ import annotations

import re
from decimal import ROUND_CEILING, Decimal

from ttap.domain.models import CatalogProduct, Unit

_QTY_RE = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(dl|cl|ml|kg|l|g)\b", re.IGNORECASE)
_MULTI_RE = re.compile(r"\b(\d+)\s*[x×]\s", re.IGNORECASE)
_FACTORS: dict[str, tuple[Decimal, Unit]] = {
    "l": (Decimal("1"), Unit.L), "dl": (Decimal("0.1"), Unit.L), "cl": (Decimal("0.01"), Unit.L),
    "ml": (Decimal("0.001"), Unit.L), "kg": (Decimal("1"), Unit.KG), "g": (Decimal("0.001"), Unit.KG),
}
TOLERANCE = Decimal("0.05")


def parse_name_quantity(name: str) -> tuple[Decimal, Unit] | None:
    match = _QTY_RE.search(name)
    if not match:
        return None
    factor, unit = _FACTORS[match.group(2).lower()]
    return Decimal(match.group(1).replace(",", ".")) * factor, unit


def content_per_sales_unit(product: CatalogProduct, requested_unit: Unit,
                           unit_net: Decimal | None, comparison_net: Decimal | None) -> tuple[Decimal, str] | None:
    ratio = unit_net / comparison_net if unit_net and comparison_net and comparison_net > 0 else None
    candidates: set[Decimal] = set()
    parsed = parse_name_quantity(product.display_name())
    if parsed and parsed[1] == requested_unit:
        single = parsed[0]
        candidates.add(single)
        sales, base = product.units.get(product.sales_unit), product.units.get(product.base_unit)
        if sales and base:
            candidates.add(single * sales / base)
        multi = _MULTI_RE.search(product.display_name())
        if multi:
            candidates.add(single * Decimal(multi.group(1)))
    if ratio is not None:
        if candidates:
            best = min(candidates, key=lambda c: abs(c - ratio))
            if abs(best - ratio) <= ratio * TOLERANCE:
                return best, "name"
        return ratio.quantize(Decimal("0.01")), "price_ratio"
    if len(candidates) == 1:
        return candidates.pop(), "name"
    return None


def sales_units_needed(requested: Decimal, content: Decimal, lot_size: Decimal) -> Decimal:
    steps = (requested / content / lot_size).to_integral_value(rounding=ROUND_CEILING)
    return steps * lot_size
```

- [ ] **Étape 4 : lancer les tests**

Lancer : `uv run pytest tests/test_quantities.py -v` → attendu : 5 PASS

- [ ] **Étape 5 : commit**

```bash
git add ttap/domain/quantities.py tests/test_quantities.py
git commit -m "feat: unit content and lot rounding" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 4 : niveaux d'assurance et contraintes obligatoires

**Fichiers :**
- Créer : `ttap/domain/assurance.py`, `tests/test_assurance.py`

**Interfaces :**
- Produit : `stock_status(av: UpstreamAvailability | None) -> StockStatus` ; `origin_assurance(p: CatalogProduct) -> tuple[OriginAssurance, list[str]]` ; `need_violation(p: CatalogProduct, need: Need) -> str | None`.

- [ ] **Étape 1 : écrire les tests qui échouent**

`tests/test_assurance.py` :
```python
from ttap.domain.assurance import need_violation, origin_assurance, stock_status
from ttap.domain.models import Need, OriginAssurance, StockStatus, UpstreamAvailability
from tests.factories import product, stock


def test_stock_status_sentinels():
    assert stock_status(stock("1", "999999", model="Terminal")) == StockStatus.UNKNOWN_SUPPLIER_STOCK
    assert stock_status(stock("1", "9999999999")) == StockStatus.VERIFIED_UNLIMITED
    assert stock_status(stock("1", "24")) == StockStatus.VERIFIED_QTY
    assert stock_status(stock("1", "0")) == StockStatus.UNAVAILABLE
    assert stock_status(UpstreamAvailability(product_id="1", sales_block=False)) == StockStatus.UNAVAILABLE
    assert stock_status(None) == StockStatus.UNAVAILABLE


def test_origin_conflict_exposes_both_sources():
    assert origin_assurance(product("1", "x", origin="gb", synkka_origins=("528",))) == (
        OriginAssurance.CONFLICT, ["gb", "nl"])
    assert origin_assurance(product("1", "x", origin="fi", synkka_origins=("246",)))[0] == OriginAssurance.CONSISTENT
    assert origin_assurance(product("1", "x", origin="fi", synkka_origins=()))[0] == OriginAssurance.SINGLE_SOURCE


def test_missing_data_is_not_a_satisfied_claim():
    need = Need(text="milk", required_claims=["FREE_FROM_LACTOSE"])
    assert need_violation(product("1", "x", with_classification=False), need) == "NOT_VERIFIABLE:FREE_FROM_LACTOSE"
    assert need_violation(product("1", "x", claims=("LOW_LACTOSE",)), need) == "CLAIM_MISSING:FREE_FROM_LACTOSE"
    assert need_violation(product("1", "x", claims=("FREE_FROM_LACTOSE",)), need) is None


def test_excluded_allergen_present():
    need = Need(text="bread", excluded_allergens=["AW"])
    assert need_violation(product("1", "x", allergens=("AW",)), need) == "ALLERGEN_PRESENT:AW"
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

Lancer : `uv run pytest tests/test_assurance.py -v` → attendu : ÉCHEC, `ModuleNotFoundError`

- [ ] **Étape 3 : écrire `ttap/domain/assurance.py`**

```python
from __future__ import annotations

from decimal import Decimal

from ttap.domain.models import CatalogProduct, Need, OriginAssurance, StockStatus, UpstreamAvailability

UNKNOWN_SUPPLIER_STOCK_SENTINEL = Decimal("999999")
UNLIMITED_SENTINEL = Decimal("9999999999")


def stock_status(av: UpstreamAvailability | None) -> StockStatus:
    if (av is None or av.sales_block or av.available_amount is None
            or av.available_amount <= 0 or av.available_date is None):
        return StockStatus.UNAVAILABLE
    if av.available_amount >= UNLIMITED_SENTINEL:
        return StockStatus.VERIFIED_UNLIMITED
    if av.available_amount == UNKNOWN_SUPPLIER_STOCK_SENTINEL:
        return StockStatus.UNKNOWN_SUPPLIER_STOCK
    return StockStatus.VERIFIED_QTY


def origin_assurance(p: CatalogProduct) -> tuple[OriginAssurance, list[str]]:
    valio = p.origin_valio
    manufacturer = set(p.origin_manufacturer)
    if not valio and not manufacturer:
        return OriginAssurance.MISSING, []
    if valio and manufacturer:
        status = OriginAssurance.CONSISTENT if valio in manufacturer else OriginAssurance.CONFLICT
        return status, sorted({valio} | manufacturer)
    return OriginAssurance.SINGLE_SOURCE, sorted({valio} if valio else manufacturer)


def need_violation(p: CatalogProduct, need: Need) -> str | None:
    hard = [*need.required_claims, *need.excluded_allergens, *need.required_labels]
    if hard and not p.has_classification_data:
        return f"NOT_VERIFIABLE:{hard[0]}"
    for claim in need.required_claims:
        if claim not in p.claims:
            return f"CLAIM_MISSING:{claim}"
    for allergen in need.excluded_allergens:
        if allergen in p.allergens_contained:
            return f"ALLERGEN_PRESENT:{allergen}"
    for label in need.required_labels:
        if label not in p.labels:
            return f"LABEL_MISSING:{label}"
    return None
```

- [ ] **Étape 4 : lancer les tests**

Lancer : `uv run pytest tests/test_assurance.py -v` → attendu : 4 PASS

- [ ] **Étape 5 : commit**

```bash
git add ttap/domain/assurance.py tests/test_assurance.py
git commit -m "feat: assurance levels and hard-constraint checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 5 : passerelle vers l'API Valio (régulateur, 429, lots)

**Fichiers :**
- Créer : `ttap/domain/errors.py`, `ttap/adapters/outbound/valio_gateway.py`, `tests/test_valio_gateway.py`

**Interfaces :**
- Produit : `ValioGateway(client: httpx.AsyncClient, api_key: str, *, min_interval=0.125, retry_after_429=30.0, max_attempts=3, sleep=asyncio.sleep, monotonic=None)` avec `async prices(ids, delivery) -> dict[str, UpstreamPrice]` et `async availability(ids, delivery) -> dict[str, UpstreamAvailability]` ; l'exception `UpstreamUnavailable`.

- [ ] **Étape 1 : écrire les tests qui échouent**

`tests/test_valio_gateway.py` :
```python
from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx

from ttap.adapters.outbound.valio_gateway import UpstreamUnavailable, ValioGateway

BASE = "https://valio.test"
PRICE_OK = {"customerId": "x", "currency": "EUR", "pricingDate": "2026-11-16T00:00:00+0200", "products": [
    {"productId": "1", "quantity": 1.0, "netPriceFound": True, "error": False,
     "catalogPrice": {"value": 31.31, "valueWithTax": 35.54, "validFrom": "2026-09-01T00:00:00+0300",
                      "validTo": "9999-12-31T00:00:00+0200", "currency": "EUR"},
     "comparisonPrice": {"value": 1.57, "valueWithTax": 1.78, "validFrom": "x", "validTo": "x", "currency": "EUR"},
     "comparisonUnit": "L", "tax": {"taxRate": 13.5, "taxValue": 4.23}},
    {"productId": "2", "quantity": 1.0, "netPriceFound": False, "error": True}]}
AVAIL_OK = {"timeNow": "x", "requestedDate": "x", "products": [
    {"productId": "1", "closingTime": "2026-11-12T15:00:00+0200", "salesBlock": False, "logisticModel": "Terminal",
     "scheduleLines": [{"salesBlock": False, "availableAmount": 999999.0, "availableDate": "2026-11-16", "salesUnit": "KI"}]},
    {"productId": "2", "salesBlock": False, "scheduleLines": []}]}


def make_gateway(sleeps: list[float]) -> ValioGateway:
    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
    return ValioGateway(httpx.AsyncClient(base_url=BASE), "k", sleep=fake_sleep, monotonic=lambda: 0.0)


@respx.mock
async def test_prices_parsed_and_api_key_sent():
    route = respx.post(f"{BASE}/api/price").mock(return_value=httpx.Response(200, json=PRICE_OK))
    out = await make_gateway([]).prices(["1", "2"], date(2026, 11, 16))
    assert route.calls[0].request.headers["X-API-Key"] == "k"
    assert out["1"].unit_net == Decimal("31.31") and out["1"].comparison_unit == "L"
    assert out["1"].vat_rate == Decimal("13.5")
    assert out["2"].error is True


@respx.mock
async def test_availability_parsed_empty_lines_unavailable():
    respx.post(f"{BASE}/api/availability").mock(return_value=httpx.Response(200, json=AVAIL_OK))
    out = await make_gateway([]).availability(["1", "2"], date(2026, 11, 16))
    assert out["1"].available_amount == Decimal("999999") and out["1"].logistic_model == "Terminal"
    assert out["2"].available_amount is None


@respx.mock
async def test_429_waits_30_seconds_then_retries():
    respx.post(f"{BASE}/api/price").mock(side_effect=[httpx.Response(429), httpx.Response(200, json=PRICE_OK)])
    sleeps: list[float] = []
    out = await make_gateway(sleeps).prices(["1"], date(2026, 11, 16))
    assert 30.0 in sleeps and "1" in out


@respx.mock
async def test_gives_up_after_max_attempts():
    respx.post(f"{BASE}/api/price").mock(return_value=httpx.Response(429))
    with pytest.raises(UpstreamUnavailable):
        await make_gateway([]).prices(["1"], date(2026, 11, 16))


@respx.mock
async def test_chunks_of_1000_and_dedup():
    route = respx.post(f"{BASE}/api/price").mock(
        return_value=httpx.Response(200, json={"customerId": "x", "currency": "EUR", "pricingDate": "x", "products": []}))
    ids = [str(i) for i in range(1500)] + ["1"]
    await make_gateway([]).prices(ids, date(2026, 11, 16))
    sizes = [len(__import__("json").loads(c.request.content)["products"]) for c in route.calls]
    assert sizes == [1000, 500]
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

Lancer : `uv run pytest tests/test_valio_gateway.py -v` → attendu : ÉCHEC, `ModuleNotFoundError`

- [ ] **Étape 3 : écrire `ttap/domain/errors.py` puis `ttap/adapters/outbound/valio_gateway.py`**

`ttap/domain/errors.py` (l'exception est un type du domaine, pour que la couche application n'importe jamais un adaptateur) :
```python
class UpstreamUnavailable(Exception):
    """The supplier system could not answer (network error, repeated 429/5xx)."""
```

`ttap/adapters/outbound/valio_gateway.py` :
```python
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import date
from decimal import Decimal

import httpx

from ttap.domain.errors import UpstreamUnavailable
from ttap.domain.models import UpstreamAvailability, UpstreamPrice

MAX_IDS_PER_CALL = 1000
UPSTREAM_CUSTOMER = "ttap-gateway"


def _dec(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _chunks(ids: list[str]) -> Iterator[list[str]]:
    unique = list(dict.fromkeys(ids))
    for i in range(0, len(unique), MAX_IDS_PER_CALL):
        yield unique[i:i + MAX_IDS_PER_CALL]


def _parse_price(p: dict) -> UpstreamPrice:
    if p.get("error"):
        return UpstreamPrice(product_id=p["productId"], error=True)
    cat = p.get("catalogPrice") or {}
    cmp_ = p.get("comparisonPrice") or {}
    tax = p.get("tax") or {}
    lst = p.get("listPrice") or {}
    return UpstreamPrice(
        product_id=p["productId"], error=False, unit_net=_dec(cat.get("value")), vat_rate=_dec(tax.get("taxRate")),
        comparison_net=_dec(cmp_.get("value")), comparison_unit=p.get("comparisonUnit"),
        list_net=_dec(lst.get("value")), valid_to=cat.get("validTo"), net_price_found=bool(p.get("netPriceFound")),
    )


def _parse_availability(p: dict) -> UpstreamAvailability:
    lines = p.get("scheduleLines") or []
    line = lines[0] if lines else {}
    return UpstreamAvailability(
        product_id=p["productId"],
        sales_block=bool(p.get("salesBlock")) or bool(line.get("salesBlock")),
        logistic_model=p.get("logisticModel"),
        available_amount=_dec(line.get("availableAmount")),
        available_date=line.get("availableDate"),
        sales_unit=line.get("salesUnit"),
        closing_time=p.get("closingTime"),
    )


class ValioGateway:
    def __init__(self, client: httpx.AsyncClient, api_key: str, *, min_interval: float = 0.125,
                 retry_after_429: float = 30.0, max_attempts: int = 3,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 monotonic: Callable[[], float] | None = None):
        self._client = client
        self._api_key = api_key
        self._min_interval = min_interval
        self._retry_after_429 = retry_after_429
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._monotonic = monotonic or (lambda: asyncio.get_running_loop().time())
        self._lock = asyncio.Lock()
        self._last_call: float | None = None

    async def _post(self, path: str, ids: list[str], delivery: date) -> dict:
        body = {"customer": UPSTREAM_CUSTOMER, "requestedDate": delivery.isoformat(), "products": ids}
        async with self._lock:  # upstream blocks the whole key on 429: serialise everything
            for _ in range(self._max_attempts):
                if self._last_call is not None:
                    wait = self._min_interval - (self._monotonic() - self._last_call)
                    if wait > 0:
                        await self._sleep(wait)
                self._last_call = self._monotonic()
                try:
                    resp = await self._client.post(path, json=body, headers={"X-API-Key": self._api_key})
                except httpx.HTTPError as exc:
                    raise UpstreamUnavailable(str(exc)) from exc
                if resp.status_code == 429:
                    await self._sleep(self._retry_after_429)
                    continue
                if resp.status_code >= 500:
                    await self._sleep(1.0)
                    continue
                resp.raise_for_status()
                return resp.json()
        raise UpstreamUnavailable(f"{path}: retries exhausted")

    async def prices(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamPrice]:
        out: dict[str, UpstreamPrice] = {}
        for chunk in _chunks(product_ids):
            data = await self._post("/api/price", chunk, delivery)
            out.update({p["productId"]: _parse_price(p) for p in data["products"]})
        return out

    async def availability(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamAvailability]:
        out: dict[str, UpstreamAvailability] = {}
        for chunk in _chunks(product_ids):
            data = await self._post("/api/availability", chunk, delivery)
            out.update({p["productId"]: _parse_availability(p) for p in data["products"]})
        return out
```

- [ ] **Étape 4 : lancer les tests**

Lancer : `uv run pytest tests/test_valio_gateway.py -v` → attendu : 5 PASS

- [ ] **Étape 5 : commit**

```bash
git add ttap/domain/errors.py ttap/adapters/outbound/valio_gateway.py tests/test_valio_gateway.py
git commit -m "feat: throttled Valio gateway with 429 backoff and batching" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 6 : évaluation des candidats et good / better / best

**Fichiers :**
- Créer : `ttap/domain/ranking.py`, `tests/test_ranking.py`

**Interfaces :**
- Utilise : `need_violation`, `stock_status`, `origin_assurance` (tâche 4) ; `content_per_sales_unit`, `sales_units_needed` (tâche 3).
- Produit : `evaluate_candidate(product, line, price, av, delivery) -> Candidate | Exclusion` ; `build_offer_line(line, products, prices: dict[str, UpstreamPrice], avail: dict[str, UpstreamAvailability], delivery) -> OfferLine`.

- [ ] **Étape 1 : écrire les tests qui échouent**

`tests/test_ranking.py` :
```python
from decimal import Decimal

from ttap.domain.models import Delivery, Need, Preferences, Quantity, RequestLine, StockStatus, Unit
from ttap.domain.ranking import build_offer_line
from tests.factories import MONDAY, price, product, stock

DELIVERY = Delivery(requested_date=MONDAY, latest_acceptable_date=MONDAY)


def line(**prefs) -> RequestLine:
    return RequestLine(line_id="L1", need=Need(text="milk", required_claims=["FREE_FROM_LACTOSE"]),
                       quantity=Quantity(value=Decimal("1000"), unit=Unit.L), preferences=Preferences(**prefs))


def test_good_is_cheapest_per_litre_meeting_hard_constraints():
    products = [product("A", "Milk 1 l", claims=("FREE_FROM_LACTOSE",)),
                product("B", "Milk 1 l", claims=("LOW_LACTOSE",)),
                product("C", "Milk 1 l", claims=("FREE_FROM_LACTOSE",))]
    prices = {"A": price("A", "1.20", "1.20"), "B": price("B", "0.90", "0.90"), "C": price("C", "1.05", "1.05")}
    avail = {pid: stock(pid, "9999999999") for pid in "ABC"}
    out = build_offer_line(line(), products, prices, avail, DELIVERY)
    assert out.tiers["good"].product_id == "C"
    assert out.tiers["good"].qty_sales_units == 1000
    assert out.tiers["good"].line_total_net == Decimal("1050.00")
    assert {e.product_id: e.reason for e in out.excluded} == {"B": "CLAIM_MISSING:FREE_FROM_LACTOSE"}


def test_better_respects_origin_preference_and_reports_changes():
    products = [product("NL", "Milk 1 l", claims=("FREE_FROM_LACTOSE",), origin="nl", synkka_origins=("528",)),
                product("FI", "Milk 1 l", claims=("FREE_FROM_LACTOSE",), origin="fi", synkka_origins=("246",))]
    prices = {"NL": price("NL", "1.00", "1.00"), "FI": price("FI", "1.10", "1.10")}
    avail = {pid: stock(pid, "9999999999") for pid in ("NL", "FI")}
    out = build_offer_line(line(origin=["fi"]), products, prices, avail, DELIVERY)
    assert out.tiers["good"].product_id == "NL"
    assert out.tiers["good"].changes_vs_request == ["origin:nl"]
    assert out.tiers["better"].product_id == "FI"


def test_exclusions_unit_mismatch_unavailable_insufficient_and_late():
    products = [product(p, "Milk 1 l", claims=("FREE_FROM_LACTOSE",)) for p in ("U", "X", "S", "T")]
    prices = {"U": price("U", "1", "1", comparison_unit="KG"), "X": price("X", "1", "1"),
              "S": price("S", "1", "1"), "T": price("T", "1", "1")}
    avail = {"U": stock("U", "9999999999"), "X": stock("X", "0"), "S": stock("S", "24"),
             "T": stock("T", "9999999999", available_date=MONDAY.replace(day=20))}
    out = build_offer_line(line(), products, prices, avail, DELIVERY)
    reasons = {e.product_id: e.reason for e in out.excluded}
    assert reasons == {"U": "COMPARISON_UNIT_MISMATCH", "X": "UNAVAILABLE",
                       "S": "INSUFFICIENT_STOCK:24", "T": "DELIVERY_TOO_LATE"}
    assert out.tiers == {} and out.exceptions == ["NO_ELIGIBLE_PRODUCT"]


def test_unknown_supplier_stock_is_kept_and_flagged():
    products = [product("T", "Milk 1 l", claims=("FREE_FROM_LACTOSE",))]
    out = build_offer_line(line(), products, {"T": price("T", "1", "1")},
                           {"T": stock("T", "999999", model="Terminal")}, DELIVERY)
    assert out.tiers["good"].stock == StockStatus.UNKNOWN_SUPPLIER_STOCK
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

Lancer : `uv run pytest tests/test_ranking.py -v` → attendu : ÉCHEC, `ModuleNotFoundError`

- [ ] **Étape 3 : écrire `ttap/domain/ranking.py`**

```python
from __future__ import annotations

from decimal import Decimal

from ttap.domain.assurance import need_violation, origin_assurance, stock_status
from ttap.domain.models import (
    CatalogProduct, Candidate, Delivery, Exclusion, OfferLine, RequestLine, StockStatus, Unit,
    UpstreamAvailability, UpstreamPrice,
)
from ttap.domain.quantities import content_per_sales_unit, sales_units_needed

CENT = Decimal("0.01")


def evaluate_candidate(p: CatalogProduct, line: RequestLine, price: UpstreamPrice | None,
                       av: UpstreamAvailability | None, delivery: Delivery) -> Candidate | Exclusion:
    reason = need_violation(p, line.need)
    if reason:
        return Exclusion(product_id=p.product_id, reason=reason)
    if price is None or price.error or price.unit_net is None:
        return Exclusion(product_id=p.product_id, reason="NO_PRICE")
    unit = line.quantity.unit
    if unit != Unit.PIECE and price.comparison_unit != unit.value:
        return Exclusion(product_id=p.product_id, reason="COMPARISON_UNIT_MISMATCH")
    status = stock_status(av)
    if status == StockStatus.UNAVAILABLE:
        return Exclusion(product_id=p.product_id, reason="UNAVAILABLE")
    assert av is not None and av.available_date is not None
    if av.available_date > delivery.latest_acceptable_date:
        return Exclusion(product_id=p.product_id, reason="DELIVERY_TOO_LATE")
    if unit == Unit.PIECE:
        content, source = Decimal("1"), "name"
    else:
        found = content_per_sales_unit(p, unit, price.unit_net, price.comparison_net)
        if found is None:
            return Exclusion(product_id=p.product_id, reason="CONTENT_UNKNOWN")
        content, source = found
    qty = sales_units_needed(line.quantity.value, content, p.lot_size)
    if status == StockStatus.VERIFIED_QTY and av.available_amount is not None and av.available_amount < qty:
        return Exclusion(product_id=p.product_id, reason=f"INSUFFICIENT_STOCK:{av.available_amount.normalize():f}")
    origin, origins = origin_assurance(p)
    changes: list[str] = []
    if line.preferences.origin and not set(origins) & set(line.preferences.origin):
        changes.append(f"origin:{'/'.join(origins) or 'unknown'}")
    if line.preferences.brands and p.brand not in line.preferences.brands:
        changes.append(f"brand:{p.brand}")
    label_hits = len(set(line.preferences.labels) & p.labels)
    verified_bonus = 0.5 if status in (StockStatus.VERIFIED_QTY, StockStatus.VERIFIED_UNLIMITED) else 0.0
    return Candidate(
        product_id=p.product_id, name=p.display_name(), qty_sales_units=qty, sales_unit=p.sales_unit,
        content_per_sales_unit=content, content_source=source, surplus=qty * content - line.quantity.value,
        unit_net=price.unit_net, line_total_net=(price.unit_net * qty).quantize(CENT),
        vat_rate=price.vat_rate or Decimal("0"),
        comparison_net=price.comparison_net if price.comparison_net is not None else price.unit_net,
        price_valid_to=price.valid_to, stock=status, available_amount=av.available_amount,
        delivery_date=av.available_date, order_cutoff=av.closing_time, origin=origin, origins=origins,
        changes_vs_request=changes, score=label_hits + verified_bonus,
    )


def build_offer_line(line: RequestLine, products: list[CatalogProduct], prices: dict[str, UpstreamPrice],
                     avail: dict[str, UpstreamAvailability], delivery: Delivery) -> OfferLine:
    candidates: list[Candidate] = []
    excluded: list[Exclusion] = []
    for p in products:
        result = evaluate_candidate(p, line, prices.get(p.product_id), avail.get(p.product_id), delivery)
        (candidates if isinstance(result, Candidate) else excluded).append(result)
    tiers: dict[str, Candidate] = {}
    if candidates:
        by_price = sorted(candidates, key=lambda c: (c.comparison_net, c.product_id))
        tiers["good"] = by_price[0]
        preferred = [c for c in by_price if not c.changes_vs_request]
        if preferred:
            tiers["better"] = preferred[0]
            tiers["best"] = sorted(preferred, key=lambda c: (-c.score, c.comparison_net, c.product_id))[0]
    return OfferLine(line_id=line.line_id, tiers=tiers, excluded=excluded,
                     exceptions=[] if candidates else ["NO_ELIGIBLE_PRODUCT"])
```

- [ ] **Étape 4 : lancer les tests**

Lancer : `uv run pytest tests/test_ranking.py -v` → attendu : 4 PASS

- [ ] **Étape 5 : commit**

```bash
git add ttap/domain/ranking.py tests/test_ranking.py
git commit -m "feat: candidate evaluation and good/better/best tiers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 7 : signature des offres (ES256 + JCS)

**Fichiers :**
- Créer : `ttap/domain/offer.py`, `ttap/adapters/outbound/jws_signer.py`, `tests/test_offer_signing.py`

**Interfaces :**
- Produit : `offer_payload(offer: Offer) -> dict` ; `offer_hash(offer: Offer) -> str` (`"sha256:<hex>"`) ; `offer_valid_until(now, ttl: timedelta, lines: list[OfferLine]) -> datetime` ; `EcdsaSigner(key: ECKey | None = None, kid: str = "ttap-1")` avec `sign(payload) -> str`, `verify(payload, token) -> bool` et `public_jwk() -> dict`.

- [ ] **Étape 1 : écrire les tests qui échouent**

`tests/test_offer_signing.py` :
```python
from datetime import timedelta

from ttap.adapters.outbound.jws_signer import EcdsaSigner
from ttap.domain.models import Offer
from ttap.domain.offer import offer_hash, offer_payload, offer_valid_until
from tests.factories import DEMO_NOW


def make_offer() -> Offer:
    return Offer(offer_id="of_1", request_id="rq_1", org_id="org_a", issued_at=DEMO_NOW,
                 valid_until=DEMO_NOW + timedelta(minutes=30), catalog_version="sha256:x", lines=[])


def test_signature_roundtrip_and_tamper_detection():
    signer = EcdsaSigner()
    offer = make_offer()
    token = signer.sign(offer_payload(offer))
    assert signer.verify(offer_payload(offer), token)
    tampered = offer.model_copy(update={"org_id": "org_b"})
    assert not signer.verify(offer_payload(tampered), token)
    assert not signer.verify(offer_payload(offer), "garbage")


def test_hash_ignores_signature_field():
    offer = make_offer()
    signed = offer.model_copy(update={"signature": "abc"})
    assert offer_hash(offer) == offer_hash(signed)
    assert offer_hash(offer).startswith("sha256:")


def test_public_jwk_has_kid_and_no_private_part():
    jwk = EcdsaSigner(kid="k9").public_jwk()
    assert jwk["kid"] == "k9" and "d" not in jwk


def test_valid_until_is_capped_by_ttl_when_no_line_constraints():
    assert offer_valid_until(DEMO_NOW, timedelta(minutes=30), []) == DEMO_NOW + timedelta(minutes=30)
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

Lancer : `uv run pytest tests/test_offer_signing.py -v` → attendu : ÉCHEC, `ModuleNotFoundError`

- [ ] **Étape 3 : écrire `ttap/domain/offer.py` et `ttap/adapters/outbound/jws_signer.py`**

`ttap/domain/offer.py` :
```python
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import rfc8785

from ttap.domain.models import Offer, OfferLine


def offer_payload(offer: Offer) -> dict:
    return offer.model_dump(mode="json", exclude={"signature"})


def offer_hash(offer: Offer) -> str:
    return "sha256:" + hashlib.sha256(rfc8785.dumps(offer_payload(offer))).hexdigest()


def offer_valid_until(now: datetime, ttl: timedelta, lines: list[OfferLine]) -> datetime:
    bounds = [now + ttl]
    for line in lines:
        for cand in line.tiers.values():
            bounds += [b for b in (cand.price_valid_to, cand.order_cutoff) if b is not None]
    return min(bounds)
```

`ttap/adapters/outbound/jws_signer.py` :
```python
from __future__ import annotations

import rfc8785
from joserfc import jws
from joserfc.errors import JoseError
from joserfc.jwk import ECKey


class EcdsaSigner:
    def __init__(self, key: ECKey | None = None, kid: str = "ttap-1"):
        self._key = key or ECKey.generate_key("P-256")
        self.kid = kid

    def sign(self, payload: dict) -> str:
        return jws.serialize_compact({"alg": "ES256", "kid": self.kid}, rfc8785.dumps(payload), self._key)

    def verify(self, payload: dict, token: str) -> bool:
        try:
            obj = jws.deserialize_compact(token, self._key)
        except JoseError:
            return False
        return obj.payload == rfc8785.dumps(payload)

    def public_jwk(self) -> dict:
        jwk = self._key.as_dict(private=False)
        jwk["kid"] = self.kid
        return jwk
```

- [ ] **Étape 4 : lancer les tests**

Lancer : `uv run pytest tests/test_offer_signing.py -v` → attendu : 4 PASS

- [ ] **Étape 5 : commit**

```bash
git add ttap/domain/offer.py ttap/adapters/outbound/jws_signer.py tests/test_offer_signing.py
git commit -m "feat: ES256/JCS offer signing and validity window" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 8 : stockage SQLite (offre à usage unique, idempotence, compare-and-set)

**Fichiers :**
- Créer : `ttap/adapters/outbound/sqlite_store.py`, `tests/test_sqlite_store.py`

**Interfaces :**
- Produit : `SqliteStore(path: str = ":memory:")` implémentant le port `Store` du plan maître. `insert_order(order) -> bool` renvoie `False` si la clé d'idempotence existe déjà pour cette organisation.

- [ ] **Étape 1 : écrire les tests qui échouent**

`tests/test_sqlite_store.py` :
```python
from datetime import timedelta
from decimal import Decimal

from ttap.adapters.outbound.sqlite_store import SqliteStore
from ttap.domain.models import Offer, Order, OrderState, SelectedLine
from tests.factories import DEMO_NOW


def offer(org="org_a") -> Offer:
    return Offer(offer_id="of_1", request_id="rq_1", org_id=org, issued_at=DEMO_NOW,
                 valid_until=DEMO_NOW + timedelta(minutes=30), catalog_version="v", lines=[])


def order(key="k1", oid="or_1") -> Order:
    return Order(order_id=oid, org_id="org_a", offer_id="of_1", offer_hash="h",
                 selected=[SelectedLine(line_id="L1", tier="good")], state=OrderState.PENDING_DECISION,
                 total_net=Decimal("10.00"), idempotency_key=key)


def test_offers_are_isolated_per_org_and_single_use():
    s = SqliteStore()
    s.save_offer(offer())
    assert s.get_offer("org_b", "of_1") is None
    assert s.claim_offer("org_a", "of_1") is True
    assert s.claim_offer("org_a", "of_1") is False


def test_idempotency_key_unique_per_org():
    s = SqliteStore()
    assert s.insert_order(order()) is True
    assert s.insert_order(order(oid="or_2")) is False
    assert s.get_order_by_idempotency_key("org_a", "k1").order_id == "or_1"


def test_transition_is_compare_and_set():
    s = SqliteStore()
    s.insert_order(order())
    updated = order().model_copy(update={"state": OrderState.AUTO_APPROVED, "version": 2})
    assert s.transition("org_a", "or_1", OrderState.PENDING_DECISION, 1, updated) is True
    stale = order().model_copy(update={"state": OrderState.CANCELLED, "version": 2})
    assert s.transition("org_a", "or_1", OrderState.PENDING_DECISION, 1, stale) is False
    assert s.get_order("org_a", "or_1").state == OrderState.AUTO_APPROVED
    assert s.get_order("org_b", "or_1") is None
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

Lancer : `uv run pytest tests/test_sqlite_store.py -v` → attendu : ÉCHEC, `ModuleNotFoundError`

- [ ] **Étape 3 : écrire `ttap/adapters/outbound/sqlite_store.py`**

```python
from __future__ import annotations

import sqlite3
import threading

from ttap.domain.models import Offer, Order, OrderState, PurchaseRequest

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (org_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
  PRIMARY KEY (org_id, id));
CREATE TABLE IF NOT EXISTS offers (org_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (org_id, id));
CREATE TABLE IF NOT EXISTS orders (org_id TEXT NOT NULL, id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
  state TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
  PRIMARY KEY (org_id, id), UNIQUE (org_id, idempotency_key));
"""


class SqliteStore:
    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        if path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)

    def _one(self, sql: str, params: tuple) -> tuple | None:
        with self._lock:
            return self._db.execute(sql, params).fetchone()

    def _write(self, sql: str, params: tuple) -> int:
        with self._lock:
            return self._db.execute(sql, params).rowcount

    def save_request(self, req: PurchaseRequest) -> None:
        self._write("INSERT INTO requests (org_id, id, body) VALUES (?, ?, ?)",
                    (req.org_id, req.request_id, req.model_dump_json()))

    def get_request(self, org_id: str, request_id: str) -> PurchaseRequest | None:
        row = self._one("SELECT body FROM requests WHERE org_id = ? AND id = ?", (org_id, request_id))
        return PurchaseRequest.model_validate_json(row[0]) if row else None

    def save_offer(self, offer: Offer) -> None:
        self._write("INSERT INTO offers (org_id, id, body) VALUES (?, ?, ?)",
                    (offer.org_id, offer.offer_id, offer.model_dump_json()))

    def get_offer(self, org_id: str, offer_id: str) -> Offer | None:
        row = self._one("SELECT body FROM offers WHERE org_id = ? AND id = ?", (org_id, offer_id))
        return Offer.model_validate_json(row[0]) if row else None

    def claim_offer(self, org_id: str, offer_id: str) -> bool:
        return self._write("UPDATE offers SET used = 1 WHERE org_id = ? AND id = ? AND used = 0",
                           (org_id, offer_id)) == 1

    def insert_order(self, order: Order) -> bool:
        try:
            self._write("INSERT INTO orders (org_id, id, idempotency_key, state, version, body) VALUES (?,?,?,?,?,?)",
                        (order.org_id, order.order_id, order.idempotency_key, order.state.value, order.version,
                         order.model_dump_json()))
        except sqlite3.IntegrityError:
            return False
        return True

    def get_order(self, org_id: str, order_id: str) -> Order | None:
        row = self._one("SELECT body FROM orders WHERE org_id = ? AND id = ?", (org_id, order_id))
        return Order.model_validate_json(row[0]) if row else None

    def get_order_by_idempotency_key(self, org_id: str, key: str) -> Order | None:
        row = self._one("SELECT body FROM orders WHERE org_id = ? AND idempotency_key = ?", (org_id, key))
        return Order.model_validate_json(row[0]) if row else None

    def transition(self, org_id: str, order_id: str, expected_state: OrderState, expected_version: int,
                   updated: Order) -> bool:
        if updated.version != expected_version + 1:
            raise ValueError("updated.version must be expected_version + 1")
        return self._write(
            "UPDATE orders SET state = ?, version = ?, body = ? "
            "WHERE org_id = ? AND id = ? AND state = ? AND version = ?",
            (updated.state.value, updated.version, updated.model_dump_json(), org_id, order_id,
             expected_state.value, expected_version)) == 1
```

- [ ] **Étape 4 : lancer les tests**

Lancer : `uv run pytest tests/test_sqlite_store.py -v` → attendu : 3 PASS

- [ ] **Étape 5 : commit**

```bash
git add ttap/adapters/outbound/sqlite_store.py tests/test_sqlite_store.py
git commit -m "feat: sqlite store with single-use offers, idempotency and CAS" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 9 : contexte de décision et moteur Cedar à 3 issues

**Fichiers :**
- Créer : `policies/base.cedar`, `ttap/domain/decision.py`, `ttap/adapters/outbound/cedar_engine.py`, `tests/test_decision.py`

**Interfaces :**
- Produit : `build_decision_context(candidates: list[Candidate], mandate: Mandate | None, now: datetime) -> dict` (clés : `mandate_active`, `total_net`, `limit_per_order_net`, `unverified_value_net`, `max_unverified_value_net`, `has_origin_conflict`, `has_changes_vs_request`) ; `CedarPolicyEngine(policies: str)` avec `.decide(context) -> Decision` ; `CedarPolicyEngine.from_file(path)`.

- [ ] **Étape 1 : écrire les règles**

`policies/base.cedar` :
```cedar
@id("mandate_not_active")
forbid (principal, action, resource)
when { !context.mandate_active };

@id("base_permit")
permit (principal, action in [Action::"submit_order", Action::"auto_approve"], resource);

@id("total_over_order_limit")
forbid (principal, action == Action::"auto_approve", resource)
when { context.total_net.greaterThan(context.limit_per_order_net) };

@id("unverified_stock_over_limit")
forbid (principal, action == Action::"auto_approve", resource)
when { context.unverified_value_net.greaterThan(context.max_unverified_value_net) };

@id("origin_conflict")
forbid (principal, action == Action::"auto_approve", resource)
when { context.has_origin_conflict };

@id("deviates_from_request")
forbid (principal, action == Action::"auto_approve", resource)
when { context.has_changes_vs_request };
```

- [ ] **Étape 2 : écrire les tests qui échouent**

`tests/test_decision.py` :
```python
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from ttap.adapters.outbound.cedar_engine import CedarPolicyEngine
from ttap.domain.decision import build_decision_context
from ttap.domain.models import Mandate
from tests.factories import DEMO_NOW

POLICIES = Path(__file__).resolve().parent.parent / "policies" / "base.cedar"
MANDATE = Mandate(org_id="org_a", version=1, valid_until=DEMO_NOW + timedelta(days=30),
                  limit_per_order_net=Decimal("2000"), max_unverified_value_net=Decimal("500"))


def ctx(**over):
    base = {"mandate_active": True, "total_net": Decimal("1010.00"), "limit_per_order_net": Decimal("2000"),
            "unverified_value_net": Decimal("0"), "max_unverified_value_net": Decimal("500"),
            "has_origin_conflict": False, "has_changes_vs_request": False}
    return base | over


def test_within_mandate_is_auto_approved():
    d = CedarPolicyEngine.from_file(POLICIES).decide(ctx())
    assert d.outcome == "AUTO_APPROVED" and d.rules_fired == []


def test_all_escalation_reasons_are_listed():
    d = CedarPolicyEngine.from_file(POLICIES).decide(
        ctx(total_net=Decimal("2340.00"), has_origin_conflict=True))
    assert d.outcome == "PENDING_HUMAN"
    assert d.rules_fired == ["origin_conflict", "total_over_order_limit"]


def test_inactive_mandate_is_denied():
    d = CedarPolicyEngine.from_file(POLICIES).decide(ctx(mandate_active=False))
    assert d.outcome == "DENIED" and d.rules_fired == ["mandate_not_active"]


def test_broken_policy_fails_closed():
    d = CedarPolicyEngine("this is not cedar").decide(ctx())
    assert d.outcome == "DENIED"


def test_context_is_computed_from_candidates_and_mandate():
    c = build_decision_context([], MANDATE, DEMO_NOW)
    assert c["mandate_active"] is True and c["total_net"] == Decimal("0")
    assert build_decision_context([], None, DEMO_NOW)["mandate_active"] is False
```

- [ ] **Étape 3 : lancer les tests et vérifier qu'ils échouent**

Lancer : `uv run pytest tests/test_decision.py -v` → attendu : ÉCHEC, `ModuleNotFoundError`

- [ ] **Étape 4 : écrire `ttap/domain/decision.py` et `ttap/adapters/outbound/cedar_engine.py`**

`ttap/domain/decision.py` :
```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ttap.domain.models import Candidate, Mandate, OriginAssurance, StockStatus

ZERO = Decimal("0")


def build_decision_context(candidates: list[Candidate], mandate: Mandate | None, now: datetime) -> dict:
    return {
        "mandate_active": mandate is not None and mandate.status == "active" and now < mandate.valid_until,
        "total_net": sum((c.line_total_net for c in candidates), ZERO),
        "limit_per_order_net": mandate.limit_per_order_net if mandate else ZERO,
        "unverified_value_net": sum(
            (c.line_total_net for c in candidates if c.stock == StockStatus.UNKNOWN_SUPPLIER_STOCK), ZERO),
        "max_unverified_value_net": mandate.max_unverified_value_net if mandate else ZERO,
        "has_origin_conflict": any(c.origin == OriginAssurance.CONFLICT for c in candidates),
        "has_changes_vs_request": any(c.changes_vs_request for c in candidates),
    }
```

`ttap/adapters/outbound/cedar_engine.py` :
```python
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import cedarpy

from ttap.domain.models import Decision

ACTIONS = ("submit_order", "auto_approve")


def _cedar_value(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return {"__extn": {"fn": "decimal", "arg": str(value.quantize(Decimal("0.0001")))}}
    return value


class CedarPolicyEngine:
    def __init__(self, policies: str):
        self._policies = policies

    @classmethod
    def from_file(cls, path: str | Path) -> CedarPolicyEngine:
        return cls(Path(path).read_text())

    def decide(self, context: dict) -> Decision:
        cedar_ctx = {k: _cedar_value(v) for k, v in context.items()}
        requests = [{"principal": 'Agent::"agent"', "action": f'Action::"{a}"',
                     "resource": 'Order::"order"', "context": cedar_ctx} for a in ACTIONS]
        try:
            submit, auto = cedarpy.is_authorized_batch(requests, self._policies, [])
        except Exception:  # unparsable policies: fail closed
            return Decision(outcome="DENIED", rules_fired=["policy_evaluation_error"], context=context)
        if submit.diagnostics.errors or auto.diagnostics.errors:
            return Decision(outcome="DENIED", rules_fired=["policy_evaluation_error"], context=context)
        if not submit.allowed:
            return Decision(outcome="DENIED", rules_fired=self._fired(submit), context=context)
        if auto.allowed:
            return Decision(outcome="AUTO_APPROVED", rules_fired=[], context=context)
        return Decision(outcome="PENDING_HUMAN", rules_fired=self._fired(auto), context=context)

    @staticmethod
    def _fired(result: cedarpy.AuthzResult) -> list[str]:
        return sorted(result.diagnostics.id_annotations_by_reason.values())
```

- [ ] **Étape 5 : lancer les tests**

Lancer : `uv run pytest tests/test_decision.py -v` → attendu : 5 PASS. Si `test_broken_policy_fails_closed` échoue parce que cedarpy ne lève pas d'exception mais renvoie un `Deny` sans erreur, le comportement reste DENIED : vérifier seulement `d.outcome == "DENIED"`, qui est la propriété requise.

- [ ] **Étape 6 : commit**

```bash
git add policies/base.cedar ttap/domain/decision.py ttap/adapters/outbound/cedar_engine.py tests/test_decision.py
git commit -m "feat: server-computed decision context and 3-outcome Cedar engine" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 10 : ports, horloges, mandats et cas d'usage (request, lookup, order)

**Fichiers :**
- Créer : `ttap/ports.py`, `ttap/adapters/outbound/clocks.py`, `ttap/adapters/outbound/memory_mandates.py`, `ttap/application/errors.py`, `ttap/application/requests.py`, `ttap/application/lookup.py`, `ttap/application/orders.py`, `tests/fakes.py`, `tests/env.py`, `tests/test_application.py`

**Interfaces :**
- Produit : `RequestService(store, new_id).create(org_id, lines, delivery) -> PurchaseRequest` ; `LookupService(catalog, gateway, signer, clock, store, new_id, offer_ttl).lookup(org_id, request_id) -> Offer` (async) ; `OrderService(store, signer, policy, mandates, clock, new_id).place(org_id, offer_id, selected, idempotency_key) -> Order` ; les erreurs `NotFound`, `OfferExpired`, `OfferAlreadyUsed`, `InvalidOfferSignature`, `InvalidSelection`, `IdempotencyMismatch`, `UpstreamError` (attributs de classe `code` et `status`) ; `FixedClock(at)`, `ShiftedClock(start)`, `SystemClock()` ; `InMemoryMandates(dict[str, Mandate])` ; `tests.fakes.FakeGateway(prices, avail)`.

- [ ] **Étape 1 : écrire les ports, les horloges, les mandats et le faux amont**

`ttap/ports.py` :
```python
from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from ttap.domain.models import (
    CatalogProduct, Decision, Mandate, Offer, Order, OrderState, PurchaseRequest, UpstreamAvailability, UpstreamPrice,
)


class CatalogRepository(Protocol):
    @property
    def version(self) -> str: ...
    def get(self, product_id: str) -> CatalogProduct | None: ...
    def search(self, text: str, limit: int = 200) -> list[CatalogProduct]: ...


class SupplierGateway(Protocol):
    async def prices(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamPrice]: ...
    async def availability(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamAvailability]: ...


class PolicyEngine(Protocol):
    def decide(self, context: dict) -> Decision: ...


class Signer(Protocol):
    def sign(self, payload: dict) -> str: ...
    def verify(self, payload: dict, token: str) -> bool: ...
    def public_jwk(self) -> dict: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class MandateRepository(Protocol):
    def get(self, org_id: str) -> Mandate | None: ...


class Store(Protocol):
    def save_request(self, req: PurchaseRequest) -> None: ...
    def get_request(self, org_id: str, request_id: str) -> PurchaseRequest | None: ...
    def save_offer(self, offer: Offer) -> None: ...
    def get_offer(self, org_id: str, offer_id: str) -> Offer | None: ...
    def claim_offer(self, org_id: str, offer_id: str) -> bool: ...
    def insert_order(self, order: Order) -> bool: ...
    def get_order(self, org_id: str, order_id: str) -> Order | None: ...
    def get_order_by_idempotency_key(self, org_id: str, key: str) -> Order | None: ...
    def transition(self, org_id: str, order_id: str, expected_state: OrderState, expected_version: int,
                   updated: Order) -> bool: ...
```

`ttap/adapters/outbound/clocks.py` :
```python
from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    def __init__(self, at: datetime):
        self.at = at

    def now(self) -> datetime:
        return self.at


class ShiftedClock:
    """Demo clock: starts at `start` and advances in real time (mock data is frozen around 2026-11-12)."""

    def __init__(self, start: datetime):
        self._start = start
        self._boot = datetime.now(UTC)

    def now(self) -> datetime:
        return self._start + (datetime.now(UTC) - self._boot)
```

`ttap/adapters/outbound/memory_mandates.py` :
```python
from ttap.domain.models import Mandate


class InMemoryMandates:
    def __init__(self, mandates: dict[str, Mandate]):
        self._mandates = mandates

    def get(self, org_id: str) -> Mandate | None:
        return self._mandates.get(org_id)
```

`tests/fakes.py` :
```python
from datetime import date

from ttap.domain.models import UpstreamAvailability, UpstreamPrice


class FakeGateway:
    def __init__(self, prices: dict[str, UpstreamPrice], avail: dict[str, UpstreamAvailability]):
        self._prices = prices
        self._avail = avail

    async def prices(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamPrice]:
        return {i: self._prices.get(i, UpstreamPrice(product_id=i, error=True)) for i in product_ids}

    async def availability(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamAvailability]:
        return {i: self._avail.get(i, UpstreamAvailability(product_id=i, sales_block=False)) for i in product_ids}
```

- [ ] **Étape 2 : écrire l'environnement de test partagé et les tests qui échouent**

`tests/env.py` (environnement de test réutilisé par les tests REST ; ce n'est pas un module de test, pour éviter que pytest collecte deux fois les mêmes tests) :
```python
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from ttap.adapters.outbound.catalog_json import JsonCatalog
from ttap.adapters.outbound.cedar_engine import CedarPolicyEngine
from ttap.adapters.outbound.clocks import FixedClock
from ttap.adapters.outbound.jws_signer import EcdsaSigner
from ttap.adapters.outbound.memory_mandates import InMemoryMandates
from ttap.adapters.outbound.sqlite_store import SqliteStore
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
        new_id = lambda prefix: f"{prefix}_{next(counter)}"
        self.requests = RequestService(self.store, new_id)
        self.lookup = LookupService(catalog, gateway, self.signer, self.clock, self.store, new_id,
                                    offer_ttl=timedelta(minutes=30))
        self.orders = OrderService(self.store, self.signer, CedarPolicyEngine.from_file(POLICIES), mandates,
                                   self.clock, new_id)

    async def offer(self, litres: str = "1000", org: str = "org_a"):
        req = self.requests.create(org, [RequestLine(
            line_id="L1", need=Need(text="lactose free milk", required_claims=["FREE_FROM_LACTOSE"]),
            quantity=Quantity(value=Decimal(litres), unit=Unit.L))],
            Delivery(requested_date=MONDAY, latest_acceptable_date=MONDAY))
        return await self.lookup.lookup(org, req.request_id)


GOOD = [SelectedLine(line_id="L1", tier="good")]
```

`tests/test_application.py` :
```python
from datetime import timedelta
from decimal import Decimal

import pytest

from ttap.application.errors import IdempotencyMismatch, InvalidOfferSignature, NotFound, OfferExpired
from ttap.domain.models import OrderState, SelectedLine
from tests.env import GOOD, Env
from tests.factories import DEMO_NOW


async def test_happy_path_auto_approved():
    env = Env()
    offer = await env.offer()
    assert offer.signature and offer.lines[0].tiers["good"].line_total_net == Decimal("1010.00")
    order = env.orders.place("org_a", offer.offer_id, GOOD, "idem-1")
    assert order.state == OrderState.AUTO_APPROVED and order.version == 2


async def test_over_limit_goes_to_human_with_reason():
    env = Env(limit="500")
    order = env.orders.place("org_a", (await env.offer()).offer_id, GOOD, "idem-1")
    assert order.state == OrderState.PENDING_HUMAN
    assert order.decision.rules_fired == ["total_over_order_limit"]


async def test_idempotent_replay_and_mismatch():
    env = Env()
    offer = await env.offer()
    first = env.orders.place("org_a", offer.offer_id, GOOD, "idem-1")
    assert env.orders.place("org_a", offer.offer_id, GOOD, "idem-1").order_id == first.order_id
    with pytest.raises(IdempotencyMismatch):
        env.orders.place("org_a", offer.offer_id, [SelectedLine(line_id="L1", tier="best")], "idem-1")


async def test_other_org_cannot_use_offer():
    env = Env()
    offer = await env.offer()
    with pytest.raises(NotFound):
        env.orders.place("org_b", offer.offer_id, GOOD, "idem-x")


async def test_expired_and_tampered_offers_rejected():
    env = Env()
    offer = await env.offer()
    env.clock.at = DEMO_NOW + timedelta(hours=1)
    with pytest.raises(OfferExpired):
        env.orders.place("org_a", offer.offer_id, GOOD, "idem-2")
    env.clock.at = DEMO_NOW
    offer2 = await env.offer()
    forged = offer2.model_copy(update={"signature": offer.signature})
    env.store._write("UPDATE offers SET body = ? WHERE id = ?", (forged.model_dump_json(), offer2.offer_id))
    with pytest.raises(InvalidOfferSignature):
        env.orders.place("org_a", offer2.offer_id, GOOD, "idem-3")
```

- [ ] **Étape 3 : lancer les tests et vérifier qu'ils échouent**

Lancer : `uv run pytest tests/test_application.py -v` → attendu : ÉCHEC, `ModuleNotFoundError: ttap.application.errors`

- [ ] **Étape 4 : écrire les cas d'usage**

`ttap/application/errors.py` :
```python
class TTAPError(Exception):
    code = "ERROR"
    status = 400


class NotFound(TTAPError):
    code, status = "NOT_FOUND", 404


class OfferExpired(TTAPError):
    code, status = "OFFER_EXPIRED", 409


class OfferAlreadyUsed(TTAPError):
    code, status = "OFFER_ALREADY_USED", 409


class InvalidOfferSignature(TTAPError):
    code, status = "INVALID_OFFER_SIGNATURE", 400


class InvalidSelection(TTAPError):
    code, status = "INVALID_SELECTION", 422


class IdempotencyMismatch(TTAPError):
    code, status = "IDEMPOTENCY_MISMATCH", 422


class UpstreamError(TTAPError):
    code, status = "UPSTREAM_UNAVAILABLE", 503
```

`ttap/application/requests.py` :
```python
from __future__ import annotations

from collections.abc import Callable

from ttap.domain.models import Delivery, PurchaseRequest, RequestLine
from ttap.ports import Store


class RequestService:
    def __init__(self, store: Store, new_id: Callable[[str], str]):
        self._store = store
        self._new_id = new_id

    def create(self, org_id: str, lines: list[RequestLine], delivery: Delivery) -> PurchaseRequest:
        req = PurchaseRequest(request_id=self._new_id("rq"), org_id=org_id, lines=lines, delivery=delivery)
        self._store.save_request(req)
        return req
```

`ttap/application/lookup.py` :
```python
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from ttap.application.errors import NotFound, UpstreamError
from ttap.domain.errors import UpstreamUnavailable
from ttap.domain.models import CatalogProduct, Offer, RequestLine
from ttap.domain.offer import offer_payload, offer_valid_until
from ttap.domain.ranking import build_offer_line
from ttap.ports import CatalogRepository, Clock, Signer, Store, SupplierGateway


class LookupService:
    def __init__(self, catalog: CatalogRepository, gateway: SupplierGateway, signer: Signer, clock: Clock,
                 store: Store, new_id: Callable[[str], str], offer_ttl: timedelta = timedelta(minutes=30),
                 search_limit: int = 60):
        self._catalog, self._gateway, self._signer = catalog, gateway, signer
        self._clock, self._store, self._new_id = clock, store, new_id
        self._ttl, self._limit = offer_ttl, search_limit

    def _candidates(self, line: RequestLine) -> list[CatalogProduct]:
        if line.need.product_id:
            p = self._catalog.get(line.need.product_id)
            return [p] if p else []
        return self._catalog.search(line.need.text, limit=self._limit)

    async def lookup(self, org_id: str, request_id: str) -> Offer:
        req = self._store.get_request(org_id, request_id)
        if req is None:
            raise NotFound(f"request {request_id}")
        per_line = {line.line_id: self._candidates(line) for line in req.lines}
        ids = [p.product_id for products in per_line.values() for p in products]
        try:
            prices = await self._gateway.prices(ids, req.delivery.requested_date) if ids else {}
            avail = await self._gateway.availability(ids, req.delivery.requested_date) if ids else {}
        except UpstreamUnavailable as exc:
            raise UpstreamError(str(exc)) from exc
        lines = [build_offer_line(line, per_line[line.line_id], prices, avail, req.delivery) for line in req.lines]
        now = self._clock.now()
        offer = Offer(offer_id=self._new_id("of"), request_id=req.request_id, org_id=org_id, issued_at=now,
                      valid_until=offer_valid_until(now, self._ttl, lines),
                      catalog_version=self._catalog.version, lines=lines)
        offer.signature = self._signer.sign(offer_payload(offer))
        self._store.save_offer(offer)
        return offer
```

`ttap/application/orders.py` :
```python
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from ttap.application.errors import (
    IdempotencyMismatch, InvalidOfferSignature, InvalidSelection, NotFound, OfferAlreadyUsed, OfferExpired,
)
from ttap.domain.decision import build_decision_context
from ttap.domain.models import Candidate, Offer, Order, OrderState, SelectedLine
from ttap.domain.offer import offer_hash, offer_payload
from ttap.ports import Clock, MandateRepository, PolicyEngine, Signer, Store

OUTCOME_TO_STATE = {"AUTO_APPROVED": OrderState.AUTO_APPROVED, "PENDING_HUMAN": OrderState.PENDING_HUMAN,
                    "DENIED": OrderState.DENIED}


class OrderService:
    def __init__(self, store: Store, signer: Signer, policy: PolicyEngine, mandates: MandateRepository,
                 clock: Clock, new_id: Callable[[str], str]):
        self._store, self._signer, self._policy = store, signer, policy
        self._mandates, self._clock, self._new_id = mandates, clock, new_id

    def get(self, org_id: str, order_id: str) -> Order:
        order = self._store.get_order(org_id, order_id)
        if order is None:
            raise NotFound(f"order {order_id}")
        return order

    def _replay(self, existing: Order, offer_id: str, selected: list[SelectedLine]) -> Order:
        if existing.offer_id != offer_id or existing.selected != selected:
            raise IdempotencyMismatch("same Idempotency-Key, different body")
        return existing

    @staticmethod
    def _resolve(offer: Offer, selected: list[SelectedLine]) -> list[Candidate]:
        lines = {line.line_id: line for line in offer.lines}
        out = []
        for sel in selected:
            line = lines.get(sel.line_id)
            if line is None or sel.tier not in line.tiers:
                raise InvalidSelection(f"{sel.line_id}/{sel.tier}")
            out.append(line.tiers[sel.tier])
        return out

    def place(self, org_id: str, offer_id: str, selected: list[SelectedLine], idempotency_key: str) -> Order:
        existing = self._store.get_order_by_idempotency_key(org_id, idempotency_key)
        if existing:
            return self._replay(existing, offer_id, selected)
        offer = self._store.get_offer(org_id, offer_id)
        if offer is None:
            raise NotFound(f"offer {offer_id}")
        if not offer.signature or not self._signer.verify(offer_payload(offer), offer.signature):
            raise InvalidOfferSignature(offer_id)
        now = self._clock.now()
        if now >= offer.valid_until:
            raise OfferExpired(offer_id)
        candidates = self._resolve(offer, selected)
        if not self._store.claim_offer(org_id, offer_id):
            existing = self._store.get_order_by_idempotency_key(org_id, idempotency_key)
            if existing:
                return self._replay(existing, offer_id, selected)
            raise OfferAlreadyUsed(offer_id)
        order = Order(order_id=self._new_id("or"), org_id=org_id, offer_id=offer_id, offer_hash=offer_hash(offer),
                      selected=selected, state=OrderState.PENDING_DECISION,
                      total_net=sum((c.line_total_net for c in candidates), Decimal("0")),
                      idempotency_key=idempotency_key)
        self._store.insert_order(order)
        decision = self._policy.decide(build_decision_context(candidates, self._mandates.get(org_id), now))
        decided = order.model_copy(update={"state": OUTCOME_TO_STATE[decision.outcome], "version": 2,
                                           "decision": decision})
        self._store.transition(org_id, order.order_id, OrderState.PENDING_DECISION, 1, decided)
        return decided
```

- [ ] **Étape 5 : lancer les tests**

Lancer : `uv run pytest tests/test_application.py -v` → attendu : 5 PASS

- [ ] **Étape 6 : commit**

```bash
git add ttap/ports.py ttap/adapters/outbound/clocks.py ttap/adapters/outbound/memory_mandates.py \
        ttap/application tests/fakes.py tests/env.py tests/test_application.py
git commit -m "feat: request, lookup and order use cases behind ports" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 11 : API REST (FastAPI), authentification par agent, erreurs problem+json

**Fichiers :**
- Créer : `ttap/adapters/inbound/rest_api.py`, `tests/test_rest_api.py`

**Interfaces :**
- Utilise : `RequestService`, `LookupService`, `OrderService`, `Signer` (tâche 10).
- Produit : `Services` (dataclass : `requests`, `lookup`, `orders`, `signer`) ; `create_app(services: Services, agent_keys: dict[str, str]) -> FastAPI`. Routes : `POST /requests` (201), `POST /requests/{id}/lookup` (200), `POST /orders` (202, en-tête `Idempotency-Key`), `GET /orders/{id}`, `GET /.well-known/ttap.json`.

- [ ] **Étape 1 : écrire les tests qui échouent**

`tests/test_rest_api.py` :
```python
from fastapi.testclient import TestClient

from ttap.adapters.inbound.rest_api import Services, create_app
from tests.env import Env

A = {"Authorization": "Bearer key-a"}
B = {"Authorization": "Bearer key-b"}
BODY = {"lines": [{"line_id": "L1", "need": {"text": "lactose free milk", "required_claims": ["FREE_FROM_LACTOSE"]},
                   "quantity": {"value": "1000", "unit": "L"}}],
        "delivery": {"requested_date": "2026-11-16", "latest_acceptable_date": "2026-11-16"}}


def client() -> TestClient:
    env = Env()
    services = Services(requests=env.requests, lookup=env.lookup, orders=env.orders, signer=env.signer)
    return TestClient(create_app(services, {"key-a": "org_a", "key-b": "org_b"}))


def test_full_flow_request_lookup_order():
    c = client()
    rq = c.post("/requests", json=BODY, headers=A)
    assert rq.status_code == 201
    offer = c.post(f"/requests/{rq.json()['request_id']}/lookup", headers=A).json()
    order = c.post("/orders", json={"offer_id": offer["offer_id"], "selected": [{"line_id": "L1", "tier": "good"}]},
                   headers=A | {"Idempotency-Key": "k1"})
    assert order.status_code == 202 and order.json()["state"] == "AUTO_APPROVED"
    assert order.headers["Location"] == f"/orders/{order.json()['order_id']}"
    assert c.get(order.headers["Location"], headers=A).json()["order_id"] == order.json()["order_id"]


def test_org_is_taken_from_token_never_from_body():
    c = client()
    assert c.post("/requests", json=BODY | {"customer": "org_b"}, headers=A).status_code == 422
    assert c.post("/requests", json=BODY).status_code in (401, 422)
    assert c.post("/requests", json=BODY, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_cross_org_access_returns_404_problem_json():
    c = client()
    rq = c.post("/requests", json=BODY, headers=A).json()
    r = c.post(f"/requests/{rq['request_id']}/lookup", headers=B)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "NOT_FOUND"


def test_well_known_publishes_public_key():
    doc = client().get("/.well-known/ttap.json").json()
    assert doc["steps"] == ["request", "lookup", "order", "approval"]
    assert "d" not in doc["jwks"]["keys"][0]
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

Lancer : `uv run pytest tests/test_rest_api.py -v` → attendu : ÉCHEC, `ModuleNotFoundError`

- [ ] **Étape 3 : écrire `ttap/adapters/inbound/rest_api.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from ttap.application.errors import TTAPError
from ttap.application.lookup import LookupService
from ttap.application.orders import OrderService
from ttap.application.requests import RequestService
from ttap.domain.models import Delivery, Offer, Order, PurchaseRequest, RequestLine, SelectedLine
from ttap.ports import Signer

PROTOCOL_VERSION = "2026-11-15"


@dataclass
class Services:
    requests: RequestService
    lookup: LookupService
    orders: OrderService
    signer: Signer


class CreateRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[RequestLine]
    delivery: Delivery


class PlaceOrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offer_id: str
    selected: list[SelectedLine]


class Unauthorized(TTAPError):
    code, status = "UNAUTHORIZED", 401


def create_app(services: Services, agent_keys: dict[str, str]) -> FastAPI:
    app = FastAPI(title="Trusted Trade Agent Protocol", version=PROTOCOL_VERSION)

    @app.exception_handler(TTAPError)
    async def _problem(_: Request, exc: TTAPError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, media_type="application/problem+json",
                            content={"type": "about:blank", "title": exc.code, "status": exc.status,
                                     "code": exc.code, "detail": str(exc)})

    def org_id(authorization: str = Header()) -> str:
        org = agent_keys.get(authorization.removeprefix("Bearer ").strip())
        if org is None:
            raise Unauthorized("unknown agent key")
        return org

    @app.post("/requests", status_code=201, response_model=PurchaseRequest)
    def create_request(body: CreateRequestBody, org: str = Depends(org_id)) -> PurchaseRequest:
        return services.requests.create(org, body.lines, body.delivery)

    @app.post("/requests/{request_id}/lookup", response_model=Offer)
    async def lookup(request_id: str, org: str = Depends(org_id)) -> Offer:
        return await services.lookup.lookup(org, request_id)

    @app.post("/orders", status_code=202, response_model=Order)
    def place_order(body: PlaceOrderBody, response: Response, org: str = Depends(org_id),
                    idempotency_key: str = Header(alias="Idempotency-Key")) -> Order:
        order = services.orders.place(org, body.offer_id, body.selected, idempotency_key)
        response.headers["Location"] = f"/orders/{order.order_id}"
        return order

    @app.get("/orders/{order_id}", response_model=Order)
    def get_order(order_id: str, org: str = Depends(org_id)) -> Order:
        return services.orders.get(org, order_id)

    @app.get("/.well-known/ttap.json")
    def well_known() -> dict:
        return {"protocol": "TTAP", "version": PROTOCOL_VERSION,
                "steps": ["request", "lookup", "order", "approval"],
                "jwks": {"keys": [services.signer.public_jwk()]}}

    return app
```

- [ ] **Étape 4 : lancer les tests**

Lancer : `uv run pytest tests/test_rest_api.py -v` → attendu : 4 PASS

- [ ] **Étape 5 : commit**

```bash
git add ttap/adapters/inbound/rest_api.py tests/test_rest_api.py
git commit -m "feat: REST adapter with per-agent org auth and problem+json" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Tâche 12 : assemblage, point d'entrée et test réel contre l'API mock

**Fichiers :**
- Créer : `ttap/bootstrap.py`, `ttap/main.py`, `scripts/smoke_milk.py`, `tests/test_bootstrap.py`

**Interfaces :**
- Produit : `DEMO_START`, `demo_mandates() -> InMemoryMandates`, `build_services(catalog, gateway, clock, store=None, signer=None, mandates=None) -> Services`, `build_live() -> tuple[Services, dict[str, str]]` (lit `VALIO_API_KEY`, `VALIO_BASE_URL`, `CATALOG_PATH`, `AGENT_KEYS`) ; `ttap.main:app`.

- [ ] **Étape 1 : écrire le test qui échoue**

`tests/test_bootstrap.py` :
```python
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
```

- [ ] **Étape 2 : lancer le test et vérifier qu'il échoue**

Lancer : `uv run pytest tests/test_bootstrap.py -v` → attendu : ÉCHEC, `ModuleNotFoundError`

- [ ] **Étape 3 : écrire `ttap/bootstrap.py`, `ttap/main.py` et `scripts/smoke_milk.py`**

`ttap/bootstrap.py` :
```python
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
from ttap.adapters.outbound.jws_signer import EcdsaSigner
from ttap.adapters.outbound.memory_mandates import InMemoryMandates
from ttap.adapters.outbound.sqlite_store import SqliteStore
from ttap.adapters.outbound.valio_gateway import ValioGateway
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
                   mandates: MandateRepository | None = None) -> Services:
    store = store or SqliteStore()
    signer = signer or EcdsaSigner()
    mandates = mandates or demo_mandates()
    return Services(
        requests=RequestService(store, new_id),
        lookup=LookupService(catalog, gateway, signer, clock, store, new_id),
        orders=OrderService(store, signer, CedarPolicyEngine.from_file(POLICIES), mandates, clock, new_id),
        signer=signer,
    )


def build_live() -> tuple[Services, dict[str, str]]:
    catalog = JsonCatalog.from_file(ROOT / os.environ.get(
        "CATALOG_PATH", "resources/valio_aimo_junction26_product_data.json"))
    client = httpx.AsyncClient(base_url=os.environ.get("VALIO_BASE_URL", "https://junction26.valioaimo.fi"),
                               timeout=30.0)
    gateway = ValioGateway(client, os.environ["VALIO_API_KEY"])
    services = build_services(catalog, gateway, ShiftedClock(DEMO_START),
                              store=SqliteStore(os.environ.get("TTAP_DB", "ttap.db")))
    keys = parse_agent_keys(os.environ.get("AGENT_KEYS", "demo-key-hotel-a:org_hotel_a,demo-key-resto-b:org_resto_b"))
    return services, keys
```

`ttap/main.py` :
```python
from ttap.adapters.inbound.rest_api import create_app
from ttap.bootstrap import build_live

_services, _keys = build_live()
app = create_app(_services, _keys)
```

`scripts/smoke_milk.py` :
```python
"""Live smoke test against the Valio mock API. Run: uv run --env-file .env python scripts/smoke_milk.py"""
import asyncio
from datetime import date
from decimal import Decimal

from ttap.bootstrap import build_live
from ttap.domain.models import Delivery, Need, Quantity, RequestLine, SelectedLine, Unit

MONDAY = date(2026, 11, 16)


async def run(litres: str, key: str) -> None:
    services, _ = build_live()
    req = services.requests.create("org_hotel_a", [RequestLine(
        line_id="L1", need=Need(text="lactose free milk", required_claims=["FREE_FROM_LACTOSE"]),
        quantity=Quantity(value=Decimal(litres), unit=Unit.L))],
        Delivery(requested_date=MONDAY, latest_acceptable_date=MONDAY))
    offer = await services.lookup.lookup("org_hotel_a", req.request_id)
    line = offer.lines[0]
    for tier, c in line.tiers.items():
        print(f"{tier:6} {c.product_id} {c.name[:50]:50} {c.qty_sales_units} {c.sales_unit} "
              f"{c.comparison_net} EUR/L total {c.line_total_net} stock {c.stock}")
    print(f"excluded: {len(line.excluded)}  valid_until: {offer.valid_until}")
    order = services.orders.place("org_hotel_a", offer.offer_id, [SelectedLine(line_id="L1", tier="good")], key)
    print("ORDER", order.state, order.total_net, order.decision.rules_fired)


if __name__ == "__main__":
    asyncio.run(run("1000", "smoke-1000"))
    asyncio.run(run("3000", "smoke-3000"))
```

- [ ] **Étape 4 : lancer les tests unitaires, puis le test réel**

Lancer : `uv run pytest -v` → attendu : toute la suite PASS (environ 40 tests).
Puis : `cp .env.example .env`, mettre la vraie clé dans `.env`, et lancer `uv run --env-file .env python scripts/smoke_milk.py`.
Attendu : 3 niveaux affichés pour 1 000 L (good ≈ 1 010 € HT), puis `ORDER OrderState.AUTO_APPROVED` ; pour 3 000 L, `ORDER OrderState.PENDING_HUMAN … ['total_over_order_limit']`. Si le niveau good tombe sur un produit non équivalent (lait de café, lait fermenté), le noter comme **comportement connu à corriger en phase 5** (re-classement par LLM juge), pas comme un échec de la phase 1.

- [ ] **Étape 5 : lancer le serveur et vérifier à la main**

Lancer : `uv run --env-file .env uvicorn ttap.main:app --port 8000`, puis ouvrir `http://localhost:8000/docs`. Attendu : les 5 routes sont visibles et `/.well-known/ttap.json` répond.

- [ ] **Étape 6 : commit**

```bash
git add ttap/bootstrap.py ttap/main.py scripts/smoke_milk.py tests/test_bootstrap.py
git commit -m "feat: bootstrap, ASGI entrypoint and live milk smoke test" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Jalon de fin de phase 1
- [ ] `uv run pytest` entièrement vert.
- [ ] `scripts/smoke_milk.py` : 1 000 L → `AUTO_APPROVED`, 3 000 L → `PENDING_HUMAN` avec `total_over_order_limit`, contre l'API réelle.
- [ ] Swagger accessible ; une commande de l'organisation B sur l'offre de A renvoie 404.

## Couverture de la spec par cette phase
| SPEC | Couvert ici | Reporté |
|---|---|---|
| §0 principes, §1 isolation, org déduite du jeton | ✅ | signature RFC 9421 (feuille de route) |
| §2 opérations Request / Lookup / Order / GET / well-known | ✅ | `/interpret`, approve / reject / modify, audit, mandat (phases 2 et 4) |
| §3 objets Request, Offer signée, Order, Mandate (sous-ensemble) | ✅ | mandat complet (phase 2 et 5) |
| §4 assurance stock, origine, données manquantes | ✅ | `STALE`, poids variable, consignes (phase 3) |
| §5 lookup : validation, filtres obligatoires, quantités, good / better / best | ✅ | liste habituelle (phase 5), dispo partielle et substitutions (phase 3) |
| §6 machine à états et compare-and-set | partiel (PENDING_DECISION → décision) | transitions humaines (phase 2) |
| §7 Cedar à 3 issues, échec sûr | ✅ (4 règles) | budget, anti-fractionnement, vitesse, etc. (phases 3 et 5) |
| §10 idempotence, offre à usage unique, compare-and-set | ✅ | réservations stock + budget (phase 3) |
| §11 régulateur, 429, lots | ✅ | cache, regroupement, file bornée, boîte d'envoi (phase 3) |
| §14 erreurs problem+json | ✅ (sous-ensemble) | — |
