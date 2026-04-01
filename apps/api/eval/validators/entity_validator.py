"""Entity validation: Wikidata API → LLM-as-judge → human review."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import structlog

from eval.models import WikidataHitResult
from eval.validators.wikidata_lookup import lookup_wikidata

if TYPE_CHECKING:
    from eval.validators.llm_judge import LLMJudge

logger = structlog.get_logger()


@dataclass(frozen=True)
class EntityValidation:
    """Result of validating a single entity keyword."""

    keyword: str
    verdict: Literal["valid", "invalid", "human_review"]
    method: Literal["wikidata", "llm_judge", "human_review"]
    wikidata_qid: str | None
    confidence: float
    reasoning: str


class EntityValidator:
    """Three-stage entity validation pipeline.

    Stage 1: Wikidata API lookup (real-time, ~60-70% of entities)
    Stage 2: LLM-as-judge (Claude Sonnet, ~25-35%)
    Stage 3: Flag for human review (~5%)
    """

    def __init__(
        self,
        llm_judge: LLMJudge | None,
        wikidata_threshold: float = 0.85,
    ) -> None:
        self._judge = llm_judge
        self._threshold = wikidata_threshold

    async def validate(
        self,
        keyword: str,
        context: str = "",
    ) -> EntityValidation:
        """Validate a single entity keyword through the 3-stage pipeline."""
        # Stage 1: Wikidata API
        match = await lookup_wikidata(keyword, self._threshold)
        if match is not None:
            return EntityValidation(
                keyword=keyword,
                verdict="valid",
                method="wikidata",
                wikidata_qid=match.qid,
                confidence=match.match_score,
                reasoning=(
                    f"Matched Wikidata entity: {match.label} ({match.qid}) - {match.description}"
                ),
            )

        # Stage 2: LLM-as-judge
        if self._judge is not None:
            try:
                judgment = await self._judge.judge_entity_validity(
                    keyword=keyword,
                    context_sentence=context,
                )
                if not judgment.needs_human_review:
                    return EntityValidation(
                        keyword=keyword,
                        verdict="valid" if judgment.is_valid else "invalid",
                        method="llm_judge",
                        wikidata_qid=None,
                        confidence=judgment.confidence,
                        reasoning=judgment.reasoning,
                    )
            except Exception:
                logger.exception(
                    "entity_validation_llm_failed",
                    keyword=keyword,
                )

        # Stage 3: Human review
        return EntityValidation(
            keyword=keyword,
            verdict="human_review",
            method="human_review",
            wikidata_qid=None,
            confidence=0.0,
            reasoning="Could not be resolved automatically",
        )

    async def validate_batch(
        self,
        entities: list[dict[str, str]],
        concurrency: int = 5,
    ) -> tuple[WikidataHitResult, list[EntityValidation]]:
        """Validate a batch of entities.

        Args:
            entities: List of {"keyword": str, "context": str} dicts.

        Returns:
            A tuple of (aggregate WikidataHitResult, list of validations).
        """
        if not entities:
            return (
                WikidataHitResult(
                    wikidata_valid_count=0,
                    llm_valid_count=0,
                    llm_invalid_count=0,
                    human_review_count=0,
                    total_count=0,
                    wikidata_hit_rate=0.0,
                ),
                [],
            )

        semaphore = asyncio.Semaphore(concurrency)

        async def _validate(item: dict[str, str]) -> EntityValidation:
            async with semaphore:
                return await self.validate(
                    keyword=item["keyword"],
                    context=item.get("context", ""),
                )

        validations = await asyncio.gather(
            *[_validate(item) for item in entities],
        )

        wikidata_valid = sum(
            1 for v in validations if v.method == "wikidata" and v.verdict == "valid"
        )
        llm_valid = sum(1 for v in validations if v.method == "llm_judge" and v.verdict == "valid")
        llm_invalid = sum(
            1 for v in validations if v.method == "llm_judge" and v.verdict == "invalid"
        )
        human_review = sum(1 for v in validations if v.verdict == "human_review")
        total = len(validations)

        result = WikidataHitResult(
            wikidata_valid_count=wikidata_valid,
            llm_valid_count=llm_valid,
            llm_invalid_count=llm_invalid,
            human_review_count=human_review,
            total_count=total,
            wikidata_hit_rate=wikidata_valid / total if total > 0 else 0.0,
        )

        return result, list(validations)
