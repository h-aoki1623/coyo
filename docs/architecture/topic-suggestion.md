# Topic Suggestion

This document describes how Coyo generates, assigns, and serves personalized topic suggestions for English conversation practice.

## Table of Contents

- [1. Overview](#1-overview)
- [2. Topic Generation](#2-topic-generation)
  - [2.1 Generation Trigger & Schedule](#21-generation-trigger--schedule)
  - [2.2 Generation Flow](#22-generation-flow)
  - [2.3 Common Topics — Keyword-Driven Generation](#23-common-topics--keyword-driven-generation)
  - [2.4 Common Topics — Trending Fallback (Cold Start)](#24-common-topics--trending-fallback-cold-start)
  - [2.5 Personal Topics — Interest-Based Generation](#25-personal-topics--interest-based-generation)
  - [2.6 LLM Prompts & Web Search](#26-llm-prompts--web-search)
  - [2.7 JSON Parsing & Fallback Chain](#27-json-parsing--fallback-chain)
  - [2.8 Keyword Sanitization](#28-keyword-sanitization)
  - [2.9 Idempotency](#29-idempotency)
- [3. Topic Assignment](#3-topic-assignment)
  - [3.1 Common Topic Assignment](#31-common-topic-assignment)
  - [3.2 Personal Topic Assignment](#32-personal-topic-assignment)
- [4. Topic Delivery & Selection](#4-topic-delivery--selection)
  - [4.1 Suggestions API](#41-suggestions-api)
  - [4.2 Mobile Client](#42-mobile-client)
  - [4.3 Fixed Topic Fallback](#43-fixed-topic-fallback)
- [5. Integration with Other Systems](#5-integration-with-other-systems)
  - [5.1 Conversation Creation](#51-conversation-creation)
  - [5.2 Memory Extraction](#52-memory-extraction)
  - [5.3 Theme Context & Memory Injection](#53-theme-context--memory-injection)
- [6. Data Model](#6-data-model)
- [7. API Reference](#7-api-reference)
- [8. Configuration Reference](#8-configuration-reference)
- [9. Key Files](#9-key-files)

---

## 1. Overview

The topic suggestion system generates daily conversation starters tailored to each user's interests. It operates as a batch pipeline that runs once per day, producing two pools of topics:

| Pool | Description | Audience | Daily Count |
|---|---|---|---|
| **common** | Trending topics driven by globally popular user interests | All users | Up to 3 |
| **personal** | News-relevant topics based on individual user interests | Per-user | Up to 7 per user |

The pipeline depends on the memory extraction system (see [Memory & Conversation Personalization](memory-and-personalization.md)) to supply user interest data. Without extracted interests, the system falls back to LLM-driven trending topic discovery.

---

## 2. Topic Generation

### 2.1 Generation Trigger & Schedule

Topic generation is triggered by a **Cloud Scheduler** job that sends an HTTP POST to `/api/topics/generate` daily at **06:00 JST** (before users start their day).

```
Cloud Scheduler (daily 06:00 JST)
      │
      ▼
POST /api/topics/generate
  Header: X-Cron-Secret (HMAC validation)
      │
      ▼
TopicGenerationService
  ├── generate_common_topics()
  ├── assign_to_users()
  └── generate_personal_topics()
```

The endpoint is protected by an HMAC secret (`X-Cron-Secret`) to prevent unauthorized invocation.

### 2.2 Generation Flow

```
POST /api/topics/generate
    │
    ├── 1. generate_common_topics()
    │       ├── Idempotency check (skip if topics exist for today)
    │       ├── Try keyword-driven generation (Section 2.3)
    │       └── Fall back to trending search (Section 2.4)
    │
    ├── 2. assign_to_users()
    │       └── Link today's common topics to all active users (Section 3.1)
    │
    └── 3. generate_personal_topics()
            ├── Idempotency check (skip if personal topics exist for today)
            ├── Collect per-user interest keywords
            ├── Deduplicate against common pool
            ├── Pool unique keywords across users
            └── For each keyword: fetch, store, and assign (Section 2.5)
```

Steps 1–3 run sequentially. Personal topic generation failure does not affect the response — it is caught and logged, returning `personal_topics_generated: 0`.

### 2.3 Common Topics — Keyword-Driven Generation

The primary path generates common topics from the most popular user interest keywords across all users.

```
InterestRepository.get_global_top_keywords(limit=3)
    │
    ├── Returns top 3 keywords by aggregate effective_weight
    │
    ▼
For each keyword:
    ├── _fetch_personal_topic(keyword)
    │       ├── Sanitize keyword (Section 2.8)
    │       ├── LLM + web search for latest news (Section 2.6)
    │       └── Parse JSON response (Section 2.7)
    │
    └── create_suggestion(pool_type="common")
```

This approach produces topics that reflect the actual interests of the user base rather than generic trending news.

### 2.4 Common Topics — Trending Fallback (Cold Start)

When no user interest keywords exist (e.g., on a fresh deployment), the system falls back to a broader LLM-driven trending search.

```
_fetch_topics()
    ├── Prompt LLM to discover 3 trending global topics
    │   (sports, technology, entertainment, science, business)
    ├── LLM uses web search tool to find current news
    └── Returns TopicSearchResult with up to 3 TopicItems
```

Each `TopicItem` includes a `source_keyword` assigned by the LLM (e.g., "NBA", "AI", "Oscars"), which is used for categorization and interest linking.

### 2.5 Personal Topics — Interest-Based Generation

Personal topics are generated from individual user interests that are marked as news-relevant (`is_news_relevant=true`).

```
Step 1: Collect per-user keywords
    For each active user:
        get_top_interests(
            keyword_type="category",
            is_news_relevant=true,
            limit=7
        )
        → List of (keyword, effective_weight) pairs

Step 2: Deduplicate against common pool
    Remove keywords that match any common topic's source_keyword
    (case-insensitive comparison)

Step 3: Pool keywords across users
    keyword → [(user_id, effective_weight), ...]
    Same keyword from multiple users → single LLM call, multiple assignments

Step 4: Fetch, store, and assign
    For each unique keyword:
        _fetch_personal_topic(keyword)   ← ONE LLM call
        create_suggestion(pool_type="personal")   ← ONE DB row
        For each user with this interest:
            create_user_suggestion(relevance_score=effective_weight)
```

**Cost optimization**: Keywords are pooled across users so each keyword triggers exactly one LLM + web search call, regardless of how many users share that interest.

**Deduplication**: Keywords already covered by the common pool are excluded to avoid showing duplicate topics.

### 2.6 LLM Prompts & Web Search

Topic generation uses the OpenAI Responses API with `web_search_preview` tool. The model decides autonomously whether to perform a web search based on the prompt.

**Common topics prompt** (trending fallback):
- Instructs the LLM to find 3 trending topics from today or recent days
- Requires diverse categories (sports, technology, entertainment, science, business)
- Each topic must include: title (max 10 words), summary (2 sentences), source_keyword, article_content (500–800 characters)

**Personal/keyword-driven prompt**:
- Instructs the LLM to search for latest news about a specific keyword
- Each topic must include: title (max 10 words), summary (2 sentences), article_content (500–800 characters)

Both prompts:
- Emphasize recency: "from TODAY or the past few days"
- Target audience: "English conversation starters for Japanese learners"
- Request valid JSON output

**LLM parameters**:

| Parameter | Value |
|---|---|
| Model | `gpt-5.4-nano` (configurable via `llm_topic_model`) |
| Temperature | 0.7 (variety in suggestions) |
| Max tokens | 2000 (common/trending), 1500 (personal/keyword) |
| Tool | `web_search_preview` (auto tool choice) |

### 2.7 JSON Parsing & Fallback Chain

LLM responses are parsed with a two-tier fallback:

```
LLM response text
    │
    ├── 1. Try parse JSON directly
    │       Strip markdown code fences (```json ... ```) if present
    │       Validate with Pydantic model
    │
    └── 2. Fallback: structured output
            Re-call LLM with structured() (JSON mode)
            Returns strongly-typed Pydantic model
```

For personal topics, if both tiers fail, the keyword is skipped and the remaining keywords proceed — partial failure does not block the pipeline.

### 2.8 Keyword Sanitization

Before interpolating a keyword into an LLM prompt, it is validated to prevent prompt injection:

- **Max length**: 100 characters
- **Allowed characters**: `^[\w\s\-'/&.,()]+$` (Unicode word characters, spaces, common punctuation)
- **Rejected keywords**: return `None`, causing the topic to be skipped

### 2.9 Idempotency

Both common and personal pipelines check for existing topics before generating:

- **Common**: `get_common_suggestions(today)` — if non-empty, return existing count
- **Personal**: `get_personal_suggestions(today)` — if non-empty, return existing count

This makes the pipeline safe to retry (Cloud Scheduler retry, manual trigger, etc.) without producing duplicate topics.

---

## 3. Topic Assignment

### 3.1 Common Topic Assignment

After common topics are generated, they are broadcast to **all active users**:

```
For each user_id in get_active_user_ids():
    For each (rank, suggestion) in today's common topics:
        create_user_suggestion(
            user_id=user_id,
            topic_suggestion_id=suggestion.id,
            relevance_score=1.0 / rank
        )
```

**Relevance scoring** by rank:

| Rank | Relevance Score |
|---|---|
| 1st topic | 1.0 |
| 2nd topic | 0.5 |
| 3rd topic | 0.333 |

Duplicate links (same user + topic) are silently skipped via `IntegrityError` handling.

### 3.2 Personal Topic Assignment

Personal topics are assigned only to users who have the matching interest:

```
For each keyword:
    For each (user_id, effective_weight) in users_with_interest:
        create_user_suggestion(
            user_id=user_id,
            topic_suggestion_id=suggestion.id,
            relevance_score=effective_weight
        )
```

The `relevance_score` equals the user's `effective_weight` for that interest (see [2-Layer Weight Model](memory-and-personalization.md#28-2-layer-weight-model)), so topics matching recently and frequently discussed interests rank higher.

---

## 4. Topic Delivery & Selection

### 4.1 Suggestions API

**GET `/api/topics/suggestions`** returns the user's topic suggestions grouped by pool type.

Query logic:
1. Join `topic_suggestions` with `user_topic_suggestions` for the current user
2. Find the latest `generated_date` from the user's assignments
3. Return all topics from that date, ordered by `relevance_score DESC`
4. Split into `personal` and `trending` arrays in the response

### 4.2 Mobile Client

The mobile app uses a Zustand store (`useSuggestionsStore`) to manage topic suggestion state:

```
App Launch
    │
    ▼
Auth initialization → prefetch() (background)
    │
    ├── GET /api/topics/suggestions
    ├── Cache result: { personal: [...], trending: [...] }
    └── Set isReady=true (unblocks splash screen)
    │
    ▼
HomeScreen mounts
    │
    ├── useSuggestions() hook reads cache
    ├── If cache empty + not loading: retry prefetch()
    └── Render SuggestionCard components
    │
    ▼
User taps suggestion card
    │
    └── POST /api/conversations { topic_suggestion_id: <uuid> }
```

**Design decisions**:
- **Prefetch during auth**: Eliminates visible delay when HomeScreen mounts
- **Generation-based invalidation**: `reset()` bumps a generation counter to cancel in-flight prefetches, preventing cross-user cache leakage on sign-out
- **Graceful degradation**: API failures flip `isReady=true` without `hasLoaded=true`, so the splash screen still dismisses but the hook retries on HomeScreen mount

### 4.3 Fixed Topic Fallback

Even without generated suggestions, users can always start a conversation from 5 predefined topic categories:

| Key | Category |
|---|---|
| `sports` | Sports |
| `business` | Business |
| `politics` | Politics |
| `technology` | Technology |
| `entertainment` | Entertainment |

These are hardcoded in the mobile app and always available regardless of API or suggestion pipeline status.

---

## 5. Integration with Other Systems

### 5.1 Conversation Creation

When a user selects a topic suggestion, the conversation is created with `topic_suggestion_id` (FK to `topic_suggestions`). This links the conversation to its originating topic for downstream use.

The `CreateConversationRequest` accepts exactly one of:
- `topic: TopicLiteral` — a fixed topic key (e.g., "sports")
- `topic_suggestion_id: UUID` — a generated suggestion

### 5.2 Memory Extraction

After a conversation ends, the memory extraction pipeline resolves the conversation's topic keyword for interest upsert:

```
_resolve_topic_keyword(conversation)
    │
    ├── topic_suggestion_id is set:
    │       → (suggestion.source_keyword, None)
    │
    ├── Fixed topic (not "suggested"):
    │       → (IAB category name, IAB ID) via _FIXED_TOPIC_IAB mapping
    │
    └── No topic:
            → (None, None)
```

The resolved keyword is upserted into `user_interests` as part of the post-processing pipeline (see [User Interests — Post-Processing Pipeline](memory-and-personalization.md#25-user-interests--post-processing-pipeline)), ensuring that the topic itself is tracked as a user interest even if the LLM did not extract it from the conversation content.

### 5.3 Theme Context & Memory Injection

When a conversation starts from a topic suggestion, the `ThemeContext` is built from the suggestion's metadata:

```
TopicSuggestion:
    source_keyword: "tennis"
    title: "Alcaraz's Grand Slam Chances"
    summary: "Discuss whether Carlos Alcaraz can win..."

    ↓

theme_text = "tennis\nAlcaraz's Grand Slam Chances\nDiscuss whether..."
    ↓
Embed → theme_embedding (1536-dim)
```

This embedding is used by `MemoryContextService` to rank user interests and conversation summaries by topical relevance (see [Theme-Relevant Selection Strategy](memory-and-personalization.md#33-theme-relevant-selection-strategy)), producing a memory injection that is contextually aligned with the selected topic.

---

## 6. Data Model

```
topic_suggestions
    id (UUID, PK)
    title (text)
    summary (text)
    source_keyword (text)
    article_content (text, 500-800 chars)
    article_url (text, nullable)
    pool_type (varchar(20), CHECK: 'common' | 'personal')
    generated_date (date)
    created_at (timestamptz)

    INDEX ix_topic_suggestions_date_pool (generated_date, pool_type)

user_topic_suggestions
    user_id (UUID, FK → users, PK)
    topic_suggestion_id (UUID, FK → topic_suggestions, PK)
    relevance_score (float)
    created_at (timestamptz)

    INDEX ix_user_topic_suggestions_user_created (user_id, created_at DESC)

conversations
    topic_suggestion_id (UUID, FK → topic_suggestions, nullable, ON DELETE SET NULL)
```

**Relationships**:
- `topic_suggestions` 1:N `user_topic_suggestions` (a topic is assigned to many users)
- `users` 1:N `user_topic_suggestions` (a user has many assigned topics)
- `topic_suggestions` 1:N `conversations` (a topic may start multiple conversations)

---

## 7. API Reference

### POST /api/topics/generate

Generate daily topic suggestions (cron endpoint).

| | |
|---|---|
| **Auth** | `X-Cron-Secret` header (HMAC) |
| **Rate Limit** | `EXPENSIVE_RATE_LIMIT` |
| **Idempotent** | Yes (returns existing count if already generated for today) |

**Response**:
```json
{
  "topics_generated": 3,
  "users_assigned": 150,
  "personal_topics_generated": 42
}
```

### GET /api/topics/suggestions

Get topic suggestions for the authenticated user.

| | |
|---|---|
| **Auth** | Bearer token |
| **Rate Limit** | `DEFAULT_RATE_LIMIT` |

**Response**:
```json
{
  "personal": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Alcaraz Targets French Open Title",
      "summary": "Carlos Alcaraz is preparing for...",
      "sourceKeyword": "tennis",
      "pool": "personal",
      "rank": 1
    }
  ],
  "trending": [
    {
      "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "title": "Tech Giants Report Strong Earnings",
      "summary": "Major technology companies reported...",
      "sourceKeyword": "AI",
      "pool": "common",
      "rank": 1
    }
  ]
}
```

---

## 8. Configuration Reference

| Parameter | Default | Description |
|---|---|---|
| `llm_topic_model` | `gpt-5.4-nano` | LLM model for topic generation |
| `cron_secret` | (Secret Manager) | HMAC secret for `/api/topics/generate` |
| `_MAX_TOPICS` | 3 | Max common topics per daily run |
| `_PERSONAL_MAX_KEYWORDS` | 7 | Max personal topic keywords per user |
| Temperature | 0.7 | LLM temperature for topic generation |
| Max tokens (common) | 2000 | Max LLM response length for trending search |
| Max tokens (personal) | 1500 | Max LLM response length for keyword search |

**Cloud Scheduler**:

| Parameter | Value |
|---|---|
| Schedule | `0 6 * * *` (daily at 06:00 JST) |
| Timezone | `Asia/Tokyo` |
| Attempt deadline | 300s |
| Max retries | 2 |

---

## 9. Key Files

| File | Purpose |
|---|---|
| `apps/api/src/coyo/services/topic_generation.py` | Core generation logic (common + personal pipelines, LLM prompts) |
| `apps/api/src/coyo/routers/topics.py` | API endpoints (`/generate`, `/suggestions`) |
| `apps/api/src/coyo/repositories/topic_suggestion.py` | Topic suggestion CRUD and user assignment queries |
| `apps/api/src/coyo/models/topic_suggestion.py` | ORM models (`TopicSuggestion`, `UserTopicSuggestion`) |
| `apps/api/src/coyo/schemas/topic.py` | API response schemas |
| `apps/api/src/coyo/services/theme_context.py` | Theme embedding for memory injection relevance ranking |
| `apps/api/src/coyo/services/llm/openai_client.py` | OpenAI client with web search tool support |
| `apps/api/src/coyo/repositories/interest.py` | `get_global_top_keywords()` for common topic keyword sourcing |
| `apps/mobile/src/stores/suggestions-store.ts` | Zustand store for suggestion caching and prefetch |
| `apps/mobile/src/features/home/hooks/useSuggestions.ts` | React hook for consuming cached suggestions |
| `apps/mobile/src/constants/topics.ts` | Fixed topic categories (fallback) |
