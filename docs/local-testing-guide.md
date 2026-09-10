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
- [`test_report.py`](file:///Users/king/dev/jrk-ai-labs/thrifty-router/eval/tests/test_report.py): Tests JSON summary extraction and static HTML report rendering.

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

To run a lightweight evaluation against a live endpoint with a small sample:

```bash
cd eval
python3 run_eval.py \
  --golden golden/golden_set.jsonl \
  --strategies lite_only semantic cascade \
  --sample-size 10 \
  --spend-ceiling 0.50 \
  --output-dir results/sample_run
```
