"""Evaluation B runner: end-to-end pipeline quality.

Measures keyword extraction quality after the full pipeline: LLM extraction
followed by KeywordPostprocessor (dedup, IAB mapping, merge detection).
Extends Eval A metrics with IAB match rate.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

import structlog
from anthropic import AsyncAnthropic

from coyo.config import get_settings
from coyo.services.embedding import EmbeddingService
from coyo.services.iab_taxonomy import get_iab_taxonomy_service
from coyo.services.keyword_postprocessor import (
    KeywordPostprocessor,
    ProcessedKeyword,
    RawKeyword,
)
from coyo.services.memory_extraction import MemoryExtractionService
from eval.loader import build_transcript_text, load_test_cases
from eval.metrics.embedding_match import compute_keyword_metrics
from eval.metrics.iab_match import compute_iab_match_metrics
from eval.metrics.news_relevant import compute_news_relevant_metrics
from eval.metrics.type_confusion import compute_type_confusion
from eval.models import (
    CategoryMetricsB,
    EntityMetrics,
    EvalBResult,
    TestCase,
)
from eval.runners.eval_a import (
    _build_case_details,
    _build_gold_kw_dicts,
    _compute_recall_breakdown,
)
from eval.validators.entity_validator import EntityValidator
from eval.validators.llm_judge import LLMJudge

if TYPE_CHECKING:
    from eval.config import EvalConfig

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_eval_b(config: EvalConfig) -> EvalBResult:
    """Run Evaluation B: measure end-to-end pipeline quality.

    Same as Eval A but also runs the KeywordPostprocessor pipeline and
    computes IAB match metrics.
    """
    cases = load_test_cases(config.cases_dir)
    if not cases:
        raise ValueError(f"No test cases found in {config.cases_dir}")

    if config.max_cases > 0:
        cases = cases[: config.max_cases]
        logger.info("eval_b_cases_limited", max_cases=config.max_cases)

    if not config.anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is required for Eval B. "
            "Set it in your .env or shell environment."
        )

    logger.info("eval_b_start", case_count=len(cases))

    embedding_service = EmbeddingService()
    iab_service = get_iab_taxonomy_service()
    postprocessor = KeywordPostprocessor(
        embedding_service=embedding_service,
        iab_taxonomy_service=iab_service,
    )
    client = AsyncAnthropic(api_key=config.anthropic_api_key)
    judge = LLMJudge(client=client, model=config.judge_model)
    semaphore = asyncio.Semaphore(config.concurrency)

    # -- Extract and post-process all cases -----------------------------------
    case_results = await _extract_and_process_all_cases(
        cases=cases,
        semaphore=semaphore,
        postprocessor=postprocessor,
    )

    # -- Aggregate and compute metrics ----------------------------------------
    result = await _aggregate_results(
        cases=cases,
        case_results=case_results,
        embedding_service=embedding_service,
        judge=judge,
        config=config,
    )

    logger.info(
        "eval_b_complete",
        category_f1=round(result.category_metrics.f1, 4),
        entity_f1=round(result.entity_metrics.f1, 4),
        iab_match_rate=round(result.category_metrics.iab_match.iab_match_rate, 4)
        if result.category_metrics.iab_match
        else 0.0,
    )

    return result


# ---------------------------------------------------------------------------
# Extraction + Post-processing
# ---------------------------------------------------------------------------


def _llm_output_to_raw_keywords(
    categories: list[Any],
    entities: list[Any],
) -> list[RawKeyword]:
    """Convert MemoryExtractionResult items to RawKeyword list."""
    raw: list[RawKeyword] = []
    for item in categories:
        raw.append(
            RawKeyword(
                keyword=item.keyword,
                keyword_type="category",
                is_news_relevant=item.is_news_relevant,
                summary=item.summary,
            )
        )
    for item in entities:
        raw.append(
            RawKeyword(
                keyword=item.keyword,
                keyword_type="entity",
                is_news_relevant=item.is_news_relevant,
                summary=item.summary,
            )
        )
    return raw


def _processed_to_dicts(
    processed: list[ProcessedKeyword],
) -> tuple[list[str], list[str], list[dict[str, object]], list[dict[str, object]]]:
    """Convert ProcessedKeyword list to category/entity string lists and kw dicts.

    Returns:
        (pred_cat_strings, pred_ent_strings, pred_kw_dicts, processed_kw_dicts)
        where processed_kw_dicts include iab_category_id for IAB match metrics.
    """
    pred_cats: list[str] = []
    pred_ents: list[str] = []
    kw_dicts: list[dict[str, object]] = []
    processed_dicts: list[dict[str, object]] = []

    for pk in processed:
        if pk.keyword_type == "category":
            pred_cats.append(pk.keyword)
        else:
            pred_ents.append(pk.keyword)

        kw_dicts.append(
            {
                "keyword": pk.keyword,
                "is_news_relevant": pk.is_news_relevant,
                "keyword_type": pk.keyword_type,
            }
        )
        processed_dicts.append(
            {
                "keyword": pk.keyword,
                "keyword_type": pk.keyword_type,
                "iab_category_id": pk.iab_category_id,
            }
        )

    return pred_cats, pred_ents, kw_dicts, processed_dicts


async def _extract_and_process_single_case(
    case: TestCase,
    semaphore: asyncio.Semaphore,
    postprocessor: KeywordPostprocessor,
) -> dict[str, Any]:
    """Extract keywords via LLM and run through the post-processing pipeline."""
    async with semaphore:
        logger.debug("eval_b_extracting", case_id=case.id)
        try:
            transcript = build_transcript_text(case)
            extraction = await MemoryExtractionService.extract_from_transcript(transcript)
        except Exception:
            logger.exception("eval_b_extraction_failed", case_id=case.id)
            return {
                "case_id": case.id,
                "predicted_categories": [],
                "predicted_entities": [],
                "predicted_kw_dicts": [],
                "processed_kw_dicts": [],
                "error": True,
            }

        # Run post-processing pipeline
        try:
            raw_keywords = _llm_output_to_raw_keywords(
                extraction.categories,
                extraction.entities,
            )
            processed = await postprocessor.process(
                new_keywords=raw_keywords,
                existing_keyword_texts=[],
            )
        except Exception:
            logger.exception("eval_b_postprocess_failed", case_id=case.id)
            return {
                "case_id": case.id,
                "predicted_categories": [],
                "predicted_entities": [],
                "predicted_kw_dicts": [],
                "processed_kw_dicts": [],
                "error": True,
            }

    pred_cats, pred_ents, kw_dicts, processed_dicts = _processed_to_dicts(
        processed,
    )

    return {
        "case_id": case.id,
        "predicted_categories": pred_cats,
        "predicted_entities": pred_ents,
        "predicted_kw_dicts": kw_dicts,
        "processed_kw_dicts": processed_dicts,
        "error": False,
    }


async def _extract_and_process_all_cases(
    cases: list[TestCase],
    semaphore: asyncio.Semaphore,
    postprocessor: KeywordPostprocessor,
) -> list[dict[str, Any]]:
    """Extract and post-process keywords for all test cases."""
    tasks = [_extract_and_process_single_case(case, semaphore, postprocessor) for case in cases]
    return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


async def _aggregate_results(
    cases: list[TestCase],
    case_results: list[dict[str, Any]],
    embedding_service: EmbeddingService,
    judge: LLMJudge,
    config: EvalConfig,
) -> EvalBResult:
    """Aggregate per-case extractions into micro-averaged metrics with IAB."""
    all_pred_cats: list[str] = []
    all_gold_cats: list[str] = []
    all_pred_ents: list[str] = []
    all_gold_ents: list[str] = []
    all_gold_cat_mention_types: list[Literal["explicit", "implicit"]] = []
    all_gold_ent_mention_types: list[Literal["explicit", "implicit"]] = []
    all_pred_kw_dicts: list[dict[str, object]] = []
    all_gold_kw_dicts: list[dict[str, object]] = []
    all_processed_kw_dicts: list[dict[str, object]] = []
    all_transcripts: list[str] = []
    all_gold_iab_ids: list[str | None] = []

    for case, cr in zip(cases, case_results, strict=True):
        all_pred_cats.extend(cr["predicted_categories"])
        all_pred_ents.extend(cr["predicted_entities"])
        all_gold_cats.extend(gk.keyword for gk in case.gold_labels.categories)
        all_gold_ents.extend(gk.keyword for gk in case.gold_labels.entities)
        all_gold_cat_mention_types.extend(gk.mention_type for gk in case.gold_labels.categories)
        all_gold_ent_mention_types.extend(gk.mention_type for gk in case.gold_labels.entities)
        all_pred_kw_dicts.extend(cr["predicted_kw_dicts"])
        all_gold_kw_dicts.extend(_build_gold_kw_dicts(case))
        all_processed_kw_dicts.extend(cr["processed_kw_dicts"])
        all_transcripts.append(build_transcript_text(case))
        for gk in case.gold_labels.categories:
            all_gold_iab_ids.append(gk.iab_category_id)

    # -- Category and entity P/R/F1 (micro-averaged) -------------------------
    cat_result = await compute_keyword_metrics(
        predicted=all_pred_cats,
        gold=all_gold_cats,
        threshold=config.category_match_threshold,
        embedding_service=embedding_service,
    )
    ent_result = await compute_keyword_metrics(
        predicted=all_pred_ents,
        gold=all_gold_ents,
        threshold=config.entity_match_threshold,
        embedding_service=embedding_service,
    )
    cat_metrics = cat_result.metrics
    ent_metrics = ent_result.metrics

    # -- Matched pairs --------------------------------------------------------
    matched_pairs: list[tuple[str, str]] = [
        (m.predicted, m.gold) for m in cat_result.matched_pairs + ent_result.matched_pairs
    ]

    # -- News relevant --------------------------------------------------------
    news_relevant = compute_news_relevant_metrics(
        predicted_keywords=all_pred_kw_dicts,
        gold_keywords=all_gold_kw_dicts,
        matched_pairs=matched_pairs,
    )

    # -- Type confusion -------------------------------------------------------
    type_confusion = compute_type_confusion(
        predicted_keywords=all_pred_kw_dicts,
        gold_keywords=all_gold_kw_dicts,
        matched_pairs=matched_pairs,
    )

    # -- IAB match (Eval B specific) ------------------------------------------
    gold_iab_non_null = [iab_id for iab_id in all_gold_iab_ids if iab_id is not None]
    iab_match, norm_accuracy = compute_iab_match_metrics(
        processed_keywords=all_processed_kw_dicts,
        gold_iab_ids=gold_iab_non_null if gold_iab_non_null else None,
    )

    # -- Wikidata hit (entity validation via Wikidata API + LLM-as-judge) -----
    all_entity_items = [
        {"keyword": str(d["keyword"]), "context": ""}
        for d in all_pred_kw_dicts
        if str(d["keyword_type"]) == "entity"
    ]
    entity_validator = EntityValidator(
        llm_judge=judge,
        wikidata_threshold=config.wikidata_match_threshold,
    )
    wikidata_hit, _entity_validations = await entity_validator.validate_batch(
        entities=all_entity_items,
        concurrency=config.concurrency,
    )

    # -- Per-case details (with per-case matching) ----------------------------
    per_case_details = await _build_case_details(
        cases=cases,
        case_results=case_results,
        niche_keywords=[],
        embedding_service=embedding_service,
        config=config,
    )

    # -- Recall breakdown by mention type (explicit vs implicit) ----------------
    cat_recall_breakdown = _compute_recall_breakdown(
        all_gold_cat_mention_types,
        cat_result.fn_gold_indices,
    )
    ent_recall_breakdown = _compute_recall_breakdown(
        all_gold_ent_mention_types,
        ent_result.fn_gold_indices,
    )

    settings = get_settings()

    return EvalBResult(
        timestamp=datetime.now(tz=UTC).isoformat(),
        model=settings.llm_interest_model,
        test_case_count=len(cases),
        category_metrics=CategoryMetricsB(
            precision=cat_metrics.precision,
            recall=cat_metrics.recall,
            f1=cat_metrics.f1,
            tp_count=cat_metrics.tp_count,
            fp_count=cat_metrics.fp_count,
            fn_count=cat_metrics.fn_count,
            iab_match=iab_match,
            normalization_accuracy=norm_accuracy,
            recall_breakdown=cat_recall_breakdown,
        ),
        entity_metrics=EntityMetrics(
            precision=ent_metrics.precision,
            recall=ent_metrics.recall,
            f1=ent_metrics.f1,
            tp_count=ent_metrics.tp_count,
            fp_count=ent_metrics.fp_count,
            fn_count=ent_metrics.fn_count,
            type_confusion=type_confusion,
            wikidata_hit=wikidata_hit,
            recall_breakdown=ent_recall_breakdown,
        ),
        news_relevant=news_relevant,
        per_case_details=per_case_details,
    )


# ---------------------------------------------------------------------------
# Helpers
# _build_case_details is imported from eval_a
