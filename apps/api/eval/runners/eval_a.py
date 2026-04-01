"""Evaluation A runner: LLM raw output quality.

Measures keyword extraction quality from raw LLM output (before post-processing).
Aggregates micro-averaged P/R/F1 across all test cases for both categories and
entities, plus niche rate, type confusion, and news-relevant metrics.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from anthropic import AsyncAnthropic

from coyo.config import get_settings
from coyo.services.embedding import EmbeddingService
from coyo.services.iab_taxonomy import get_iab_taxonomy_service
from coyo.services.memory_extraction import MemoryExtractionService
from eval.loader import build_transcript_text, load_test_cases
from eval.metrics.embedding_match import compute_keyword_metrics
from eval.metrics.news_relevant import compute_news_relevant_metrics
from eval.metrics.niche_rate import compute_niche_rate
from eval.metrics.type_confusion import compute_type_confusion
from eval.models import (
    CaseDetail,
    CategoryMetricsA,
    EntityMetrics,
    EvalAResult,
    MatchedPairDetail,
    TestCase,
)
from eval.validators.entity_validator import EntityValidator
from eval.validators.llm_judge import LLMJudge

if TYPE_CHECKING:
    from coyo.services.iab_taxonomy import IABTaxonomyService
    from eval.config import EvalConfig

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_eval_a(config: EvalConfig) -> EvalAResult:
    """Run Evaluation A: measure LLM raw extraction quality.

    1. Load test cases and extract keywords via the production LLM.
    2. Aggregate metrics across all cases (micro-averaged).
    3. Return structured results.
    """
    cases = load_test_cases(config.cases_dir)
    if not cases:
        raise ValueError(f"No test cases found in {config.cases_dir}")

    if config.max_cases > 0:
        cases = cases[: config.max_cases]
        logger.info("eval_a_cases_limited", max_cases=config.max_cases)

    if not config.anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is required for Eval A. "
            "Set it in your .env or shell environment."
        )

    logger.info("eval_a_start", case_count=len(cases))

    embedding_service = EmbeddingService()
    iab_service = get_iab_taxonomy_service()
    client = AsyncAnthropic(api_key=config.anthropic_api_key)
    judge = LLMJudge(client=client, model=config.judge_model)
    semaphore = asyncio.Semaphore(config.concurrency)

    # -- Extract keywords for all cases concurrently --------------------------
    case_results = await _extract_all_cases(cases, semaphore)

    # -- Aggregate and compute metrics ----------------------------------------
    result = await _aggregate_results(
        cases=cases,
        case_results=case_results,
        embedding_service=embedding_service,
        iab_service=iab_service,
        judge=judge,
        config=config,
    )

    logger.info(
        "eval_a_complete",
        category_f1=round(result.category_metrics.f1, 4),
        entity_f1=round(result.entity_metrics.f1, 4),
        niche_rate=round(result.category_metrics.niche_rate.niche_rate, 4),
    )

    return result


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


async def _extract_single_case(
    case: TestCase,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    """Extract keywords for a single test case via the production LLM.

    Returns a dict with predicted_categories, predicted_entities, and raw
    keyword dicts needed for downstream metric computation.
    """
    async with semaphore:
        logger.debug("eval_a_extracting", case_id=case.id)
        try:
            extraction = await MemoryExtractionService.extract_from_transcript(
                build_transcript_text(case),
            )
        except Exception:
            logger.exception("eval_a_extraction_failed", case_id=case.id)
            return {
                "case_id": case.id,
                "predicted_categories": [],
                "predicted_entities": [],
                "predicted_kw_dicts": [],
                "error": True,
            }

    pred_cat_strings = [item.keyword for item in extraction.categories]
    pred_ent_strings = [item.keyword for item in extraction.entities]

    pred_kw_dicts: list[dict[str, object]] = []
    for item in extraction.categories:
        pred_kw_dicts.append(
            {
                "keyword": item.keyword,
                "is_news_relevant": item.is_news_relevant,
                "keyword_type": "category",
            }
        )
    for item in extraction.entities:
        pred_kw_dicts.append(
            {
                "keyword": item.keyword,
                "is_news_relevant": item.is_news_relevant,
                "keyword_type": "entity",
            }
        )

    return {
        "case_id": case.id,
        "predicted_categories": pred_cat_strings,
        "predicted_entities": pred_ent_strings,
        "predicted_kw_dicts": pred_kw_dicts,
        "error": False,
    }


async def _extract_all_cases(
    cases: list[TestCase],
    semaphore: asyncio.Semaphore,
) -> list[dict[str, Any]]:
    """Extract keywords for all test cases with concurrency control."""
    tasks = [_extract_single_case(case, semaphore) for case in cases]
    return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _build_gold_kw_dicts(case: TestCase) -> list[dict[str, object]]:
    """Build gold keyword dicts from a test case's gold labels."""
    gold_dicts: list[dict[str, object]] = []
    for gk in case.gold_labels.categories:
        gold_dicts.append(
            {
                "keyword": gk.keyword,
                "is_news_relevant": gk.is_news_relevant,
                "keyword_type": "category",
            }
        )
    for gk in case.gold_labels.entities:
        gold_dicts.append(
            {
                "keyword": gk.keyword,
                "is_news_relevant": gk.is_news_relevant,
                "keyword_type": "entity",
            }
        )
    return gold_dicts


async def _aggregate_results(
    cases: list[TestCase],
    case_results: list[dict[str, Any]],
    embedding_service: EmbeddingService,
    iab_service: IABTaxonomyService,
    judge: LLMJudge,
    config: EvalConfig,
) -> EvalAResult:
    """Aggregate per-case extractions into micro-averaged metrics."""
    # Collect combined predicted/gold lists across all cases
    all_pred_cats: list[str] = []
    all_gold_cats: list[str] = []
    all_pred_ents: list[str] = []
    all_gold_ents: list[str] = []
    all_pred_kw_dicts: list[dict[str, object]] = []
    all_gold_kw_dicts: list[dict[str, object]] = []
    all_transcripts: list[str] = []

    for case, cr in zip(cases, case_results, strict=True):
        all_pred_cats.extend(cr["predicted_categories"])
        all_pred_ents.extend(cr["predicted_entities"])
        all_gold_cats.extend(gk.keyword for gk in case.gold_labels.categories)
        all_gold_ents.extend(gk.keyword for gk in case.gold_labels.entities)
        all_pred_kw_dicts.extend(cr["predicted_kw_dicts"])
        all_gold_kw_dicts.extend(_build_gold_kw_dicts(case))
        all_transcripts.append(build_transcript_text(case))

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

    # -- Matched pairs for news_relevant and type_confusion -------------------
    matched_pairs: list[tuple[str, str]] = [
        (m.predicted, m.gold) for m in cat_result.matched_pairs + ent_result.matched_pairs
    ]

    # -- News relevant metrics ------------------------------------------------
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

    # -- Niche rate (IAB score-based: categories with sim < VALIDATE_THRESHOLD) -
    niche_result, niche_keywords = await compute_niche_rate(
        predicted_categories=all_pred_cats,
        embedding_service=embedding_service,
        iab_service=iab_service,
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
        niche_keywords=niche_keywords,
        embedding_service=embedding_service,
        config=config,
    )

    settings = get_settings()

    return EvalAResult(
        timestamp=datetime.now(tz=UTC).isoformat(),
        model=settings.llm_interest_model,
        test_case_count=len(cases),
        category_metrics=CategoryMetricsA(
            precision=cat_metrics.precision,
            recall=cat_metrics.recall,
            f1=cat_metrics.f1,
            tp_count=cat_metrics.tp_count,
            fp_count=cat_metrics.fp_count,
            fn_count=cat_metrics.fn_count,
            niche_rate=niche_result,
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
        ),
        news_relevant=news_relevant,
        per_case_details=per_case_details,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_case_details(
    cases: list[TestCase],
    case_results: list[dict[str, Any]],
    niche_keywords: list[str],
    embedding_service: EmbeddingService,
    config: EvalConfig,
) -> list[CaseDetail]:
    """Build per-case detail records with TP/FP/FN and matched pair info."""
    niche_set = set(niche_keywords)
    details: list[CaseDetail] = []

    # Build lookup for predicted is_news_relevant by keyword
    pred_news_lookup: dict[str, bool] = {}
    for cr in case_results:
        for d in cr["predicted_kw_dicts"]:
            pred_news_lookup[str(d["keyword"])] = bool(d.get("is_news_relevant", False))

    for case, cr in zip(cases, case_results, strict=True):
        pred_cats = cr["predicted_categories"]
        pred_ents = cr["predicted_entities"]
        gold_cats = [gk.keyword for gk in case.gold_labels.categories]
        gold_ents = [gk.keyword for gk in case.gold_labels.entities]

        # Per-case embedding matching for categories
        cat_result = await compute_keyword_metrics(
            predicted=pred_cats,
            gold=gold_cats,
            threshold=config.category_match_threshold,
            embedding_service=embedding_service,
        )
        # Per-case embedding matching for entities
        ent_result = await compute_keyword_metrics(
            predicted=pred_ents,
            gold=gold_ents,
            threshold=config.entity_match_threshold,
            embedding_service=embedding_service,
        )

        # Build gold is_news_relevant lookup
        gold_news: dict[str, bool] = {}
        for gk in case.gold_labels.categories + case.gold_labels.entities:
            gold_news[gk.keyword] = gk.is_news_relevant

        # Build matched pair details with is_news_relevant comparison
        matched_pairs: list[MatchedPairDetail] = []
        news_errors: list[MatchedPairDetail] = []

        for kw_type, match_result in [
            ("category", cat_result),
            ("entity", ent_result),
        ]:
            for m in match_result.matched_pairs:
                pred_nr = pred_news_lookup.get(m.predicted, False)
                gold_nr = gold_news.get(m.gold, False)
                detail = MatchedPairDetail(
                    predicted=m.predicted,
                    gold=m.gold,
                    similarity=round(m.similarity, 4),
                    keyword_type=kw_type,
                    predicted_is_news_relevant=pred_nr,
                    gold_is_news_relevant=gold_nr,
                    news_relevant_correct=(pred_nr == gold_nr),
                )
                matched_pairs.append(detail)
                if not detail.news_relevant_correct:
                    news_errors.append(detail)

        case_niche = [kw for kw in pred_cats + pred_ents if kw in niche_set]

        details.append(
            CaseDetail(
                case_id=case.id,
                domain=case.domain,
                predicted_categories=pred_cats,
                predicted_entities=pred_ents,
                gold_categories=gold_cats,
                gold_entities=gold_ents,
                category_tp=cat_result.tp_keywords,
                category_fp=cat_result.fp_keywords,
                category_fn=cat_result.fn_keywords,
                entity_tp=ent_result.tp_keywords,
                entity_fp=ent_result.fp_keywords,
                entity_fn=ent_result.fn_keywords,
                matched_pairs=matched_pairs,
                news_relevant_errors=news_errors,
                niche_keywords=case_niche,
            )
        )

    return details
