# Interests Extraction Evaluation Model

This document describes the evaluation framework for measuring the quality of Coyo's interests extraction system. The framework lives in `apps/api/eval/` and assesses extraction across three complementary evaluations.

## Overview

| Evaluation | What it Measures | Key Metrics |
|---|---|---|
| **Eval A** | LLM raw output quality | P/R/F1, niche rate, news relevance, type confusion, Wikidata hit |
| **Eval B** | End-to-end pipeline quality (LLM + post-processing) | All of Eval A + IAB match rate, normalization accuracy |
| **Eval C** | Keyword deduplication accuracy | False merge rate, false split rate |

The split isolates where quality problems originate. If Eval A scores are high but Eval B degrades, post-processing is the problem. If both are poor, the LLM prompt needs tuning. Eval C is independent and tests the dedup algorithm in isolation.

---

## Test Cases

### Structure

Each test case is a YAML file containing a conversation transcript paired with human-annotated gold labels.

```yaml
id: cp-finance-02
source: corpus          # "corpus" | "generated" | "recorded"
domain: finance
transcript:
  - role: user
    text: "I've been watching Tesla stock closely..."
  - role: ai
    text: "Are you interested in the EV market overall?"
  - role: user
    text: "Mainly Tesla and Rivian, yes."
gold_labels:
  categories:
    - keyword: electric vehicles
      is_news_relevant: true
      keyword_type: category
      iab_category_id: "224"
      mention_type: explicit
  entities:
    - keyword: tesla
      is_news_relevant: true
      keyword_type: entity
      mention_type: explicit
    - keyword: rivian
      is_news_relevant: true
      keyword_type: entity
      mention_type: explicit
```

### Gold Keyword Fields

| Field | Description |
|---|---|
| `keyword` | The interest keyword string |
| `is_news_relevant` | Whether this keyword generates regular news (sports, politics, tech) vs. evergreen topics (food, hobbies) |
| `keyword_type` | `"category"` (broad topic) or `"entity"` (specific proper noun) |
| `iab_category_id` | IAB Content Taxonomy ID (Tier 1-4). Used for normalization accuracy in Eval B |
| `mention_type` | `"explicit"` (user directly states interest) or `"implicit"` (inferred from context/behavior) |

### Collection

- **40 Corpus cases** (`cp-*`): Hand-curated, 4 per domain across 10 domains (work, relationship, school-life, tourism, finance, health, politics, culture-education, attitude-emotion, ordinary-life)
- **21 Generated cases** (`gen-*`): Synthetic, covering edge cases and multi-topic scenarios (sports, tech-ai, english-learning, ambiguous, edge-case, multi-topic)
- Located in `eval/data/cases/corpus/` and `eval/data/cases/generated/`

---

## Eval A: LLM Raw Output Quality

Eval A measures whether the production LLM extracts the right keywords from conversation transcripts, **before** any post-processing.

### Pipeline

```
Test Case (transcript + gold labels)
    |
    v
MemoryExtractionService.extract_from_transcript()
    |  (production LLM call)
    v
Predicted keywords (categories + entities)
    |
    v
Bipartite matching against gold labels
    |
    v
Metric computation
```

### Primary Metrics: P/R/F1

Precision, Recall, and F1 are computed separately for categories and entities using **micro-averaged** bipartite matching across all test cases.

#### Matching Algorithm

Keyword matching uses embedding-based bipartite matching rather than exact string comparison. This handles semantic equivalence (e.g., "artificial intelligence" matching "AI").

1. **Embed** all predicted and gold keywords in a single batch call
2. **Build** a cosine similarity matrix (predicted x gold)
3. **Zero out** similarities below the threshold (category: 0.90, entity: 0.85)
4. **Solve** maximum-weight bipartite matching via the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`)
5. **Classify** each keyword:
   - **TP**: Predicted keyword matched to a gold keyword (above threshold)
   - **FP**: Predicted keyword with no matching gold keyword
   - **FN**: Gold keyword with no matching predicted keyword

```
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * P * R / (P + R)
```

#### Recall Breakdown by Mention Type

Recall is further broken down by `mention_type` (explicit vs. implicit). This reveals whether the LLM struggles with implicit signals (e.g., inferring "tennis" from a discussion about a tennis player) compared to explicit statements ("I love tennis").

### Secondary Metrics

#### Niche Rate

Measures what percentage of predicted category keywords are "niche" — topics not recognized in the IAB Content Taxonomy.

- For each predicted category, compute its best cosine similarity to any IAB taxonomy label embedding
- If `best_similarity < keyword_validate_threshold` (configurable), the keyword is classified as niche
- **Niche rate** = niche count / total predicted categories
- A high niche rate may indicate the LLM is hallucinating non-standard topics, or it may indicate legitimate niche interests depending on the test set

#### News Relevance (`is_news_relevant`)

Evaluates the accuracy of the `is_news_relevant` flag on matched keyword pairs. Computed as a confusion matrix (TP/FP/FN/TN) split by keyword type (category, entity, overall).

- Only evaluated on **matched pairs** (TP from the bipartite matching)
- Compares the predicted flag against the gold flag
- Reports P/R/F1 derived from the confusion matrix

#### Type Confusion

Measures the rate of entity/category misclassification on matched keyword pairs.

- For each matched pair, compare `keyword_type` of predicted vs. gold
- **Type confusion rate** = confused pairs / total matched pairs
- Example: Gold says "Tesla" is an `entity`, but the LLM classified it as a `category`

#### Wikidata Hit Rate

Validates whether predicted entity keywords correspond to real-world entities using a three-stage pipeline:

1. **Stage 1 — Wikidata API**: Look up the keyword in Wikidata. If a match is found above the threshold (0.85), mark as `valid` via `wikidata` method
2. **Stage 2 — LLM-as-judge**: If Wikidata lookup fails, send to Claude Haiku for judgment. If the LLM is confident, mark as `valid` or `invalid` via `llm_judge` method
3. **Stage 3 — Human review**: If both automated stages are inconclusive, flag for `human_review`

**Wikidata hit rate** = Stage 1 valid count / total entity count. This measures what fraction of entity keywords can be confirmed via Wikidata alone.

### Output

```
EvalAResult
  ├── timestamp, model, test_case_count
  ├── category_metrics (P/R/F1 + recall_breakdown + niche_rate)
  ├── entity_metrics   (P/R/F1 + recall_breakdown + type_confusion + wikidata_hit)
  ├── news_relevant    (by category / entity / overall)
  └── per_case_details (TP/FP/FN, matched pairs, niche keywords, etc.)
```

---

## Eval B: End-to-End Pipeline Quality

Eval B extends Eval A by running the **full production pipeline**: LLM extraction followed by `KeywordPostprocessor`.

### Pipeline

```
Test Case (transcript + gold labels)
    |
    v
MemoryExtractionService.extract_from_transcript()
    |  (production LLM call)
    v
Raw keywords
    |
    v
KeywordPostprocessor.process()
    |  (dedup, IAB mapping, merge detection)
    v
Processed keywords (with iab_category_id)
    |
    v
Bipartite matching against gold labels
    |
    v
Metric computation (Eval A metrics + IAB metrics)
```

### Additional Metrics (Beyond Eval A)

#### IAB Match Rate

Measures what percentage of predicted category keywords were successfully mapped to an IAB taxonomy ID by the post-processor.

- **IAB match rate** = categories with `iab_category_id != null` / total categories
- A low rate indicates the post-processor is struggling to map keywords to IAB categories

#### Normalization Accuracy

If gold labels include `iab_category_id`, this metric checks whether the predicted IAB ID matches the gold IAB ID.

- **Accuracy** = correct matches / checked pairs
- Only computed when gold IAB IDs are available
- Evaluates the precision of IAB taxonomy assignment

### Output

```
EvalBResult
  ├── timestamp, model, test_case_count
  ├── category_metrics (P/R/F1 + recall_breakdown + iab_match + normalization_accuracy)
  ├── entity_metrics   (P/R/F1 + recall_breakdown + type_confusion + wikidata_hit)
  ├── news_relevant    (by category / entity / overall)
  └── per_case_details (TP/FP/FN, matched pairs, etc.)
```

---

## Eval C: Dedup Accuracy

Eval C measures the accuracy of the keyword deduplication algorithm in isolation. It uses dedicated test sets of keyword pairs rather than conversation transcripts.

### Test Data

Two YAML files in `eval/data/dedup_pairs/`:

- **`should_merge.yaml`**: Pairs that represent the same concept (e.g., "AI" / "artificial intelligence")
- **`should_not_merge.yaml`**: Pairs that are different concepts (e.g., "machine learning" / "machine")

### Hybrid Algorithm (Production)

The evaluation mirrors the production dedup logic, which uses a two-stage approach:

```
Keyword pair (a, b)
    |
    v
Compute cosine similarity of embeddings
    |
    ├── similarity >= dedup_threshold ──────> Auto-merge (no LLM)
    |
    ├── candidate_threshold <= similarity
    |   < dedup_threshold ─────────────────> LLM confirmation
    |                                          |
    |                                          ├── LLM says synonym ──> Merge
    |                                          └── LLM says different -> No merge
    |
    └── similarity < candidate_threshold ──> No merge (no LLM)
```

The three zones:

| Zone | Condition | Action |
|---|---|---|
| **Auto-merge** | `sim >= dedup_threshold` | Merge without LLM (high confidence) |
| **Candidate** | `candidate_threshold <= sim < dedup_threshold` | Ask LLM to confirm |
| **No merge** | `sim < candidate_threshold` | Treat as distinct (high confidence) |

### Metrics

| Metric | Formula | Target |
|---|---|---|
| **False Merge Rate** | false merges / should_not_merge pairs | < 2% |
| **False Split Rate** | false splits / should_merge pairs | < 10% |

A false merge (merging distinct concepts) is more damaging than a false split (keeping synonyms separate), so the target is asymmetric.

### Output

```
EvalCResult
  ├── timestamp, threshold_used, candidate_threshold_used
  ├── false_merge_rate, false_split_rate
  ├── merge_pair_count, split_pair_count
  ├── false_merge_pairs (per-pair details)
  ├── false_split_pairs (per-pair details)
  └── all_results (every pair with similarity, expected, actual, llm_invoked, llm_reason)
```

---

## Configuration

| Parameter | Default | Description |
|---|---|---|
| `category_match_threshold` | 0.90 | Min embedding similarity for a category to count as TP |
| `entity_match_threshold` | 0.85 | Min embedding similarity for an entity to count as TP |
| `wikidata_match_threshold` | 0.85 | Min Wikidata match score to accept entity as valid |
| `keyword_validate_threshold` | ~0.60 | Max IAB similarity for a keyword to be classified as "niche" |
| `keyword_dedup_threshold` | 0.85 | Min similarity for auto-merge in Eval C |
| `keyword_dedup_candidate_threshold` | 0.70 | Min similarity for LLM confirmation zone in Eval C |
| `concurrency` | 5 | Max parallel LLM/embedding calls |
| `judge_model` | claude-haiku-4-5-20251001 | Claude model used for LLM-as-judge (entity validation, synonym detection) |

Override via environment variables or CLI flags:

```bash
python -m eval run-a --concurrency 2 --max-cases 10
```

---

## Running Evaluations

```bash
cd apps/api

# Individual evaluations
python -m eval run-a              # LLM raw output quality
python -m eval run-b              # End-to-end pipeline quality
python -m eval run-c              # Dedup accuracy

# All evaluations sequentially
python -m eval run-all

# Options
python -m eval run-a --dry-run    # Load and validate test cases only (no API calls)
python -m eval run-a --verbose    # Print per-case TP/FP/FN details
python -m eval run-a --max-cases 5  # Limit test cases for quick checks
python -m eval run-a --output-dir /tmp/eval  # Override results directory
```

### Prerequisites

- `ANTHROPIC_API_KEY` in `.env` or environment (required for Eval A/B entity validation and Eval C LLM confirmation)
- `OPENAI_API_KEY` in `.env` or environment (required for embedding service and LLM extraction)

### Output

- **Console**: Markdown summary table
- **JSON results**: Timestamped files in `eval/results/` (e.g., `eval_a_2026-04-06T08-01-25.json`)

---

## Data Flow: Production vs. Evaluation

```
                    PRODUCTION                          EVALUATION
                    ----------                          ----------

Conversation ──> extract_from_transcript() ──> Raw keywords
                                                   |
                        ┌──────────────────────────┤
                        |                          |
                        v                          v
                 PostProcessor              Eval A: compare raw
                        |                   keywords to gold labels
                        v
                 Processed keywords ──────> Eval B: compare processed
                        |                   keywords to gold labels
                        v
                  UserInterest DB

                                            Eval C: test dedup pairs
                                            (independent of A/B)
```

---

## Directory Structure

```
apps/api/eval/
├── __init__.py
├── __main__.py              # CLI entry point
├── config.py                # Eval-specific settings (thresholds, paths)
├── loader.py                # YAML test case and dedup pair loader
├── models.py                # Pydantic models (TestCase, GoldKeyword, result types)
├── report.py                # Console summary and JSON result output
├── runners/
│   ├── eval_a.py            # LLM raw output quality
│   ├── eval_b.py            # End-to-end pipeline quality
│   └── eval_c.py            # Dedup accuracy
├── metrics/
│   ├── embedding_match.py   # P/R/F1 via bipartite matching (Hungarian algorithm)
│   ├── news_relevant.py     # is_news_relevant confusion matrix
│   ├── niche_rate.py        # IAB similarity-based niche detection
│   ├── type_confusion.py    # Entity/category type confusion rate
│   ├── iab_match.py         # IAB normalization metrics (Eval B)
│   └── dedup_accuracy.py    # False merge/split rates (Eval C)
├── validators/
│   ├── entity_validator.py  # 3-stage entity validation (Wikidata -> LLM -> Human)
│   ├── llm_judge.py         # LLM-as-judge service
│   └── wikidata_lookup.py   # Wikidata API integration
├── scripts/
│   ├── generate_cases.py    # Generate synthetic test cases
│   ├── generate_corpus_cases.py
│   └── annotate_iab_ids.py  # Annotate gold labels with IAB IDs
├── data/
│   ├── cases/
│   │   ├── corpus/          # 40 hand-curated test cases (4 per domain)
│   │   └── generated/       # 21 synthetic test cases
│   ├── dedup_pairs/         # Keyword pair dedup test sets
│   ├── wikidata/            # Cached Wikidata lookups
│   └── .cache/              # Embedding cache
└── results/                 # Timestamped evaluation results (JSON)
```
