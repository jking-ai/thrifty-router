"""Tests for report metric calculation and partial-result enforcement."""

import json
import os
import shutil
import tempfile
import pytest

from eval.report import compute_metrics


def setup_fixture_data(num_items: int = 60) -> str:
    temp_dir = tempfile.mkdtemp()
    responses_file = os.path.join(temp_dir, "responses.jsonl")
    judgments_file = os.path.join(temp_dir, "judgments.jsonl")

    # Generate fixture lines for fixed:pro and cascade
    with open(responses_file, "w", encoding="utf-8") as rf, open(judgments_file, "w", encoding="utf-8") as jf:
        for i in range(1, num_items + 1):
            item_id = f"g_{i:04d}"

            # fixed:pro entry (cost 0.006, score 5)
            pro_resp = {
                "item_id": item_id,
                "strategy_label": "fixed:pro",
                "request_id": f"req_pro_{i}",
                "response": {
                    "output": "Pro answer",
                    "routing": {"strategy": "fixed", "tier": "pro", "model": "pro-m", "attempts": [{"role": "completion", "tier": "pro"}]},
                    "usage": {"total_cost_usd": 0.006},
                },
                "error": None,
                "latency_ms": 1000,
            }
            rf.write(json.dumps(pro_resp) + "\n")
            jf.write(json.dumps({
                "item_id": item_id,
                "strategy_label": "fixed:pro",
                "score": 5,
                "rationale": "Perfect",
                "judge_cost_usd": 0.004,
            }) + "\n")

            # cascade entry (cost 0.0015, score 4, escalated half the time)
            escalated = (i % 2 == 0)
            attempts = [
                {"role": "completion", "tier": "lite", "accepted": not escalated}
            ]
            if escalated:
                attempts.append({"role": "completion", "tier": "standard", "accepted": True})

            chosen_tier = "standard" if escalated else "lite"
            cascade_resp = {
                "item_id": item_id,
                "strategy_label": "cascade",
                "request_id": f"req_cas_{i}",
                "response": {
                    "output": "Cascade answer",
                    "routing": {
                        "strategy": "cascade",
                        "tier": chosen_tier,
                        "model": "model-m",
                        "attempts": attempts,
                    },
                    "usage": {"total_cost_usd": 0.0015},
                },
                "error": None,
                "latency_ms": 800,
            }
            rf.write(json.dumps(cascade_resp) + "\n")
            jf.write(json.dumps({
                "item_id": item_id,
                "strategy_label": "cascade",
                "score": 4,
                "rationale": "Good",
                "judge_cost_usd": 0.004,
            }) + "\n")

    return temp_dir


def test_metrics_from_fixture():
    """Verify calculated metrics match hand-computed fixture expectations."""
    temp_dir = setup_fixture_data(num_items=60)
    try:
        summary = compute_metrics(results_dir=temp_dir, allow_partial=False)
        assert summary["partial"] is False
        assert summary["items"] == 60

        strats = summary["strategies"]
        pro = strats["fixed:pro"]
        cas = strats["cascade"]

        # Mean scores
        assert pro["mean_score"] == 5.0
        assert cas["mean_score"] == 4.0
        # Quality retention: 4.0 / 5.0 = 0.80
        assert cas["quality_retention"] == 0.80

        # Costs: 60 * 0.006 = 0.36 for pro, 60 * 0.0015 = 0.09 for cascade
        assert abs(pro["total_cost_usd"] - 0.36) < 1e-4
        assert abs(cas["total_cost_usd"] - 0.09) < 1e-4
        # Cost ratio: 0.09 / 0.36 = 0.25
        assert cas["cost_ratio_vs_pro"] == 0.25

        # Escalation rate: 30 / 60 = 0.50
        assert cas["escalation_rate"] == 0.50
        # Tier mix: 30 lite (0.5), 30 standard (0.5), 0 pro
        assert cas["tier_mix"]["lite"] == 0.50
        assert cas["tier_mix"]["standard"] == 0.50
        assert cas["tier_mix"]["pro"] == 0.0
    finally:
        shutil.rmtree(temp_dir)


def test_refuses_partial_without_flag():
    """Verify ValueError is raised when judged items < 50 without --allow-partial."""
    temp_dir = setup_fixture_data(num_items=20)
    try:
        with pytest.raises(ValueError, match="< 50"):
            compute_metrics(results_dir=temp_dir, allow_partial=False)
    finally:
        shutil.rmtree(temp_dir)


def test_partial_flag_stamps_summary():
    """Verify allow_partial=True permits runs < 50 items and stamps partial: true."""
    temp_dir = setup_fixture_data(num_items=20)
    try:
        summary = compute_metrics(results_dir=temp_dir, allow_partial=True)
        assert summary["partial"] is True
    finally:
        shutil.rmtree(temp_dir)


def test_export_golden_set_writes_explorer_fields():
    """Golden export keeps only the explorer fields and preserves row count and order."""
    from eval.report import export_golden_set, GOLDEN_EXPORT_FIELDS

    temp_dir = tempfile.mkdtemp()
    try:
        golden_path = os.path.join(temp_dir, "golden.jsonl")
        out_path = os.path.join(temp_dir, "report", "golden.json")
        with open(golden_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "id": "g_0001", "category": "doc_qa", "expected_tier": "lite", "prompt": "What is 2+2?",
                "rubric": "Must answer 4.", "reviewed": True, "source": "seed:seed_doc_qa_lite_1",
                "system": None, "json_schema": None, "reference": None, "internal_note": "drop me",
            }) + "\n")
            f.write("\n")  # blank lines are tolerated
            f.write(json.dumps({
                "id": "g_0002", "category": "creative", "expected_tier": "pro", "prompt": "Write a sonnet.",
                "rubric": "Fourteen lines.", "reviewed": True, "source": "seed:seed_creative_pro_1",
            }) + "\n")

        count = export_golden_set(golden_path=golden_path, out_path=out_path)
        assert count == 2

        with open(out_path, "r", encoding="utf-8") as f:
            exported = json.load(f)
        assert [row["id"] for row in exported] == ["g_0001", "g_0002"]
        assert set(exported[0].keys()) == set(GOLDEN_EXPORT_FIELDS)
        assert "internal_note" not in exported[0]
        assert exported[1]["expected_tier"] == "pro"
    finally:
        shutil.rmtree(temp_dir)


def test_export_golden_set_rejects_rows_missing_required_fields():
    """A row without a prompt or tier must fail loudly instead of publishing a broken explorer."""
    from eval.report import export_golden_set

    temp_dir = tempfile.mkdtemp()
    try:
        golden_path = os.path.join(temp_dir, "golden.jsonl")
        with open(golden_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "g_0001", "category": "doc_qa", "expected_tier": "lite"}) + "\n")
        with pytest.raises(ValueError, match="missing required field"):
            export_golden_set(golden_path=golden_path, out_path=os.path.join(temp_dir, "golden.json"))
    finally:
        shutil.rmtree(temp_dir)


def test_export_golden_set_rejects_empty_file():
    from eval.report import export_golden_set

    temp_dir = tempfile.mkdtemp()
    try:
        golden_path = os.path.join(temp_dir, "golden.jsonl")
        open(golden_path, "w").close()
        with pytest.raises(ValueError, match="No golden items"):
            export_golden_set(golden_path=golden_path, out_path=os.path.join(temp_dir, "golden.json"))
    finally:
        shutil.rmtree(temp_dir)
