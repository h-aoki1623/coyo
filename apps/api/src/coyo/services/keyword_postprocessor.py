"""Post-processing pipeline for extracted keywords.

Applies three stages between LLM extraction and DB upsert:
- Process A: Deduplicate new keywords against each other (semantic)
- Process B: Validate categories against IAB Content Taxonomy 3.1
- Process C: Deduplicate against existing DB keywords
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from coyo.config import get_settings
from coyo.services.similarity import find_best_match, find_duplicates

if TYPE_CHECKING:
    from coyo.services.embedding import EmbeddingService
    from coyo.services.iab_taxonomy import IABTaxonomyService

logger = structlog.get_logger()


@dataclass(frozen=True)
class RawKeyword:
    """A keyword extracted by the LLM, before post-processing."""

    keyword: str
    keyword_type: str  # "category" or "entity"
    is_news_relevant: bool
    summary: str | None


@dataclass(frozen=True)
class ProcessedKeyword:
    """A keyword after the full post-processing pipeline."""

    keyword: str
    keyword_type: str  # "category" or "entity"
    is_news_relevant: bool
    summary: str | None
    iab_category_id: str | None
    merge_target: str | None  # existing DB keyword to merge into


class KeywordPostprocessor:
    """Three-stage post-processing pipeline for extracted keywords."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        iab_taxonomy_service: IABTaxonomyService,
    ) -> None:
        self._embedding = embedding_service
        self._iab = iab_taxonomy_service

    async def process(
        self,
        new_keywords: list[RawKeyword],
        existing_keyword_texts: list[str],
    ) -> list[ProcessedKeyword]:
        """Run the full post-processing pipeline.

        1. Process A: Deduplicate new keywords against each other
        2. Process B: Validate categories against IAB taxonomy
        3. Process C: Deduplicate against existing DB keywords
        """
        if not new_keywords:
            return []

        # Batch-embed all new keywords + existing DB keywords in one API call
        new_texts = [kw.keyword for kw in new_keywords]
        all_texts = new_texts + existing_keyword_texts
        all_embeddings = await self._embedding.embed(all_texts)

        new_embeddings = all_embeddings[: len(new_texts)]
        existing_embeddings = all_embeddings[len(new_texts) :]

        # Process A: Deduplicate new keywords against each other
        deduped_keywords, deduped_embeddings = self._process_a(
            new_keywords, new_embeddings
        )

        logger.info(
            "postprocessor_process_a",
            input_count=len(new_keywords),
            output_count=len(deduped_keywords),
            removed=len(new_keywords) - len(deduped_keywords),
        )

        # Process B: IAB validation for categories
        await self._iab.ensure_embeddings(self._embedding)
        validated_keywords, validated_embeddings = self._process_b(
            deduped_keywords, deduped_embeddings
        )

        # Count Process B outcomes for logging
        category_input = sum(
            1 for kw in deduped_keywords if kw.keyword_type == "category"
        )
        category_output = sum(
            1 for kw in validated_keywords if kw.keyword_type == "category"
        )
        normalized_count = sum(
            1
            for kw in validated_keywords
            if kw.keyword_type == "category" and kw.iab_category_id is not None
        )
        logger.info(
            "postprocessor_process_b",
            category_input=category_input,
            category_output=category_output,
            normalized=normalized_count,
            rejected=category_input - category_output,
        )

        # Process C: Deduplicate against existing DB keywords
        result = self._process_c(
            validated_keywords,
            validated_embeddings,
            existing_keyword_texts,
            existing_embeddings,
        )

        merge_count = sum(1 for kw in result if kw.merge_target is not None)
        new_count = sum(1 for kw in result if kw.merge_target is None)
        logger.info(
            "postprocessor_process_c",
            input_count=len(validated_keywords),
            merge_count=merge_count,
            new_count=new_count,
        )

        return result

    def _process_a(
        self,
        keywords: list[RawKeyword],
        embeddings: list[list[float]],
    ) -> tuple[list[RawKeyword], list[list[float]]]:
        """Process A: Deduplicate new keywords against each other.

        Uses Union-Find to group similar keywords, keeping the shortest
        keyword in each group as the representative.
        """
        settings = get_settings()
        n = len(keywords)
        if n <= 1:
            return keywords, embeddings

        # Find duplicate pairs
        pairs = find_duplicates(embeddings, settings.keyword_dedup_threshold)
        if not pairs:
            return keywords, embeddings

        # Union-Find to group connected components
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for i, j, _sim in pairs:
            union(i, j)

        # For each group, pick the keyword with the shortest text
        groups: dict[int, list[int]] = {}
        for i in range(n):
            root = find(i)
            groups.setdefault(root, []).append(i)

        keep_indices: list[int] = []
        for members in groups.values():
            best = min(members, key=lambda idx: len(keywords[idx].keyword))
            keep_indices.append(best)

        keep_indices.sort()
        return (
            [keywords[i] for i in keep_indices],
            [embeddings[i] for i in keep_indices],
        )

    def _process_b(
        self,
        keywords: list[RawKeyword],
        embeddings: list[list[float]],
    ) -> tuple[list[ProcessedKeyword], list[list[float]]]:
        """Process B: IAB validation for categories, pass-through for entities.

        Categories are matched against IAB taxonomy:
        - normalize: replace keyword with IAB name (lowercased), set iab_category_id
        - valid: keep original keyword, iab_category_id=None
        - invalid: discard

        Entities skip IAB validation entirely.
        """
        result_keywords: list[ProcessedKeyword] = []
        result_embeddings: list[list[float]] = []

        for kw, emb in zip(keywords, embeddings, strict=True):
            if kw.keyword_type == "entity":
                # Entities pass through without IAB validation
                result_keywords.append(
                    ProcessedKeyword(
                        keyword=kw.keyword,
                        keyword_type=kw.keyword_type,
                        is_news_relevant=kw.is_news_relevant,
                        summary=kw.summary,
                        iab_category_id=None,
                        merge_target=None,
                    )
                )
                result_embeddings.append(emb)
                continue

            # Category: validate against IAB taxonomy
            match_result = self._iab.match(emb)

            if match_result.action == "normalize" and match_result.iab_name is not None:
                result_keywords.append(
                    ProcessedKeyword(
                        keyword=match_result.iab_name.lower(),
                        keyword_type=kw.keyword_type,
                        is_news_relevant=kw.is_news_relevant,
                        summary=kw.summary,
                        iab_category_id=match_result.iab_id,
                        merge_target=None,
                    )
                )
                result_embeddings.append(emb)
            elif match_result.action == "valid":
                result_keywords.append(
                    ProcessedKeyword(
                        keyword=kw.keyword,
                        keyword_type=kw.keyword_type,
                        is_news_relevant=kw.is_news_relevant,
                        summary=kw.summary,
                        iab_category_id=None,
                        merge_target=None,
                    )
                )
                result_embeddings.append(emb)
            else:
                # invalid: discard
                logger.debug(
                    "postprocessor_category_rejected",
                    keyword=kw.keyword,
                    best_iab_similarity=match_result.similarity,
                )

        return result_keywords, result_embeddings

    def _process_c(
        self,
        keywords: list[ProcessedKeyword],
        keyword_embeddings: list[list[float]],
        existing_keyword_texts: list[str],
        existing_embeddings: list[list[float]],
    ) -> list[ProcessedKeyword]:
        """Process C: Deduplicate against existing DB keywords.

        If similarity >= threshold with an existing keyword, set merge_target.
        Otherwise, the keyword is new.
        """
        if not existing_keyword_texts or not keywords:
            return list(keywords)

        settings = get_settings()
        result: list[ProcessedKeyword] = []

        for kw, emb in zip(keywords, keyword_embeddings, strict=True):
            best_idx, best_sim = find_best_match(emb, existing_embeddings)

            if best_sim >= settings.keyword_dedup_threshold:
                # Merge into existing keyword
                result.append(
                    ProcessedKeyword(
                        keyword=kw.keyword,
                        keyword_type=kw.keyword_type,
                        is_news_relevant=kw.is_news_relevant,
                        summary=kw.summary,
                        iab_category_id=kw.iab_category_id,
                        merge_target=existing_keyword_texts[best_idx],
                    )
                )
            else:
                result.append(kw)

        return result
