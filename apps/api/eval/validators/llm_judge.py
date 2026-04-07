"""LLM-as-judge for entity validation using Anthropic Claude."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Judgment result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntityJudgment:
    """Result of entity validity judgment for a single keyword."""

    is_valid: bool
    confidence: float
    reasoning: str
    needs_human_review: bool


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_ENTITY_SYSTEM_PROMPT = (
    "You validate whether a keyword is a real-world entity (proper noun "
    "with unique identity). "
    "Criteria: has a real-world referent (person, org, product, event, place), "
    "is a proper noun not a common noun, could have a Wikipedia article. "
    "Return ONLY valid JSON: "
    '{"is_valid": true/false, "confidence": 0.0-1.0, '
    '"reasoning": "...", "needs_human_review": true/false}'
)

_MAX_TOKENS = 256


# ---------------------------------------------------------------------------
# LLM Judge
# ---------------------------------------------------------------------------


class LLMJudge:
    """LLM-as-judge using Anthropic Claude for entity validation."""

    def __init__(self, client: AsyncAnthropic, model: str) -> None:
        self._client = client
        self._model = model

    async def judge_entity_validity(
        self,
        keyword: str,
        context_sentence: str,
    ) -> EntityJudgment:
        """Judge whether *keyword* is a valid real-world entity."""
        user_content = f"Keyword: {keyword}\nContext: {context_sentence}"

        raw = await self._call_judge(_ENTITY_SYSTEM_PROMPT, user_content)
        return _parse_entity_judgment(raw, keyword)

    async def judge_entity_batch(
        self,
        items: list[dict[str, str]],
        concurrency: int = 5,
    ) -> list[EntityJudgment]:
        """Judge entity validity for a batch of keywords.

        Args:
            items: Each dict has ``keyword`` and ``context`` keys.
            concurrency: Max concurrent LLM calls.
        """
        if not items:
            return []

        semaphore = asyncio.Semaphore(concurrency)

        async def _judge(item: dict[str, str]) -> EntityJudgment:
            async with semaphore:
                return await self.judge_entity_validity(
                    keyword=item["keyword"],
                    context_sentence=item["context"],
                )

        return await asyncio.gather(*[_judge(item) for item in items])

    # -- Internal helpers -----------------------------------------------------

    async def _call_judge(self, system: str, user_content: str) -> str:
        """Send a single judge request and return the raw text response."""
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user_content}],
            )
            from anthropic.types import TextBlock

            for block in response.content:
                if isinstance(block, TextBlock):
                    return block.text
            logger.warning(
                "llm_judge_no_text_block",
                block_types=[type(b).__name__ for b in response.content],
            )
            return ""
        except Exception:
            logger.exception("llm_judge_call_failed")
            return ""


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from LLM responses."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


def _parse_entity_judgment(raw: str, keyword: str) -> EntityJudgment:
    """Parse LLM response into an ``EntityJudgment``."""
    try:
        data = json.loads(_strip_code_fences(raw))
        return EntityJudgment(
            is_valid=bool(data["is_valid"]),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=str(data.get("reasoning", "")),
            needs_human_review=bool(data.get("needs_human_review", False)),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning(
            "entity_judgment_parse_failed",
            keyword=keyword,
            raw=raw,
        )
        return EntityJudgment(
            is_valid=False,
            confidence=0.0,
            reasoning="parse_error",
            needs_human_review=True,
        )
