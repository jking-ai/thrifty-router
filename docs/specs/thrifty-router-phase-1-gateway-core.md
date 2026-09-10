# Thrifty Router Phase 1: Gateway Core — Design Spec

**Date:** 2026-09-08
**Part of:** [Thrifty Router overview](thrifty-router-overview.md)

---

## What This Phase Delivers

A deployable FastAPI service exposing `POST /api/v1/complete` with the `fixed` strategy, a config-driven tier table, exact per-request cost accounting, API-key auth, per-IP rate limits, a daily budget stop, and the house documentation skeleton.

**Why:** Every strategy, the cache, and the eval harness build on this request contract and cost ledger.

## Architecture

```
POST /api/v1/complete (X-API-Key)
  → auth middleware → slowapi limit → BudgetLedger.check()
  → Router.route(request) → for "fixed": tier = request.tier
  → GeminiTierClient.generate(tier, prompt, system, json_schema, temperature, max_output_tokens)
  → CostCalculator.cost(usage, tier prices)   # thinking tokens at output rate
  → BudgetLedger.add(cost) ; JSON log line
  ← CompleteResponse
```

## Requirements

1. Project skeleton per the overview's bootstrap section, using `synthetic-student-generator/backend/` as the layout template and `vision-first-study-buddy/backend/Dockerfile` as the Dockerfile template.
2. Tier table loaded at startup from `backend/app/router.yaml` (Contracts). Startup fails with a clear `ValueError` naming the missing key if the file is invalid.
3. `POST /api/v1/complete` implementing strategy `fixed` exactly as in Contracts. Other strategy names return 400 `STRATEGY_NOT_AVAILABLE` in this phase.
4. Cost per attempt computed as `(input_tokens * price_in + (output_tokens + thinking_tokens) * price_out) / 1_000_000`, rounded to 6 decimals.
5. `X-API-Key` auth on every route except `GET /api/v1/health` and `GET /api/v1/tiers`, compared with `secrets.compare_digest`.
6. Per-IP rate limit on `/api/v1/complete` using `slowapi` with the key function and 429 envelope from `vision-first-study-buddy/backend/app/rate_limit.py`.
7. In-process daily budget: sum of `total_cost_usd` for the current UTC day; when the sum is at or above `DAILY_BUDGET_USD` the request is rejected before any model call.
8. One JSON log line per completed or failed request (Contracts).
9. `GET /api/v1/health`, `GET /api/v1/tiers`, `GET /api/v1/usage` as in Contracts.
10. `scripts/deploy.sh` following `synthetic-student-generator/scripts/deploy.sh` (backend part only) with the flags listed in Technical Notes.
11. All model access goes through a `GeminiTierClient` class injected via a FastAPI dependency so tests substitute a fake.

**Permissions:** Single shared API key. Missing or wrong key: 401 `{"detail":{"code":"UNAUTHORIZED","message":"Missing or invalid API key"}}`.

**Error behavior:** All errors use `{"detail":{"code":"<CODE>","message":"<string>"}}` except request-body validation, which keeps FastAPI's default 422 body. Upstream Gemini exception: 502 `UPSTREAM_ERROR` with the exception class name in `message`. Upstream call exceeding `GEMINI_TIMEOUT_SECONDS`: 504 `UPSTREAM_TIMEOUT`. No automatic retries.

## Contracts

### `backend/app/router.yaml`

```yaml
tiers:                       # order = escalation order, cheapest first
  - name: lite
    model: gemini-3.1-flash-lite-preview
    price_per_m_input_usd: 0.25
    price_per_m_output_usd: 1.50
  - name: standard
    model: gemini-3-flash-preview
    price_per_m_input_usd: 0.50
    price_per_m_output_usd: 3.00
  - name: pro
    model: gemini-3.1-pro-preview
    price_per_m_input_usd: 2.00
    price_per_m_output_usd: 12.00
default_tier: lite
```
Tier names are `^[a-z][a-z0-9_]{0,15}$`. `default_tier` must name a listed tier. Later phases add top-level keys (`semantic`, `classifier`, `cascade`, `cache`); unknown keys are ignored in this phase.

### `POST /api/v1/complete`

Request body:
```json
{
  "prompt": "string, 1..MAX_PROMPT_CHARS",
  "system": "string, optional, <= 4000 chars",
  "strategy": "fixed",
  "tier": "lite | standard | pro   (required when strategy is fixed)",
  "temperature": 0.2,
  "max_output_tokens": 1024,
  "json_schema": null
}
```
- `strategy` enum in this phase: `["fixed"]`. Unknown value: 400 `STRATEGY_NOT_AVAILABLE`.
- `tier` not in the table: 400 `UNKNOWN_TIER`. Missing when `strategy` is `fixed`: 400 `TIER_REQUIRED`.
- `temperature` default `0.2`, range `0.0..2.0`.
- `max_output_tokens` default `MAX_OUTPUT_TOKENS`, range `1..MAX_OUTPUT_TOKENS`.
- `json_schema` optional JSON Schema object; when present the model is called with `response_mime_type="application/json"` and `response_schema` set to it, and `output` is the raw JSON string.

Response 200:
```json
{
  "request_id": "req_<12 hex>",
  "output": "string",
  "routing": {
    "strategy": "fixed",
    "tier": "lite",
    "model": "gemini-3.1-flash-lite-preview",
    "reason": "caller-specified",
    "attempts": [
      {
        "role": "completion",
        "tier": "lite",
        "model": "gemini-3.1-flash-lite-preview",
        "latency_ms": 412,
        "input_tokens": 120,
        "output_tokens": 340,
        "thinking_tokens": 0,
        "cost_usd": 0.00054,
        "accepted": true,
        "reject_reason": null
      }
    ]
  },
  "usage": {
    "input_tokens": 120,
    "output_tokens": 340,
    "thinking_tokens": 0,
    "total_cost_usd": 0.00054
  },
  "latency_ms": 430
}
```
- `attempts[].role` enum: `completion` (this phase), `classifier` (Phase 2), `verifier` reserved.
- `usage` is the sum over all attempts.
- `latency_ms` is wall time for the whole request.
- Token counts come from `usage_metadata` (`prompt_token_count`, `candidates_token_count`, `thoughts_token_count`); missing fields are `0`.

Errors: 401 `UNAUTHORIZED`; 400 `STRATEGY_NOT_AVAILABLE`, `UNKNOWN_TIER`, `TIER_REQUIRED`; 413 `PROMPT_TOO_LONG` when `prompt` exceeds `MAX_PROMPT_CHARS`; 422 FastAPI validation; 429 `RATE_LIMITED` (header `Retry-After: 60`); 429 `DAILY_BUDGET_EXCEEDED` (no `Retry-After`); 502 `UPSTREAM_ERROR`; 504 `UPSTREAM_TIMEOUT`.

### `GET /api/v1/health` (no auth, no limit)

```json
{"status":"ok","tiers":["lite","standard","pro"],"strategies":["fixed"],"version":"<git short sha or 'dev'>"}
```

### `GET /api/v1/tiers` (no auth, no limit)

```json
{"default_tier":"lite","tiers":[{"name":"lite","model":"gemini-3.1-flash-lite-preview","price_per_m_input_usd":0.25,"price_per_m_output_usd":1.5}, ...]}
```

### `GET /api/v1/usage` (auth, no limit)

```json
{"date":"2026-09-08","requests":12,"total_cost_usd":0.0131,"daily_budget_usd":2.0,"by_tier":{"lite":{"requests":10,"cost_usd":0.0031},"pro":{"requests":2,"cost_usd":0.01}}}
```
Resets at UTC midnight. Values are process-local.

### Config (`backend/app/config.py`, `Settings`, pydantic-settings, `snake_case` fields like `vision-first-study-buddy/backend/app/config.py`)

| Field | Env var | Type | Default | Notes |
|---|---|---|---|---|
| `gcp_project_id` | `GCP_PROJECT_ID` | str | `""` | Required; startup error if empty. |
| `gemini_location` | `GEMINI_LOCATION` | str | `"global"` | Passed to `genai.Client(vertexai=True, project=..., location=...)`. |
| `api_key` | `API_KEY` | str | `""` | Required; startup error if empty. |
| `allowed_origins` | `ALLOWED_ORIGINS` | list[str] | `[]` | JSON list or comma string. |
| `docs_enabled` | `DOCS_ENABLED` | bool | `False` | |
| `router_config_path` | `ROUTER_CONFIG_PATH` | str | `"app/router.yaml"` | Relative to `backend/`. |
| `daily_budget_usd` | `DAILY_BUDGET_USD` | float | `2.0` | |
| `complete_limits` | `COMPLETE_LIMITS` | str | `"10/minute;200/day"` | slowapi syntax. |
| `max_prompt_chars` | `MAX_PROMPT_CHARS` | int | `20000` | |
| `max_output_tokens` | `MAX_OUTPUT_TOKENS` | int | `1024` | Ceiling and default. |
| `gemini_timeout_seconds` | `GEMINI_TIMEOUT_SECONDS` | int | `60` | Per model call. |

### Request log line (stdout, one JSON object)

```json
{"event":"complete","request_id":"req_...","strategy":"fixed","tier":"lite","model":"...","status":200,"input_tokens":120,"output_tokens":340,"thinking_tokens":0,"total_cost_usd":0.00054,"latency_ms":430,"attempts":1,"client_ip":"1.2.3.4"}
```
On error, `status` is the HTTP status and `error_code` carries the code; token fields are `0`.

### Python module layout

```
backend/app/main.py            create_app(), routers under /api/v1, "/" redirects to /api/v1/health
backend/app/config.py
backend/app/rate_limit.py      limiter, get_client_ip, COMPLETE_LIMITS constant mirror, 429 handler
backend/app/auth.py            require_api_key dependency
backend/app/dependencies.py    get_settings, get_router_config, get_tier_client, get_ledger
backend/app/models/requests.py CompleteRequest
backend/app/models/responses.py CompleteResponse, Attempt, Routing, Usage, TiersResponse, UsageResponse, HealthResponse
backend/app/services/tier_client.py   GeminiTierClient (google-genai, Vertex backend)
backend/app/services/cost.py          cost_usd(usage, tier)
backend/app/services/ledger.py        BudgetLedger
backend/app/services/router.py        Router with strategy registry; Phase 1 registers "fixed"
backend/app/router.yaml
backend/tests/                 pytest, asyncio_mode = auto, conftest with fake tier client
backend/scripts/smoke.sh       curl examples for every route
```

Internal design is implementer's choice provided these contracts hold. The strategy registry shape is free as long as Phases 2 and 3 can add strategies without editing the `complete` handler.

## Technical Notes

**Non-discoverable context**
- Use `google-genai` with `vertexai=True`; do not use `google-cloud-aiplatform` (`vertexai.generative_models` is the older SDK used only by `vision-first-study-buddy`).
- Prices in `router.yaml` are the values on 2026-09-08 for prompts under 200K tokens. The gateway does not model the long-context price step; `MAX_PROMPT_CHARS` keeps prompts far below it.
- Budget and rate-limit state are process-local; deploy with `--max-instances 1` and document the rationale as `vision-first-study-buddy/docs/production-deployment.md:52` does.
- Deploy flags: `gcloud run deploy thrifty-router --source ./backend --region us-central1 --project YOUR_GCP_PROJECT --service-account thrifty-router-sa@YOUR_GCP_PROJECT.iam.gserviceaccount.com --allow-unauthenticated --memory 512Mi --cpu 1 --min-instances 0 --max-instances 1 --timeout 120 --set-env-vars GCP_PROJECT_ID=YOUR_GCP_PROJECT,GEMINI_LOCATION=global --set-secrets API_KEY=thrifty-router-api-key:latest`.
- Secret `thrifty-router-api-key` in Secret Manager; the service account needs `roles/secretmanager.secretAccessor` on it.
- Python 3.13, plain `pip` and `requirements.txt` (no pyproject, no uv), no linter configured in the portfolio; add `ruff` only if the user asks.

**Patterns to follow**
- App factory and docs toggle: `synthetic-student-generator/backend/app/main.py` `create_app()`.
- Settings with validators: `vision-first-study-buddy/backend/app/config.py` (`allowed_origins` validator lines 45-50, `validate_required_fields` line 52, `get_settings` line 68).
- Rate limiting: `vision-first-study-buddy/backend/app/rate_limit.py` (key func, `headers_enabled=False` note, 429 handler).
- Test fixtures: `vision-first-study-buddy/backend/tests/conftest.py` (`_StickyOverrides`, autouse cache clearing, `limiter.reset()`).
- Token usage extraction: `synthetic-student-generator/backend/app/services/gemini_client.py` `GenerateResult(content, usage)`.
- API key middleware semantics: `fin-ops-advisor/internal/middleware/auth.go` (exempt paths, 401 envelope), but with constant-time compare.

## Acceptance Criteria

- [ ] (R2) `backend/tests/test_config.py::test_router_yaml_loads_three_tiers` and `test_router_yaml_missing_default_tier_raises`.
- [ ] (R3) `backend/tests/test_complete.py::test_fixed_returns_contract_shape` — fake client returns fixed usage; response matches every field in Contracts, `routing.reason == "caller-specified"`, one attempt with `role == "completion"` and `accepted is True`.
- [ ] (R3) `test_fixed_missing_tier_400`, `test_unknown_tier_400`, `test_unknown_strategy_400`, `test_prompt_too_long_413`, `test_json_schema_passthrough` (fake records `response_mime_type == "application/json"`).
- [ ] (R4) `backend/tests/test_cost.py::test_thinking_tokens_billed_as_output` — 1000 in, 1000 out, 500 thinking on `pro` gives `0.02 + 0.018 == 0.038`.
- [ ] (R5) `backend/tests/test_auth.py::test_missing_key_401`, `test_wrong_key_401`, `test_health_and_tiers_no_auth`.
- [ ] (R6) `backend/tests/test_rate_limit.py::test_complete_rate_limited_429` — with `COMPLETE_LIMITS="2/minute"`, third call returns 429 `RATE_LIMITED` with `Retry-After: 60`.
- [ ] (R7) `backend/tests/test_budget.py::test_budget_exceeded_429_before_model_call` — with `DAILY_BUDGET_USD=0.0001` and one prior request, the next returns 429 `DAILY_BUDGET_EXCEEDED` and the fake client's call count does not increase.
- [ ] (R8) `backend/tests/test_logging.py::test_request_log_line` — captured stdout has one JSON line with `"event": "complete"` and every field in Contracts.
- [ ] (R9) `backend/tests/test_usage.py::test_usage_accumulates_by_tier`.
- [ ] (R11) `grep -n "get_tier_client" backend/app/dependencies.py backend/app/routers/complete.py` hits both.
- [ ] (R1, R10) Files exist: `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/README.md`, `docs/architecture.md`, `docs/api-contracts.md`, `docs/milestones.md`, `docs/local-dev-guide.md`, `docs/local-testing-guide.md`, `docs/production-deployment.md`, `backend/.env.example`, `backend/Dockerfile`, `scripts/deploy.sh`, `backend/scripts/smoke.sh`.
- [ ] `cd backend && pytest` exits 0.
- [ ] `docs/api-contracts.md` reproduces every request, response, and error code in this spec; `AGENTS.md` lists every env var and the security posture (key, limits, budget, max-instances).

## Verification

1. `cd backend && pytest -q` → exit 0.
2. `cd backend && GCP_PROJECT_ID=your-gcp-project-id API_KEY=dev uvicorn app.main:app --port 8000`, then `bash scripts/smoke.sh http://localhost:8000 dev` → prints a 200 body for `/complete` with `strategy: fixed` and `tier: lite`, a 401 for a missing key, and the `/usage` body showing one request. Requires ADC (`gcloud auth application-default login`).
3. `bash scripts/deploy.sh backend` → prints the Cloud Run URL and a passing `/api/v1/health` curl.

## Do NOT

- Do not implement `semantic`, `classifier`, or `cascade` (Phases 2 and 3).
- Do not add Firestore, embeddings, or caching (Phase 4).
- Do not add a frontend, Firebase Hosting config, or a proxy function.
- Do not add retries or fallbacks between tiers.
- Do not add dependencies beyond `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `slowapi`, `google-genai`, `pyyaml`, `pytest`, `pytest-asyncio`, `httpx`.
- Do not create the GitHub remote.

## Dependencies

**Requires:** None.
**Blocks:** Phases 2, 3, 4, 5.

## Out of Scope

- Multi-key or per-key budgets.
- Streaming responses.
- OpenAI-compatible endpoint.
