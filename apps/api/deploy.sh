#!/usr/bin/env bash
# Deploy Coto API to Google Cloud Run
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated: gcloud auth login
#   2. GCP project set: gcloud config set project <PROJECT_ID>
#   3. APIs enabled: gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
#   4. Artifact Registry repo created (see below)
#   5. Secrets created in Secret Manager (see below)
#
# Usage:
#   ./deploy.sh                  # Deploy with defaults
#   ./deploy.sh --tag v0.1.0     # Deploy with specific tag

set -euo pipefail

# --- Configuration ---
PROJECT_ID="${GCP_PROJECT_ID:-coto-prod}"
REGION="${CLOUD_RUN_REGION:-asia-northeast1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-coto-api}"
REPO_NAME="coto"
IMAGE_NAME="coto-api"

# Parse arguments
TAG="${TAG:-latest}"
while [[ $# -gt 0 ]]; do
  case $1 in
    --tag) TAG="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo "=== Coto API Deployment ==="
echo "Project:  ${PROJECT_ID}"
echo "Region:   ${REGION}"
echo "Image:    ${IMAGE}"
echo ""

# --- Step 1: Build and push Docker image ---
echo ">>> Building Docker image..."
docker build -t "${IMAGE}" -f apps/api/Dockerfile apps/api/

echo ">>> Pushing to Artifact Registry..."
docker push "${IMAGE}"

# --- Step 2: Run database migrations ---
echo ">>> Running database migrations..."
echo "  NOTE: Run migrations manually before first deploy:"
echo "    cd apps/api"
echo "    DATABASE_URL=<production-url> alembic upgrade head"
echo ""

# --- Step 3: Deploy to Cloud Run ---
echo ">>> Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5 \
  --timeout 300 \
  --concurrency 80 \
  --set-env-vars "ENVIRONMENT=production,GCS_BUCKET_NAME=coto-audio-prod,RATE_LIMIT_PER_MINUTE=30,CORS_ALLOWED_ORIGINS=[]" \
  --set-secrets "DATABASE_URL=database-url:latest,REDIS_URL=redis-url:latest,OPENAI_API_KEY=openai-api-key:latest" \
  --allow-unauthenticated \
  --execution-environment gen2 \
  --no-cpu-throttling

# --- Step 4: Verify ---
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format 'value(status.url)')
echo ""
echo "=== Deployment complete ==="
echo "Service URL: ${SERVICE_URL}"
echo ""
echo ">>> Verifying health check..."
curl -s "${SERVICE_URL}/health" | python3 -m json.tool
echo ""
