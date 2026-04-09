"""Post-processing pipeline for extracted keywords.

Applies three stages between LLM extraction and DB upsert:
- Process A: Deduplicate new keywords against each other (semantic)
- Process B: Validate categories against IAB Content Taxonomy 3.1
- Process C: Deduplicate against existing DB keywords
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import structlog
from pydantic import BaseModel

from coyo.config import get_settings
from coyo.services.llm.base import ChatMessage, ChatOptions
from coyo.services.llm.openai_client import OpenAIClient
from coyo.services.similarity import find_best_match, find_duplicates
from coyo.services.synonym_judge import (
    build_synonym_system_message,
    judge_synonym_pair,
)

if TYPE_CHECKING:
    from coyo.services.embedding import EmbeddingService
    from coyo.services.iab_taxonomy import IABTaxonomyService

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Pydantic model for LLM-based IAB classification (Process B)
# ---------------------------------------------------------------------------


class IABClassification(BaseModel):
    """LLM response model for classifying a keyword against IAB taxonomy."""

    action: Literal["normalize", "valid", "delete"]
    iab_category_id: str | None = None
    iab_name: str | None = None


_IAB_CLASSIFICATION_SYSTEM_PROMPT = """\
You are classifying interest keywords against the IAB Content Taxonomy.

{taxonomy_table}

For the given keyword, decide:
- NORMALIZE: keyword is essentially synonymous with an IAB category. \
Replace with the IAB name. (e.g., "war" -> "War and Conflicts", "food" -> "Food & Drink")
- VALID: keyword relates to an IAB category but is more specific or precise. \
Keep the original keyword, but link to the closest IAB category ID. \
(e.g., "F1" is related to "Auto Racing" but F1 is more specific, \
so keep "f1" with IAB ID for Auto Racing)
- DELETE: keyword is not a meaningful interest category or doesn't relate \
to any IAB category. Discard it. \
(e.g., "challenge system", "video review", "news")

Return JSON: {{"action": "normalize"|"valid"|"delete", \
"iab_category_id": "1.2" or null, "iab_name": "Category Name" or null}}

Rules:
- For NORMALIZE: iab_category_id and iab_name MUST be set
- For VALID: iab_category_id MUST be set, iab_name MUST be set
- For DELETE: iab_category_id and iab_name should be null"""


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
    embedding: list[float] | None = None  # carried forward from dedup pass


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
        deduped_keywords, deduped_embeddings = self._process_a(new_keywords, new_embeddings)

        logger.info(
            "postprocessor_process_a",
            input_count=len(new_keywords),
            output_count=len(deduped_keywords),
            removed=len(new_keywords) - len(deduped_keywords),
        )

        # Process B: IAB validation for categories
        await self._iab.ensure_embeddings(self._embedding)
        validated_keywords, validated_embeddings = await self._process_b(
            deduped_keywords, deduped_embeddings
        )

        # Count Process B outcomes for logging
        category_input = sum(1 for kw in deduped_keywords if kw.keyword_type == "category")
        category_output = sum(1 for kw in validated_keywords if kw.keyword_type == "category")
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
        result = await self._process_c(
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

    async def _process_b(
        self,
        keywords: list[RawKeyword],
        embeddings: list[list[float]],
    ) -> tuple[list[ProcessedKeyword], list[list[float]]]:
        """Process B: IAB validation for categories, pass-through for entities.

        Categories are classified by LLM against IAB taxonomy:
        - normalize: replace keyword with IAB name (lowercased), set iab_category_id
        - valid: keep original keyword, set iab_category_id to closest match
        - delete: discard

        Falls back to embedding-based matching if LLM call fails.
        Entities skip IAB validation entirely.
        """
        result_keywords: list[ProcessedKeyword] = []
        result_embeddings: list[list[float]] = []

        # Build LLM system prompt once for all categories (prompt cache optimization)
        settings = get_settings()
        taxonomy_table = self._iab.format_for_prompt()
        system_content = _IAB_CLASSIFICATION_SYSTEM_PROMPT.format(
            taxonomy_table=taxonomy_table,
        )
        system_message = ChatMessage(role="system", content=system_content)
        llm = OpenAIClient(model=settings.llm_interest_model)

        # Collect category indices for parallel LLM classification
        category_indices: list[int] = []
        for i, kw in enumerate(keywords):
            if kw.keyword_type == "entity":
                result_keywords.append(
                    ProcessedKeyword(
                        keyword=kw.keyword,
                        keyword_type=kw.keyword_type,
                        is_news_relevant=kw.is_news_relevant,
                        summary=kw.summary,
                        iab_category_id=None,
                        merge_target=None,
                        embedding=embeddings[i],
                    )
                )
                result_embeddings.append(embeddings[i])
            else:
                category_indices.append(i)

        if not category_indices:
            return result_keywords, result_embeddings

        # Safeguard: exact IAB name match skips LLM (always NORMALIZE)
        llm_needed_indices: list[int] = []
        exact_match_results: dict[int, IABClassification] = {}
        for i in category_indices:
            iab_cat = self._iab.find_by_name(keywords[i].keyword)
            if iab_cat is not None:
                exact_match_results[i] = IABClassification(
                    action="normalize",
                    iab_category_id=iab_cat.id,
                    iab_name=iab_cat.name,
                )
            else:
                llm_needed_indices.append(i)

        # Classify remaining categories in parallel via LLM
        llm_results: dict[int, IABClassification] = {}
        if llm_needed_indices:
            classification_tasks = [
                self._classify_category_llm(
                    llm, system_message, keywords[i].keyword, embeddings[i]
                )
                for i in llm_needed_indices
            ]
            llm_classifications = await asyncio.gather(*classification_tasks)
            for idx, classification in zip(llm_needed_indices, llm_classifications, strict=True):
                llm_results[idx] = classification

        # Merge results in original order
        classifications = [exact_match_results.get(i) or llm_results[i] for i in category_indices]

        for idx, classification in zip(category_indices, classifications, strict=True):
            kw = keywords[idx]
            emb = embeddings[idx]

            if classification.action == "normalize" and classification.iab_name is not None:
                result_keywords.append(
                    ProcessedKeyword(
                        keyword=classification.iab_name.lower(),
                        keyword_type=kw.keyword_type,
                        is_news_relevant=kw.is_news_relevant,
                        summary=kw.summary,
                        iab_category_id=classification.iab_category_id,
                        merge_target=None,
                        embedding=emb,
                    )
                )
                result_embeddings.append(emb)
            elif classification.action == "valid":
                result_keywords.append(
                    ProcessedKeyword(
                        keyword=kw.keyword,
                        keyword_type=kw.keyword_type,
                        is_news_relevant=kw.is_news_relevant,
                        summary=kw.summary,
                        iab_category_id=None,
                        merge_target=None,
                        embedding=emb,
                    )
                )
                result_embeddings.append(emb)
            else:
                # delete: discard
                logger.debug(
                    "postprocessor_category_rejected",
                    keyword=kw.keyword,
                    action="delete",
                )

        return result_keywords, result_embeddings

    async def _classify_category_llm(
        self,
        llm: OpenAIClient,
        system_message: ChatMessage,
        keyword: str,
        embedding: list[float],
    ) -> IABClassification:
        """Classify a single category keyword via LLM, with embedding fallback."""
        try:
            messages = [
                system_message,
                ChatMessage(role="user", content=f'Classify: "{keyword}"'),
            ]
            return await llm.structured(
                messages,
                response_model=IABClassification,
                options=ChatOptions(temperature=0.0, max_tokens=128),
            )
        except Exception:
            logger.warning(
                "postprocessor_llm_fallback",
                keyword=keyword,
                exc_info=True,
            )
            return self._classify_category_embedding(embedding)

    def _classify_category_embedding(
        self,
        embedding: list[float],
    ) -> IABClassification:
        """Fallback: classify a category keyword using embedding similarity."""
        match_result = self._iab.match(embedding)

        if match_result.action == "normalize":
            return IABClassification(
                action="normalize",
                iab_category_id=match_result.iab_id,
                iab_name=match_result.iab_name,
            )
        elif match_result.action == "valid":
            return IABClassification(
                action="valid",
                iab_category_id=match_result.iab_id,
                iab_name=match_result.iab_name,
            )
        else:
            return IABClassification(action="delete")

    async def _process_c(
        self,
        keywords: list[ProcessedKeyword],
        keyword_embeddings: list[list[float]],
        existing_keyword_texts: list[str],
        existing_embeddings: list[list[float]],
    ) -> list[ProcessedKeyword]:
        """Process C: Deduplicate against existing DB keywords.

        Three-tier decision for each new keyword:
        1. similarity >= keyword_dedup_threshold (0.90): auto-merge
           (near-identical strings don't need LLM confirmation).
        2. keyword_dedup_candidate_threshold <= similarity < 0.90:
           ask the LLM to confirm whether the pair are synonyms.
        3. similarity < candidate_threshold: keyword is new.

        LLM calls for candidate-zone pairs run in parallel via
        ``asyncio.gather``. On LLM failure the safe default is to not merge
        (keyword stays new).
        """
        if not existing_keyword_texts or not keywords:
            return list(keywords)

        settings = get_settings()
        dedup_threshold = settings.keyword_dedup_threshold
        candidate_threshold = settings.keyword_dedup_candidate_threshold

        # First pass: compute best embedding match per keyword, bucket into
        # auto-merge / candidate / no-merge. No LLM calls yet.
        best_matches: list[tuple[int, float]] = []
        candidate_indices: list[int] = []
        for emb in keyword_embeddings:
            best_idx, best_sim = find_best_match(emb, existing_embeddings)
            best_matches.append((best_idx, best_sim))

        for i, (_idx, sim) in enumerate(best_matches):
            if candidate_threshold <= sim < dedup_threshold:
                candidate_indices.append(i)

        # Second pass: judge all candidate-zone pairs in parallel.
        llm_judgments: dict[int, bool] = {}
        if candidate_indices:
            llm = OpenAIClient(model=settings.llm_interest_model)
            system_message = build_synonym_system_message()
            tasks = [
                judge_synonym_pair(
                    llm,
                    system_message,
                    keywords[i].keyword,
                    existing_keyword_texts[best_matches[i][0]],
                )
                for i in candidate_indices
            ]
            judgments = await asyncio.gather(*tasks)
            for idx, judgment in zip(candidate_indices, judgments, strict=True):
                # None (LLM failure) falls through as False = do not merge.
                llm_judgments[idx] = bool(judgment is not None and judgment.is_synonym)

        # Third pass: assemble results.
        result: list[ProcessedKeyword] = []
        for i, kw in enumerate(keywords):
            best_idx, best_sim = best_matches[i]
            best_existing = existing_keyword_texts[best_idx]

            if best_sim >= dedup_threshold:
                should_merge = True
            elif best_sim >= candidate_threshold:
                should_merge = llm_judgments.get(i, False)
            else:
                should_merge = False

            if should_merge:
                # Merge target already has its own embedding (from its
                # original insert) — do not overwrite via the upsert path.
                result.append(
                    ProcessedKeyword(
                        keyword=kw.keyword,
                        keyword_type=kw.keyword_type,
                        is_news_relevant=kw.is_news_relevant,
                        summary=kw.summary,
                        iab_category_id=kw.iab_category_id,
                        merge_target=best_existing,
                        embedding=None,
                    )
                )
            else:
                # New keyword — carry the embedding so the upsert call
                # site can persist it on the INSERT path.
                result.append(
                    ProcessedKeyword(
                        keyword=kw.keyword,
                        keyword_type=kw.keyword_type,
                        is_news_relevant=kw.is_news_relevant,
                        summary=kw.summary,
                        iab_category_id=kw.iab_category_id,
                        merge_target=None,
                        embedding=keyword_embeddings[i],
                    )
                )

        return result
