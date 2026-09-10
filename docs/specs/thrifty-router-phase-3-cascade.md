# Thrifty Router Phase 3: Cascade Strategy — Design Spec

**Date:** 2026-09-08
**Part of:** [Thrifty Router overview](thrifty-router-overview.md)

---

## What This Phase Delivers

The `cascade` strategy: call the cheapest tier first, verify the answer without an extra model call, and escalate up the tier order until an answer is accepted or the last tier is reached.

**Why:** Cheap-first cascades are the strategy the 2026 literature reports the largest savings for, and the one whose quality trade-off the eval harness most needs to measure.

## Architecture

```
strategy=cascade:
  tier = cascade.start_tier
  loop:
    attempt = completion(tier, prompt + confidence instruction if text mode)
    verdict = Verifier.check(attempt)          # finish_reason, non-empty, schema or confidence
    if verdict.accepted or tier is last or escalations == max_escalations: return
    tier = next tier in table order; escalations += 1
```

## Requirements

1. `strategy` enum gains `cascade`; health lists it.
2. Escalation order is the tier table order starting at `cascade.start_tier`.
3. Verifier rules, applied in order; the first failing rule sets `reject_reason`:
   1. `finish_reason` is `STOP` → else `finish_reason:<value>`.
   2. Output non-empty after stripping whitespace → else `empty_output`.
   3. When `json_schema` is present: output parses as JSON and validates against the schema (`jsonschema` library, Draft 2020-12) → else `schema_invalid:<first error message, <= 120 chars>`.
   4. When `json_schema` is absent: the output's final line matches `^CONFIDENCE:\s*(\d{1,3})\s*$`, the number is `0..100`, and it is at least `cascade.min_confidence` → else `low_confidence:<n>` or `no_confidence_line`.
4. In text mode (no `json_schema`), every non-final-tier completion prompt has the confidence instruction from `backend/app/prompts/cascade_confidence_suffix.txt` appended to `system` (or used as `system` when absent). The `CONFIDENCE:` line is stripped from `output` before it is returned. The final tier never receives the suffix and is always accepted.
5. `routing.attempts` lists every attempt in order with `accepted` and `reject_reason`; `routing.tier` and `model` are the accepted attempt's; `usage` sums all attempts.
6. `max_escalations` caps escalation count; when reached, the last attempt is accepted regardless of verdict with `reject_reason` left as the verifier's value and `accepted: true`, and `reason` states `max_escalations`.

**Permissions:** Unchanged.

**Error behavior:** An upstream error on any attempt aborts the request with 502 `UPSTREAM_ERROR`; earlier attempts' cost is still added to the ledger and logged.

## Contracts

### `router.yaml` additions

```yaml
cascade:
  start_tier: lite
  min_confidence: 70
  max_escalations: 2
```
`start_tier` must be a listed tier; `min_confidence` in `0..100`; `max_escalations` in `0..(number of tiers - 1)`.

### `routing.reason`

| Case | Reason |
|---|---|
| Accepted at first tier | `cascade accepted at <tier>` |
| Escalated n times, then accepted | `cascade escalated <n>x accepted at <tier>` |
| Cap reached | `cascade escalated <n>x max_escalations accepted at <tier>` |
| Last tier reached | `cascade escalated <n>x last_tier accepted at <tier>` |

### `Attempt.reject_reason` values

`finish_reason:<value>`, `empty_output`, `schema_invalid:<msg>`, `low_confidence:<n>`, `no_confidence_line`, or `null`.

### `backend/app/prompts/cascade_confidence_suffix.txt`

Required content: an instruction to answer normally and then, on the final line by itself, write `CONFIDENCE: <0-100>` reflecting how likely the answer is fully correct and complete, with `100` meaning certain. The file is one paragraph; the exact wording is the implementer's choice provided the regex in R3.4 matches the model's output in the smoke test.

Internal design is implementer's choice provided these contracts hold.

## Technical Notes

**Non-discoverable context**
- Self-reported confidence is a known-weak but free signal. The spec accepts that; Phase 5 measures it. Do not "improve" it with a second judging call inside the gateway.
- The confidence line must be stripped even when the attempt is rejected, because the eval harness stores every attempt's `output` for inspection (`attempts[].output` is not part of the API response; the harness gets it from `output` of the accepted attempt only).
- Thinking tokens on `pro` can dominate escalation cost; the ledger already bills them as output.

**Integration points**
- `backend/app/services/strategies/cascade.py`, `backend/app/services/verifier.py`, `backend/app/prompts/cascade_confidence_suffix.txt`, `backend/app/router.yaml`, `backend/app/services/router.py`.
- `requirements.txt`: add `jsonschema>=4.0`.
- Docs: `docs/api-contracts.md` (reason strings, reject reasons), `docs/architecture.md` (cascade diagram and verifier rules), `README.md` patterns table row "Model cascade with cost-free verification".

**Patterns to follow**
- Strategy registration and attempt recording from Phase 2's classifier strategy.

## Acceptance Criteria

- [ ] (R3, R5) `backend/tests/test_cascade.py::test_accepts_first_tier` — fake returns `"42\nCONFIDENCE: 90"`; one attempt, `output == "42"`, reason `cascade accepted at lite`.
- [ ] (R3.4) `test_escalates_on_low_confidence` — lite returns `CONFIDENCE: 40`, standard returns `CONFIDENCE: 85`; two attempts, first `accepted false` with `reject_reason == "low_confidence:40"`, tier `standard`, reason `cascade escalated 1x accepted at standard`.
- [ ] (R3.4) `test_escalates_on_missing_confidence_line` — `reject_reason == "no_confidence_line"`.
- [ ] (R3.3) `test_escalates_on_schema_invalid` — with a schema requiring `{"answer": int}`, lite returns `{"answer":"x"}`; reject reason starts with `schema_invalid:`; standard returns valid JSON and is accepted.
- [ ] (R3.1) `test_escalates_on_max_tokens_finish` — `finish_reason MAX_TOKENS` yields `reject_reason == "finish_reason:MAX_TOKENS"`.
- [ ] (R4) `test_final_tier_no_suffix_and_always_accepted` — fake records that the `pro` call's system has no confidence suffix and the attempt is accepted with output lacking a confidence line even when none was provided.
- [ ] (R6) `test_max_escalations_cap` — with `max_escalations: 1` and all tiers low-confidence, two attempts, last `accepted true`, reason contains `max_escalations`.
- [ ] (R5) `test_usage_sums_all_attempts`.
- [ ] Error path: `test_upstream_error_mid_cascade_502_and_ledger_charged` — lite succeeds low, standard raises; response 502 and `/usage` shows lite's cost.
- [ ] (R1) `test_health_lists_cascade`.
- [ ] `cd backend && pytest` exits 0; docs updated per Integration points.

## Verification

1. `cd backend && pytest -q` → exit 0.
2. Local server with ADC: `curl ... -d '{"prompt":"Explain the trade-offs of HNSW vs IVF indexes for a 10M-vector store","strategy":"cascade"}'` → `attempts` has at least one entry; if the first is rejected its `reject_reason` matches one of the enumerated values; `output` contains no line beginning `CONFIDENCE:`.
3. Same with `"prompt":"What is 2+2?"` → exactly one attempt accepted at `lite`.

## Do NOT

- Do not add a separate LLM judge or verifier call.
- Do not retry the same tier.
- Do not change the Phase 1 or Phase 2 reason strings.
- Do not add dependencies beyond `jsonschema`.

## Dependencies

**Requires:** Phase 1 (strategy registry, attempts, ledger).
**Blocks:** Phase 5.

## Out of Scope

- Cost-aware early stopping (skip a tier when the remaining budget cannot afford it).
- Parallel speculative calls to two tiers.
