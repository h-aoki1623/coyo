"""Wikidata entity lookup via the public API (wbsearchentities).

Uses the Wikidata API for real-time entity validation instead of a local index.
The API is free and has generous rate limits for the small number of entity
lookups needed during evaluation (~30-50 per eval run).
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()

_API_URL = "https://www.wikidata.org/w/api.php"
_USER_AGENT = "CoyoEval/1.0 (keyword extraction evaluation)"


@dataclass(frozen=True)
class WikidataMatch:
    """A matched Wikidata entity."""

    qid: str
    label: str
    description: str
    match_score: float  # 1.0 for exact match, lower for partial


async def lookup_wikidata(keyword: str, threshold: float = 0.85) -> WikidataMatch | None:
    """Look up a keyword in Wikidata via the wbsearchentities API.

    Returns a WikidataMatch if a sufficiently close entity is found,
    or None if no match meets the threshold.
    """
    # Run the synchronous HTTP call in a thread to avoid blocking
    return await asyncio.to_thread(_lookup_sync, keyword, threshold)


def _lookup_sync(keyword: str, threshold: float) -> WikidataMatch | None:
    """Synchronous Wikidata API lookup."""
    params = urllib.parse.urlencode(
        {
            "action": "wbsearchentities",
            "search": keyword,
            "language": "en",
            "limit": "3",
            "format": "json",
        }
    )
    url = f"{_API_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        logger.warning("wikidata_api_failed", keyword=keyword)
        return None

    results = data.get("search", [])
    if not results:
        return None

    # Score candidates based on label match quality
    best: WikidataMatch | None = None
    best_score = 0.0

    for result in results:
        label = result.get("label", "")
        score = _compute_match_score(keyword, label)

        if score > best_score:
            best_score = score
            best = WikidataMatch(
                qid=result.get("id", ""),
                label=label,
                description=result.get("description", ""),
                match_score=score,
            )

    if best is not None and best.match_score >= threshold:
        return best

    return None


def _compute_match_score(keyword: str, label: str) -> float:
    """Compute a simple match score between keyword and Wikidata label.

    Returns 1.0 for exact match (case-insensitive), lower for partial matches.
    """
    kw = keyword.strip().lower()
    lb = label.strip().lower()

    if kw == lb:
        return 1.0

    # One contains the other
    if kw in lb or lb in kw:
        shorter = min(len(kw), len(lb))
        longer = max(len(kw), len(lb))
        return shorter / longer if longer > 0 else 0.0

    return 0.0


async def lookup_wikidata_batch(
    keywords: list[str],
    threshold: float = 0.85,
    concurrency: int = 3,
) -> list[WikidataMatch | None]:
    """Look up multiple keywords with concurrency control."""
    semaphore = asyncio.Semaphore(concurrency)

    async def _lookup(kw: str) -> WikidataMatch | None:
        async with semaphore:
            return await lookup_wikidata(kw, threshold)

    return await asyncio.gather(*[_lookup(kw) for kw in keywords])
