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
