"""Niche rate metric based on IAB embedding similarity scores.

A category keyword is considered "niche" if its best IAB taxonomy similarity
score falls below VALIDATE_THRESHOLD — meaning it does not correspond to any
recognized IAB content category.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from coyo.config import get_settings
from eval.models import NicheRateResult

if TYPE_CHECKING:
    from coyo.services.embedding import EmbeddingService
    from coyo.services.iab_taxonomy import IABTaxonomyService

logger = structlog.get_logger()


async def compute_niche_rate(
    predicted_categories: list[str],
    embedding_service: EmbeddingService,
    iab_service: IABTaxonomyService,
) -> tuple[NicheRateResult, list[str]]:
    """Compute niche rate for predicted category keywords via IAB similarity.

    A keyword is "niche" if its best IAB similarity < VALIDATE_THRESHOLD.

    Args:
        predicted_categories: Category keyword strings from LLM output.
        embedding_service: For computing keyword embeddings.
        iab_service: IAB taxonomy with pre-computed label embeddings.

    Returns:
        A tuple of (NicheRateResult, list of niche keyword strings).
    """
    if not predicted_categories:
        return NicheRateResult(niche_count=0, total_count=0, niche_rate=0.0), []

    settings = get_settings()
    threshold = settings.keyword_validate_threshold

    # Ensure IAB embeddings are computed
    await iab_service.ensure_embeddings(embedding_service)

    # Embed all predicted categories
    embeddings = await embedding_service.embed(predicted_categories)

    niche_keywords: list[str] = []
    for keyword, emb in zip(predicted_categories, embeddings, strict=True):
        match_result = iab_service.match(emb)
        if match_result.similarity < threshold:
            niche_keywords.append(keyword)

    total = len(predicted_categories)
    niche_count = len(niche_keywords)
    rate = niche_count / total if total > 0 else 0.0

    logger.debug(
        "niche_rate_computed",
        niche=niche_count,
        total=total,
        rate=round(rate, 4),
        threshold=threshold,
        niche_keywords=niche_keywords,
    )

    return NicheRateResult(
        niche_count=niche_count,
        total_count=total,
        niche_rate=rate,
    ), niche_keywords
