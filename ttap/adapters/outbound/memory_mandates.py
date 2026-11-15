from ttap.domain.models import Mandate


class InMemoryMandates:
    def __init__(self, mandates: dict[str, Mandate]):
        self._mandates = mandates

    def get(self, org_id: str) -> Mandate | None:
        return self._mandates.get(org_id)
