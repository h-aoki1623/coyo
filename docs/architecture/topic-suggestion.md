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
- [3. Key Files](#3-key-files)

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

Topic generation is triggered by a **Cloud Scheduler** job that sends an HTTP POST to `/api/topics/generate` daily at **06:00 JST** (before users start their day). The endpoint is protected by an HMAC secret (`X-Cron-Secret`) to prevent unauthorized invocation. Upon receiving the request, `TopicGenerationService` executes three steps in sequence: common topic generation, user assignment, and personal topic generation.

### 2.2 Generation Flow

The generation endpoint performs three sequential operations. First, it generates common topics — checking for idempotency (skip if today's topics already exist), then trying keyword-driven generation (Section 2.3) with a fallback to trending search (Section 2.4). Second, it assigns the generated common topics to all active users. Third, it generates personal topics — again with an idempotency check, followed by collecting per-user interest keywords, deduplicating against the common pool, pooling unique keywords across users, and fetching a topic for each keyword (Section 2.5).

These steps run sequentially. Personal topic generation failure does not affect the response — it is caught and logged, returning `personal_topics_generated: 0`.

### 2.3 Common Topics — Keyword-Driven Generation

The primary path generates common topics from the most popular user interest keywords across all users. The system retrieves the top 3 keywords by aggregate effective weight, then for each keyword, fetches the latest news via LLM with web search and stores the result as a common topic suggestion.

This approach produces topics that reflect the actual interests of the user base rather than generic trending news.

### 2.4 Common Topics — Trending Fallback (Cold Start)

When no user interest keywords exist (e.g., on a fresh deployment), the system falls back to a broader LLM-driven trending search. The LLM is prompted to discover 3 trending global topics across diverse categories (sports, technology, entertainment, science, business), using its web search tool to find current news. Each resulting topic includes a `source_keyword` assigned by the LLM (e.g., "NBA", "AI", "Oscars"), which is used for categorization and interest linking.

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

## 3. Key Files

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
