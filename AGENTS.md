# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

Thrifty Router (`thrifty-router`) is an open-source, cost-optimizing LLM proxy for Google Cloud Vertex AI (Gemini 2.5 / 1.5). It dynamically routes incoming prompts to the cheapest tier (`lite`, `standard`, `pro`) capable of handling them with high fidelity, while enforcing spend ceilings, circuit breakers, and sub-10ms semantic caching.

- **Backend:** FastAPI 0.115+ (Python 3.12+) on Google Cloud Run
- **Evaluation / Harness:** Automated 300-sample golden evaluation runner with Gemini Pro LLM-as-a-judge scoring
- **Semantic Caching:** In-memory fake store (local dev / tests) and Firestore Vector Search (production)
- **Embedding:** `gemini-embedding-001` (768-dim, L2-normalized) via Google Gen AI SDK
- **GCP Hosting:** Google Cloud Run, region `us-central1`

## Build & Run Commands

### Virtual Environment Setup
```bash
# Create and activate virtual environment at repository root
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -r eval/requirements.txt
```

### Backend (`backend/` directory)
```bash
cd backend
# Local dev server on :8000
uvicorn app.main:app --reload --port 8000

# Run full backend test suite
pytest -v tests/

# Build container
docker build -t thrifty-router:latest .

# Run container locally
docker run -p 8080:8080 --env-file .env thrifty-router:latest
```

### Evaluation Harness (`eval/` directory)
```bash
cd eval
# Run evaluation test suite
pytest -v tests/

# Validate golden dataset schema & distribution
python3 scripts/validate_golden.py golden/golden_set.jsonl

# Run evaluation suite across strategies
python3 run_eval.py --golden golden/golden_set.jsonl --strategies baseline lite_only semantic classifier cascade --sample-size 50

# Run LLM-as-a-judge grading
python3 judge.py --eval-dir results/latest

# Generate HTML & JSON benchmark reports
python3 report.py --eval-dir results/latest --output-dir ../report
```

### Deployment & Smoke Testing
```bash
# Deploy Cloud Run service and Firebase Hosting proxy
bash scripts/deploy.sh all

# Run live smoke verification against deployed endpoint
bash backend/scripts/smoke.sh https://thrifty-router.jking.ai my-api-key
```

## Architecture & Request Flow

```
Client (X-API-Key)
       │
       ▼
Cloud Run (FastAPI + Slowapi Rate Limiter)
       │
       ├─► CostLedger (Check DAILY_BUDGET_USD ceiling)
       │
       ├─► SemanticCache (exact sha256 + cosine >= 0.92) ──► Cache Hit (cost: $0)
       │
       ├─► Route Strategy Orchestration:
       │     ├─ fixed: Static tier configuration
       │     ├─ semantic: gemini-embedding-001 cosine similarity against tier anchors
       │     ├─ classifier: Zero-temperature few-shot prompt to Gemini 2.5 Flash
       │     └─ cascade: Attempt lite -> verify -> escalate to standard -> verify -> pro
       │
       ├─► TierClient (google-genai SDK Vertex AI call)
       │
       └─► Record Usage & Return Cost Headers (X-Thrifty-Tier, X-Thrifty-Cost-Usd, etc.)
```

### Key Design Decisions
- **Vertex AI Client:** Uses official `google-genai` SDK with `vertexai=True`, avoiding deprecated libraries.
- **Micro-Dollar Ledger:** Token costs calculated via official million-token rates, treating thinking tokens as output tokens, rounded to 6 decimal places.
- **Thread-Safe Spend Guardrail:** Process-level in-memory budget tracker (`threading.Lock`) fails closed with `402 Payment Required` when spend meets or exceeds `DAILY_BUDGET_USD`.
- **Confidence Escapes in Cascade:** Cascade verifier combines structural checks (finish reason, non-empty, JSON schema) with an optional self-assessed confidence tag (`CONFIDENCE: <0-100>`). If confidence falls below 70, it escalates.
- **Fail-Safe Caching:** Cache errors log warnings and proceed to live routing without failing client queries.

## Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `GCP_PROJECT_ID` | String | `""` | Google Cloud project ID for Vertex AI |
| `GCP_REGION` | String | `us-central1` | Google Cloud region |
| `API_KEY` | String | `""` | Master API key required in `X-API-Key` or `Bearer` header |
| `DAILY_BUDGET_USD` | Float | `10.0` | Daily spend ceiling; 402 returned if exceeded |
| `DEFAULT_STRATEGY` | Enum | `cascade` | Default routing strategy (`fixed`, `semantic`, `classifier`, `cascade`) |
| `COMPLETE_LIMITS` | String | `60/minute,1000/day` | Slowapi rate limit per IP for `/v1/complete` |
| `CACHE_ENABLED` | Boolean | `true` | Enable semantic and exact response caching |
| `CACHE_SIMILARITY_THRESHOLD`| Float | `0.92` | Minimum cosine similarity for vector cache hit |
| `FIRESTORE_DATABASE` | String | `(default)` | Firestore database for production vector cache |
| `LOG_LEVEL` | String | `INFO` | Application log verbosity |

## Security Posture

- **Zero Secret Commits:** Strict `.gitignore` protects all `.env` files, credentials, local databases, and temporary execution traces.
- **Constant-Time Auth:** Header validation uses `secrets.compare_digest` to mitigate timing side-channel attacks.
- **Production Guardrails:** Interactive OpenAPI docs (`/docs`, `/redoc`) disabled in production.
- **Rate-Limiting Defense:** Forwarded headers (`X-Forwarded-For`) inspected to enforce per-client rate limits.

## Project Documentation

Detailed specifications and architectural guides live in `docs/`:
- [`docs/README.md`](docs/README.md) -- Documentation index and quick links
- [`docs/architecture.md`](docs/architecture.md) -- Detailed system architecture, tiers, and strategy mechanics
- [`docs/api-contracts.md`](docs/api-contracts.md) -- Full OpenAPI specifications and request/response payloads
- [`docs/milestones.md`](docs/milestones.md) -- Phased milestones and delivery verification
- [`docs/local-dev-guide.md`](docs/local-dev-guide.md) -- Local environment bootstrap and debugging tips
- [`docs/local-testing-guide.md`](docs/local-testing-guide.md) -- Comprehensive testing guide (pytest, mocks, integration)
- [`docs/production-deployment.md`](docs/production-deployment.md) -- GCP Cloud Run, Firestore, and DNS setup
