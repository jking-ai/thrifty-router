# Thrifty Router Phase 2: Pre-Routing Strategies — Design Spec

**Date:** 2026-09-08
**Part of:** [Thrifty Router overview](thrifty-router-overview.md)

---

## What This Phase Delivers

Two strategies that choose a tier before the completion call: `semantic` (embedding similarity against example utterances) and `classifier` (a Flash-Lite call that labels the prompt's difficulty).

**Why:** These are the two dominant "route first" families; the eval harness needs both to compare against the cascade.

## Architecture

```
strategy=semantic:  Embedder.embed(prompt) → cosine vs. route utterance embeddings (built at startup)
                    → best route score >= threshold ? route.tier : default_tier → completion
strategy=classifier: GeminiTierClient.generate(lite, classifier prompt, json_schema) → {"tier","reason"}
                    → tier (fallback default_tier on error) → completion
```

## Requirements

1. `strategy` enum gains `semantic` and `classifier`; `/api/v1/health` lists them.
2. `semantic`: routes and threshold from `router.yaml` (Contracts). Route utterance embeddings are computed once, lazily on the first semantic request, and held in memory. Prompt embedding uses the same embedder. Score per route is the maximum cosine similarity over its utterances. Selected tier is the best route's tier when its score is at least `semantic.threshold`, otherwise `default_tier`.
3. `classifier`: one call to the tier named `classifier.tier` with `backend/app/prompts/classifier_template.txt` and the JSON schema in Contracts. The call is recorded as an attempt with `role: "classifier"` and counted in `usage`. Any failure or an unknown tier in the reply falls back to `default_tier` with `reason` starting with `classifier_error:`.
4. An `Embedder` abstraction injected via a dependency (`get_embedder`) so tests use a fake. Production implementation: `gemini-embedding-001` on Vertex via `google-genai`, `output_dimensionality=768`, `task_type="SEMANTIC_SIMILARITY"`, L2-normalized in code.
5. `routing.reason` strings exactly as in Contracts.

**Permissions:** Unchanged.

**Error behavior:** Embedding failure on a `semantic` request: 502 `EMBEDDING_ERROR`. Classifier failure never fails the request (falls back). Everything else as Phase 1.

## Contracts

### `router.yaml` additions

```yaml
semantic:
  threshold: 0.60
  routes:
    - name: simple_lookup
      tier: lite
      utterances:
        - "What is the capital of France?"
        - "Convert 5 miles to kilometers"
    - name: structured_extraction
      tier: standard
      utterances:
        - "Extract the rubric dimensions from this text into JSON"
    - name: deep_reasoning
      tier: pro
      utterances:
        - "Analyze this Terraform module and explain the security implications of each resource"
classifier:
  tier: lite
```
Rules: at least one route, each with a unique `name`, a tier from the table, and at least one utterance. `threshold` in `0.0..1.0`. The shipped file must contain at least 8 utterances per tier, drawn from the task categories in Phase 5's seed list (`rubric_parse`, `diagram_gen`, `doc_qa`, `classify`, `summarize`, `code_explain`, `math_reasoning`, `creative`).

### `routing.reason`

| Strategy | Reason |
|---|---|
| semantic, matched | `semantic route=<name> score=<0.000>` |
| semantic, below threshold | `semantic no_match best=<name> score=<0.000> default=<tier>` |
| classifier, ok | `classifier tier=<tier>: <model reason, <= 200 chars>` |
| classifier, fallback | `classifier_error: <exception class or 'unknown_tier'> default=<tier>` |

### Classifier response schema

```json
{"type":"object","properties":{"tier":{"type":"string","enum":["lite","standard","pro"]},"reason":{"type":"string"}},"required":["tier","reason"]}
```
The enum is generated from the tier table at startup, not hard-coded.

### `backend/app/prompts/classifier_template.txt`

Placeholders: `{tier_descriptions}` (one line per tier: name, model, one-phrase intended use from a new optional `description` key per tier in `router.yaml`, defaulting to the tier name) and `{prompt}` (truncated to the first 4000 characters). Required stated rule: pick the cheapest tier that can answer with high quality; prefer `lite` for lookup, formatting, and short classification; `standard` for extraction and multi-step but bounded tasks; `pro` for long reasoning, code analysis, and open-ended synthesis.

### Attempt for the classifier call

Same `Attempt` shape as Phase 1 with `role: "classifier"`, `accepted: true`, `reject_reason: null`. It precedes the completion attempt in `attempts`.

### Config additions

| Field | Env var | Type | Default |
|---|---|---|---|
| `embedding_model` | `EMBEDDING_MODEL` | str | `"gemini-embedding-001"` |
| `embedding_dimensions` | `EMBEDDING_DIMENSIONS` | int | `768` |

Internal design is implementer's choice provided these contracts hold.

## Technical Notes

**Non-discoverable context**
- `gemini-embedding-001` returns unnormalized vectors below 3072 dimensions; cosine on unnormalized vectors is still correct, but the Phase 4 cache uses Firestore cosine distance and stores the same vectors, so normalize once here and everywhere.
- Embedding cost is small (Vertex lists it per 1K characters); it is not part of `usage` because it is not a tier call. Log it in the request log line as `embedding_calls` (int) instead.
- Building route embeddings lazily avoids paying for them on every cold start of a service that mostly serves `fixed` and `cascade`.

**Integration points**
- `backend/app/services/router.py` (register two strategies), new `backend/app/services/embedder.py`, `backend/app/services/strategies/semantic.py`, `backend/app/services/strategies/classifier.py`, `backend/app/prompts/classifier_template.txt`, `backend/app/router.yaml`, `backend/app/dependencies.py` (`get_embedder`), `backend/app/config.py`.
- Docs: `docs/api-contracts.md` (strategy enum, reasons, classifier attempt), `docs/architecture.md` (strategy section), `AGENTS.md` (env vars), `backend/.env.example`.

**Patterns to follow**
- Dependency injection and fakes: Phase 1 `get_tier_client`.
- Prompt file loading: `vision-first-study-buddy/backend/app/services/quiz_generator.py` `_build_prompt` reading `prompts/quiz_template.txt`.

## Acceptance Criteria

- [ ] (R2) `backend/tests/test_semantic.py::test_picks_route_above_threshold` — fake embedder returns unit vectors such that the `pro` route scores 0.9; response `routing.tier == "pro"` and `reason == "semantic route=deep_reasoning score=0.900"`.
- [ ] (R2) `test_falls_back_below_threshold` — best score 0.3; tier is `default_tier`, reason matches `^semantic no_match best=\S+ score=0\.300 default=lite$`.
- [ ] (R2) `test_route_embeddings_built_once` — two requests, fake embedder's utterance-embed call count equals the number of utterances, not double.
- [ ] (R4) `test_embedder_normalizes` — production `Embedder` wrapper with a stubbed SDK response `[3, 4]` yields `[0.6, 0.8]`.
- [ ] (R3) `backend/tests/test_classifier.py::test_classifier_selects_tier` — fake returns `{"tier":"standard","reason":"extraction"}`; `attempts[0].role == "classifier"`, `attempts[1].tier == "standard"`, `usage` sums both attempts, reason starts with `classifier tier=standard:`.
- [ ] (R3) `test_classifier_error_falls_back` — fake raises; tier is `lite`, reason starts with `classifier_error:`, response is 200.
- [ ] (R3) `test_classifier_unknown_tier_falls_back` — fake returns `{"tier":"ultra",...}`; reason contains `unknown_tier`.
- [ ] (R1) `test_health_lists_strategies` — `strategies == ["fixed","semantic","classifier"]`.
- [ ] `backend/tests/test_config.py::test_router_yaml_semantic_routes_valid` — shipped `router.yaml` has at least 8 utterances per tier and unique route names.
- [ ] `cd backend && pytest` exits 0; docs updated per Integration points.

## Verification

1. `cd backend && pytest -q` → exit 0.
2. Against a local server with ADC: `curl -s -X POST localhost:8000/api/v1/complete -H "X-API-Key: dev" -H "Content-Type: application/json" -d '{"prompt":"What is 12 times 9?","strategy":"semantic"}'` → `routing.tier` is `lite` and `reason` starts with `semantic route=`. Same prompt with `"strategy":"classifier"` → two attempts, first with `role` `classifier`.

## Do NOT

- Do not implement `cascade` (Phase 3) or caching (Phase 4).
- Do not cache route embeddings on disk or in Firestore.
- Do not add the `semantic-router` PyPI package or any vector library; cosine over lists with `math` or `numpy` only (`numpy` is allowed as the single new dependency).
- Do not change the Phase 1 response shape except adding the `classifier` attempt role.

## Dependencies

**Requires:** Phase 1 (strategy registry, attempts contract, tier client).
**Blocks:** Phase 5.

## Out of Scope

- Learned classifiers trained on the golden set.
- Per-route thresholds.
