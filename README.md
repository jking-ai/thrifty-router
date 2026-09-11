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
| **Automated Eval Benchmark & LLM Judge** | 300 hand-written, self-contained golden prompts across 8 domains evaluated with a temperature-0 Gemini 3.1 Pro judge, emitting quality retention and cost ratios |
| **Interactive Static Reporting** | Zero-build dark-mode interactive scatter plot with Chart.js hosted on Firebase Hosting, plus a browsable [golden set explorer](https://thrifty-router.jking.ai/golden) with category, tier, and text filters |

---

## Tech Stack

| Layer | Component | Details |
|---|---|---|
| **Language & Framework** | Python 3.12+ / FastAPI 0.115+ | High-performance asynchronous REST API |
| **Compute** | Google Cloud Run | Scale-to-zero container deployment (`--max-instances 1`) |
| **Foundation Models** | Google Gen AI SDK (`google-genai`) | Gemini 3.1 Flash-Lite, Gemini 3 Flash, Gemini 3.1 Pro (Vertex AI backend) |
| **Embeddings & Vector Cache** | `gemini-embedding-001` + Firestore | 768-dimensional L2-normalized vector similarity search |
| **Rate Limiting & Budgets** | `slowapi` + In-process Ledger | Per-IP token bucket and UTC daily dollar hard-stop |
| **Evaluation & Reporting** | Custom Python Harness + Firebase Hosting | 300-item hand-written golden benchmark with static Chart.js report |

---

## Results & Benchmark Highlights

Benchmark results evaluated across 300 golden test items with temperature-0 Gemini 3.1 Pro judge:

| Strategy | Judge Score (1-5) | Quality Retention vs Pro | Cost / 1k Requests | Cost Ratio vs Pro | Latency (p50 / p95) | Tier Mix (L / S / P) |
|---|---|---|---|---|---|---|
| **fixed:lite** | 4.82 | 98% | $0.50 | 3% | 2,551 ms / 5,455 ms | 100% / 0% / 0% |
| **fixed:standard** | 4.90 | 100% | $2.78 | 16% | 6,943 ms / 18,030 ms | 0% / 100% / 0% |
| **fixed:pro** (baseline) | 4.90 | 100% | $16.98 | 100% | 10,656 ms / 28,916 ms | 0% / 0% / 100% |
| **semantic** | 4.88 | 100% | $6.61 | 39% | 9,863 ms / 24,060 ms | 29% / 47% / 24% |
| **classifier** | 4.84 | 99% | $8.30 | 49% | 6,399 ms / 28,170 ms | 39% / 42% / 19% |
| **cascade** | 4.82 | 98% | $0.53 | 3% | 2,664 ms / 5,144 ms | 100% / 0% / 0% |

Run of 2026-09-11 (`eval/results/latest/summary.json`). Latency was measured from a laptop against Vertex AI, not from Cloud Run.

> [!NOTE]
> **What the run showed.** Flash-Lite alone keeps 98% of Pro's judge score at 3% of the cost. Fixed standard and semantic routing match Pro's score at 16% and 39% of its cost, so the honest "same quality, cheaper" number is 61% to 84% savings, not 97%. The cascade never escalated: Gemini 3.1 Flash-Lite reports `CONFIDENCE: 95` or higher on every prompt, including formal proofs, so the 70% gate never fires and cascade is fixed lite with a longer prompt. The semantic cache served 120 of 120 repeated lite prompts on the second pass.
>
> The judge scores near the ceiling for every strategy, so this set does not separate the tiers as sharply as a harder one would. Ten long-form answers still hit the 8,192-token output budget.
>
> 📊 **Full Interactive Report:** [https://thrifty-router.jking.ai](https://thrifty-router.jking.ai)

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

- **Live Benchmark Report:** [https://thrifty-router.jking.ai](https://thrifty-router.jking.ai)
- **Golden Set Explorer:** [https://thrifty-router.jking.ai/golden](https://thrifty-router.jking.ai/golden)
- **Portfolio Case Study:** [https://labs.jking.ai/projects/thrifty-router](https://labs.jking.ai/projects/thrifty-router)
