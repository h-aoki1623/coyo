# Memory Feature — Production Deployment Guide

This guide covers the deployment procedure for the memory feature. It assumes the base deployment ([DEPLOY.md](./DEPLOY.md)) and topic suggestion deployment ([DEPLOY-TOPIC-SUGGESTION.md](./DEPLOY-TOPIC-SUGGESTION.md)) are already complete.

## Overview

The memory feature adds user personalization to conversations by:
1. **Extracting** user information (profile attributes, interests with summaries, conversation summaries) after each conversation ends
2. **Injecting** remembered information into system prompts when starting new conversations

### Architecture

```
[User ends conversation]
        │
        ▼
[Cloud Tasks queue] ──HTTP POST──▶ [/api/tasks/extract-memory]
        │                                      │
        │                                      ▼
        │                            [LLM: unified extraction]
        │                                      │
        │                              ┌───────┼───────┐
        │                              ▼       ▼       ▼
        │                     [user_interests] [user_profile_attributes] [conversation_summaries]
        │                              │
        │                     (every 5th conversation)
        │                              │
        │                     ┌────────┴────────┐
        │                     ▼                 ▼
        │           [Regenerate interest  [Regenerate profile
        │            summaries]            summary narrative]
        │
========│=========== (on next conversation start) ==========================
        │
[User starts conversation]
        │
        ▼
[Load memory context] ──▶ [Inject into system prompt]
        │
        ├── user_profile_summary (narrative)
        ├── user_profile_attributes (4 background items)
        ├── user_interests top 20 (with summaries)
        └── conversation_summaries last 5
```

### Breaking Changes

This deployment **replaces** Pipeline A (Interest Extraction) from the topic suggestion feature:

| Before | After |
|---|---|
| Endpoint: `/api/tasks/extract-interests` | Endpoint: `/api/tasks/extract-memory` |
| Queue: `interest-extraction` | Queue: `memory-extraction` |
| Extracts: interests only | Extracts: interests + profile attributes + conversation summary |

Pipeline B (Topic Generation) is **unchanged**.

## Prerequisites

- Base deployment completed ([DEPLOY.md](./DEPLOY.md))
- Topic suggestion deployment completed ([DEPLOY-TOPIC-SUGGESTION.md](./DEPLOY-TOPIC-SUGGESTION.md))
- `gcloud` CLI authenticated with project access
- Cloud Run service deployed and running

## Step 1: Pre-deployment — Drain Existing Queue

Before deploying, pause the existing `interest-extraction` queue to prevent in-flight tasks from targeting the old endpoint:

```bash
REGION="asia-northeast1"

# Pause the queue to stop dispatching new tasks
gcloud tasks queues pause interest-extraction --location=${REGION}

# Wait for in-flight tasks to complete
gcloud tasks queues describe interest-extraction --location=${REGION}
# Verify: stats.tasksCount == 0 or all tasks are completed

# List any remaining tasks
gcloud tasks list --queue=interest-extraction --location=${REGION}
```

## Step 2: Deploy via CI/CD

Merge the PR to `main`. The existing `deploy-api.yml` GitHub Actions workflow handles:

1. **Build** Docker image → push to Artifact Registry
2. **Migrate** — `alembic upgrade head` creates:
   - `user_profile_attributes` table
   - `user_profile_summaries` table
   - `conversation_summaries` table
   - New columns on `user_interests` (summary, summary_updated_at, needs_summary_update)
   - New column on `conversations` (memory_extracted)
   - Backfills `memory_extracted = true` for already-processed conversations
3. **Deploy** new Cloud Run revision with updated code

## Step 3: Replace Cloud Tasks Queue

After the new Cloud Run revision is live:

```bash
REGION="asia-northeast1"

# Delete the old queue
gcloud tasks queues delete interest-extraction --location=${REGION}

# Create the new queue
gcloud tasks queues create memory-extraction \
  --location=${REGION} \
  --max-dispatches-per-second=5 \
  --max-concurrent-dispatches=2 \
  --max-attempts=3 \
  --min-backoff=10s \
  --max-backoff=300s
```

## Step 4: Update GitHub Actions Variables

Update the `CLOUD_TASKS_QUEUE` variable in GitHub Settings > Secrets and variables > Actions > Variables:

| Variable | Old Value | New Value |
|---|---|---|
| `CLOUD_TASKS_QUEUE` | `interest-extraction` | `memory-extraction` |

Then redeploy (or update the Cloud Run service directly):

```bash
SERVICE_NAME="coyo-api"
REGION="asia-northeast1"

gcloud run services update ${SERVICE_NAME} \
  --region ${REGION} \
  --update-env-vars "CLOUD_TASKS_QUEUE=memory-extraction"
```

## Step 5: Verify

### 5.1 Health Check

```bash
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --region ${REGION} \
  --format 'value(status.url)')

curl "${SERVICE_URL}/health"
# Expected: {"status":"ok"}
```

### 5.2 Queue Status

```bash
gcloud tasks queues describe memory-extraction \
  --location=${REGION}
# Verify: state is RUNNING
```

### 5.3 End-to-End Test

1. Complete a conversation in the app
2. Check Cloud Tasks for the enqueued job:
   ```bash
   gcloud tasks list --queue=memory-extraction --location=${REGION}
   ```
3. Check Cloud Run logs for successful extraction:
   ```bash
   gcloud logging read \
     'resource.type="cloud_run_revision" AND jsonPayload.event="memory_extraction_complete"' \
     --limit=5 \
     --format="table(timestamp, jsonPayload.conversation_id)"
   ```
4. Verify database tables are populated:
   ```sql
   -- Conversation summary created
   SELECT * FROM conversation_summaries ORDER BY created_at DESC LIMIT 5;

   -- User interests have summaries (for new keywords)
   SELECT keyword, summary, needs_summary_update FROM user_interests
   WHERE summary IS NOT NULL LIMIT 10;

   -- Profile attributes extracted (if user shared background info)
   SELECT * FROM user_profile_attributes ORDER BY created_at DESC LIMIT 10;
   ```
5. Start a new conversation and verify the AI references prior context naturally

## Verification Checklist

- [ ] Old queue `interest-extraction` deleted
- [ ] New queue `memory-extraction` created and RUNNING
- [ ] `CLOUD_TASKS_QUEUE` GitHub variable updated to `memory-extraction`
- [ ] Cloud Run env var `CLOUD_TASKS_QUEUE` set to `memory-extraction`
- [ ] Database migration completed (3 new tables, 2 altered tables)
- [ ] Ending a conversation enqueues a task to `memory-extraction` queue
- [ ] Task completes: `conversation_summaries` row created
- [ ] Task completes: `user_interests` has summaries for new keywords
- [ ] Profile summary regenerated after 5th conversation
- [ ] New conversations include memory context in AI responses
- [ ] Pipeline B (Topic Generation) still works unchanged

## Rollback

If issues are found after deployment:

```bash
REGION="asia-northeast1"
SERVICE_NAME="coyo-api"

# 1. Rollback Cloud Run to previous revision
gcloud run revisions list --service ${SERVICE_NAME} --region ${REGION}
gcloud run services update-traffic ${SERVICE_NAME} \
  --region ${REGION} \
  --to-revisions PREVIOUS_REVISION=100

# 2. Recreate the old queue
gcloud tasks queues create interest-extraction \
  --location=${REGION} \
  --max-dispatches-per-second=5 \
  --max-concurrent-dispatches=2 \
  --max-attempts=3 \
  --min-backoff=10s \
  --max-backoff=300s

# 3. Update env var back
gcloud run services update ${SERVICE_NAME} \
  --region ${REGION} \
  --update-env-vars "CLOUD_TASKS_QUEUE=interest-extraction"

# 4. Update GitHub variable back
# CLOUD_TASKS_QUEUE = interest-extraction
```

Database rollback is **NOT needed** — all schema changes are additive (new tables and columns). The old code ignores them.

## Troubleshooting

### Tasks fail with 404

**Cause:** New endpoint `/api/tasks/extract-memory` not deployed yet.

Verify the Cloud Run revision has the updated code:
```bash
gcloud run services describe ${SERVICE_NAME} --region ${REGION} \
  --format='value(status.latestReadyRevisionName)'
```

### Tasks fail with 401

**Cause:** OIDC token verification failure. Same troubleshooting as [DEPLOY-TOPIC-SUGGESTION.md](./DEPLOY-TOPIC-SUGGESTION.md#pipeline-a-tasks-fail-with-401).

### No memory context in conversations

**Cause:** User needs at least one completed conversation with successful extraction before memory is available. Check:

```sql
SELECT memory_extracted FROM conversations
WHERE user_id = '<user-id>' AND status = 'completed'
ORDER BY ended_at DESC LIMIT 5;
```

## Cost Impact

| Resource | Monthly Cost (1,000 MAU) | Notes |
|---|---|---|
| Unified extraction (GPT-5 nano) | ~$0 | Absorbed by existing interest extraction cost |
| Profile summary regeneration | ~$0.50 | GPT-5 nano, every 5th conversation |
| Memory injection (input tokens) | ~$8.30 | +1,650 tokens/conversation × 20,000 conversations |
| **Total incremental** | **~$9/month** | +4.3% over base cost of ~$214/month |
