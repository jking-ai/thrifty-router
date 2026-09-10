# Production Deployment Guide

This document describes how to deploy **Thrifty Router** to Google Cloud Platform.

---

## Architecture Topology

```
                       User / Client
                             │
                             ▼
               Firebase Hosting Proxy (CDN)
                 thrifty-router.your-domain.com
                             │
                             ▼
                     Google Cloud Run
                 thrifty-router (service)
                     (us-central1)
                   /               \
                  ▼                 ▼
          Vertex AI Gemini       Firestore Native DB
           (Model Tiers)        (Vector Search Cache)
```

---

## Prerequisites

1. **GCP Project:** `YOUR_GCP_PROJECT_ID`
2. **Region:** `us-central1`
3. **gcloud CLI:** Installed and authenticated with permissions to manage Cloud Run, Firestore, and Artifact Registry.
4. **Firebase CLI:** (Optional) for hosting rewrite configurations (`firebase deploy --only hosting`).

### Required IAM Roles
Ensure the Cloud Run runtime service account has the following roles:
- `roles/aiplatform.user` -- Call Vertex AI Gemini models and embedding APIs.
- `roles/datastore.user` -- Read and write to Firestore for semantic caching.
- `roles/logging.logWriter` -- Write structured JSON logs to Cloud Logging.

---

## Firestore Vector Search Setup

To enable vector search on the `cache_entries` collection:
1. Ensure the Firestore database is in **Native mode**.
2. Create a vector index on the `embedding` field:

```bash
gcloud firestore indexes composite create \
  --project=YOUR_GCP_PROJECT_ID \
  --collection-group=cache_entries \
  --query-scope=COLLECTION \
  --field-config vector-config='{"dimension":"768","flat": "{}"}',field-path=embedding
```

---

## Deployment Script (`scripts/deploy.sh`)

The repository includes an automated deployment script in `scripts/deploy.sh`.

### 1. Deploy Cloud Run Backend
```bash
# Deploys backend container to Cloud Run
bash scripts/deploy.sh backend
```

What this does:
1. Builds the container image using Google Cloud Build.
2. Deploys the image to Cloud Run service `thrifty-router` in `us-central1`.
3. Injects production environment variables (`GCP_PROJECT_ID`, `DAILY_BUDGET_USD`, `CACHE_ENABLED`, etc.).
4. Configures minimum instances (0 for scale-to-zero) and concurrency.

### 2. Deploy Firebase Hosting Proxy
```bash
# Deploys hosting rewrites to route thrifty-router.jking.ai -> Cloud Run
bash scripts/deploy.sh frontend
```

### 3. Deploy All
```bash
bash scripts/deploy.sh all
```

---

## Post-Deployment Smoke Verification

Verify that the live endpoint is functioning correctly using the automated smoke test script:

```bash
bash backend/scripts/smoke.sh https://thrifty-router-xxxx-uc.a.run.app <your-api-key>
```

The smoke script tests:
1. `GET /health` returns HTTP 200 with healthy status.
2. `GET /v1/tiers` lists `lite`, `standard`, and `pro`.
3. `POST /v1/complete` (fixed strategy) generates valid output.
4. `POST /v1/complete` (cascade strategy) executes and verifies output.
5. Response headers include `X-Thrifty-Tier`, `X-Thrifty-Cost-Usd`, and `X-Thrifty-Latency-Ms`.
6. Budget and rate limiting behaviors are actively enforced.

---

## Monitoring & Telemetry

- **Cloud Logging:** The application emits structured JSON logs including prompt hashes, selected tier, cost in USD, and latency.
- **Spend Ceiling:** Process-level ledger tracks total spend against `DAILY_BUDGET_USD`.
- **GCP Billing Budget Alerts:** Configured at the GCP project level to notify administrators if spending approaches billing limits.
