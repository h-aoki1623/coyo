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
  - [2.6 Idempotency](#26-idempotency)
- [3. Topic Delivery & Selection](#3-topic-delivery--selection)
  - [3.1 Suggestions API](#31-suggestions-api)
  - [3.2 Mobile Client](#32-mobile-client)
  - [3.3 Fixed Topic Fallback](#33-fixed-topic-fallback)
- [4. Integration with Other Systems](#4-integration-with-other-systems)
  - [4.1 Conversation Creation](#41-conversation-creation)
  - [4.2 Memory Extraction](#42-memory-extraction)
  - [4.3 Theme Context & Memory Injection](#43-theme-context--memory-injection)
- [5. Data Model](#5-data-model)
- [6. API Reference](#6-api-reference)
- [7. Configuration Reference](#7-configuration-reference)
- [8. Key Files](#8-key-files)

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

Personal topics are generated from individual user interests that are marked as news-relevant (`is_news_relevant=true`). The process follows four steps:

**Step 1 — Collect per-user keywords**: For each active user, the system retrieves up to 7 top interests of type `category` that have `is_news_relevant=true`, ranked by effective weight (see [2-Layer Weight Model](memory-and-personalization.md#28-2-layer-weight-model)). Each result is a keyword paired with the user's effective weight for that interest.

**Step 2 — Deduplicate against common pool**: Keywords that match any of today's common topics' `source_keyword` (case-insensitive) are removed. This prevents personal topics from duplicating content already available to the user via the common pool.

**Step 3 — Pool keywords across users**: The remaining keywords are pooled into a single map from keyword to the list of users who hold that interest (along with each user's effective weight). If multiple users share the same interest keyword, it appears only once in the pool — the system generates the topic once and assigns it to all relevant users.

**Step 4 — Fetch, store, and assign**: For each unique keyword in the pool, the system fetches a topic via a single LLM + web search call, stores it as one `topic_suggestions` row with `pool_type="personal"`, and then creates a `user_topic_suggestions` link for every user who has that interest, using the user's effective weight as the relevance score.

### 2.6 Idempotency

Both common and personal pipelines check for existing topics before generating:

- **Common**: `get_common_suggestions(today)` — if non-empty, return existing count
- **Personal**: `get_personal_suggestions(today)` — if non-empty, return existing count

This makes the pipeline safe to retry (Cloud Scheduler retry, manual trigger, etc.) without producing duplicate topics.

---

## 3. Topic Delivery & Selection

### 3.1 Suggestions API

**GET `/api/topics/suggestions`** returns the user's topic suggestions grouped by pool type.

Query logic:
1. Join `topic_suggestions` with `user_topic_suggestions` for the current user
2. Find the latest `generated_date` from the user's assignments
3. Return all topics from that date, ordered by `relevance_score DESC`
4. Split into `personal` and `trending` arrays in the response

### 3.2 Mobile Client

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

### 3.3 Fixed Topic Fallback

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

## 4. Integration with Other Systems

### 4.1 Conversation Creation

When a user selects a topic suggestion, the conversation is created with `topic_suggestion_id` (FK to `topic_suggestions`). This links the conversation to its originating topic for downstream use.

The `CreateConversationRequest` accepts exactly one of:
- `topic: TopicLiteral` — a fixed topic key (e.g., "sports")
- `topic_suggestion_id: UUID` — a generated suggestion

### 4.2 Memory Extraction

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

### 4.3 Theme Context & Memory Injection

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

## 5. Data Model

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

## 6. API Reference

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

## 7. Configuration Reference

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

## 8. Key Files

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
