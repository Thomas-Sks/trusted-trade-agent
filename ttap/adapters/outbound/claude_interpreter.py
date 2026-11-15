"""Step 0 adapter: Claude turns free text (fr/en/fi/sv) into a validated InterpretedRequest (structured outputs)."""
from __future__ import annotations

from datetime import date

import os

import anthropic

from ttap.adapters.outbound.llm_errors import LLMFailure
from ttap.domain.interpretation import CLAIM_CODES, LABEL_CODES, InterpretedRequest

# Simple extraction: Haiku is fast and cheap. Override with TTAP_INTERPRETER_MODEL.
MODEL = os.environ.get("TTAP_INTERPRETER_MODEL", "claude-haiku-5-5")
# Server-side refusal fallbacks exist for Sonnet/Opus/Fable, not for Haiku.
_FALLBACK_KW = {} if "haiku" in MODEL else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
SYSTEM = f"""You convert a food-service buyer's purchase message into a structured request for a wholesaler.
Rules:
- Hard constraints (allergies, diets, 'must be organic') go to required_claims / required_labels using ONLY these codes.
  Claims: {", ".join(CLAIM_CODES)}. Labels: {", ".join(LABEL_CODES)}.
  "lactose-free" is FREE_FROM_LACTOSE, never LOW_LACTOSE.
- Wishes ("preferably Finnish") are soft preferences, not constraints.
- need_text is a short generic English product name for catalogue search (e.g. "milk", "cherry tomatoes").
- Use product_id only if the message clearly refers to one of the buyer's usual products listed below.
- Convert relative dates using today's date. If no date is given, use the next delivery day and say so.
- quantity_unit is L for liquids, KG for weight, PIECE for countable items.
- Record every guess in `assumptions`, written in English. Write questions in English. Ask a question only if the answer would change the
  product, the quantity or a hard constraint; otherwise choose a sensible default and state it.
Never invent prices or stock."""


class ClaudeInterpreter:
    def __init__(self, client: anthropic.AsyncAnthropic | None = None):
        self._client = client or anthropic.AsyncAnthropic()

    async def interpret(self, text: str, today: date, usual: list[tuple[str, str]]) -> InterpretedRequest:
        usual_txt = "\n".join(f"- {pid}: {name}" for pid, name in usual) or "- (none)"
        try:
            response = await self._parse(text, today, usual_txt)
        except anthropic.APIError as exc:
            raise LLMFailure(exc) from exc
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise ValueError(f"interpretation unavailable (stop_reason={response.stop_reason})")
        return response.parsed_output

    async def _parse(self, text: str, today: date, usual_txt: str):
        return await self._client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            output_config={"effort": "low"},
            system=SYSTEM,
            messages=[{"role": "user", "content":
                       f"Today is {today.isoformat()} ({today.strftime('%A')}).\nBuyer's usual products:\n{usual_txt}"
                       f"\n\nMessage:\n{text}"}],
            output_format=InterpretedRequest,
            **_FALLBACK_KW,
        )
