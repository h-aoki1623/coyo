# Interests Extraction Evaluation Model

This document describes the evaluation framework for measuring the quality of Coyo's interests extraction system. The framework lives in `apps/api/eval/` and assesses extraction across three complementary evaluations.

## Overview

| Evaluation | What it Measures | Key Metrics |
|---|---|---|
| **Eval A** | LLM raw output quality | Precision/Recall/F1, niche rate, news relevance, type confusion, Wikidata hit |
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

**Category**

| Metric | Target | Description |
|---|---|---|
| Precision / Recall / F1 | — | Keyword extraction accuracy for broad topics |
| Recall Breakdown | — | Recall split by explicit vs. implicit mentions |
| Niche Rate | — | % of categories not matching IAB taxonomy |

**Entity**

| Metric | Target | Description |
|---|---|---|
| Precision / Recall / F1 | — | Keyword extraction accuracy for proper nouns |
| Recall Breakdown | — | Recall split by explicit vs. implicit mentions |
| Type Confusion | — | Entity/category misclassification rate |
| Wikidata Hit Rate | — | % of entities confirmed via Wikidata API |

**is_news_relevant**

| Metric | Target | Description |
|---|---|---|
| Precision / Recall / F1 | — | `is_news_relevant` flag accuracy (confusion matrix, split by category/entity/overall) |

### Precision / Recall / F1

Precision, Recall, F1 are computed separately for categories and entities, **micro-averaged** across all test cases. The same Precision/Recall/F1 formulas are also used for `is_news_relevant` classification, where the confusion matrix is derived from matched keyword pairs.

- **Precision** — Of the keywords extracted, what fraction matched the gold labels. For `is_news_relevant`, of the keywords predicted as news-relevant, what fraction was correct
- **Recall** — Of the gold-label keywords, what fraction was successfully extracted. For `is_news_relevant`, of the actually news-relevant keywords, what fraction was correctly flagged
- **F1** — Harmonic mean of Precision and Recall. Balances both into a single score

```
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * Precision * Recall / (Precision + Recall)
```

#### Category / Entity Keyword Matching

For categories and entities, TP/FP/FN are determined via **embedding-based bipartite matching** rather than exact string comparison. This handles semantic equivalence (e.g., "artificial intelligence" matching "AI"). Precision/Recall/F1 are then computed from these TP/FP/FN counts.

1. Embed all predicted and gold keywords in a single batch call
2. Build a cosine similarity matrix (predicted x gold)
3. Zero out similarities below the threshold (category: 0.90, entity: 0.85)
4. Solve maximum-weight bipartite matching via the Hungarian algorithm
5. Classify each keyword:
   - **TP**: Predicted keyword matched to a gold keyword (above threshold)
   - **FP**: Predicted keyword with no matching gold keyword
   - **FN**: Gold keyword with no matching predicted keyword
6. Compute Precision/Recall/F1 from the TP/FP/FN counts

#### is_news_relevant Classification

For `is_news_relevant`, Precision/Recall/F1 are computed from a binary confusion matrix rather than bipartite matching:

1. Take only **matched pairs** (TP from the category/entity bipartite matching above)
2. For each pair, compare the predicted `is_news_relevant` flag against the gold flag
3. Build a confusion matrix (TP/FP/FN/TN) where TP = both predicted and gold are `true`, FP = predicted `true` but gold `false`, etc.
4. Compute Precision/Recall/F1 from this confusion matrix, split by keyword type (category, entity, overall)

### Recall Breakdown (Category / Entity)

Recall is further broken down by `mention_type` (explicit vs. implicit). This reveals whether the LLM struggles with implicit signals (e.g., inferring "tennis" from a discussion about a tennis player) compared to explicit statements ("I love tennis").

### Niche Rate (Category)

Measures what percentage of predicted category keywords are "niche" — topics not recognized in the IAB Content Taxonomy.

- For each predicted category, compute its best cosine similarity to any IAB taxonomy label embedding
- If the best similarity falls below the validation threshold (configurable), the keyword is classified as niche
- **Niche rate** = niche count / total predicted categories
- A high niche rate may indicate the LLM is hallucinating non-standard topics, or it may indicate legitimate niche interests depending on the test set

### Type Confusion (Category / Entity)

Measures the rate of entity/category misclassification on matched keyword pairs.

- For each matched pair, compare `keyword_type` of predicted vs. gold
- **Type confusion rate** = confused pairs / total matched pairs
- Example: Gold says "Tesla" is an `entity`, but the LLM classified it as a `category`

### Wikidata Hit Rate (Entity)

Validates whether predicted entity keywords correspond to real-world entities using a three-stage pipeline:

1. **Stage 1 — Wikidata API**: Look up the keyword in Wikidata. If a match is found above the threshold (0.85), mark as `valid` via `wikidata` method
2. **Stage 2 — LLM-as-judge**: If Wikidata lookup fails, send to Claude Haiku for judgment. If the LLM is confident, mark as `valid` or `invalid` via `llm_judge` method
3. **Stage 3 — Human review**: If both automated stages are inconclusive, flag for `human_review`

**Wikidata hit rate** = Stage 1 valid count / total entity count. This measures what fraction of entity keywords can be confirmed via Wikidata alone.

---

## Eval B: End-to-End Pipeline Quality

Eval B extends Eval A by running the **full production pipeline**: LLM extraction followed by `KeywordPostprocessor`.

**Category**

| Metric | Target | Description |
|---|---|---|
| Precision / Recall / F1 | — | Same as Eval A, measured after post-processing |
| Recall Breakdown | — | Recall split by explicit vs. implicit mentions |
| IAB Match Rate | — | % of categories successfully mapped to an IAB taxonomy ID |
| Normalization Accuracy | — | Predicted IAB ID vs. gold IAB ID match rate |

**Entity**

| Metric | Target | Description |
|---|---|---|
| Precision / Recall / F1 | — | Same as Eval A, measured after post-processing |
| Recall Breakdown | — | Recall split by explicit vs. implicit mentions |
| Type Confusion | — | Entity/category misclassification rate |
| Wikidata Hit Rate | — | % of entities confirmed via Wikidata API |

**is_news_relevant**

| Metric | Target | Description |
|---|---|---|
| Precision / Recall / F1 | — | `is_news_relevant` flag accuracy (confusion matrix, split by category/entity/overall) |

### Precision / Recall / F1

Computed identically to Eval A (see [Eval A: Precision / Recall / F1](#precision--recall--f1)), but measured on the **post-processed** keywords rather than raw LLM output. The same bipartite matching and is_news_relevant classification methods apply.

### IAB Match Rate (Category)

Measures what percentage of predicted category keywords were successfully mapped to an IAB taxonomy ID by the post-processor.

- **IAB match rate** = categories with a non-null `iab_category_id` / total categories
- A low rate indicates the post-processor is struggling to map keywords to IAB categories

### Normalization Accuracy (Category)

If gold labels include `iab_category_id`, this metric checks whether the predicted IAB ID matches the gold IAB ID.

- **Accuracy** = correct matches / checked pairs
- Only computed when gold IAB IDs are available
- Evaluates the precision of IAB taxonomy assignment

---

## Eval C: Dedup Accuracy

Eval C measures the accuracy of the keyword deduplication algorithm in isolation. It uses dedicated test sets of keyword pairs rather than conversation transcripts.

| Metric | Target | Description |
|---|---|---|
| False Merge Rate | < 2% | % of distinct pairs incorrectly merged |
| False Split Rate | < 10% | % of synonym pairs incorrectly kept separate |

### Test Data

Two YAML files in `eval/data/dedup_pairs/`:

- **`should_merge.yaml`**: Pairs that represent the same concept (e.g., "AI" / "artificial intelligence")
- **`should_not_merge.yaml`**: Pairs that are different concepts (e.g., "machine learning" / "machine")

### False Merge Rate / False Split Rate

The evaluation mirrors the production dedup logic, which uses a hybrid two-stage approach (embedding similarity + LLM confirmation) to decide whether a keyword pair should be merged.

#### Dedup Algorithm

For each keyword pair, the merge decision is made in three zones based on embedding cosine similarity:

| Zone | Condition | Action |
|---|---|---|
| **Auto-merge** | Similarity at or above the dedup threshold | Merge without LLM (high confidence) |
| **Candidate** | Similarity between the candidate threshold and the dedup threshold | Ask LLM to confirm whether the pair are synonyms |
| **No merge** | Similarity below the candidate threshold | Treat as distinct (high confidence) |

#### Metric Computation

Each pair's merge decision is compared against the gold label (should_merge or should_not_merge):

- **False Merge** — A pair from `should_not_merge` that was incorrectly merged
- **False Split** — A pair from `should_merge` that was incorrectly kept separate

```
False Merge Rate = false merges / total should_not_merge pairs
False Split Rate = false splits / total should_merge pairs
```

A false merge (merging distinct concepts) is more damaging than a false split (keeping synonyms separate), so the target is asymmetric (< 2% vs. < 10%).

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
