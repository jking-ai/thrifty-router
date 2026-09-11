# Local Testing Guide

This guide details how to execute unit tests, integration tests, and evaluation benchmarks for **Thrifty Router**.

---

## Testing Principles

1. **Zero GCP Cost During Unit Tests:** All unit tests mock the `google-genai` client and use `FakeCacheStore`. No Vertex AI API calls are initiated and no cloud charges are incurred during automated testing.
2. **Determinism:** Tests isolate time and random state where appropriate to guarantee repeatable results.
3. **Comprehensive Coverage:** Tests exercise authentication, rate limiting, ledger budget stops, dynamic routing strategies, and caching edge cases.

---

## Running Backend Unit Tests

The backend test suite is located in `backend/tests/`.

```bash
cd backend
# Run all tests with verbose output
pytest -v tests/

# Run a specific test module
pytest -v tests/test_cascade.py

# Run tests matching a keyword
pytest -k "budget or rate_limit"
```

### Key Test Suites

- [`test_config.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/backend/tests/test_config.py): Verifies configuration parsing and environment defaults.
- [`test_auth.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/backend/tests/test_auth.py): Verifies missing, invalid, and valid API keys (`X-API-Key` and `Bearer`).
- [`test_rate_limit.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/backend/tests/test_rate_limit.py): Validates Slowapi throttling on `/v1/complete` and unrate-limited `/health`.
- [`test_budget.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/backend/tests/test_budget.py): Validates thread-safe budget enforcement and `402 BUDGET_EXCEEDED` stops.
- [`test_semantic.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/backend/tests/test_semantic.py): Tests embedding anchor comparisons and fallback mechanisms.
- [`test_classifier.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/backend/tests/test_classifier.py): Tests few-shot classification and fallback to `standard`.
- [`test_cascade.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/backend/tests/test_cascade.py): Tests multi-tier escalation, schema checking, and confidence validation.
- [`test_cache.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/backend/tests/test_cache.py): Tests exact SHA-256 and cosine similarity vector cache hits.

---

## Running Evaluation Harness Tests

The evaluation test suite is located in `eval/tests/`.

```bash
cd eval
pytest -v tests/
```

### Key Eval Suites

- [`test_validate_golden.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/eval/tests/test_validate_golden.py): Tests golden dataset validation logic.
- [`test_run_eval.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/eval/tests/test_run_eval.py): Tests evaluation execution loop, spend ceiling stops, and cache replays.
- [`test_judge.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/eval/tests/test_judge.py): Tests LLM judge grading prompt parsing and scoring formulas.
- [`test_retry_failed_responses.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/eval/tests/test_retry_failed_responses.py): Tests the in-place retry of failed gateway responses.
- [`test_report.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/eval/tests/test_report.py): Tests JSON summary extraction, static HTML report rendering, and the golden set export.

---

## Validating Golden Dataset

Ensure the golden dataset conforms to schema and target tier distributions (40% lite, 35% standard, 25% pro):

```bash
cd eval
python3 scripts/validate_golden.py golden/golden_set.jsonl
```

Expected output:
```text
Loaded 300 golden items from golden/golden_set.jsonl
All items passed validation!
Tier distribution:
  lite: 120 (40.0%)
  standard: 105 (35.0%)
  pro: 75 (25.0%)
```

---

## Running an End-to-End Evaluation Sample

To run a small slice against a gateway (all commands run from the repo root):

```bash
python3 eval/run_eval.py \
  --base-url http://localhost:8000 --api-key local-eval-key \
  --strategies fixed:lite,semantic,cascade \
  --limit 10 --max-spend-usd 0.50 \
  --out eval/results/sample_run

python3 eval/judge.py \
  --base-url http://localhost:8000 --api-key local-eval-key \
  --results eval/results/sample_run --max-spend-usd 0.50

python3 eval/report.py --results eval/results/sample_run --allow-partial
```

## Running the Full Benchmark

A full run is 1,800 gateway calls plus 1,800 judge calls, which the production gateway's per-IP limits (`10/minute;200/day`) and $2 daily budget will not allow. Run it against a local backend with the limits raised:

```bash
cd backend
GCP_PROJECT_ID=jking-ai-labs GCP_REGION=us-central1 GEMINI_LOCATION=global \
API_KEY=local-eval-key DAILY_BUDGET_USD=30 COMPLETE_LIMITS="1000/minute;100000/day" \
CACHE_ENABLED=true \
../.venv/bin/uvicorn app.main:app --port 8000
```

Leave `MAX_OUTPUT_TOKENS` at its default of 8192. Gemini 3.x counts thinking tokens against that budget, and pro-tier thinking alone reached about 2,000 tokens on the golden set, so a smaller cap cuts answers off mid-sentence and the judge scores the truncation rather than the model. `CACHE_ENABLED=true` is only needed for the `--cache-replay` experiment; the main replay and the judge send `use_cache: false` on every request.

Then, from the repo root:

```bash
RUN_ID=$(date -u +%Y-%m-%dT%H-%M-%SZ)
python3 eval/run_eval.py --base-url http://localhost:8000 --api-key local-eval-key \
  --max-spend-usd 12 --concurrency 4 --cache-replay --out eval/results/$RUN_ID
# Replay only the pairs that hit a 429 or timeout (about 1% of calls on the pro model).
# Add --rerun-capped-at N to also replay answers whose thinking + output reached a token cap;
# their judgments are dropped so the judge rescores them on --resume.
python3 eval/scripts/retry_failed_responses.py --base-url http://localhost:8000 --api-key local-eval-key \
  --results eval/results/$RUN_ID
python3 eval/judge.py --base-url http://localhost:8000 --api-key local-eval-key \
  --results eval/results/$RUN_ID --max-spend-usd 8 --concurrency 4
python3 eval/report.py --results eval/results/$RUN_ID
cp eval/results/$RUN_ID/summary.json eval/results/latest/summary.json
```

Expect roughly $9 for generation and $7 for judging in Vertex AI spend, and about two and a half hours of wall-clock time at concurrency 4. The judge retries 429s and timeouts three times on its own. If the judge is interrupted, rerun it with `--resume` to keep every scored line and score only the rest.

---

## Previewing the Benchmark Report Locally

The report site is static, but the golden set explorer fetches `golden.json` and links use Firebase clean URLs (`/golden`), so preview it with the Hosting emulator rather than opening the files directly:

```bash
# Regenerate index.html, data.json, and golden.json from the committed summary
python3 eval/report.py --summary report/data.json

# Serve report/ on http://localhost:5055 with production rewrites and clean URLs
firebase emulators:start --only hosting --project jking-ai-labs
```

Open `http://localhost:5055/` for the benchmark report and `http://localhost:5055/golden` for the explorer. The explorer accepts `?category=`, `?tier=`, and `?q=` query parameters, which the preview card on the home page uses for its deep links.

