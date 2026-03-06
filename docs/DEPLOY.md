# Production Deployment Guide

This guide covers deploying Coyo to production: API on Cloud Run, mobile apps via EAS Build.

## Prerequisites

- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- [Docker](https://docs.docker.com/get-docker/)
- [Expo CLI](https://docs.expo.dev/get-started/installation/) (`npx expo`)
- [EAS CLI](https://docs.expo.dev/eas/) (`npm install -g eas-cli`)

## Phase 1: External Services Setup

### 1.1 GCP Project

```bash
# Create project
gcloud projects create coyo-app-prod --name="Coyo Production"
gcloud config set project coyo-app-prod

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create coyo \
  --repository-format=docker \
  --location=asia-northeast1

# Configure Docker auth
gcloud auth configure-docker asia-northeast1-docker.pkg.dev
```

### 1.2 Supabase (PostgreSQL)

1. Create a new project at [supabase.com](https://supabase.com)
2. Choose a region close to Cloud Run (e.g., `ap-northeast-1` for Tokyo)
3. Copy the connection string from **Settings > Database > Connection string**
   - Use **Transaction mode** (port 6543) for serverless compatibility
   - Format: `postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?ssl=require`

### 1.3 Upstash Redis

1. Create a Redis database at [upstash.com](https://upstash.com)
2. Choose a region close to Cloud Run
3. Copy the Redis URL from the database details
   - Format: `rediss://default:<password>@<endpoint>.upstash.io:6379`

### 1.4 GCS Bucket (Audio Buffering)

```bash
# Create bucket with auto-delete lifecycle
gcloud storage buckets create gs://coyo-audio-prod \
  --location=asia-northeast1 \
  --uniform-bucket-level-access

# Set lifecycle rule: delete objects after 1 day (minimum GCS granularity)
# NOTE: GCS lifecycle operates in days, not hours. The app uses signed URLs
# with 1-hour TTL for access control. Objects are cleaned up within 24 hours.
cat > /tmp/lifecycle.json << 'EOF'
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 1}
    }
  ]
}
EOF
gcloud storage buckets update gs://coyo-audio-prod --lifecycle-file=/tmp/lifecycle.json
```

### 1.5 OpenAI API Key

1. Create a production API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Set usage limits appropriate for your budget

### 1.6 Sentry (Optional)

1. Create a project at [sentry.io](https://sentry.io)
2. Copy the DSN for later use

### 1.7 Store Secrets in GCP Secret Manager

```bash
# Create secrets (you'll be prompted to enter each value)
echo -n "postgresql+asyncpg://..." | gcloud secrets create database-url --data-file=-
echo -n "rediss://..." | gcloud secrets create redis-url --data-file=-
echo -n "sk-..." | gcloud secrets create openai-api-key --data-file=-

# Grant Cloud Run access to secrets
PROJECT_NUMBER=$(gcloud projects describe coyo-app-prod --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding database-url \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding redis-url \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## Phase 2: Backend Deployment (Cloud Run)

### 2.1 Run Database Migrations

```bash
cd apps/api

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Run migrations against production database
# NOTE: Use single quotes to avoid shell interpretation of special characters in password
DATABASE_URL='postgresql+asyncpg://<user>:<password>@<host>:6543/<database>?ssl=require' \
REDIS_URL='redis://localhost:6379' \
OPENAI_API_KEY='dummy' \
alembic upgrade head

# Deactivate when done
deactivate
```

### 2.2 Build and Deploy

**Option A: Manual deploy script**

```bash
# From repo root
./apps/api/deploy.sh
```

**Option B: gcloud CLI**

```bash
# Build image
IMAGE="asia-northeast1-docker.pkg.dev/coyo-app-prod/coyo/coyo-api:v0.1.0"
docker build --platform linux/amd64 -t "${IMAGE}" -f apps/api/Dockerfile apps/api/
docker push "${IMAGE}"

# Deploy
gcloud run deploy coyo-api \
  --image "${IMAGE}" \
  --region asia-northeast1 \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5 \
  --timeout 300 \
  --concurrency 80 \
  --execution-environment gen2 \
  --no-cpu-throttling \
  --allow-unauthenticated \
  --set-env-vars "ENVIRONMENT=production,GCS_BUCKET_NAME=coyo-audio-prod,RATE_LIMIT_PER_MINUTE=30" \
  --set-secrets "DATABASE_URL=database-url:latest,REDIS_URL=redis-url:latest,OPENAI_API_KEY=openai-api-key:latest"
```

### 2.3 Verify

```bash
# Get service URL
URL=$(gcloud run services describe coyo-api --region asia-northeast1 --format 'value(status.url)')

# Health check
curl "${URL}/health"
# Expected: {"status":"ok"}
```

### 2.4 Update CORS (After Getting Service URL)

Update the `CORS_ALLOWED_ORIGINS` environment variable if needed:

```bash
gcloud run services update coyo-api \
  --region asia-northeast1 \
  --set-env-vars "CORS_ALLOWED_ORIGINS=[\"${URL}\"]"
```

## Phase 3: Mobile App Deployment (EAS Build)

### 3.1 EAS Project Setup

```bash
cd apps/mobile

# Login to Expo
npx eas login

# Initialize EAS project (links to Expo account)
npx eas init

# Update app.config.ts with the EAS project ID from the output above
```

### 3.2 Update eas.json

Edit `apps/mobile/eas.json` and replace placeholder values:
- `API_BASE_URL` in the `production` profile → your Cloud Run service URL
- Apple/Google credentials in `submit.production`

### 3.3 Build for iOS

```bash
cd apps/mobile

# Preview build (internal testing via TestFlight)
npx eas build --platform ios --profile preview

# Production build (App Store submission)
npx eas build --platform ios --profile production
```

### 3.4 Build for Android

```bash
cd apps/mobile

# Preview build (internal testing APK)
npx eas build --platform android --profile preview

# Production build (Google Play submission)
npx eas build --platform android --profile production
```

### 3.5 Submit to Stores

```bash
# Submit to App Store (requires Apple Developer account)
npx eas submit --platform ios --profile production

# Submit to Google Play (requires Google Play Console + service account)
npx eas submit --platform android --profile production
```

## Phase 4: CI/CD Setup (GitHub Actions)

### 4.1 Workload Identity Federation (WIF)

Set up WIF to allow GitHub Actions to deploy to Cloud Run without service account keys:

```bash
PROJECT_ID="coyo-app-prod"
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')

# Create Workload Identity Pool
gcloud iam workload-identity-pools create "github" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --display-name="GitHub Actions"

# Create Workload Identity Provider
gcloud iam workload-identity-pools providers create-oidc "github-actions" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github" \
  --display-name="GitHub Actions" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='h-aoki1623/coyo'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Create service account for deployments
gcloud iam service-accounts create github-actions-deploy \
  --display-name="GitHub Actions Deploy"

# Grant required roles
SA_EMAIL="github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
for ROLE in run.admin artifactregistry.writer secretmanager.secretAccessor iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/${ROLE}"
done

# Allow GitHub to impersonate the service account
REPO="h-aoki1623/coyo"  # Replace with your repo
gcloud iam service-accounts add-iam-policy-binding ${SA_EMAIL} \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/attribute.repository/${REPO}"
```

### 4.2 GitHub Repository Secrets

Add these secrets in GitHub Settings > Secrets and variables > Actions:

| Secret | Value |
|--------|-------|
| `WIF_PROVIDER` | `projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github/providers/github-actions` |
| `WIF_SERVICE_ACCOUNT` | `github-actions-deploy@coyo-app-prod.iam.gserviceaccount.com` |
| `DATABASE_URL` | Production database URL (for migrations) |

Add these variables in GitHub Settings > Secrets and variables > Actions > Variables:

| Variable | Value |
|----------|-------|
| `GCP_PROJECT_ID` | `coyo-app-prod` |
| `CLOUD_RUN_REGION` | `asia-northeast1` |
| `CLOUD_RUN_SERVICE` | `coyo-api` |
| `GCS_BUCKET_NAME` | `coyo-audio-prod` |

## Verification Checklist

### Backend
- [ ] `/health` returns `{"status":"ok"}`
- [ ] Database migrations completed successfully
- [ ] Can create a conversation via API
- [ ] SSE streaming works (test with `curl`)
- [ ] OpenAI API calls succeed (STT, LLM, TTS)
- [ ] Redis connection works (rate limiting active)

### Mobile
- [ ] App connects to production API
- [ ] Audio recording works
- [ ] Conversation flow completes end-to-end
- [ ] History screen loads correctly
- [ ] Offline screen appears when disconnected

### Monitoring
- [ ] Cloud Run logs visible in GCP Console
- [ ] Sentry receiving error reports (if configured)
- [ ] Cloud Run metrics dashboard accessible

## Rollback

```bash
# List revisions
gcloud run revisions list --service coyo-api --region asia-northeast1

# Rollback to previous revision
gcloud run services update-traffic coyo-api \
  --region asia-northeast1 \
  --to-revisions PREVIOUS_REVISION=100
```

## Cost Monitoring

Set up a budget alert in GCP:

```bash
# Set a monthly budget of $50 (adjust as needed)
# Go to: GCP Console > Billing > Budgets & alerts > Create budget
```

Estimated monthly costs at MAU 1,000:
- Cloud Run: ~$5
- Supabase Pro: $25
- Upstash Redis: $0 (free tier)
- OpenAI APIs: ~$183
- GCS: ~$0.50
- **Total: ~$214/month**
