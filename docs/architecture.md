# Architecture & System Design

Thrifty Router acts as an intelligent intermediary between LLM client applications and Google Cloud Vertex AI (Gemini model family). Its mission is to minimize cost without sacrificing response quality.

## System Topology

```
┌────────────────────────────────────────────────────────┐
│                   Client Application                   │
│        (X-API-Key: bearer-token / Authorization)       │
└───────────────────────────┬────────────────────────────┘
                            │
                            │ HTTPS
                            ▼
┌────────────────────────────────────────────────────────┐
│                   Google Cloud Run                     │
│               (FastAPI + Uvicorn Async)                │
│                                                        │
│  ┌─────────────────┐             ┌──────────────────┐  │
│  │ Slowapi Limiter │ ──────────► │ Cost Ledger      │  │
│  │ (IP / Key rate) │             │ (Daily Budget)   │  │
│  └─────────────────┘             └────────┬─────────┘  │
│                                           │            │
│  ┌────────────────────────────────────────┴─────────┐  │
│  │ Semantic Cache Engine                            │  │
│  │  1. Exact Match: SHA-256(normalized prompt)      │  │
│  │  2. Vector Match: gemini-embedding-001 (cos>=.92)│  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │ (Miss)                     │
│  ┌────────────────────────▼─────────────────────────┐  │
│  │ Strategy Dispatcher                              │  │
│  │  • fixed: static mapping                         │  │
│  │  • semantic: embedding route anchors             │  │
│  │  • classifier: zero-temp few-shot prompt         │  │
│  │  • cascade: opportunistic escalation             │  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │                            │
│  ┌────────────────────────▼─────────────────────────┐  │
│  │ Tier Client Adapter (google-genai SDK)           │  │
│  └────────────────────────┬─────────────────────────┘  │
└───────────────────────────┼────────────────────────────┘
                            │ gRPC / TLS
                            ▼
┌────────────────────────────────────────────────────────┐
│                 Google Cloud Vertex AI                 │
│                                                        │
│   [lite]               [standard]             [pro]    │
│ Gemini 2.5 Flash   Gemini 1.5 Flash      Gemini 2.5 Pro│
│ ($0.075 / $0.30)   ($0.075 / $0.30)      ($1.25 / $5.0)│
└────────────────────────────────────────────────────────┘
```

## Model Tiers & Pricing Mechanics

Model tiers are defined in `router.yaml` and loaded during application startup. Pricing is tracked per million tokens:

| Tier | Vertex AI Model | Input Price / 1M | Output Price / 1M | Use Cases |
|---|---|---|---|---|
| `lite` | `gemini-2.5-flash` | $0.075 | $0.30 | Greetings, factual lookups, classifications, extraction |
| `standard` | `gemini-1.5-flash` | $0.075 | $0.30 | Summaries, routine transformations, standard drafting |
| `pro` | `gemini-2.5-pro` | $1.250 | $5.00 | Complex reasoning, multi-step math, code synthesis, nuanced evaluation |

### Micro-Dollar Cost Ledger
The cost formula accounts for input tokens, generated output tokens, and chain-of-thought/thinking tokens:
$$\text{Cost} = \left(\frac{\text{prompt\_tokens}}{10^6} \times P_{\text{in}}\right) + \left(\frac{\text{candidates\_tokens} + \text{thinking\_tokens}}{10^6} \times P_{\text{out}}\right)$$

All calculations are rounded to 6 decimal places ($0.000001). If the cumulative daily spend meets or exceeds `DAILY_BUDGET_USD`, the gateway immediately rejects incoming generation requests with `402 Payment Required` and `BUDGET_EXCEEDED`.

## Routing Strategies

### 1. Fixed (`fixed`)
Routes directly to a configured tier or the caller's requested tier without dynamic evaluation. Useful for deterministic workflows or regression benchmarking.

### 2. Semantic (`semantic`)
Pre-computes 768-dimensional L2-normalized embeddings for curated prompt archetypes across `lite`, `standard`, and `pro`. When a query arrives:
1. Generate query embedding using `gemini-embedding-001`.
2. Compute cosine similarity against all route anchors.
3. Assign the tier of the closest matching centroid above a confidence margin.

### 3. Classifier (`classifier`)
Sends the user prompt to a fast zero-temperature classifier prompt run against Gemini 2.5 Flash. The classifier returns a strict JSON object:
```json
{
  "tier": "lite|standard|pro",
  "reason": "short explanation"
}
```
If the classifier response cannot be parsed or times out, the router fails safe to `standard`.

### 4. Cascade (`cascade`)
Opportunistic escalation based on iterative generation and verification:
1. Attempt execution on the cheapest candidate tier (default: `lite`).
2. Run response through the **Verifier Pipeline**:
   - `finish_reason == "STOP"` (no truncation or safety blocks).
   - `non_empty` (non-whitespace text length >= 1).
   - `json_schema` (if `schema` requested in call parameters).
   - `confidence_score` (if confidence suffix enabled, self-rated confidence must be >= 70).
3. If all verification checks pass, return the response immediately.
4. If verification fails, record rejection reason and escalate to the next tier (`lite` -> `standard` -> `pro`).
5. If `max_escalations` is reached or the top tier (`pro`) is reached, accept the output.

## Semantic Caching Topology

```
Prompt Input
     │
     ▼
Normalize String (strip trailing whitespace, lowercase match if configured)
     │
     ├─► Hash SHA-256 ──► In-Memory / Firestore Exact Index
     │                          │
     │                          ▼
     │                     Cache Hit? ──(Yes)──► Return Cached Output ($0.00)
     │                          │
     │                          ▼ (No)
     └─► Embed Query (gemini-embedding-001)
                │
                ▼
         Firestore Vector Search (find_nearest, COSINE, threshold >= 0.92)
                │
                ├─► Distance <= 0.08? ──(Yes)──► Return Cached Output ($0.00)
                │
                └─► (No) ──────────────► Route to Live Tier & Store Result (TTL: 24h)
```

## Resilience & Failure Modes

1. **Fail-Safe Caching:** Any Firestore timeout, network disconnection, or vector search failure is logged as a warning. The request falls back smoothly to live generation without impacting the client.
2. **Circuit Breaking:** Consecutive Vertex AI 5xx failures trigger a 30-second backoff window for affected tiers before retrying.
3. **In-Flight Rate Limiting:** Slowapi prevents noisy neighbors from exhausting Cloud Run concurrency or Vertex AI quota limits.
