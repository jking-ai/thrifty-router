# Thrifty Router Phase 6: Labs Site Registration — Design Spec

**Date:** 2026-09-08
**Part of:** [Thrifty Router overview](thrifty-router-overview.md)

---

## What This Phase Delivers

Thrifty Router appears on https://labs.jking.ai with a project page, gallery card, images, and the machine-readable listings the site maintains.

**Why:** The portfolio site is the front door; an unlisted project does not exist.

## Requirements

1. New entry in `labs-portfolio/src/data/projects.js` with every field in Contracts, appended after the last existing entry.
2. Images under `labs-portfolio/public/images/projects/`: `thrifty-router.png` (screenshot of the deployed report page, 1600 px wide) and `thrifty-router-architecture.svg` (request pipeline with strategies, cache, ledger) and `thrifty-router-eval-pipeline.svg` (golden set, runner, judge, report). SVGs are hand-authored or exported, under 200 KB each, with a transparent background.
3. `labs-portfolio/public/llms.txt` gains a bullet under `## Pages` and a topic line under `## Key Topics`.
4. `labs-portfolio/public/sitemap.xml` gains `https://labs.jking.ai/projects/thrifty-router`.
5. `labs-portfolio/projects/ideas.md` gains a section `### 6. Thrifty Router (The Cost Optimizer)` in the existing format.
6. Hand-maintained page counts in `labs-portfolio/AGENTS.md` and `labs-portfolio/README.md` are incremented.

**Permissions:** Not applicable.

**Error behavior:** Not applicable; a failed `npm run build` is the failure signal.

## Contracts

### `projects.js` entry

```js
{
  id: 'thrifty-router',
  title: 'Thrifty Router',
  subtitle: 'Route each prompt to the cheapest Gemini model that can answer it, and prove it with numbers.',
  desc: 'A Cloud Run gateway that picks a Gemini tier per request (semantic, classifier, or cascade), caches near-duplicate prompts in Firestore, and publishes a cost-versus-quality report from an LLM-judged golden set.',
  img: '/images/projects/thrifty-router.png',
  heroImg: '/images/projects/thrifty-router.png',
  status: 'Live',
  statusClass: 'status-live',
  tags: ['Python', 'FastAPI', 'Model Routing', 'LLM Evals', 'Firestore', 'Gemini'],
  liveUrl: 'https://thrifty-router.web.app',
  githubUrls: [{ label: 'Source', url: '<set by user when the remote exists>' }],
  overview: '<2-4 sentences>',
  problem: '<2-4 sentences>',
  approach: '<2-4 sentences>',
  techStack: [
    { icon: 'alt_route', color: 'teal', title: 'Routing strategies', desc: 'fixed, semantic (gemini-embedding-001), classifier (Flash-Lite), cascade with cost-free verification' },
    { icon: 'savings', color: 'green', title: 'Cost ledger', desc: 'Per-attempt cost from usage metadata, thinking tokens billed as output, daily budget stop' },
    { icon: 'cached', color: 'blue', title: 'Semantic cache', desc: 'Firestore vector search, cosine 0.95, 24h TTL' },
    { icon: 'fact_check', color: 'orange', title: 'Eval harness', desc: '300-item golden set, Pro judge, cost-vs-quality report' },
    { icon: 'cloud', color: 'teal', title: 'Cloud Run + Firebase Hosting', desc: 'Scale-to-zero gateway, static report' },
  ],
  diagrams: [
    { title: 'Request pipeline', desc: 'Auth, limits, budget, strategy, tier client, ledger', img: '/images/projects/thrifty-router-architecture.svg' },
    { title: 'Eval pipeline', desc: 'Seed tasks to golden set to judged report', img: '/images/projects/thrifty-router-eval-pipeline.svg' },
  ],
  highlights: [<8-10 strings, each under 60 characters, including the headline numbers from eval/results/latest/summary.json: quality retention and cost ratio for cascade>],
  effort: 'Medium',
  lang: 'Python',
}
```
Tags `Python` and `FastAPI` are mandatory so the gallery's PYTHON chip matches (`labs-portfolio/src/pages/gallery.astro` `categoriesFor()`); other tags are free text.

### `llms.txt` additions

- Under `## Pages`: `- [Thrifty Router](https://labs.jking.ai/projects/thrifty-router): Cost-aware Gemini model router with semantic cache and an LLM-judged eval report (Python, FastAPI, Cloud Run, Firestore)`
- Under `## Key Topics`: `- LLM model routing, cascades, semantic caching, and eval-driven cost/quality measurement`

### `ideas.md` section

Same shape as the existing five: Focus, Primary Language, Tech Stack (API, LLM, Data, UI), Engineering Flex, Research Topics (two links: the Vertex pricing page and the Firestore vector search doc), Level of Effort `Medium`.

Internal design is implementer's choice provided these contracts hold.

## Technical Notes

**Non-discoverable context**
- `public/.well-known/mcp.json` does not enumerate projects; no change there (`labs-portfolio/AGENTS.md` lists exactly the three files to update).
- The site has no CI; verification is a local build and a manual look at the page.
- Screenshot the report page after Phase 5's deploy, in a 1600 px wide window, light theme.

**Integration points**
- `labs-portfolio/src/data/projects.js`, `public/llms.txt`, `public/sitemap.xml`, `public/images/projects/`, `projects/ideas.md`, `AGENTS.md`, `README.md`.

**Patterns to follow**
- Entry shape: the `adk-enterprise-agent-platform` and `webmcp-portfolio` entries in `projects.js`.
- Image naming: `ssg-architecture-v2.svg`, `ssg-generation-pipeline.svg`.

## Acceptance Criteria

- [ ] (R1) `node -e "import('./src/data/projects.js').then(m=>{const p=m.projects.find(p=>p.id==='thrifty-router');if(!p)process.exit(1);for(const k of ['title','subtitle','desc','img','heroImg','status','statusClass','tags','liveUrl','overview','problem','approach','techStack','diagrams','highlights','effort','lang'])if(p[k]==null)process.exit(2)})"` run in `labs-portfolio/` exits 0.
- [ ] (R1) `grep -n "'Python'" labs-portfolio/src/data/projects.js` shows the tag in the new entry.
- [ ] (R2) `ls labs-portfolio/public/images/projects/thrifty-router.png labs-portfolio/public/images/projects/thrifty-router-architecture.svg labs-portfolio/public/images/projects/thrifty-router-eval-pipeline.svg` lists all three.
- [ ] (R3, R4) `grep -n "projects/thrifty-router" labs-portfolio/public/llms.txt labs-portfolio/public/sitemap.xml` hits both.
- [ ] (R5) `grep -n "### 6. Thrifty Router" labs-portfolio/projects/ideas.md` hits.
- [ ] `cd labs-portfolio && npm run build` exits 0 and `ls dist/projects/thrifty-router/index.html` exists.
- [ ] (R6) Page counts in `labs-portfolio/AGENTS.md` and `README.md` equal the number of entries in `projects.js` plus the fixed pages listed there.

## Verification

1. `cd labs-portfolio && npm run build && npx serve dist` (or `npm run preview`) → open `/projects/thrifty-router` and `/gallery`, filter by PYTHON. Expected observation: the card appears under PYTHON, the detail page shows both diagrams and the screenshot, and the live link opens the report.
2. `firebase deploy --only hosting --project labs-portfolio` from `labs-portfolio/` → https://labs.jking.ai/projects/thrifty-router returns 200.

## Do NOT

- Do not change `gallery.astro` category matching.
- Do not touch `mcp.json`.
- Do not restyle `ProjectCard.astro` or the detail page.
- Do not edit other projects' entries.

## Dependencies

**Requires:** Phase 5 (report URL, headline numbers, screenshot).
**Blocks:** None.

## Out of Scope

- A blog post or write-up beyond the project page.
