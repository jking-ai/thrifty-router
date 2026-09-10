#!/usr/bin/env python3
"""Runner script to replay the golden set through Thrifty Router strategies."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
import httpx

DEFAULT_STRATEGIES = [
    "fixed:lite",
    "fixed:standard",
    "fixed:pro",
    "semantic",
    "classifier",
    "cascade",
]


async def run_single_item(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    item: Dict[str, Any],
    strategy_label: str,
    use_cache: bool = False,
) -> Dict[str, Any]:
    """Send a single prompt to the gateway and record response envelope."""
    # Parse strategy and tier
    if strategy_label.startswith("fixed:"):
        strat = "fixed"
        tier = strategy_label.split(":", 1)[1]
    else:
        strat = strategy_label
        tier = None

    payload: Dict[str, Any] = {
        "prompt": item["prompt"],
        "strategy": strat,
        "temperature": 0.2,
        "use_cache": use_cache,
    }
    if tier:
        payload["tier"] = tier
    if item.get("system"):
        payload["system"] = item["system"]
    if item.get("json_schema"):
        payload["json_schema"] = item["json_schema"]

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    start_time = time.perf_counter()
    resp_body = None
    err_body = None
    req_id = None

    try:
        r = await client.post(f"{base_url}/api/v1/complete", headers=headers, json=payload)
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        try:
            data = r.json()
        except Exception:
            data = {"raw_text": r.text}

        if r.status_code == 200:
            resp_body = data
            req_id = data.get("request_id")
        else:
            err_body = data.get("detail", data)
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        err_body = {"code": "CLIENT_EXCEPTION", "message": str(exc)}

    return {
        "item_id": item["id"],
        "strategy_label": strategy_label,
        "request_id": req_id,
        "response": resp_body,
        "error": err_body,
        "latency_ms": latency_ms,
    }


async def execute_eval_run(
    base_url: str,
    api_key: str,
    strategies: List[str],
    limit: Optional[int],
    max_spend_usd: float,
    out_dir: str,
    golden_set_path: str = "eval/golden/golden_set.jsonl",
    cache_replay: bool = False,
) -> None:
    # 1. Load golden items
    with open(golden_set_path, "r", encoding="utf-8") as f:
        items = [json.loads(line.strip()) for line in f if line.strip()]

    # Filter reviewed only
    items = [i for i in items if i.get("reviewed") is True]
    if limit is not None:
        items = items[:limit]

    print(f"Loaded {len(items)} reviewed golden set items for evaluation.")
    print(f"Strategies to run: {', '.join(strategies)}")
    print(f"Spend ceiling: ${max_spend_usd:.2f}")

    os.makedirs(out_dir, exist_ok=True)
    responses_file = os.path.join(out_dir, "responses.jsonl")

    total_spend_usd = 0.0
    aborted_by_spend = False
    concurrency_limit = 4
    semaphore = asyncio.Semaphore(concurrency_limit)

    timeout = httpx.Timeout(120.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        with open(responses_file, "a", encoding="utf-8") as out_f:
            for strat in strategies:
                if aborted_by_spend:
                    break
                print(f"\n--- Running strategy: {strat} ---")

                async def worker(item: Dict[str, Any]):
                    nonlocal total_spend_usd, aborted_by_spend
                    if aborted_by_spend:
                        return None
                    async with semaphore:
                        res = await run_single_item(
                            client=client,
                            base_url=base_url,
                            api_key=api_key,
                            item=item,
                            strategy_label=strat,
                            use_cache=False,
                        )
                        # Accumulate spend
                        if res.get("response"):
                            usage = res["response"].get("usage", {})
                            cost = usage.get("total_cost_usd", 0.0)
                            total_spend_usd += cost
                            if total_spend_usd >= max_spend_usd:
                                print(f"\n⚠ Spend ceiling of ${max_spend_usd:.2f} reached (current: ${total_spend_usd:.4f}). Aborting further calls.")
                                aborted_by_spend = True
                        return res

                # Run items sequentially or in bounded chunks
                for item in items:
                    if aborted_by_spend:
                        break
                    res = await worker(item)
                    if res:
                        out_f.write(json.dumps(res) + "\n")
                        out_f.flush()

        # Optional cache replay experiment
        cache_hit_rate = None
        if cache_replay:
            print("\n--- Running Cache Replay Experiment (lite items) ---")
            lite_items = [i for i in items if i.get("expected_tier") == "lite"]
            if not lite_items:
                lite_items = items[:20]

            # Pass 1: Warmup
            print(f"Pass 1: Warming up cache for {len(lite_items)} items...")
            for it in lite_items:
                await run_single_item(client, base_url, api_key, it, "fixed:lite", use_cache=True)

            # Pass 2: Measure hits
            print("Pass 2: Measuring cache hits...")
            hits = 0
            for it in lite_items:
                res = await run_single_item(client, base_url, api_key, it, "fixed:lite", use_cache=True)
                if res.get("response") and res["response"].get("cache", {}).get("hit") is True:
                    hits += 1
            cache_hit_rate = round(hits / len(lite_items), 4) if lite_items else 1.0
            print(f"✓ Cache hit rate second pass: {cache_hit_rate * 100:.1f}% ({hits}/{len(lite_items)})")

            # Store cache replay in metadata
            cache_meta_path = os.path.join(out_dir, "cache_replay.json")
            with open(cache_meta_path, "w", encoding="utf-8") as cm:
                json.dump({"cache_hit_rate_second_pass": cache_hit_rate}, cm)

    print(f"\n✓ Completed evaluation replay! Results written to: {responses_file}")
    print(f"Total gateway spend during run: ${total_spend_usd:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Run golden set eval against Thrifty Router.")
    parser.add_argument("--base-url", required=True, help="Gateway base URL")
    parser.add_argument("--api-key", required=True, help="Gateway API Key")
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES), help="Comma-separated strategy list")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to run")
    parser.add_argument("--max-spend-usd", type=float, default=3.0, help="Spend ceiling abort threshold")
    parser.add_argument("--out", default=None, help="Output directory path")
    parser.add_argument("--cache-replay", action="store_true", help="Run cache replay experiment")
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out or f"eval/results/{ts}"
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]

    asyncio.run(
        execute_eval_run(
            base_url=args.base_url.rstrip("/"),
            api_key=args.api_key,
            strategies=strategies,
            limit=args.limit,
            max_spend_usd=args.max_spend_usd,
            out_dir=out_dir,
            cache_replay=args.cache_replay,
        )
    )


if __name__ == "__main__":
    main()
