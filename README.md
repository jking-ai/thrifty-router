# Thrifty Router

**One-line summary:** Route each prompt to the cheapest Gemini model that can answer it, and prove it with numbers.

A Cloud Run gateway in front of three Gemini tiers (Flash-Lite, Flash, and Pro) that dynamically picks a tier per request using one of several strategies (`fixed`, `semantic`, `classifier`, `cascade`), accounts exact cost per request, caches semantically near-identical prompts in Firestore via vector search, and ships with an evaluation harness that benchmarks every strategy on a 300-prompt golden set with an LLM judge.

---

## Problem Statement

Generative AI applications face a sharp tension between model quality and API costs. Top-tier reasoning models like Gemini 3.1 Pro excel at complex architectural analysis and mathematical deduction, but costing $2.00 / $12.00 per million tokens makes using them universally prohibitive for high-volume consumer or enterprise workloads. Conversely, lightweight models like Gemini 3.1 Flash-Lite ($0.25 / $1.50 per million) deliver rapid latency and 90% cost savings on simple lookups, factual extraction, and basic formatting, but fail silently on nuanced reasoning.

Most teams either overpay by directing all traffic to the flagship tier or sacrifice user experience by locking their app to the cheapest model. **Thrifty Router** provides an intelligent, automated routing gateway that routes prompts to the cheapest capable model and backs every routing claim with empirical cost-versus-quality evaluation.

---

## Skills and Engineering Patterns Showcased

| Pattern | Description |
|---|---|
| **Model Cascade with Cost-Free Verification** | Starts at the cheapest tier (Flash-Lite), validates response non-emptiness, JSON schema, or self-reported confidence without an extra LLM judge call, escalating to higher tiers only on rejection |
| **Fast LLM Difficulty Classification** | Uses a rapid Flash-Lite call with enforced JSON schema to classify prompt complexity and route prior to completion |
| **Embedding-Based Semantic Routing** | Matches prompt vectors against pre-embedded domain route clusters using `gemini-embedding-001` (768-dim normalized cosine distance) |
| **Semantic Vector Caching** | Native Firestore vector search (`find_nearest`) with pre-filters on system instruction and schema hashes, 24-hour TTL, achieving >95% cache hit rates on repeat queries |
| **Micro-Dollar Ledger & Spend Guardrails** | Sub-cent per-attempt cost calculation (with thinking tokens billed at output rates), thread-safe in-process daily budget stops, and per-IP slowapi rate limits |
| **Automated Eval Benchmark & LLM Judge** | 300-prompt curated golden set across 8 domains evaluated with a temperature-0 Gemini 3.1 Pro judge, emitting quality retention and cost ratios |
| **Interactive Static Reporting** | Zero-build dark-mode interactive scatter plot with Chart.js hosted on Firebase Hosting |

---

## Tech Stack

| Layer | Component | Details |
|---|---|---|
| **Language & Framework** | Python 3.12+ / FastAPI 0.115+ | High-performance asynchronous REST API |
| **Compute** | Google Cloud Run | Scale-to-zero container deployment (`--max-instances 1`) |
| **Foundation Models** | Google Gen AI SDK (`google-genai`) | Gemini 3.1 Flash-Lite, Gemini 3 Flash, Gemini 3.1 Pro (Vertex AI backend) |
| **Embeddings & Vector Cache** | `gemini-embedding-001` + Firestore | 768-dimensional L2-normalized vector similarity search |
| **Rate Limiting & Budgets** | `slowapi` + In-process Ledger | Per-IP token bucket and UTC daily dollar hard-stop |
| **Evaluation & Reporting** | Custom Python Harness + Firebase Hosting | 300-item golden benchmark with static Chart.js report |

---

## Results & Benchmark Highlights

Benchmark results evaluated across 300 golden test items with temperature-0 Gemini 3.1 Pro judge:

| Strategy | Judge Score (1-5) | Quality Retention vs Pro | Cost / 1k Requests | Cost Ratio vs Pro | Latency (p50 / p95) | Tier Mix (L / S / P) |
|---|---|---|---|---|---|---|
| **fixed:lite** | 3.42 | 76% | $0.32 | 5% | 380 ms / 720 ms | 100% / 0% / 0% |
| **fixed:standard** | 4.15 | 92% | $0.95 | 16% | 520 ms / 1,100 ms | 0% / 100% / 0% |
| **fixed:pro** (Baseline) | 4.52 | 100% | $5.93 | 100% | 1,200 ms / 2,800 ms | 0% / 0% / 100% |
| **semantic** | 4.22 | 93% | $1.73 | 29% | 610 ms / 1,450 ms | 42% / 35% / 23% |
| **classifier** | 4.29 | 95% | $1.93 | 33% | 850 ms / 1,800 ms | 39% / 36% / 25% |
| **cascade** *(Recommended)* | **4.34** | **96%** | **$1.37** | **23%** | 890 ms / 2,900 ms | **71% / 19% / 10%** |

> [!TIP]
> **Key Finding**: The **Cascade** strategy captures **96% of Pro-level quality** while slashing API spend by **77%** (cost ratio of 0.23 vs Pro). In addition, the Firestore semantic cache achieves a **98% hit rate** on repeated semantically similar queries at $0.00 model cost.
>
> 📊 **Full Interactive Report:** [https://thrifty-router.web.app](https://thrifty-router.web.app)

---

## Quick Start

### 1. Authenticate with GCP
```bash
gcloud auth application-default login
```

### 2. Configure Environment
```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your GCP_PROJECT_ID and API_KEY
```

### 3. Install and Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Start FastAPI server on localhost:8000
cd backend && uvicorn app.main:app --reload --port 8000
```

### 4. Execute a Route Request
```bash
curl -X POST http://localhost:8000/api/v1/complete \
  -H "X-API-Key: dev" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the capital of France?",
    "strategy": "cascade"
  }'
```

---

## Security & Cost Guardrails

- **API Key Authentication**: Constant-time `secrets.compare_digest` validation on all operational endpoints.
- **Per-IP Rate Limiting**: Enforced with `slowapi` (`10/minute`, `200/day`) resolving true client IP from `X-Forwarded-For`.
- **In-Process Daily Budget Ceiling**: Configured via `DAILY_BUDGET_USD` (default $2.00). If cost hits the ceiling, subsequent calls are rejected with HTTP 429 `DAILY_BUDGET_EXCEEDED` *before* invoking any model.
- **Scale-to-Zero Deployment**: Deployed with `--max-instances 1` so in-memory budget and rate-limit buckets are strictly enforced without distributed coordination overhead.
- **No Secrets in Repo**: Secret Manager (`thrifty-router-api-key`) stores production credentials; `.gitignore` strictly blocks environment and credential files.

---

## Project Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Complete system architecture, request pipeline, strategy details, cache, and ledger |
| [API Contracts](docs/api-contracts.md) | Endpoint specifications, schemas, error envelopes, and reason strings |
| [Milestones](docs/milestones.md) | Development phases 1 through 6 deliverables |
| [Local Development Guide](docs/local-dev-guide.md) | Local environment setup, ADC authentication, and uvicorn server execution |
| [Local Testing Guide](docs/local-testing-guide.md) | Unit test execution, smoke tests, and running cheap evaluation slices |
| [Production Deployment](docs/production-deployment.md) | Cloud Run flags, Secret Manager, Firestore vector index, and Firebase Hosting |

---

## Links & Demo

- **Live Benchmark Report:** [https://thrifty-router.web.app](https://thrifty-router.web.app)
- **Portfolio Case Study:** [https://labs.jking.ai/projects/thrifty-router](https://labs.jking.ai/projects/thrifty-router)
