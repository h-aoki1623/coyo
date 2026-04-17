# Memory & Conversation Personalization

This document describes how Coyo extracts, stores, and injects user memories to personalize English conversation practice sessions.

## Table of Contents

- [1. Memory Architecture](#1-memory-architecture)
  - [1.1 Overview](#11-overview)
  - [1.2 User Profile Summary](#12-user-profile-summary)
  - [1.3 User Attributes](#13-user-attributes)
  - [1.4 User Interests](#14-user-interests)
  - [1.5 Conversation Summaries](#15-conversation-summaries)
- [2. Memory Extraction & Update Design](#2-memory-extraction--update-design)
  - [2.1 Extraction Trigger & Flow](#21-extraction-trigger--flow)
  - [2.2 Unified LLM Extraction](#22-unified-llm-extraction)
  - [2.3 User Attributes](#23-user-attributes)
  - [2.4 User Interests](#24-user-interests)
  - [2.5 Conversation Summaries](#25-conversation-summaries)
  - [2.6 User Profile Summary](#26-user-profile-summary)
- [3. Memory Injection into Conversations](#3-memory-injection-into-conversations)
  - [3.1 Injected Memory Format](#31-injected-memory-format)
  - [3.2 Injection Timing & Snapshot Strategy](#32-injection-timing--snapshot-strategy)
  - [3.3 Theme Context Construction](#33-theme-context-construction)
  - [3.4 Theme-Relevant Selection Strategy](#34-theme-relevant-selection-strategy)
  - [3.5 Legacy Selection Strategy (Fallback)](#35-legacy-selection-strategy-fallback)
- [4. Configuration Reference](#4-configuration-reference)
- [5. Key Files](#5-key-files)

---

## 1. Memory Architecture

### 1.1 Overview

The memory system operates in two phases:

**Phase 1: Extraction** — After a conversation ends, the transcript is asynchronously sent to an LLM to extract user attributes, interest keywords, and a conversation summary, which are then persisted to the database.

**Phase 2: Injection** — At conversation start, stored memories are ranked by relevance to the topic's theme and the top results are injected into the system prompt.

Four memory types are extracted and maintained per user:

| Memory Type | Granularity | Max Size | Update Frequency |
|---|---|---|---|
| **User Profile Summary** | 1 per user | 150–250 words | Every 5 conversations |
| **User Attributes** | 4 fixed keys per user | 200 chars per value | Every conversation (if mentioned) |
| **User Interests** | Unbounded keywords per user | 200 chars per summary | Every conversation (mention bump); summary every 5 conversations |
| **Conversation Summaries** | 1 per conversation | 60 words | Created once per conversation |

### 1.2 User Profile Summary

A free-text narrative (150–250 words) that synthesizes the user's overall profile — professional background, interests, learning goals, and notable experiences.

- **Storage**: One-to-one relationship with users
- **Regeneration trigger**: Every 5 conversations
- **Input sources**: User attributes, top 10 interests (with summaries), and last 5 conversation summaries
- **LLM config**: Temperature 0.5, max tokens 1024

### 1.3 User Attributes

Fixed-key background facts about the user. Only 4 keys exist:

| Key | Description | Example |
|---|---|---|
| `english_goal` | English learning goal or purpose | "Business communication" |
| `job_industry` | Industry, job type, or role | "Software engineer in fintech" |
| `hometown_or_location` | Hometown or current city/country | "Tokyo, Japan" |
| `family_status` | Family situation | "Married with two kids" |

- **Storage**: One record per user per key (4 records max per user)
- **Confidence threshold**: 0.5 (minimum to store)
- **Confidence scale**: 1.0 = stated directly, 0.7 = strongly implied, 0.5 = inferred
- **Supports negation**: A negation flag deletes an existing attribute

### 1.4 User Interests

Keywords representing the user's interests. Two subtypes:

| Subtype | Description | Max per Conversation | Examples |
|---|---|---|---|
| **category** | Broad interest subjects (IAB taxonomy-aligned) | 3 | "tennis", "personal finance", "technology & computing" |
| **entity** | Specific proper nouns (notable public figures, organizations, products) | 3 | "carlos alcaraz", "tesla", "olympics" |

- **Storage**: One record per keyword per user, with a 1536-dim embedding
- **Weight model**: 2-layer (long-term + short-term) — see [2-Layer Weight Model](#2-layer-weight-model)
- **Summary**: 200-char max description, regenerated every 5 conversations when flagged for update
- **IAB mapping**: Categories are validated and linked to IAB Content Taxonomy 3.1 (400+ categories, Tier 1–4)
- **News relevance**: A news-relevant flag on each interest drives topic suggestion generation

### 1.5 Conversation Summaries

Per-conversation summaries for recall and context.

- **Storage**: One record per conversation, with a 1536-dim embedding
- **Max length**: 60 words, 1–2 sentences
- **Metadata**: Topic title (from topic suggestion or "Free conversation") and source keyword (topic suggestion keyword, if any)
- **Embedding text**: Composed from the source keyword (or topic title) and the summary text, mirroring the theme context structure for cosine similarity

---

## 2. Memory Extraction & Update Design

### 2.1 Extraction Trigger & Flow

When a conversation ends, Cloud Tasks enqueues an extraction task. The extraction proceeds through the following steps:

1. **Idempotency check** — Skip if this conversation has already been processed.
2. **Increment conversation count** — Atomically update the user's conversation counter to prevent race conditions.
3. **Build transcript** — Assemble all user and AI turns into a single transcript.
4. **LLM extraction** — Send the transcript to an LLM in a single call to extract user attributes, interests, and a conversation summary.
5. **Save conversation summary** — Persist the summary with its embedding.
6. **Process user attributes** — Add, update, or delete attributes based on the extraction results.
7. **Upsert interests** — Run extracted interests through the post-processing pipeline and persist them.
8. **Batch regeneration** — Every 5 conversations, regenerate interest summaries and the user profile summary.
9. **Mark complete** — Flag the conversation as processed to ensure idempotency.

Cloud Tasks provides at-least-once delivery with retry on failure. The idempotency check in Step 1 prevents duplicate processing.

### 2.2 Unified LLM Extraction

A single LLM call extracts all three memory types — user attributes, user interests, and a conversation summary — from the conversation transcript.

- **Model**: `gpt-5.4-nano` (configurable via `llm_interest_model`)
- **Temperature**: 0.3
- **Max tokens**: 1024
- **Input**: Full conversation transcript (user + AI turns)

**Response schema** (`MemoryExtractionResult`):

```json
{
  "conversation_summary": "1-2 sentence summary (max 60 words, English)",
  "memories": [
    {"key": "english_goal", "value": "...", "confidence": 0.8, "is_negation": false}
  ],
  "categories": [
    {"keyword": "tennis", "is_news_relevant": true, "summary": "User follows..."}
  ],
  "entities": [
    {"keyword": "carlos alcaraz", "is_news_relevant": true, "summary": "User is a fan..."}
  ]
}
```

### 2.3 User Attributes

#### Extraction

The LLM extracts each attribute with a confidence score and an optional negation flag. The confidence score reflects how explicitly the user stated the information:

| Score | Meaning | Example |
|---|---|---|
| 1.0 | Directly stated | "I'm a software engineer" |
| 0.7 | Strongly implied | User discusses daily standups and code reviews in detail |
| 0.5 | Inferred | User mentions debugging once in passing |

Attributes below the minimum confidence threshold (0.5) are discarded.

#### Update Logic

Each extracted attribute is compared against the user's existing attributes and handled as follows:

- **Skip** — The extracted value is empty and is not a negation.
- **Delete** — The extraction is a negation, removing the existing attribute (e.g., "I don't have kids" deletes `family_status`).
- **Add** — No existing record exists and the confidence meets the minimum threshold.
- **Update** — An existing record exists and the new confidence is equal to or higher than the stored confidence.
- **No-op** — The existing value is semantically the same, or the new confidence is lower than the stored one.

The core principle is that **higher confidence always wins** — a directly stated fact overwrites an inferred one, but never the reverse.

### 2.4 User Interests

#### Extraction

Interest extraction uses a 3-step decision process within the LLM prompt. These rules apply only to interests (categories and entities), not to user attributes or conversation summaries.

**Step 1 — Signal detection**: The LLM looks for explicit signals (e.g., "I love X", sustained enthusiasm) or implicit signals (e.g., specialized knowledge, repeated positive references). If neither is present, no interests are extracted.

**Step 2 — Exclusion filters**: Even when a signal is detected, certain cases are excluded — transactional context (hotel check-in does not imply travel interest), non-celebrity personal names, topics introduced by the AI rather than the user, daily routines without genuine passion, conversation-scoped curiosity, casual mentions without follow-up, generic locations as background, and language learning activity (the app's core purpose, not a personal interest).

**Step 3 — Formatting rules**: Categories must correspond to an IAB Content Taxonomy category (Tier 1–4). Entities must be notable proper nouns with a Wikipedia-level public presence. Granularity should match the scope of interest the user expressed. Only one keyword per concept is kept to avoid semantic duplication.

#### Post-Processing Pipeline

After LLM extraction, interests pass through a 3-stage pipeline before being persisted:

1. **Self-deduplication** — Semantically similar keywords among the newly extracted set are merged using embedding similarity (threshold: 0.90). The shortest keyword in each group is kept.
2. **IAB validation** (categories only) — Each category is validated against the IAB Content Taxonomy. An exact name match auto-normalizes the keyword. Otherwise, an LLM classifies it as normalize, valid, or delete. If the LLM fails, an embedding fallback is used (normalize at similarity >= 0.92, validate at >= 0.75). Entities pass through unchanged.
3. **DB deduplication** — Each keyword is compared against existing user interests by embedding similarity. High similarity (>= 0.90) auto-merges with the existing keyword. Medium similarity (0.40–0.90) triggers an LLM synonym judgment. Low similarity (< 0.40) creates a new keyword.

After the pipeline, new keywords are inserted with initial weight, summary, and embedding. Existing keywords receive a weight boost (decay + boost) and are flagged for summary regeneration.

All keywords are batch-embedded in a single API call at the start of the pipeline. Additionally, the conversation's topic keyword is upserted as an interest if not already extracted by the LLM.

#### Summary Regeneration

Interest summaries are regenerated every 5 conversations. The system fetches interests flagged for summary update, finds related conversation summaries by keyword match, and has the LLM generate a fresh 1–2 sentence summary (200 char max, third person) for each. If the summary text changed, the interest's embedding is regenerated to keep theme retrieval accurate.

#### 2-Layer Weight Model

User interests use a 2-layer weight model that balances long-term loyalty with recent activity. The effective weight is the sum of two components:

```
Weight = Long-Term + Short-Term

Long-Term  = 0.5 × log(1 + N)
Short-Term = S × 0.85^G
```

Where:
- **N** = total number of mentions across all conversations
- **S** = stored short-term value from the last update
- **G** = number of conversations since the keyword was last mentioned

**Parameters**:

| Parameter | Value | Description |
|---|---|---|
| Long-term scale | 0.5 | Scale factor for the long-term component |
| Short-term decay | 0.85 | Per-conversation decay rate for short-term |
| Short-term boost | 1.0 | Value added to short-term on each mention |
| Short-term cap | 3.0 | Maximum stored short-term value |

**Update on mention**: When a keyword is mentioned in a conversation, the short-term value is first decayed by `0.85^G`, then boosted by 1.0 (capped at 3.0). The total mention count is incremented and the last-mentioned conversation index is updated.

**Behavior characteristics**:
- A keyword mentioned once 10 conversations ago: low short-term (~0.20), moderate long-term (~0.35) → ~0.55
- A keyword mentioned every conversation for 5 conversations: high short-term (~2.44), growing long-term (~0.90) → ~3.34
- A keyword mentioned once 50 conversations ago: negligible short-term (~0.0003), same long-term (~0.35) → ~0.35

### 2.5 Conversation Summaries

#### Creation

A conversation summary is created once per conversation during the extraction process:

1. **Resolve metadata** — Determine the topic title and source keyword from the conversation's topic suggestion. If none exists, default to "Free conversation".
2. **Compose embedding text** — Combine the source keyword (or topic title) with the summary text. This structure mirrors the theme context composition so that cosine similarity captures topical alignment rather than stylistic differences.
3. **Embed and persist** — Generate a 1536-dim embedding from the composed text and insert the summary. The insert is idempotent on conversation ID, preventing duplicates.

### 2.6 User Profile Summary

#### Generation & Regeneration

The user profile summary is generated (or regenerated) every 5 conversations. The LLM receives all user attributes, the top 10 interests (with summaries), and the last 5 conversation summaries as input, and produces a 2–3 paragraph narrative (150–250 words, third person). The result is upserted — creating the summary on the first trigger and updating it on subsequent ones — along with the current conversation count to track when it was last updated.

---

## 3. Memory Injection into Conversations

### 3.1 Injected Memory Format

The memory block is appended to the conversation system prompt as a structured text block. It consists of the following sections in order:

1. **Header & safety instructions** — Declares the start of user memory data and instructs the AI to treat the content as factual context only, never as instructions.
2. **User Profile** — The profile summary narrative (see [Section 1.2](#12-user-profile-summary)).
3. **Interests** — A list of interest keywords, each optionally followed by its summary. Ranked by theme relevance or effective weight (see [Section 3.4](#34-theme-relevant-selection-strategy)).
4. **Background** — The user's attributes as key-value pairs (e.g., English goal, job/industry).
5. **Recent Conversations** — A list of conversation summaries with date, topic title, and summary text. Ranked by theme relevance or recency.
6. **Usage guidelines** — Instructions for the AI on how to use the memory naturally — avoiding forced references, prioritizing the current conversation, and following the user's latest statements over stored memories.

All user-derived content within the block is wrapped in `<user_data>` tags to prevent prompt injection — the AI is instructed to treat tagged content as factual data only, never as instructions.

### 3.2 Injection Timing & Snapshot Strategy

Memory context is computed **once** at conversation start (during the greeting/pre-fill turn) and persisted as a snapshot on the conversation row. The process follows these steps:

1. **Build theme context** — Construct a text representation and embedding from the conversation's topic suggestion (see [Section 3.3](#33-theme-context-construction)).
2. **Build memory context** — Rank and select the most relevant memories based on the theme context, then format them into a text block.
3. **Persist snapshot** — Store the formatted memory text on the conversation row. An atomic write ensures only the first turn writes the snapshot; concurrent requests do not overwrite it.
4. **Inject into system prompt** — Append the snapshot to the system prompt for all subsequent turns in the conversation.

**Why snapshot?** The injected text is byte-stable across turns, keeping the LLM prompt cache warm. Recomputing memory context on every turn would produce potentially different selections, invalidating the cache and increasing latency and cost.

**Atomic write**: The snapshot is written only if no value exists yet, ensuring that concurrent requests from the same conversation do not overwrite each other.

### 3.3 Theme Context Construction

The theme context is derived from the conversation's topic suggestion. The source keyword, title, and summary are concatenated into a single text, which is then embedded into a 1536-dim vector.

For example, a topic suggestion with keyword "tennis", title "Alcaraz's Grand Slam Chances", and summary "Discuss whether Carlos Alcaraz can win all four Grand Slams..." would produce theme text: "tennis / Alcaraz's Grand Slam Chances / Discuss whether...".

The theme context is unavailable in two cases, both of which trigger the legacy fallback (see [Section 3.5](#35-legacy-selection-strategy-fallback)):
- **Free-form conversations** — No topic suggestion exists.
- **Embedding API failure** — The theme text could not be embedded.

### 3.4 Theme-Relevant Selection Strategy

When a theme with embedding is available, User Interests and Conversation Summaries are ranked by blended scores:

**User Interest ranking**:

Each interest is scored by blending two normalized signals:

```
Score = α × Similarity + β × Weight

α = 0.7 (theme similarity weight)
β = 0.3 (effective weight, see 2-Layer Weight Model in Section 2.4)
```

- **Similarity** — Min-max normalized cosine similarity between the interest embedding and the theme embedding.
- **Weight** — Min-max normalized effective weight from the 2-layer weight model.
- Ties are broken by keyword in ascending order to ensure byte-stable output for prompt caching.
- The top 10 interests are selected.

**Conversation Summary ranking**:

Each summary is scored by blending theme similarity with recency:

```
Score = α × Similarity + β × Recency

α = 0.7 (theme similarity weight)
β = 0.3 (recency decay weight)
```

- **Similarity** — Min-max normalized cosine similarity between the summary embedding and the theme embedding.
- **Recency** — Exponential decay based on age: `e^(-D / 14)`, where D is the number of days since the conversation. A 14-day half-life means summaries lose half their recency score every two weeks.
- The top 5 summaries are selected.

**Fallback top-up**: If theme-ranked results are fewer than the target count (e.g., embeddings not yet backfilled), the remaining slots are filled from the legacy path (top-N by weight / most recent).

### 3.5 Legacy Selection Strategy (Fallback)

Used when no theme embedding is available:

- **User Interests**: Top 10 by effective weight (descending)
- **Conversation Summaries**: Most recent 5 by creation date (descending)

---

## 4. Configuration Reference

All values are configurable via environment variables / `Settings`:

| Parameter | Default | Description |
|---|---|---|
| `llm_interest_model` | `gpt-5.4-nano` | LLM model for extraction and regeneration |
| `memory_theme_alpha` | 0.7 | Similarity weight for interest ranking |
| `memory_theme_beta` | 0.3 | Effective weight for interest ranking |
| `memory_summary_alpha` | 0.7 | Similarity weight for summary ranking |
| `memory_summary_beta` | 0.3 | Recency decay weight for summary ranking |
| `memory_summary_half_life_days` | 14 | Half-life for summary recency decay |
| `memory_k_interest` | 10 | Max interests injected per conversation |
| `memory_k_summary` | 5 | Max conversation summaries injected |
| `memory_candidate_fetch_limit` | 2000 | DoS guard: max candidates fetched per user |
| `keyword_normalize_threshold` | 0.92 | Embedding similarity to normalize to IAB name |
| `keyword_validate_threshold` | 0.75 | Embedding similarity to link IAB category |
| `keyword_dedup_threshold` | 0.90 | Auto-merge threshold for keyword deduplication |
| `keyword_dedup_candidate_threshold` | 0.40 | LLM synonym check threshold |
| `cloud_tasks_queue` | `memory-extraction` | Cloud Tasks queue name |

---

## 5. Key Files

| File | Purpose |
|---|---|
| `apps/api/src/coyo/services/memory_extraction.py` | Core extraction pipeline (9 steps), LLM prompts |
| `apps/api/src/coyo/services/memory_context.py` | Memory context building, ranking, and formatting |
| `apps/api/src/coyo/services/theme_context.py` | Theme embedding for relevance ranking |
| `apps/api/src/coyo/services/keyword_postprocessor.py` | 3-stage keyword post-processing (A/B/C) |
| `apps/api/src/coyo/services/iab_taxonomy.py` | IAB Content Taxonomy validation and embedding |
| `apps/api/src/coyo/repositories/interest.py` | Interest CRUD with 2-layer weight model |
| `apps/api/src/coyo/repositories/profile_attribute.py` | User attribute CRUD |
| `apps/api/src/coyo/repositories/profile_summary.py` | Profile summary CRUD |
| `apps/api/src/coyo/repositories/conversation_summary.py` | Conversation summary CRUD |
| `apps/api/src/coyo/models/user_interest.py` | UserInterest ORM model |
| `apps/api/src/coyo/models/user_attribute.py` | UserAttribute ORM model |
| `apps/api/src/coyo/models/user_profile_summary.py` | UserProfileSummary ORM model |
| `apps/api/src/coyo/models/conversation_summary.py` | ConversationSummary ORM model |
| `apps/api/src/coyo/routers/tasks.py` | Cloud Tasks endpoint (`/extract-memory`) |
| `apps/api/src/coyo/services/turn_orchestrator.py` | Conversation handler (injects memory into system prompt) |
