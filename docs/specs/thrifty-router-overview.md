# Thrifty Router — Feature Overview

**Date:** 2026-09-08
**Project:** `thrifty-router` (new, `/Users/king/dev/jrk-ai-labs/thrifty-router`)
**Phase specs:** [1 Gateway core](thrifty-router-phase-1-gateway-core.md) · [2 Pre-routing strategies](thrifty-router-phase-2-pre-routing-strategies.md) · [3 Cascade](thrifty-router-phase-3-cascade.md) · [4 Semantic cache](thrifty-router-phase-4-semantic-cache.md) · [5 Eval harness](thrifty-router-phase-5-eval-harness.md) · [6 Labs site registration](thrifty-router-phase-6-labs-site-registration.md)

---

## Feature

A Cloud Run gateway in front of three Gemini tiers (Flash-Lite, Flash, Pro) that picks a tier per request using one of several strategies, accounts cost per request, caches semantically similar prompts, and ships with an evaluation harness that scores every strategy on a golden set with an LLM judge and publishes a cost-versus-quality report.

**One-line summary for the README:** Route each prompt to the cheapest Gemini model that can answer it, and prove it with numbers.

## Decisions made during spec'ing (not discoverable from the repo)

| Decision | Choice | Why |
|---|---|---|
| Language and layout | Python 3.13, FastAPI, `google-genai` with the Vertex AI backend, `backend/app/{main,config,rate_limit,dependencies}.py` layout | Newest Python project convention (`synthetic-student-generator/backend/`). Firestore vector search client support is Python and Node only. |
| API shape | Custom `POST /api/v1/complete` with routing metadata in the body, `X-API-Key` auth | Small explicit contract. Auth pattern from `fin-ops-advisor/internal/middleware/auth.go`, using a constant-time compare. |
| Tiers | `lite` = `gemini-3.1-flash-lite-preview`, `standard` = `gemini-3-flash-preview`, `pro` = `gemini-3.1-pro-preview`, all via Vertex AI, all config-driven in `router.yaml` | IDs already used in the portfolio (`fin-ops-advisor/internal/agent/orchestrator.go:39`, `vision-first-study-buddy/backend/app/config.py:27`). Prices as of 2026-09-08: lite $0.25/$1.50, standard $0.50/$3.00, pro $2.00/$12.00 per 1M input/output tokens. Thinking tokens bill as output. |
| Strategies | `fixed`, `semantic`, `classifier`, `cascade` | Covers the three families in the 2026 literature: embedding routers, LLM classifiers, cheap-first cascades. |
| Cascade verifier | Self-reported confidence line for text, JSON-schema validation for structured requests | Zero extra model calls. A separate judge call would double the cost of the cheap path. |
| Semantic cache | Firestore vector search, cosine, similarity at least 0.95, 24-hour TTL, only for `temperature <= 0.3` | First Firestore vector use in the portfolio; no new infrastructure. |
| Golden set | About 300 prompts synthesized with Pro from 24 hand-written seed tasks modeled on portfolio projects, hand-reviewed | On-brand, cheap, no license questions. |
| Judge | `gemini-3.1-pro-preview`, temperature 0, 1 to 5 rubric score | Strongest available tier. Judge cost is reported separately. |
| UI | Static eval report page only, on Firebase Hosting | No playground, so no key-hiding proxy needed. |
| Spend guardrails | `X-API-Key`, per-IP rate limits, in-process daily budget with a hard stop, `--max-instances 1`, eval runner spend ceiling | Same posture as every other project (`vision-first-study-buddy/AGENTS.md` security posture). |

## Phase breakdown

| Phase | Delivers | Requires |
|---|---|---|
| 1 — Gateway core | Project skeleton, `fixed` strategy, cost ledger, auth, limits, budget, deploy, docs skeleton | None |
| 2 — Pre-routing strategies | `semantic` and `classifier` | Phase 1 (extends the `strategy` enum and attempts contract) |
| 3 — Cascade | `cascade` with verifier and escalation | Phase 1 |
| 4 — Semantic cache | Firestore vector cache, `cache` response field | Phase 1; reuses the embedder from Phase 2 if present, otherwise adds it |
| 5 — Eval harness | Golden set, runner, judge, report page | Phases 1 to 4 (evaluates every strategy and reports cache separately) |
| 6 — Labs site registration | Portfolio entry, images, sitemap, llms.txt | Phase 5 (needs the report URL and screenshot) |

## Dependency graph

```
Phase 1 ──┬──► Phase 2 ──┐
          ├──► Phase 3 ──┼──► Phase 5 ──► Phase 6
          └──► Phase 4 ──┘
```
Phases 2, 3, and 4 are independent of each other and can run in parallel after Phase 1 merges.

## Project bootstrap (applies to Phase 1)

- Directory `thrifty-router/` at the repo-collection root, sibling of `synthetic-student-generator/`.
- Initialize a git repository; the GitHub remote is created by the user, not the implementer.
- House files: `README.md` (structure of `synthetic-student-generator/README.md` plus a `## Tech Stack` table and a `## Project` block as in `fin-ops-advisor/README.md`), `AGENTS.md` (section order of `synthetic-student-generator/AGENTS.md`), `CLAUDE.md` (one-line pointer), `docs/README.md`, `docs/architecture.md`, `docs/api-contracts.md`, `docs/milestones.md`, `docs/local-dev-guide.md`, `docs/local-testing-guide.md`, `docs/production-deployment.md`.
- GCP: project `<your-gcp-project-id>`, region `us-central1`, service `thrifty-router`, service account `thrifty-router-sa@<your-gcp-project-id>.iam.gserviceaccount.com` with `roles/aiplatform.user` (and `roles/datastore.user` from Phase 4).

## External facts the implementer should re-verify before starting

- Model IDs and prices on Vertex AI: https://cloud.google.com/vertex-ai/generative-ai/pricing and https://docs.cloud.google.com/vertex-ai/generative-ai/docs/release-notes. Gemini 2.5 models retire 2026-10-16; none are used here.
- Thinking tokens are billed at the output rate (both `cloudzero.com/blog/gemini-pricing` and the Vertex pricing page).
- `gemini-embedding-001` on Vertex: supports `output_dimensionality`; vectors below 3072 dimensions must be L2-normalized by the caller. https://ai.google.dev/gemini-api/docs/embeddings
- Firestore vector search: `find_nearest(vector_field, query_vector, distance_measure, limit, distance_result_field, distance_threshold)`, cosine distance in [0, 2], max 2048 dimensions, pre-filters allowed with a composite index. https://docs.cloud.google.com/firestore/native/docs/vector-search
