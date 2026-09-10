"""Tests for golden set validation script."""

import json
import os
import tempfile
import pytest

from eval.scripts.validate_golden import validate_golden_set


def create_sample_items(count: int, lite_ratio: float = 0.4, duplicate_id: bool = False):
    items = []
    categories = [
        "rubric_parse", "diagram_gen", "doc_qa", "classify",
        "summarize", "code_explain", "math_reasoning", "creative"
    ]
    for i in range(1, count + 1):
        if duplicate_id and i == 2:
            item_id = "g_0001"
        else:
            item_id = f"g_{i:04d}"

        cat = categories[(i - 1) % len(categories)]
        if i <= int(count * lite_ratio):
            tier = "lite"
        elif i <= int(count * (lite_ratio + 0.35)):
            tier = "standard"
        else:
            tier = "pro"

        items.append({
            "id": item_id,
            "category": cat,
            "expected_tier": tier,
            "prompt": f"Test prompt {i}",
            "system": None,
            "json_schema": None,
            "reference": None,
            "rubric": "Sample rubric criteria",
            "reviewed": True,
            "source": "seed:test",
        })
    return items


def test_rejects_bad_distribution():
    """Verify validation fails if tier distribution deviates from target bounds."""
    # 300 items with 80% lite (way above 45% upper bound)
    items = create_sample_items(300, lite_ratio=0.80)
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as tmp:
        for it in items:
            tmp.write(json.dumps(it) + "\n")
        tmp_path = tmp.name

    try:
        assert validate_golden_set(tmp_path) is False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_rejects_duplicate_ids():
    """Verify validation fails if duplicate IDs exist."""
    items = create_sample_items(300, duplicate_id=True)
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as tmp:
        for it in items:
            tmp.write(json.dumps(it) + "\n")
        tmp_path = tmp.name

    try:
        assert validate_golden_set(tmp_path) is False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_validates_shipped_golden_set():
    """Verify shipped eval/golden/golden_set.jsonl passes validation."""
    assert validate_golden_set("eval/golden/golden_set.jsonl") is True
