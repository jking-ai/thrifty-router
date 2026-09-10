#!/usr/bin/env python3
"""Synthesize candidate golden set items from seed tasks using the Pro tier."""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List
import httpx


async def synthesize_candidates(
    base_url: str,
    api_key: str,
    per_seed: int,
    out_path: str,
) -> None:
    seed_file = "eval/golden/seed_tasks.md"
    if not os.path.exists(seed_file):
        print(f"Error: Seed file not found at {seed_file}", file=sys.stderr)
        sys.exit(1)

    with open(seed_file, "r", encoding="utf-8") as f:
        seed_content = f.read()

    prompt = f"""You are generating evaluation dataset items for an LLM routing benchmark based on these seed tasks:
{seed_content}

Generate variations for these seeds. For each item, output a JSON object with:
- category: one of [rubric_parse, diagram_gen, doc_qa, classify, summarize, code_explain, math_reasoning, creative]
- expected_tier: one of [lite, standard, pro]
- prompt: the test prompt text
- rubric: grading criteria what a 5/5 answer must contain
- source: "synth:run"

Generate a JSON array of items.
"""

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "strategy": "fixed",
        "tier": "pro",
        "temperature": 0.3,
        "max_output_tokens": 4096,
    }

    print(f"Calling gateway {base_url}/api/v1/complete to synthesize candidates...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{base_url}/api/v1/complete", headers=headers, json=payload)
        if resp.status_code != 200:
            print(f"Gateway error {resp.status_code}: {resp.text}", file=sys.stderr)
            sys.exit(1)
        data = resp.json()
        raw_output = data.get("output", "")

    try:
        items = json.loads(raw_output)
        if not isinstance(items, list):
            items = [items]
    except Exception:
        # Fallback to empty candidate set if model didn't return pure JSON
        items = []

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for idx, item in enumerate(items, 1):
            item["id"] = f"cand_{idx:04d}"
            item["reviewed"] = False
            item["system"] = item.get("system")
            item["json_schema"] = item.get("json_schema")
            item["reference"] = item.get("reference")
            f.write(json.dumps(item) + "\n")

    print(f"✓ Wrote {len(items)} candidate items to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Synthesize candidate golden set items.")
    parser.add_argument("--base-url", required=True, help="Gateway base URL")
    parser.add_argument("--api-key", required=True, help="API Key")
    parser.add_argument("--per-seed", type=int, default=12, help="Number of items per seed")
    parser.add_argument("--out", default="eval/golden/candidates.jsonl", help="Output file path")
    args = parser.parse_args()

    asyncio.run(
        synthesize_candidates(
            base_url=args.base_url.rstrip("/"),
            api_key=args.api_key,
            per_seed=args.per_seed,
            out_path=args.out,
        )
    )


if __name__ == "__main__":
    main()
