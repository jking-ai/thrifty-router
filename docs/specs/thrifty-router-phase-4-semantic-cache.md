# Thrifty Router Phase 4: Semantic Cache — Design Spec

**Date:** 2026-09-08
**Part of:** [Thrifty Router overview](thrifty-router-overview.md)

---

## What This Phase Delivers

A Firestore-backed cache that returns a stored answer for an identical or semantically near-identical prompt, skipping the model call entirely, and reports hits in the response.

**Why:** Caching is the other half of cost optimization and this is the portfolio's first use of Firestore vector search.

## Architecture

```
POST /complete (cache enabled, use_cache true, temperature <= 0.3)
  → key = sha256(normalize(prompt) | system | json_schema | strategy-independent)
  → exact: doc thrifty_cache/<key> exists and not expired → HIT exact
  → semantic: Embedder.embed(prompt) → find_nearest(cosine, limit 1, distance_threshold, prefilter system_hash+schema_hash)
       → distance <= 1 - threshold → HIT semantic
  → MISS → run strategy → on 200 with accepted attempt: write doc (fire-and-forget, errors logged)
```

## Requirements

1. New top-level `cache` block in `router.yaml` and `CACHE_ENABLED` flag (Contracts). When disabled, behavior is identical to Phase 3 except the response gains `"cache":{"hit":false,"kind":null,"similarity":null}`.
2. Request field `use_cache` (bool, default `true`). Cache lookups and writes happen only when `CACHE_ENABLED` is true, `use_cache` is true, and `temperature <= cache.max_temperature`.
3. Lookup order: exact key, then semantic nearest neighbor. Semantic candidates must share `system_hash` and `schema_hash` (pre-filter) and have cosine similarity at least `cache.similarity_threshold`.
4. On a hit: `output` is the stored output; `routing.strategy` is the requested strategy; `routing.tier` and `routing.model` are the stored values; `routing.attempts` is `[]`; `routing.reason` is `cache hit exact` or `cache hit semantic similarity=<0.000>`; `usage` is all zeros; `cache.hit` true with `kind` and `similarity` (`1.0` for exact). The ledger is not charged. `hit_count` on the document is incremented.
5. On a miss with a 200 response, one document is written (Contracts). Writes never block the response and never fail it.
6. Expired documents (`expires_at` in the past) are treated as misses. A Firestore TTL policy on `expires_at` is documented and created by the deploy docs, not by code.
7. `CacheStore` abstraction injected via `get_cache_store` so tests use an in-memory fake; production uses `google-cloud-firestore` with `find_nearest`.
8. `GET /api/v1/usage` gains `cache: {"lookups": n, "hits_exact": n, "hits_semantic": n}` for the day.

**Permissions:** Unchanged.

**Error behavior:** Any Firestore or embedding error during lookup is logged with `event: "cache_error"` and treated as a miss; the request proceeds. Write errors are logged the same way.

## Contracts

### `router.yaml` additions

```yaml
cache:
  similarity_threshold: 0.95
  ttl_hours: 24
  max_temperature: 0.3
  collection: thrifty_cache
```

### Config additions

| Field | Env var | Type | Default |
|---|---|---|---|
| `cache_enabled` | `CACHE_ENABLED` | bool | `False` |
| `firestore_database` | `FIRESTORE_DATABASE` | str | `"(default)"` |

### Request addition

`"use_cache": true` (optional, default `true`).

### Response addition

```json
"cache": {"hit": true, "kind": "semantic", "similarity": 0.973}
```
`kind` enum: `exact`, `semantic`, `null`.

### Firestore document `thrifty_cache/<key>`

| Field | Type | Notes |
|---|---|---|
| `key` | string | sha256 hex of `normalize(prompt) + "\x1f" + (system or "") + "\x1f" + canonical_json(json_schema or null)`. `normalize` = strip, collapse internal whitespace runs to one space, lowercase. |
| `system_hash` | string | sha256 of `system or ""`. |
| `schema_hash` | string | sha256 of canonical JSON of `json_schema` or `"null"`. |
| `prompt_embedding` | Vector(768) | L2-normalized, from Phase 2's `Embedder`. |
| `prompt_preview` | string | First 200 characters of the original prompt. |
| `output` | string | |
| `tier` | string | |
| `model` | string | |
| `strategy` | string | Strategy that produced it. |
| `created_at` | timestamp | |
| `expires_at` | timestamp | `created_at + ttl_hours`. |
| `hit_count` | int | Starts at 0. |

Vector index (documented in `docs/production-deployment.md`, run once):
```bash
gcloud firestore indexes composite create \
  --project=YOUR_GCP_PROJECT --database='(default)' \
  --collection-group=thrifty_cache --query-scope=COLLECTION \
  --field-config=field-path=system_hash,order=ASCENDING \
  --field-config=field-path=schema_hash,order=ASCENDING \
  --field-config=field-path=prompt_embedding,vector-config='{"dimension":"768","flat":"{}"}'
```
TTL policy: `gcloud firestore fields ttls update expires_at --collection-group=thrifty_cache --enable-ttl --project=YOUR_GCP_PROJECT`.

Semantic query: `collection.where("system_hash","==",h).where("schema_hash","==",s).find_nearest(vector_field="prompt_embedding", query_vector=Vector(v), distance_measure=DistanceMeasure.COSINE, limit=1, distance_result_field="distance", distance_threshold=1 - similarity_threshold)`. `similarity = 1 - distance`.

### Log lines

- Hit: request log line gains `"cache_hit": "exact" | "semantic" | null` and `"cache_similarity": <float|null>`.
- Error: `{"event":"cache_error","stage":"lookup"|"write","error":"<class>: <message>"}`.

Internal design is implementer's choice provided these contracts hold.

## Technical Notes

**Non-discoverable context**
- Firestore cosine distance ranges 0 to 2; `distance_threshold` is a distance, so the threshold is `1 - similarity`.
- Pre-filtering on two equality fields plus the vector requires the composite index above; without it Firestore returns an error whose message contains the exact index-creation command. Capture that in the deploy docs.
- The cache is strategy-independent on purpose: a `pro` answer cached under `fixed` is returned to a later `cascade` request. That is the desired behavior (best available answer, zero cost) and is why `tier` is stored.
- Firestore free tier covers this comfortably at demo volumes; no cost guard beyond TTL is needed.
- The service account needs `roles/datastore.user`.

**Integration points**
- `backend/app/services/cache_store.py` (new), `backend/app/services/cache.py` (key, lookup, write orchestration), `backend/app/routers/complete.py`, `backend/app/dependencies.py`, `backend/app/config.py`, `backend/app/router.yaml`, `backend/app/models/{requests,responses}.py`.
- `requirements.txt`: add `google-cloud-firestore>=2.16`.
- Docs: `docs/api-contracts.md`, `docs/production-deployment.md` (index, TTL, IAM), `docs/architecture.md`, `AGENTS.md`, `backend/.env.example`, `backend/scripts/smoke.sh` (two identical calls show the second as a hit).
- If Phase 2 has not merged when this phase starts, this phase adds `Embedder` and `get_embedder` exactly as Phase 2 specifies them, and Phase 2 then reuses them.

**Patterns to follow**
- Fake store in tests: same injection shape as `get_tier_client`.
- Firestore client wrapper style: `sentry-go/internal/gcp/firestore.go` (thin wrapper, collection name from config), translated to Python.

## Acceptance Criteria

- [ ] (R3, R4) `backend/tests/test_cache.py::test_exact_hit` — second identical request returns `cache.kind == "exact"`, `attempts == []`, `usage.total_cost_usd == 0`, fake tier client call count unchanged, fake store `hit_count` is 1.
- [ ] (R3) `test_semantic_hit_above_threshold` — fake embedder gives similarity 0.97 to a stored doc with matching hashes; `kind == "semantic"`, `similarity == 0.97`, reason `cache hit semantic similarity=0.970`.
- [ ] (R3) `test_semantic_miss_below_threshold` — similarity 0.90 → miss, model called.
- [ ] (R3) `test_semantic_prefilter_excludes_other_system` — same prompt, different `system` → miss.
- [ ] (R2) `test_high_temperature_skips_cache` — `temperature 0.9` → no lookup, no write (fake store call counts zero).
- [ ] (R2) `test_use_cache_false_skips_cache`.
- [ ] (R1) `test_cache_disabled_response_shape` — `cache == {"hit": false, "kind": null, "similarity": null}` and store never called.
- [ ] (R5) `test_write_after_miss` — fake store receives one document with every field in Contracts; `expires_at - created_at == 24h`.
- [ ] (R6) `test_expired_doc_is_miss`.
- [ ] Error path: `test_store_error_is_miss_and_logged` — fake store raises on lookup; response 200 from the model; stdout has a `cache_error` line with `stage == "lookup"`.
- [ ] (R8) `test_usage_cache_counters`.
- [ ] `grep -n "find_nearest" backend/app/services/cache_store.py` hits.
- [ ] `cd backend && pytest` exits 0; docs updated per Integration points.

## Verification

1. `cd backend && pytest -q` → exit 0.
2. With `CACHE_ENABLED=true`, ADC, index and TTL created: run `bash backend/scripts/smoke.sh` → the second of two identical `/complete` calls prints `"kind": "exact"`; a third call with the same prompt reworded (`"What's the capital city of France?"` after `"What is the capital of France?"`) prints `"kind": "semantic"` with `similarity` at least 0.95, or `"hit": false` if the embedder places it below threshold (both are valid; the observation is that no error occurs and the field is populated).
3. `curl .../api/v1/usage -H "X-API-Key: ..."` → `cache.lookups` at least 3.

## Do NOT

- Do not cache error responses or rejected cascade attempts.
- Do not cache when `temperature > cache.max_temperature`.
- Do not add Memorystore, Redis, or an in-process LRU as a second layer.
- Do not create the index or TTL policy from application code.
- Do not change any Phase 1 to 3 reason strings or attempt shapes.

## Dependencies

**Requires:** Phase 1 (request pipeline, ledger, usage endpoint). Reuses Phase 2's `Embedder` when present.
**Blocks:** Phase 5 (the runner disables the cache per request and reports it separately).

## Out of Scope

- Cache invalidation API.
- Per-key or per-tenant cache partitions.
