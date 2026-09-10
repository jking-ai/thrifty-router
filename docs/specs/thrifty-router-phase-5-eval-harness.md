# Thrifty Router Phase 5: Eval Harness — Design Spec

**Date:** 2026-09-08
**Part of:** [Thrifty Router overview](thrifty-router-overview.md)

---

## What This Phase Delivers

A golden set of labeled prompts, a runner that replays it through every strategy, a Pro judge that scores each answer, and a static report page on Firebase Hosting with the cost-versus-quality chart.

**Why:** The router's whole claim is "cheaper at near-equal quality"; this phase produces the numbers that back or refute it.

## Architecture

```
eval/golden/seed_tasks.md ──synthesize_golden.py (pro)──► eval/golden/golden_set.jsonl (reviewed: true/false)
eval/run_eval.py --base-url --api-key --strategies ... ──► eval/results/<ts>/responses.jsonl
eval/judge.py  (pro, temp 0)                              ──► eval/results/<ts>/judgments.jsonl
eval/report.py                                            ──► eval/results/<ts>/summary.json + report/data.json + report/index.html
firebase deploy --only hosting:router-report              ──► https://thrifty-router.web.app
```

## Requirements

1. Golden set file `eval/golden/golden_set.jsonl` with at least 300 items matching the item schema, distribution within ±5 points of 40% `lite`, 35% `standard`, 25% `pro`, at least 30 items per category, and every item `reviewed: true` before it counts in a report.
2. `eval/scripts/synthesize_golden.py` generates candidate items from `eval/golden/seed_tasks.md` (24 hand-written seed tasks, 3 per category, each with an example prompt and the expected tier with a one-line justification) using the `pro` tier through the gateway, writing `reviewed: false`. `eval/scripts/validate_golden.py` checks the schema, id uniqueness, distribution, and category minimums and exits non-zero on violation.
3. `eval/run_eval.py` replays every reviewed item through each requested strategy with `use_cache: false`, concurrency 4, and records one line per (item, strategy) with the full gateway response plus `item_id`, `strategy_label`, `error` (null or the error envelope). Strategy labels: `fixed:lite`, `fixed:standard`, `fixed:pro`, `semantic`, `classifier`, `cascade`. A `--max-spend-usd` ceiling (default `3.0`) aborts the run when the summed `usage.total_cost_usd` reaches it; partial results are kept.
4. `eval/judge.py` scores each response 1 to 5 with `eval/prompts/judge_template.txt` on the `pro` tier at temperature 0 with the JSON schema in Contracts, using the item's `rubric` and `reference` (when present). Judge cost is summed separately. Errors produce `score: null` and are excluded from means but counted.
5. `eval/report.py` computes per-strategy metrics (Contracts) and writes `summary.json`, then renders `report/index.html` from `report/template.html` by injecting `data.json`.
6. Report page: a scatter chart of `cost_per_1k_requests_usd` (x, log scale) versus `mean_score` (y) with one point per strategy, a table of every metric, and a per-category breakdown table. Static HTML, inline CSS, Chart.js from `https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js`, no build step.
7. Firebase Hosting site `thrifty-router` with target `router-report` serving `report/`, deployed by `scripts/deploy.sh report`.
8. Additional cache experiment: `eval/run_eval.py --cache-replay` sends the reviewed `lite` items twice with `use_cache: true` against a `CACHE_ENABLED=true` gateway and reports `cache_hit_rate_second_pass` in `summary.json`.

**Permissions:** The runner and judge use the gateway's `X-API-Key`. The judge calls the gateway with `strategy: fixed, tier: pro`, so judge spend appears in `/usage` and the ledger's daily budget applies. Set `DAILY_BUDGET_USD` at least `10.0` on the gateway used for eval runs, and document it.

**Error behavior:** Gateway errors are recorded per line and the run continues. The spend ceiling and a `--limit N` item cap are the only abort paths. `report.py` refuses to run on a results directory with fewer than 50 judged lines per strategy unless `--allow-partial` is passed, and stamps `partial: true` into `summary.json` when it is.

## Contracts

### Golden item (one JSON object per line)

```json
{
  "id": "g_0001",
  "category": "rubric_parse | diagram_gen | doc_qa | classify | summarize | code_explain | math_reasoning | creative",
  "expected_tier": "lite | standard | pro",
  "prompt": "string",
  "system": "string | null",
  "json_schema": "object | null",
  "reference": "string | null",
  "rubric": "string, what a 5/5 answer must contain",
  "reviewed": true,
  "source": "seed:<seed id> | synth:<run id>"
}
```
Ids are `g_` plus four digits, unique, gapless in file order.

### Response line (`responses.jsonl`)

`{"item_id","strategy_label","request_id","response": <gateway 200 body> | null,"error": <error envelope> | null,"latency_ms": <client-measured int>}`

### Judgment line (`judgments.jsonl`)

`{"item_id","strategy_label","score": 1..5 | null,"rationale": "string","judge_cost_usd": float}`

Judge JSON schema: `{"type":"object","properties":{"score":{"type":"integer","minimum":1,"maximum":5},"rationale":{"type":"string"}},"required":["score","rationale"]}`.

### `summary.json`

```json
{
  "run_id": "2026-09-08T18-02-11Z",
  "partial": false,
  "items": 300,
  "judge_cost_usd": 1.21,
  "strategies": {
    "cascade": {
      "n": 300, "errors": 0,
      "mean_score": 4.31,
      "quality_retention": 0.96,
      "total_cost_usd": 0.41,
      "cost_per_1k_requests_usd": 1.37,
      "cost_ratio_vs_pro": 0.23,
      "latency_p50_ms": 900, "latency_p95_ms": 3100,
      "tier_mix": {"lite": 0.71, "standard": 0.19, "pro": 0.10},
      "routing_accuracy": null,
      "escalation_rate": 0.29,
      "by_category": {"doc_qa": {"n": 40, "mean_score": 4.4, "cost_per_1k_requests_usd": 1.1}}
    }
  },
  "cache_hit_rate_second_pass": 0.98
}
```
- `quality_retention` = strategy `mean_score` / `fixed:pro` `mean_score`.
- `cost_ratio_vs_pro` = strategy `total_cost_usd` / `fixed:pro` `total_cost_usd`.
- `routing_accuracy` = share of items where the final `routing.tier` equals `expected_tier`; `null` for `fixed:*`.
- `escalation_rate` = share of items with more than one completion attempt; `null` for non-cascade.
- `tier_mix` sums to 1.0 over the tiers that answered.
- `cache_hit_rate_second_pass` is `null` when `--cache-replay` was not run.

### `eval/prompts/judge_template.txt`

Placeholders: `{prompt}`, `{rubric}`, `{reference}` (rendered as `No reference answer provided.` when null), `{answer}`. Required stated scale: 5 fully correct and complete per rubric; 4 minor omission; 3 partially correct; 2 mostly wrong or off-task; 1 wrong, empty, or harmful. Required instruction: judge the answer only, do not solve the task yourself, output JSON only.

### `scripts/deploy.sh report`

Runs `firebase target:apply hosting router-report thrifty-router --project YOUR_GCP_PROJECT` then `firebase deploy --only hosting:router-report --project YOUR_GCP_PROJECT`. `firebase.json` at project root: hosting target `router-report`, `public: "report"`, `cleanUrls: true`, no rewrites.

### CLI

```
python eval/run_eval.py --base-url URL --api-key KEY [--strategies a,b,c] [--limit N] [--max-spend-usd 3.0] [--out eval/results/<ts>] [--cache-replay]
python eval/judge.py --base-url URL --api-key KEY --results DIR [--max-spend-usd 3.0]
python eval/report.py --results DIR [--allow-partial]
python eval/scripts/validate_golden.py [eval/golden/golden_set.jsonl]
python eval/scripts/synthesize_golden.py --base-url URL --api-key KEY --per-seed 12 --out eval/golden/candidates.jsonl
```

Internal design is implementer's choice provided these contracts hold.

## Technical Notes

**Non-discoverable context**
- Expected spend for one full run at 300 items: roughly $0.10 for `fixed:lite`, $0.25 for `fixed:standard`, $1.50 to $2.50 for `fixed:pro`, and $1 to $2 for the judge. The `--max-spend-usd` default of 3.0 is per invocation; a full six-strategy run needs about three invocations or a raised ceiling.
- The judge scoring `fixed:pro` outputs with a `pro` judge is a known self-preference bias. Report it in the page's footnote; do not correct for it.
- `eval/results/` is gitignored except `eval/results/latest/summary.json`, which is committed so the report page can be rebuilt without rerunning.
- The seed tasks reference portfolio domains: rubric text from `synthetic-student-generator/backend/app/data/`, diagram prompts from `diagram-as-code-architect`, handbook Q&A from `classroom-clarity`. Copy short excerpts into the seed file; do not import those projects.
- The report page follows the artifact CDN rule used elsewhere in the portfolio: scripts only from cdnjs, everything else inline.

**Integration points**
- New: `eval/` tree as above, `report/template.html`, `report/index.html` (generated, committed), `report/data.json` (generated, committed), `firebase.json`, `.firebaserc`.
- `scripts/deploy.sh` gains the `report` target.
- Docs: `docs/local-testing-guide.md` (how to run a cheap `--limit 20` eval), `docs/production-deployment.md` (report hosting, eval budget note), `README.md` (`## Results` section with the latest `summary.json` headline numbers and the report URL; success criteria updated), `AGENTS.md` (eval commands), `.gitignore`.
- `requirements-eval.txt`: `httpx`, `jsonschema`, `numpy` (percentiles). No plotting libraries.

**Patterns to follow**
- Script style: `synthetic-student-generator/backend/scripts/test_gemini.py` (plain argparse scripts).
- Firebase Hosting config: `firebase.json` (`cleanUrls`, no SPA rewrite).

## Acceptance Criteria

- [ ] (R1, R2) `python eval/scripts/validate_golden.py` exits 0 on the shipped set and prints counts per tier and category; `eval/tests/test_validate_golden.py::test_rejects_bad_distribution` and `test_rejects_duplicate_ids` pass.
- [ ] (R3) `eval/tests/test_run_eval.py::test_records_error_lines_and_continues` — a fake gateway returning 502 for one item yields a line with `error` set and the run completes.
- [ ] (R3) `test_spend_ceiling_aborts` — fake responses costing 1.0 each with `--max-spend-usd 2.5` produce exactly 3 lines.
- [ ] (R4) `eval/tests/test_judge.py::test_parses_score_and_null_on_error`.
- [ ] (R5) `eval/tests/test_report.py::test_metrics_from_fixture` — fixture results for two strategies produce `quality_retention`, `cost_ratio_vs_pro`, `routing_accuracy`, `escalation_rate`, `tier_mix`, and percentiles equal to hand-computed values in the test.
- [ ] (R5) `test_refuses_partial_without_flag` and `test_partial_flag_stamps_summary`.
- [ ] (R6) `grep -n "cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1" report/template.html` hits; `grep -c "<script src=" report/template.html` equals 1.
- [ ] (R7) `grep -n "router-report" firebase.json scripts/deploy.sh` hits both.
- [ ] (R8) `eval/tests/test_run_eval.py::test_cache_replay_hit_rate` — fake gateway reporting hits on the second pass yields `cache_hit_rate_second_pass == 1.0`.
- [ ] `cd eval && pytest` exits 0 and `cd backend && pytest` still exits 0.
- [ ] `README.md` has a `## Results` section citing `eval/results/latest/summary.json` values and the report URL; docs updated per Integration points.

## Verification

1. `cd eval && pytest -q` → exit 0.
2. Cheap live run against the deployed gateway: `python eval/run_eval.py --base-url https://thrifty-router-<hash>-uc.a.run.app --api-key $KEY --strategies fixed:lite,cascade --limit 20 --max-spend-usd 0.5 --out eval/results/smoke`, then `python eval/judge.py --results eval/results/smoke --max-spend-usd 0.5`, then `python eval/report.py --results eval/results/smoke --allow-partial` → `summary.json` has both strategies with `n == 20`, `partial: true`, and `report/index.html` opens in a browser showing two points on the scatter.
3. `bash scripts/deploy.sh report` → `https://thrifty-router.web.app` renders the chart.

## Do NOT

- Do not call Vertex AI directly from the eval scripts; every model call goes through the gateway so the ledger sees it.
- Do not add promptfoo, deepeval, ragas, pandas, matplotlib, or a frontend framework.
- Do not commit raw `responses.jsonl` or `judgments.jsonl`.
- Do not modify gateway behavior in this phase (except raising `DAILY_BUDGET_USD` by deploy config).
- Do not treat the quality hypothesis (cascade at or above 0.90 retention under 0.50 cost ratio) as an acceptance gate; report whatever the numbers are.

## Dependencies

**Requires:** Phase 1 (gateway and `fixed`), Phase 2 (`semantic`, `classifier`), Phase 3 (`cascade`), Phase 4 (`use_cache` field and cache replay).
**Blocks:** Phase 6.

## Out of Scope

- Human preference labeling.
- Pairwise judging or Elo.
- Scheduled re-runs.
