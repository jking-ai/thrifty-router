#!/usr/bin/env python3
"""Re-run the (item, strategy) pairs in a responses.jsonl whose gateway call failed.

Transient upstream errors (429 quota rejections, timeouts) leave `error` lines in
responses.jsonl. The report excludes those from means but they still lower the
judged sample. This script replays only the failed pairs through the gateway,
in place, so a full run does not have to be repeated. Lines that still fail after
the retries are left as they were.

With --rerun-capped-at N, responses whose last attempt used at least N thinking
plus output tokens are treated as failed too (the gateway's output budget cut
them off). Replaced pairs are removed from judgments.jsonl, if present, so a
`judge.py --resume` scores only the new answers.

Usage (from the repo root):
    python3 eval/scripts/retry_failed_responses.py --base-url URL --api-key KEY \
        --results eval/results/<run-id> [--attempts 2] [--golden eval/golden/golden_set.jsonl]
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from eval.run_eval import run_single_item  # noqa: E402


async def retry_failed(
    base_url: str,
    api_key: str,
    results_dir: str,
    golden_set_path: str,
    attempts: int,
    concurrency: int = 4,
    rerun_capped_at: Optional[int] = None,
) -> Dict[str, int]:
    responses_path = os.path.join(results_dir, "responses.jsonl")
    with open(responses_path, "r", encoding="utf-8") as f:
        lines: List[Dict[str, Any]] = [json.loads(line) for line in f if line.strip()]
    with open(golden_set_path, "r", encoding="utf-8") as f:
        golden = {i["id"]: i for i in (json.loads(line) for line in f if line.strip())}

    def capped(row: Dict[str, Any]) -> bool:
        if rerun_capped_at is None or not row.get("response"):
            return False
        attempts_list = row["response"].get("routing", {}).get("attempts") or []
        if not attempts_list:
            return False
        last = attempts_list[-1]
        return (last.get("thinking_tokens", 0) or 0) + (last.get("output_tokens", 0) or 0) >= rerun_capped_at

    failed_idx = [i for i, row in enumerate(lines) if row.get("error") or capped(row)]
    stats = {"failed_before": len(failed_idx), "recovered": 0, "still_failed": 0}
    if not failed_idx:
        print("No failed responses to retry.")
        return stats

    sem = asyncio.Semaphore(concurrency)
    timeout = httpx.Timeout(120.0, connect=10.0)

    async def retry_one(idx: int) -> None:
        row = lines[idx]
        item = golden.get(row["item_id"])
        if item is None:
            return
        async with sem:
            for attempt in range(1, attempts + 1):
                res = await run_single_item(
                    client=client,
                    base_url=base_url,
                    api_key=api_key,
                    item=item,
                    strategy_label=row["strategy_label"],
                    use_cache=False,
                )
                if not res.get("error"):
                    lines[idx] = res
                    stats["recovered"] += 1
                    print(f"✓ {row['item_id']} {row['strategy_label']} recovered on attempt {attempt}")
                    return
                await asyncio.sleep(2.0 * attempt)
            stats["still_failed"] += 1
            print(f"✗ {row['item_id']} {row['strategy_label']} still failing after {attempts} attempts")

    async with httpx.AsyncClient(timeout=timeout) as client:
        await asyncio.gather(*(retry_one(i) for i in failed_idx))

    replaced = {(lines[i]["item_id"], lines[i]["strategy_label"]) for i in failed_idx if not lines[i].get("error")}
    tmp_path = responses_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as out:
        for row in lines:
            out.write(json.dumps(row) + "\n")
    os.replace(tmp_path, responses_path)

    judgments_path = os.path.join(results_dir, "judgments.jsonl")
    if replaced and os.path.exists(judgments_path):
        with open(judgments_path, "r", encoding="utf-8") as f:
            judgments = [json.loads(line) for line in f if line.strip()]
        kept = [j for j in judgments if (j["item_id"], j["strategy_label"]) not in replaced]
        with open(judgments_path + ".tmp", "w", encoding="utf-8") as out:
            for j in kept:
                out.write(json.dumps(j) + "\n")
        os.replace(judgments_path + ".tmp", judgments_path)
        print(f"Dropped {len(judgments) - len(kept)} stale judgments; rerun judge.py --resume to rescore them.")
    print(f"Retried {stats['failed_before']} failed responses: {stats['recovered']} recovered, {stats['still_failed']} still failing.")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry failed gateway responses in place.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--results", required=True, help="Results directory containing responses.jsonl")
    parser.add_argument("--golden", default="eval/golden/golden_set.jsonl")
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--rerun-capped-at", type=int, default=None,
                        help="Also replay responses whose thinking + output tokens reached this cap")
    args = parser.parse_args()
    asyncio.run(retry_failed(
        base_url=args.base_url.rstrip("/"),
        api_key=args.api_key,
        results_dir=args.results,
        golden_set_path=args.golden,
        attempts=args.attempts,
        concurrency=args.concurrency,
        rerun_capped_at=args.rerun_capped_at,
    ))


if __name__ == "__main__":
    main()
