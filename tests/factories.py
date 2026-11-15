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
