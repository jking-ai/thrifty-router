#!/usr/bin/env python3
"""Validation script for Thrifty Router Golden Set.

Validates:
- Exactly or at least 300 items
- Gapless IDs in file order: g_0001, g_0002, ...
- Valid categories (at least 30 per category across all 8 categories)
- Tier distribution within ±5% of targets:
    lite: 40% ± 5% (35% - 45%)
    standard: 35% ± 5% (30% - 40%)
    pro: 25% ± 5% (20% - 30%)
- Every item has reviewed: true
- Required schema fields
"""

import json
import os
import re
import sys
from typing import Any, Dict, List

ALLOWED_CATEGORIES = {
    "rubric_parse",
    "diagram_gen",
    "doc_qa",
    "classify",
    "summarize",
    "code_explain",
    "math_reasoning",
    "creative",
}
ALLOWED_TIERS = {"lite", "standard", "pro"}
ID_REGEX = re.compile(r"^g_\d{4}$")


def validate_golden_set(filepath: str) -> bool:
    if not os.path.exists(filepath):
        # Try finding relative to current dir or script dir
        script_dir = os.path.dirname(os.path.abspath(__file__))
        alt_path = os.path.normpath(os.path.join(script_dir, "..", "..", filepath))
        if os.path.exists(alt_path):
            filepath = alt_path
        else:
            alt2 = os.path.normpath(os.path.join(script_dir, "..", filepath))
            if os.path.exists(alt2):
                filepath = alt2
            else:
                alt3 = os.path.normpath(os.path.join(script_dir, "..", "golden", os.path.basename(filepath)))
                if os.path.exists(alt3):
                    filepath = alt3
                else:
                    print(f"Error: Golden set file not found: {filepath}", file=sys.stderr)
                    return False

    items: List[Dict[str, Any]] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                items.append(data)
            except Exception as e:
                print(f"Error line {line_num}: Invalid JSON: {e}", file=sys.stderr)
                return False

    n = len(items)
    if n < 300:
        print(f"Error: Golden set has {n} items; expected at least 300", file=sys.stderr)
        return False

    tier_counts = {"lite": 0, "standard": 0, "pro": 0}
    category_counts = {cat: 0 for cat in ALLOWED_CATEGORIES}
    seen_ids = set()

    for idx, item in enumerate(items, 1):
        item_id = item.get("id")
        expected_id = f"g_{idx:04d}"

        if not item_id or not ID_REGEX.match(item_id):
            print(f"Error item {idx}: Invalid id format '{item_id}'", file=sys.stderr)
            return False

        if item_id != expected_id:
            print(f"Error item {idx}: Non-gapless id. Expected '{expected_id}', got '{item_id}'", file=sys.stderr)
            return False

        if item_id in seen_ids:
            print(f"Error item {idx}: Duplicate id '{item_id}'", file=sys.stderr)
            return False
        seen_ids.add(item_id)

        # Check category
        cat = item.get("category")
        if cat not in ALLOWED_CATEGORIES:
            print(f"Error item {idx}: Unknown category '{cat}'", file=sys.stderr)
            return False
        category_counts[cat] += 1

        # Check tier
        tier = item.get("expected_tier")
        if tier not in ALLOWED_TIERS:
            print(f"Error item {idx}: Unknown expected_tier '{tier}'", file=sys.stderr)
            return False
        tier_counts[tier] += 1

        # Check prompt
        prompt = item.get("prompt")
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            print(f"Error item {idx}: Empty prompt", file=sys.stderr)
            return False

        # Check rubric
        rubric = item.get("rubric")
        if not rubric or not isinstance(rubric, str) or not rubric.strip():
            print(f"Error item {idx}: Empty rubric", file=sys.stderr)
            return False

        # Check reviewed
        if item.get("reviewed") is not True:
            print(f"Error item {idx}: Item has reviewed={item.get('reviewed')}; must be True", file=sys.stderr)
            return False

        # Check source
        src = item.get("source")
        if not src or not (src.startswith("seed:") or src.startswith("synth:")):
            print(f"Error item {idx}: Invalid source '{src}'", file=sys.stderr)
            return False

    # Check category minimums (>= 30 each)
    for cat, count in category_counts.items():
        if count < 30:
            print(f"Error: Category '{cat}' has {count} items; expected at least 30", file=sys.stderr)
            return False

    # Check tier distribution within ±5%
    # lite: 40% ± 5% -> 35% .. 45%
    # standard: 35% ± 5% -> 30% .. 40%
    # pro: 25% ± 5% -> 20% .. 30%
    lite_pct = (tier_counts["lite"] / n) * 100
    std_pct = (tier_counts["standard"] / n) * 100
    pro_pct = (tier_counts["pro"] / n) * 100

    if not (35.0 <= lite_pct <= 45.0):
        print(f"Error: Lite tier is {lite_pct:.1f}%; expected 35%..45%", file=sys.stderr)
        return False
    if not (30.0 <= std_pct <= 40.0):
        print(f"Error: Standard tier is {std_pct:.1f}%; expected 30%..40%", file=sys.stderr)
        return False
    if not (20.0 <= pro_pct <= 30.0):
        print(f"Error: Pro tier is {pro_pct:.1f}%; expected 20%..30%", file=sys.stderr)
        return False

    print(f"✓ Golden set validated successfully! Total items: {n}")
    print("\n--- Tier Distribution ---")
    for t in ["lite", "standard", "pro"]:
        pct = (tier_counts[t] / n) * 100
        print(f"  {t:10}: {tier_counts[t]:3d} ({pct:.1f}%)")

    print("\n--- Category Breakdown ---")
    for c in sorted(ALLOWED_CATEGORIES):
        print(f"  {c:16}: {category_counts[c]:3d}")

    return True


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "eval/golden/golden_set.jsonl"
    success = validate_golden_set(path)
    sys.exit(0 if success else 1)
