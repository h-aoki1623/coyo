# Topic Suggestion — Production Deployment Guide

This guide covers the infrastructure setup required to run the topic suggestion feature in production. It assumes the base deployment from [DEPLOY.md](./DEPLOY.md) is already complete.

## Overview

The topic suggestion feature consists of two pipelines:

| Pipeline | Trigger | What it does |
|---|---|---|
| **Pipeline A** (Memory Extraction) | Automatic — after each conversation ends | Extracts user interests, profile attributes, and conversation summaries via LLM. See [DEPLOY-MEMORY.md](./DEPLOY-MEMORY.md) for details |
| **Pipeline B** (Topic Generation) | Scheduled — daily at 06:00 JST | Generates trending + personalized topic suggestions for all users |

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
        │                                      ▼
        │                            [Store in user_interests +
        │                             user_attributes +
        │                             conversation_summaries]
        │
========│=========== (daily at 06:00 JST) ==========================
        │
[Cloud Scheduler] ──HTTP POST──▶ [/api/topics/generate]
                                           │
                                    ┌──────┴──────┐
                                    ▼              ▼
                             [Common Topics]  [Personal Topics]
                             (web search)     (based on interests)
                                    │              │
                                    ▼              ▼
                             [Store in topic_suggestions]
                                    │
                                    ▼
                             [Assign to users]
```

## Prerequisites

- Base deployment completed ([DEPLOY.md](./DEPLOY.md))
- `gcloud` CLI authenticated with project access
- Cloud Run service deployed and running

## Step 1: Enable GCP APIs

```bash
gcloud services enable \
  cloudtasks.googleapis.com \
  cloudscheduler.googleapis.com
```

## Step 2: Create Cloud Tasks Queue (Pipeline A)

> **Note:** If deploying the memory feature, use queue name `memory-extraction` instead of `interest-extraction`. See [DEPLOY-MEMORY.md](./DEPLOY-MEMORY.md) for details.

```bash
gcloud tasks queues create memory-extraction \
  --location=asia-northeast1 \
  --max-dispatches-per-second=5 \
  --max-concurrent-dispatches=2 \
  --max-attempts=3 \
  --min-backoff=10s \
  --max-backoff=300s
```

| Parameter | Value | Rationale |
|---|---|---|
| `max-dispatches-per-second` | 5 | Avoid overwhelming the LLM API |
| `max-concurrent-dispatches` | 2 | Limit parallel extraction jobs |
| `max-attempts` | 3 | Retry transient failures (LLM timeout, DB connection) |
| `min-backoff` / `max-backoff` | 10s / 300s | Exponential backoff between retries |

## Step 3: Create Secrets

```bash
# Generate a random cron secret
CRON_SECRET=$(openssl rand -hex 32)
echo -n "${CRON_SECRET}" | gcloud secrets create cron-secret --data-file=-

# Grant Cloud Run access
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get project) --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding cron-secret \
  --member="serviceAccount:${SA}" \
  --role="roles/secretmanager.secretAccessor"
```

## Step 4: Grant IAM Permissions

The Cloud Run default service account needs permission to create Cloud Tasks:

```bash
PROJECT_ID=$(gcloud config get project)
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Cloud Tasks: enqueue tasks
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA}" \
  --role="roles/cloudtasks.enqueuer"

# Cloud Tasks: create OIDC tokens for task callbacks
gcloud iam service-accounts add-iam-policy-binding ${SA} \
  --member="serviceAccount:${SA}" \
  --role="roles/iam.serviceAccountUser"
```

## Step 5: Update Cloud Run Environment Variables

Get the Cloud Run service URL:

```bash
SERVICE_NAME="coyo-api"  # Your Cloud Run service name
REGION="asia-northeast1"

SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --region ${REGION} \
  --format 'value(status.url)')

echo "Service URL: ${SERVICE_URL}"
```

Update the service with Cloud Tasks and cron settings:

Get the default Compute Engine service account email:

```bash
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "Service Account: ${SA_EMAIL}"
```

Update the service with Cloud Tasks and cron settings:

```bash
gcloud run services update ${SERVICE_NAME} \
  --region ${REGION} \
  --update-env-vars "\
CLOUD_TASKS_PROJECT=$(gcloud config get project),\
CLOUD_TASKS_LOCATION=${REGION},\
CLOUD_TASKS_QUEUE=memory-extraction,\
CLOUD_RUN_SERVICE_URL=${SERVICE_URL},\
CLOUD_TASKS_SERVICE_ACCOUNT=${SA_EMAIL}" \
  --update-secrets "CRON_SECRET=cron-secret:latest"
```

### Environment Variables Summary

| Variable | Source | Purpose |
|---|---|---|
| `CLOUD_TASKS_PROJECT` | GCP project ID | Cloud Tasks API project |
| `CLOUD_TASKS_LOCATION` | e.g. `asia-northeast1` | Cloud Tasks queue region |
| `CLOUD_TASKS_QUEUE` | `memory-extraction` | Queue name |
| `CLOUD_RUN_SERVICE_URL` | Cloud Run service URL | Task callback URL + OIDC audience |
| `CLOUD_TASKS_SERVICE_ACCOUNT` | SA email | Service account for OIDC token in Cloud Tasks |
| `CRON_SECRET` | Secret Manager | HMAC secret for `/api/topics/generate` |

> **Note:** All 5 `CLOUD_TASKS_*` variables must be set together. The app validates this at startup and will fail if only some are configured.

## Step 6: Create Cloud Scheduler Job (Pipeline B)

```bash
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --region ${REGION} \
  --format 'value(status.url)')

CRON_SECRET=$(gcloud secrets versions access latest --secret=cron-secret)

gcloud scheduler jobs create http coyo-topic-generation \
  --location=${REGION} \
  --schedule="0 6 * * *" \
  --time-zone="Asia/Tokyo" \
  --uri="${SERVICE_URL}/api/topics/generate" \
  --http-method=POST \
  --headers="X-Cron-Secret=${CRON_SECRET}" \
  --attempt-deadline=300s \
  --max-retry-attempts=2 \
  --min-backoff=30s
```

| Parameter | Value | Rationale |
|---|---|---|
| `schedule` | `0 6 * * *` | Daily at 06:00 JST (before users start their day) |
| `time-zone` | `Asia/Tokyo` | Target user timezone |
| `attempt-deadline` | 300s | Topic generation involves multiple LLM + web search calls |
| `max-retry-count` | 2 | Retry on transient failures |

## Step 7: Verify

### 7.1 Pipeline A (Interest Extraction)

Pipeline A is triggered automatically when a user ends a conversation. Verify by checking Cloud Tasks:

```bash
# Check queue status
gcloud tasks queues describe memory-extraction \
  --location=asia-northeast1

# After a user ends a conversation, check for tasks
gcloud tasks list \
  --queue=memory-extraction \
  --location=asia-northeast1
```

Check Cloud Run logs for successful extraction:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND jsonPayload.event="memory_extraction_complete"' \
  --limit=5 \
  --format="table(timestamp, jsonPayload.conversation_id, jsonPayload.keywords_count)"
```

### 7.2 Pipeline B (Topic Generation)

Trigger a manual run to verify:

```bash
# Manual trigger
gcloud scheduler jobs run coyo-topic-generation \
  --location=asia-northeast1

# Check the result in logs
gcloud logging read \
  'resource.type="cloud_run_revision" AND httpRequest.requestUrl="/api/topics/generate"' \
  --limit=1 \
  --format="table(timestamp, httpRequest.status, jsonPayload)"
```

Or test directly:

```bash
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --region ${REGION} \
  --format 'value(status.url)')
CRON_SECRET=$(gcloud secrets versions access latest --secret=cron-secret)

curl -X POST "${SERVICE_URL}/api/topics/generate" \
  -H "X-Cron-Secret: ${CRON_SECRET}"
# Expected: {"topics_generated": 3, "users_assigned": N, "personal_topics_generated": N}
```

### 7.3 End-to-End

1. Complete a conversation in the app → interests are extracted (check `user_interests` table)
2. Wait for or manually trigger topic generation → topics appear in `topic_suggestions`
3. Open the app → personalized + trending topics displayed on the topic selection screen

## Verification Checklist

- [ ] Cloud Tasks queue `memory-extraction` created
- [ ] Cloud Scheduler job `coyo-topic-generation` created
- [ ] `CRON_SECRET` stored in Secret Manager and attached to Cloud Run
- [ ] 4 `CLOUD_TASKS_*` env vars set on Cloud Run
- [ ] IAM: Cloud Run SA has `cloudtasks.enqueuer` role
- [ ] IAM: Cloud Run SA has `iam.serviceAccountUser` on itself
- [ ] Pipeline A: ending a conversation enqueues a Cloud Task
- [ ] Pipeline A: task completes → interests visible in DB
- [ ] Pipeline B: manual trigger returns topic counts
- [ ] Pipeline B: scheduler cron fires at 06:00 JST
- [ ] Mobile app: topic suggestions screen shows generated topics

## Troubleshooting

### Pipeline A: Tasks fail with 401

**Cause:** OIDC token verification failure.

```bash
# Check that CLOUD_RUN_SERVICE_URL matches the actual service URL
gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)'
```

The OIDC audience must match `CLOUD_RUN_SERVICE_URL` exactly.

### Pipeline A: Tasks fail with 500

**Cause:** Interest extraction error (LLM timeout, DB issue).

Cloud Tasks will retry up to `max-attempts` times with exponential backoff. The extraction is idempotent — retries are safe.

```bash
# Check error logs
gcloud logging read \
  'resource.type="cloud_run_revision" AND severity>=ERROR AND jsonPayload.event="memory_extraction_failed"' \
  --limit=10
```

### Pipeline B: Scheduler returns 403

**Cause:** `CRON_SECRET` mismatch between Cloud Scheduler and Cloud Run.

```bash
# Verify the secret is correctly attached
gcloud run services describe ${SERVICE_NAME} --region ${REGION} \
  --format='yaml(spec.template.spec.containers[0].env)'

# Re-read from Secret Manager and update scheduler if needed
CRON_SECRET=$(gcloud secrets versions access latest --secret=cron-secret)
gcloud scheduler jobs update http coyo-topic-generation \
  --location=${REGION} \
  --headers="X-Cron-Secret=${CRON_SECRET}"
```

### Pipeline B: No personal topics generated

**Cause:** No users have news-relevant interests yet.

Personal topics require:
1. Users have completed conversations
2. Interest extraction has run (Pipeline A)
3. At least one extracted interest has `is_news_relevant = true`

Check user interests:

```sql
SELECT keyword, keyword_type, is_news_relevant, total_mentions
FROM user_interests
WHERE is_news_relevant = true
ORDER BY total_mentions DESC
LIMIT 20;
```

## Cost Estimates

| Resource | Monthly Cost (1,000 MAU) | Notes |
|---|---|---|
| Cloud Tasks | ~$0 | Free tier: 1M tasks/month |
| Cloud Scheduler | ~$0 | Free tier: 3 jobs/month |
| OpenAI (interest extraction) | ~$2 | gpt-5.4-nano, ~1,000 calls × ~500 tokens |
| OpenAI (topic generation) | ~$15 | gpt-5.4-nano + web search, 30 calls/day × 30 days |
| **Total (incremental)** | **~$17/month** | On top of base deployment costs |
