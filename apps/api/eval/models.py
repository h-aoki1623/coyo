"""Pydantic models for test cases, gold labels, and evaluation results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Test case schema
# ---------------------------------------------------------------------------


class TranscriptTurn(BaseModel):
    """A single turn in a conversation transcript."""

    role: Literal["user", "ai"]
    text: str


class GoldKeyword(BaseModel):
    """A gold-label keyword with expected attributes."""

    keyword: str
    is_news_relevant: bool
    keyword_type: Literal["category", "entity"]
    iab_category_id: str | None = None


class GoldLabels(BaseModel):
    """Gold labels for a test case."""

    categories: list[GoldKeyword] = []
    entities: list[GoldKeyword] = []


class TestCase(BaseModel):
    """A single evaluation test case with transcript and gold labels."""

    id: str
    source: Literal["corpus", "generated", "recorded"]
    domain: str
    transcript: list[TranscriptTurn]
    gold_labels: GoldLabels
    notes: str | None = None


# ---------------------------------------------------------------------------
# Eval C dedup pair schema
# ---------------------------------------------------------------------------


class DedupPair(BaseModel):
    """A keyword pair for deduplication evaluation."""

    a: str
    b: str
    reason: str | None = None


class DedupPairSet(BaseModel):
    """A set of dedup pairs (should_merge or should_not_merge)."""

    pairs: list[DedupPair]


# ---------------------------------------------------------------------------
# Metric result models
# ---------------------------------------------------------------------------


class KeywordMetrics(BaseModel):
    """Precision, Recall, F1 for a keyword type."""

    precision: float
    recall: float
    f1: float
    tp_count: int = 0
    fp_count: int = 0
    fn_count: int = 0


class ConfusionMatrix(BaseModel):
    """Confusion matrix for binary classification."""

    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0


class NewsRelevantResult(BaseModel):
    """is_news_relevant metrics with confusion matrix, split by type."""

    precision: float
    recall: float
    f1: float
    confusion: ConfusionMatrix


class NicheRateResult(BaseModel):
    """Result of LLM-as-judge niche rate evaluation."""

    niche_count: int
    total_count: int
    niche_rate: float


class TypeConfusionResult(BaseModel):
    """Type confusion rate for entity/category misclassification."""

    confused_count: int
    total_count: int
    type_confusion_rate: float


class WikidataHitResult(BaseModel):
    """Wikidata hit rate for entity validation."""

    wikidata_valid_count: int
    llm_valid_count: int
    llm_invalid_count: int
    human_review_count: int
    total_count: int
    wikidata_hit_rate: float


class IABMatchResult(BaseModel):
    """IAB matching metrics for Eval B."""

    iab_matched_count: int
    total_category_count: int
    iab_match_rate: float


class NormalizationAccuracyResult(BaseModel):
    """Normalization accuracy for IAB category ID assignment."""

    checked: int = 0
    correct: int = 0
    accuracy: float | None = None


# ---------------------------------------------------------------------------
# Per-case detail for debugging
# ---------------------------------------------------------------------------


class MatchedPairDetail(BaseModel):
    """A single matched keyword pair with comparison details."""

    predicted: str
    gold: str
    similarity: float
    keyword_type: str  # "category" or "entity"
    predicted_is_news_relevant: bool = False
    gold_is_news_relevant: bool = False
    news_relevant_correct: bool = True


class CaseDetail(BaseModel):
    """Detailed per-case evaluation result."""

    case_id: str
    domain: str
    predicted_categories: list[str] = []
    predicted_entities: list[str] = []
    gold_categories: list[str] = []
    gold_entities: list[str] = []
    category_tp: list[str] = []
    category_fp: list[str] = []
    category_fn: list[str] = []
    entity_tp: list[str] = []
    entity_fp: list[str] = []
    entity_fn: list[str] = []
    matched_pairs: list[MatchedPairDetail] = []
    news_relevant_errors: list[MatchedPairDetail] = []
    niche_keywords: list[str] = []
    type_confused_keywords: list[str] = []


# ---------------------------------------------------------------------------
# Evaluation result models
# ---------------------------------------------------------------------------


class CategoryMetricsA(KeywordMetrics):
    """Category metrics for Eval A (includes niche rate)."""

    niche_rate: NicheRateResult = Field(
        default_factory=lambda: NicheRateResult(niche_count=0, total_count=0, niche_rate=0.0),
    )


class CategoryMetricsB(KeywordMetrics):
    """Category metrics for Eval B (includes IAB match and normalization accuracy)."""

    iab_match: IABMatchResult | None = None
    normalization_accuracy: NormalizationAccuracyResult | None = None


class EntityMetrics(KeywordMetrics):
    """Entity metrics including type confusion and Wikidata hit rate."""

    type_confusion: TypeConfusionResult = Field(
        default_factory=lambda: TypeConfusionResult(
            confused_count=0,
            total_count=0,
            type_confusion_rate=0.0,
        ),
    )
    wikidata_hit: WikidataHitResult = Field(
        default_factory=lambda: WikidataHitResult(
            wikidata_valid_count=0,
            llm_valid_count=0,
            llm_invalid_count=0,
            human_review_count=0,
            total_count=0,
            wikidata_hit_rate=0.0,
        ),
    )


class NewsRelevantByType(BaseModel):
    """is_news_relevant metrics split by keyword type."""

    category: NewsRelevantResult
    entity: NewsRelevantResult
    overall: NewsRelevantResult


class EvalAResult(BaseModel):
    """Result of Evaluation A (LLM raw output quality)."""

    timestamp: str
    model: str
    test_case_count: int
    category_metrics: CategoryMetricsA
    entity_metrics: EntityMetrics
    news_relevant: NewsRelevantByType
    per_case_details: list[CaseDetail] = []


class EvalBResult(BaseModel):
    """Result of Evaluation B (end-to-end pipeline quality)."""

    timestamp: str
    model: str
    test_case_count: int
    category_metrics: CategoryMetricsB
    entity_metrics: EntityMetrics
    news_relevant: NewsRelevantByType
    per_case_details: list[CaseDetail] = []


class PairResult(BaseModel):
    """Result for a single dedup pair evaluation."""

    a: str
    b: str
    similarity: float
    expected_merge: bool
    actual_merge: bool
    correct: bool


class EvalCResult(BaseModel):
    """Result of Evaluation C (Process C dedup accuracy)."""

    timestamp: str
    threshold_used: float
    false_merge_rate: float
    false_split_rate: float
    merge_pair_count: int
    split_pair_count: int
    false_merge_pairs: list[PairResult] = []
    false_split_pairs: list[PairResult] = []
    all_results: list[PairResult] = []
