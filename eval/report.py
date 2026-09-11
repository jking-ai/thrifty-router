#!/usr/bin/env python3
"""Statistical aggregator and HTML report generator for Thrifty Router eval."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional
import numpy as np


def compute_metrics(
    results_dir: str,
    allow_partial: bool = False,
    golden_set_path: str = "eval/golden/golden_set.jsonl",
) -> Dict[str, Any]:
    responses_path = os.path.join(results_dir, "responses.jsonl")
    judgments_path = os.path.join(results_dir, "judgments.jsonl")

    if not os.path.exists(responses_path):
        raise FileNotFoundError(f"Missing {responses_path}")

    # Load golden items
    golden_items = {}
    if os.path.exists(golden_set_path):
        with open(golden_set_path, "r", encoding="utf-8") as f:
            golden_items = {i["id"]: i for i in (json.loads(line) for line in f if line.strip())}

    # Load responses
    responses_by_strat: Dict[str, List[Dict[str, Any]]] = {}
    with open(responses_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            strat = entry["strategy_label"]
            responses_by_strat.setdefault(strat, []).append(entry)

    # Load judgments
    judgments_by_pair: Dict[str, Dict[str, Any]] = {}
    total_judge_cost = 0.0
    if os.path.exists(judgments_path):
        with open(judgments_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                j = json.loads(line)
                key = f"{j['item_id']}::{j['strategy_label']}"
                judgments_by_pair[key] = j
                total_judge_cost += j.get("judge_cost_usd", 0.0)

    # Check line counts
    is_partial = False
    for strat, items in responses_by_strat.items():
        judged_count = sum(1 for item in items if f"{item['item_id']}::{strat}" in judgments_by_pair and judgments_by_pair[f"{item['item_id']}::{strat}"].get("score") is not None)
        if judged_count < 50:
            if not allow_partial:
                raise ValueError(
                    f"Strategy '{strat}' has only {judged_count} judged items (< 50). "
                    "Pass --allow-partial to generate report on partial results."
                )
            is_partial = True

    # Read cache replay result if present
    cache_hit_rate_second_pass = None
    cache_meta_path = os.path.join(results_dir, "cache_replay.json")
    if os.path.exists(cache_meta_path):
        with open(cache_meta_path, "r", encoding="utf-8") as cm:
            cache_hit_rate_second_pass = json.load(cm).get("cache_hit_rate_second_pass")

    # First pass: calculate mean score and total cost per strategy
    strat_raw: Dict[str, Dict[str, Any]] = {}

    for strat, resps in responses_by_strat.items():
        n = len(resps)
        errors = 0
        scores: List[int] = []
        costs: List[float] = []
        latencies: List[int] = []
        tier_counts = {"lite": 0, "standard": 0, "pro": 0}
        correct_routing_count = 0
        cascade_escalation_count = 0
        by_category_data: Dict[str, Dict[str, Any]] = {}

        for r in resps:
            item_id = r["item_id"]
            golden_item = golden_items.get(item_id, {})
            category = golden_item.get("category", "unknown")
            expected_tier = golden_item.get("expected_tier")

            cat_stats = by_category_data.setdefault(category, {"scores": [], "costs": [], "n": 0})
            cat_stats["n"] += 1

            if r.get("error") is not None or not r.get("response"):
                errors += 1
                continue

            resp_data = r["response"]
            usage = resp_data.get("usage", {})
            cost = usage.get("total_cost_usd", 0.0)
            costs.append(cost)
            cat_stats["costs"].append(cost)

            lat = r.get("latency_ms", 0)
            latencies.append(lat)

            # Routing tier
            routing = resp_data.get("routing", {})
            chosen_tier = routing.get("tier")
            if chosen_tier in tier_counts:
                tier_counts[chosen_tier] += 1

            # Routing accuracy
            if expected_tier and chosen_tier == expected_tier:
                correct_routing_count += 1

            # Cascade escalation rate
            attempts = routing.get("attempts", [])
            completion_attempts = [a for a in attempts if a.get("role") == "completion"]
            if len(completion_attempts) > 1:
                cascade_escalation_count += 1

            # Judgments
            j_key = f"{item_id}::{strat}"
            if j_key in judgments_by_pair:
                score = judgments_by_pair[j_key].get("score")
                if score is not None:
                    scores.append(score)
                    cat_stats["scores"].append(score)

        mean_score = round(float(np.mean(scores)), 2) if scores else 0.0
        total_cost = round(float(sum(costs)), 6)
        cost_per_1k = round((total_cost / n) * 1000.0, 4) if n > 0 else 0.0

        p50 = int(np.percentile(latencies, 50)) if latencies else 0
        p95 = int(np.percentile(latencies, 95)) if latencies else 0

        # Tier mix
        total_answered = sum(tier_counts.values()) or 1
        tier_mix = {
            t: round(tier_counts[t] / total_answered, 2)
            for t in ["lite", "standard", "pro"]
        }

        # Routing accuracy (null for fixed:*)
        routing_accuracy = None
        if not strat.startswith("fixed:"):
            valid_resps = n - errors
            routing_accuracy = round(correct_routing_count / valid_resps, 2) if valid_resps > 0 else 0.0

        # Escalation rate (null for non-cascade)
        escalation_rate = None
        if strat == "cascade":
            valid_resps = n - errors
            escalation_rate = round(cascade_escalation_count / valid_resps, 2) if valid_resps > 0 else 0.0

        # By category summary
        by_cat_summary = {}
        for c, cdata in by_category_data.items():
            cn = cdata["n"]
            cscores = cdata["scores"]
            ccosts = cdata["costs"]
            c_mean_score = round(float(np.mean(cscores)), 2) if cscores else 0.0
            c_cost_1k = round((sum(ccosts) / cn) * 1000.0, 4) if cn > 0 else 0.0
            by_cat_summary[c] = {
                "n": cn,
                "mean_score": c_mean_score,
                "cost_per_1k_requests_usd": c_cost_1k,
            }

        strat_raw[strat] = {
            "n": n,
            "errors": errors,
            "mean_score": mean_score,
            "total_cost_usd": total_cost,
            "cost_per_1k_requests_usd": cost_per_1k,
            "latency_p50_ms": p50,
            "latency_p95_ms": p95,
            "tier_mix": tier_mix,
            "routing_accuracy": routing_accuracy,
            "escalation_rate": escalation_rate,
            "by_category": by_cat_summary,
        }

    # Pro baseline metrics
    pro_baseline = strat_raw.get("fixed:pro")
    pro_score = pro_baseline["mean_score"] if pro_baseline and pro_baseline["mean_score"] > 0 else 4.5
    pro_cost = pro_baseline["total_cost_usd"] if pro_baseline and pro_baseline["total_cost_usd"] > 0 else 1.8

    # Second pass: compute quality_retention and cost_ratio_vs_pro
    strategies_summary: Dict[str, Any] = {}
    for strat, data in strat_raw.items():
        q_retention = round(data["mean_score"] / pro_score, 2) if pro_score > 0 else 1.0
        c_ratio = round(data["total_cost_usd"] / pro_cost, 2) if pro_cost > 0 else 1.0

        item_dict = dict(data)
        item_dict["quality_retention"] = q_retention
        item_dict["cost_ratio_vs_pro"] = c_ratio
        strategies_summary[strat] = item_dict

    total_items = max((d["n"] for d in strategies_summary.values()), default=300)
    run_id = os.path.basename(os.path.normpath(results_dir))

    summary = {
        "run_id": run_id,
        "partial": is_partial,
        "items": total_items,
        "judge_cost_usd": round(total_judge_cost, 4),
        "strategies": strategies_summary,
        "cache_hit_rate_second_pass": cache_hit_rate_second_pass,
    }

    # Write summary.json
    summary_path = os.path.join(results_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Wrote {summary_path}")

    return summary


GOLDEN_EXPORT_FIELDS = ("id", "category", "expected_tier", "prompt", "rubric", "reference", "reviewed", "source")


def export_golden_set(golden_path: str, out_path: str) -> int:
    """Copy the golden set into the static report as a JSON array.

    Only the fields the browsable explorer needs are kept, so the published
    file stays small and its shape is stable even if the JSONL grows new
    internal columns. Returns the number of items written.
    """
    items = []
    with open(golden_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            missing = [k for k in ("id", "category", "expected_tier", "prompt") if not row.get(k)]
            if missing:
                raise ValueError(f"{golden_path}:{line_no} missing required field(s): {', '.join(missing)}")
            items.append({k: row.get(k) for k in GOLDEN_EXPORT_FIELDS})

    if not items:
        raise ValueError(f"No golden items found in {golden_path}")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as out:
        json.dump(items, out, indent=1, ensure_ascii=False)
        out.write("\n")
    print(f"✓ Exported {len(items)} golden items: {out_path}")
    return len(items)


def render_html_report(summary: Dict[str, Any], template_path: str, output_path: str, data_path: str) -> None:
    """Render interactive HTML report by injecting data.json into template."""
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    data_json_str = json.dumps(summary, indent=2)
    os.makedirs(os.path.dirname(data_path) or ".", exist_ok=True)
    with open(data_path, "w", encoding="utf-8") as df:
        df.write(data_json_str)
    print(f"✓ Wrote data file: {data_path}")

    rendered = template.replace("/* __DATA_JSON_PLACEHOLDER__ */", f"window.__EVAL_DATA__ = {data_json_str};")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out:
        out.write(rendered)
    print(f"✓ Rendered HTML report: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate eval results, generate the HTML report, and export the golden set for the explorer page."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--results", help="Results directory containing responses.jsonl and judgments.jsonl")
    src.add_argument(
        "--summary",
        help="Re-render the report from an existing summary (e.g. report/data.json) without raw results",
    )
    parser.add_argument("--allow-partial", action="store_true", help="Allow fewer than 50 items per strategy")
    parser.add_argument("--template", default="report/template.html", help="HTML template path")
    parser.add_argument("--out-html", default="report/index.html", help="HTML output path")
    parser.add_argument("--out-data", default="report/data.json", help="Data JSON output path")
    parser.add_argument("--golden", default="eval/golden/golden_set.jsonl", help="Golden set JSONL to publish")
    parser.add_argument("--out-golden", default="report/golden.json", help="Golden set JSON output path")
    parser.add_argument("--skip-golden", action="store_true", help="Do not export the golden set")
    args = parser.parse_args()

    if args.summary:
        with open(args.summary, "r", encoding="utf-8") as f:
            summary = json.load(f)
    else:
        summary = compute_metrics(
            results_dir=args.results,
            allow_partial=args.allow_partial,
        )
    render_html_report(
        summary=summary,
        template_path=args.template,
        output_path=args.out_html,
        data_path=args.out_data,
    )
    if not args.skip_golden:
        export_golden_set(golden_path=args.golden, out_path=args.out_golden)


if __name__ == "__main__":
    main()
