from __future__ import annotations

from datetime import date
from typing import Protocol

from ttap.application.auditing import Auditor
from ttap.application.errors import TTAPError
from ttap.domain.interpretation import InterpretedRequest, to_request
from ttap.ports import CatalogRepository, Clock, MandateRepository


class Interpreter(Protocol):
    async def interpret(self, text: str, today: date, usual: list[tuple[str, str]]) -> InterpretedRequest: ...


class InterpreterUnavailable(TTAPError):
    code, status = "INTERPRETER_UNAVAILABLE", 503


class InterpretService:
    """Step 0 (buyer side, before the protocol): free text -> draft request + explicit assumptions."""

    def __init__(self, interpreter: Interpreter | None, catalog: CatalogRepository, mandates: MandateRepository,
                 clock: Clock, auditor: Auditor):
        self._interpreter, self._catalog, self._mandates = interpreter, catalog, mandates
        self._clock, self._auditor = clock, auditor

    async def interpret(self, org_id: str, text: str) -> dict:
        if self._interpreter is None:
            raise InterpreterUnavailable("no LLM interpreter configured (set ANTHROPIC_API_KEY)")
        mandate = self._mandates.get(org_id)
        usual = [(u.product_id, p.display_name()) for u in (mandate.usual_list if mandate else [])
                 if (p := self._catalog.get(u.product_id)) is not None]
        try:
            interp = await self._interpreter.interpret(text, self._clock.now().date(), usual)
        except Exception as exc:  # LLM failures never break the protocol: the buyer can still send a Request
            raise InterpreterUnavailable(str(exc)) from exc
        lines, delivery = to_request(interp)
        draft = {"lines": [ln.model_dump(mode="json") for ln in lines], "delivery": delivery.model_dump(mode="json"),
                 "assumptions": interp.assumptions, "questions": interp.questions}
        self._auditor.record(org_id=org_id, step="request", action="interpreted", subject="interpretation",
                             actor="llm:interpreter", outcome="draft",
                             explanation=f"Texte libre interprété en {len(lines)} ligne(s) ; hypothèses : "
                                         + ("; ".join(interp.assumptions) or "aucune"),
                             data={"text": text, "draft": draft})
        return draft
