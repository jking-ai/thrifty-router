#!/usr/bin/env python3
"""LLM Judge script scoring evaluation responses using Gemini 3.1 Pro."""

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
import httpx

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 5},
        "rationale": {"type": "string"},
    },
    "required": ["score", "rationale"],
}


async def score_single_response(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    template: str,
    item: Dict[str, Any],
    resp_entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Judge a single model answer against the rubric using the Pro tier."""
    item_id = resp_entry["item_id"]
    strat_label = resp_entry["strategy_label"]

    gateway_resp = resp_entry.get("response")
    if not gateway_resp or not gateway_resp.get("output"):
        return {
            "item_id": item_id,
            "strategy_label": strat_label,
            "score": None,
            "rationale": "Gateway error or empty response; unjudged",
            "judge_cost_usd": 0.0,
        }

    answer_text = gateway_resp["output"]
    reference_text = item.get("reference") or "No reference answer provided."
    rubric_text = item.get("rubric", "")
    prompt_text = item.get("prompt", "")

    rendered_judge_prompt = (
        template.replace("{rubric}", rubric_text)
        .replace("{reference}", reference_text)
        .replace("{prompt}", prompt_text)
        .replace("{answer}", answer_text)
    )

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": rendered_judge_prompt,
        "strategy": "fixed",
        "tier": "pro",
        "temperature": 0.0,
        "json_schema": JUDGE_SCHEMA,
    }

    try:
        r = await client.post(f"{base_url}/api/v1/complete", headers=headers, json=payload)
        if r.status_code == 200:
            res_json = r.json()
            raw_judge_output = res_json.get("output", "{}")
            cost_usd = res_json.get("usage", {}).get("total_cost_usd", 0.0)
            data = json.loads(raw_judge_output)
            score = data.get("score")
            if score is not None:
                score = int(score)
            rationale = str(data.get("rationale", "")).strip()
            return {
                "item_id": item_id,
                "strategy_label": strat_label,
                "score": score,
                "rationale": rationale,
                "judge_cost_usd": cost_usd,
            }
        else:
            return {
                "item_id": item_id,
                "strategy_label": strat_label,
                "score": None,
                "rationale": f"Judge gateway call failed with status {r.status_code}",
                "judge_cost_usd": 0.0,
            }
    except Exception as exc:
        return {
            "item_id": item_id,
            "strategy_label": strat_label,
            "score": None,
            "rationale": f"Judge exception: {str(exc)}",
            "judge_cost_usd": 0.0,
        }


async def run_judge(
    base_url: str,
    api_key: str,
    results_dir: str,
    max_spend_usd: float = 3.0,
    golden_set_path: str = "eval/golden/golden_set.jsonl",
) -> None:
    responses_path = os.path.join(results_dir, "responses.jsonl")
    if not os.path.exists(responses_path):
        print(f"Error: Responses file not found: {responses_path}", file=sys.stderr)
        sys.exit(1)

    template_path = "eval/prompts/judge_template.txt"
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Load golden items map
    with open(golden_set_path, "r", encoding="utf-8") as f:
        golden_items = {i["id"]: i for i in (json.loads(line.strip()) for line in f if line.strip())}

    with open(responses_path, "r", encoding="utf-8") as f:
        responses = [json.loads(line.strip()) for line in f if line.strip()]

    print(f"Loaded {len(responses)} responses to score.")
    judgments_path = os.path.join(results_dir, "judgments.jsonl")

    total_judge_spend = 0.0
    aborted = False
    concurrency = 4
    sem = asyncio.Semaphore(concurrency)

    timeout = httpx.Timeout(120.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        with open(judgments_path, "w", encoding="utf-8") as out_f:
            for resp_entry in responses:
                if aborted:
                    break
                item_id = resp_entry["item_id"]
                golden_item = golden_items.get(item_id, {"id": item_id, "prompt": "", "rubric": ""})

                async with sem:
                    judg = await score_single_response(
                        client=client,
                        base_url=base_url,
                        api_key=api_key,
                        template=template,
                        item=golden_item,
                        resp_entry=resp_entry,
                    )
                    total_judge_spend += judg.get("judge_cost_usd", 0.0)
                    out_f.write(json.dumps(judg) + "\n")
                    out_f.flush()

                    if total_judge_spend >= max_spend_usd:
                        print(f"⚠ Judge spend ceiling of ${max_spend_usd:.2f} reached. Halting.")
                        aborted = True

    print(f"\n✓ Completed judging! Wrote judgments to: {judgments_path}")
    print(f"Total judge spend: ${total_judge_spend:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Judge evaluated responses using Pro tier.")
    parser.add_argument("--base-url", required=True, help="Gateway base URL")
    parser.add_argument("--api-key", required=True, help="Gateway API Key")
    parser.add_argument("--results", required=True, help="Results directory containing responses.jsonl")
    parser.add_argument("--max-spend-usd", type=float, default=3.0, help="Maximum spend ceiling for judging")
    args = parser.parse_args()

    asyncio.run(
        run_judge(
            base_url=args.base_url.rstrip("/"),
            api_key=args.api_key,
            results_dir=args.results,
            max_spend_usd=args.max_spend_usd,
        )
    )


if __name__ == "__main__":
    main()
