#!/bin/bash
# AEGIS GCP Infrastructure Provisioning & Deployment Script
# Configured for the Gemini Enterprise Agent Platform.

# Exit immediately if a command exits with a non-zero status
set -e

PROJECT_ID="gen-lang-client-0799848863"
REGION="us-central1"
SERVICE_ACCOUNT_NAME="aegis-backend-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== 1. Setting Active GCP Project ==="
gcloud config set project "${PROJECT_ID}"

echo "=== 2. Enabling Required GCP APIs ==="
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  bigquery.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com

echo "=== 3. Creating Service Account ==="
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
    --description="Service account for AEGIS Gateway & Agent Service" \
    --display-name="AEGIS Backend Service Account"
else
  echo "Service account ${SERVICE_ACCOUNT_EMAIL} already exists."
fi

echo "=== 4. Binding Least-Privilege IAM Roles ==="
# BigQuery roles (Read-only data access and query runner)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/bigquery.jobUser"

# Firestore roles (Read/write access to session logs/briefs)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/datastore.user"

# Gemini / Vertex AI roles (Call live Gemini models on the platform)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/aiplatform.user"

echo "=== 5. Deploying FastAPI Backend Gateway to Cloud Run ==="
# Deploying directly from local directory using Cloud Build
gcloud run deploy aegis-backend \
  --source . \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --set-env-vars DEPLOYMENT_ENV=production,GOOGLE_CLOUD_PROJECT="${PROJECT_ID}" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --min-instances=1

echo "=== 6. Deploying React Frontend to Firebase Hosting ==="
# Move into the frontend directory, install packages, and build assets
cd frontend
npm install
npm run build
cd ..

# Deploying web assets to Firebase Hosting
firebase deploy --only hosting --project "${PROJECT_ID}"

echo "=== Deployment Completed Successfully ==="
