"""IAB Content Taxonomy 3.1 service for keyword validation and normalization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import structlog

from coyo.config import get_settings
from coyo.services.similarity import find_best_match

if TYPE_CHECKING:
    from coyo.services.embedding import EmbeddingService

logger = structlog.get_logger()

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "iab_content_taxonomy.json"


@dataclass(frozen=True)
class IABCategory:
    """A single IAB Content Taxonomy category."""

    id: str
    name: str
    parent_id: str | None
    tier: int


@dataclass(frozen=True)
class IABMatchResult:
    """Result of matching a keyword against the IAB taxonomy."""

    action: Literal["normalize", "valid", "invalid"]
    iab_id: str | None
    iab_name: str | None
    similarity: float


class IABTaxonomyService:
    """Loads IAB Content Taxonomy 3.1 and matches keywords via embeddings."""

    def __init__(self) -> None:
        self._categories: dict[str, IABCategory] = {}
        self._ordered_categories: list[IABCategory] = []
        self._label_list: list[str] = []
        self._label_embeddings: list[list[float]] | None = None
        self._load_taxonomy()

    def _load_taxonomy(self) -> None:
        with open(_DATA_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        for item in raw:
            cat = IABCategory(
                id=item["id"],
                name=item["name"],
                parent_id=item.get("parent_id"),
                tier=item["tier"],
            )
            self._categories[cat.id] = cat
        self._ordered_categories = list(self._categories.values())
        self._label_list = [cat.name for cat in self._ordered_categories]

    def get_all_labels(self) -> list[str]:
        """Return all category names."""
        return list(self._label_list)

    def get_category(self, iab_id: str) -> IABCategory | None:
        """Look up a category by ID."""
        return self._categories.get(iab_id)

    async def ensure_embeddings(self, embedding_service: EmbeddingService) -> None:
        """Compute and cache label embeddings if not already done."""
        if self._label_embeddings is not None:
            return
        logger.info(
            "iab_computing_embeddings",
            label_count=len(self._label_list),
        )
        self._label_embeddings = await embedding_service.embed(self._label_list)

    def match(self, keyword_embedding: list[float]) -> IABMatchResult:
        """Match a keyword embedding against all IAB labels.

        Returns an IABMatchResult indicating whether to normalize, keep, or discard.
        Requires ensure_embeddings() to have been called first.
        """
        if self._label_embeddings is None:
            raise RuntimeError("Call ensure_embeddings() before match()")

        settings = get_settings()
        best_idx, best_sim = find_best_match(keyword_embedding, self._label_embeddings)

        best_cat = self._ordered_categories[best_idx]

        if best_sim >= settings.keyword_normalize_threshold:
            return IABMatchResult(
                action="normalize",
                iab_id=best_cat.id,
                iab_name=best_cat.name,
                similarity=best_sim,
            )
        elif best_sim >= settings.keyword_validate_threshold:
            return IABMatchResult(
                action="valid",
                iab_id=None,
                iab_name=None,
                similarity=best_sim,
            )
        else:
            return IABMatchResult(
                action="invalid",
                iab_id=None,
                iab_name=None,
                similarity=best_sim,
            )


@lru_cache(maxsize=1)
def get_iab_taxonomy_service() -> IABTaxonomyService:
    """Lazily instantiate and cache the IAB taxonomy service."""
    return IABTaxonomyService()
