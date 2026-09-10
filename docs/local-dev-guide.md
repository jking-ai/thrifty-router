# Local Development Guide

This guide describes how to configure, run, and develop on **Thrifty Router** in a local environment.

---

## Prerequisites

- **Python:** 3.12 or newer
- **Google Cloud SDK (`gcloud`):** Installed and authenticated for Vertex AI access
- **Docker:** (Optional) for containerized testing
- **Git:** Version control

---

## Environment Setup

### 1. Clone & Setup Virtual Environment
```bash
cd /Users/king/dev/jrk-ai-labs/thrifty-router
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt -r eval/requirements.txt
```

### 2. Configure Environment Variables
Copy the example configuration:
```bash
cp backend/.env.example backend/.env
```

Adjust the values in `backend/.env`:
```env
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1
API_KEY=dev-secret-key-12345
DAILY_BUDGET_USD=10.0
DEFAULT_STRATEGY=cascade
DOCS_ENABLED=true
COMPLETE_LIMITS=120/minute,5000/day
CACHE_ENABLED=true
CACHE_SIMILARITY_THRESHOLD=0.92
FIRESTORE_DATABASE=(default)
LOG_LEVEL=DEBUG
```

### 3. Google Cloud Authentication
Ensure your local environment has Application Default Credentials (ADC) configured with access to Vertex AI:
```bash
gcloud auth application-default login
gcloud config set project your-gcp-project-id
```

---

## Running the Backend Locally

Start the development server with auto-reload enabled:
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

With `DOCS_ENABLED=true`, you can inspect interactive OpenAPI documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Verifying Endpoints

### 1. Health Check
```bash
curl http://localhost:8000/health
```

### 2. Available Tiers
```bash
curl -H "X-API-Key: dev-secret-key-12345" http://localhost:8000/v1/tiers
```

### 3. Test a Prompt Completion
```bash
curl -X POST http://localhost:8000/v1/complete \
  -H "X-API-Key: dev-secret-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the capital of Canada?",
    "strategy": "cascade"
  }'
```

---

## Common Issues & Troubleshooting

### Vertex AI Permission Denied (`403 Forbidden`)
- Verify that your active Google account or service account has the `roles/aiplatform.user` role assigned in your GCP project.
- Re-authenticate via `gcloud auth application-default login`.

### Budget Limit Exceeded (`402 Payment Required`)
- The in-memory ledger accumulates spend until reset or server restart.
- To reset or increase the budget for local testing, update `DAILY_BUDGET_USD` in `backend/.env` or restart the server.

### Rate Limit Errors (`429 Too Many Requests`)
- Slowapi uses in-memory IP keys. To temporarily disable rate limiting during heavy load tests, increase `COMPLETE_LIMITS` or test against unrate-limited endpoints like `/health`.
