"""Tests for the in-place retry of failed gateway responses."""

import json
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from eval.scripts.retry_failed_responses import retry_failed


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


@pytest.mark.asyncio
async def test_retries_only_failed_lines_and_keeps_order():
    temp_dir = tempfile.mkdtemp()
    try:
        golden = os.path.join(temp_dir, "golden.jsonl")
        _write_jsonl(golden, [
            {"id": "g_0001", "category": "doc_qa", "expected_tier": "lite", "prompt": "p1", "rubric": "r", "reviewed": True, "source": "seed:x"},
            {"id": "g_0002", "category": "doc_qa", "expected_tier": "lite", "prompt": "p2", "rubric": "r", "reviewed": True, "source": "seed:x"},
        ])
        ok = {"item_id": "g_0001", "strategy_label": "fixed:lite", "request_id": "r1", "response": {"output": "fine", "usage": {"total_cost_usd": 0.001}}, "error": None, "latency_ms": 10}
        bad = {"item_id": "g_0002", "strategy_label": "fixed:lite", "request_id": None, "response": None, "error": {"code": "UPSTREAM_ERROR", "message": "429"}, "latency_ms": 10}
        _write_jsonl(os.path.join(temp_dir, "responses.jsonl"), [ok, bad])

        calls = []

        async def fake_run_single(*args, **kwargs):
            calls.append(kwargs["item"]["id"])
            return {"item_id": kwargs["item"]["id"], "strategy_label": kwargs["strategy_label"], "request_id": "r2",
                    "response": {"output": "recovered", "usage": {"total_cost_usd": 0.002}}, "error": None, "latency_ms": 20}

        with patch("eval.scripts.retry_failed_responses.run_single_item", side_effect=fake_run_single):
            stats = await retry_failed("http://fake", "k", temp_dir, golden, attempts=2)

        assert calls == ["g_0002"]
        assert stats == {"failed_before": 1, "recovered": 1, "still_failed": 0}
        with open(os.path.join(temp_dir, "responses.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        assert [r["item_id"] for r in rows] == ["g_0001", "g_0002"]
        assert rows[0]["response"]["output"] == "fine"
        assert rows[1]["error"] is None and rows[1]["response"]["output"] == "recovered"
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_leaves_line_when_retries_keep_failing():
    temp_dir = tempfile.mkdtemp()
    try:
        golden = os.path.join(temp_dir, "golden.jsonl")
        _write_jsonl(golden, [{"id": "g_0001", "category": "doc_qa", "expected_tier": "lite", "prompt": "p1", "rubric": "r", "reviewed": True, "source": "seed:x"}])
        bad = {"item_id": "g_0001", "strategy_label": "cascade", "request_id": None, "response": None, "error": {"code": "UPSTREAM_TIMEOUT", "message": "t"}, "latency_ms": 10}
        _write_jsonl(os.path.join(temp_dir, "responses.jsonl"), [bad])

        async def still_bad(*args, **kwargs):
            return dict(bad)

        with patch("eval.scripts.retry_failed_responses.run_single_item", side_effect=still_bad), patch("asyncio.sleep", return_value=None):
            stats = await retry_failed("http://fake", "k", temp_dir, golden, attempts=2)

        assert stats == {"failed_before": 1, "recovered": 0, "still_failed": 1}
        with open(os.path.join(temp_dir, "responses.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        assert rows[0]["error"]["code"] == "UPSTREAM_TIMEOUT"
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_rerun_capped_responses_and_prune_judgments():
    temp_dir = tempfile.mkdtemp()
    try:
        golden = os.path.join(temp_dir, "golden.jsonl")
        _write_jsonl(golden, [
            {"id": "g_0001", "category": "creative", "expected_tier": "pro", "prompt": "p1", "rubric": "r", "reviewed": True, "source": "seed:x"},
            {"id": "g_0002", "category": "creative", "expected_tier": "pro", "prompt": "p2", "rubric": "r", "reviewed": True, "source": "seed:x"},
        ])
        def resp(item_id, thinking, output):
            return {"item_id": item_id, "strategy_label": "fixed:pro", "request_id": "r", "error": None, "latency_ms": 10,
                    "response": {"output": "x", "usage": {"total_cost_usd": 0.01},
                                 "routing": {"attempts": [{"thinking_tokens": thinking, "output_tokens": output}]}}}
        _write_jsonl(os.path.join(temp_dir, "responses.jsonl"), [resp("g_0001", 1900, 150), resp("g_0002", 300, 200)])
        _write_jsonl(os.path.join(temp_dir, "judgments.jsonl"), [
            {"item_id": "g_0001", "strategy_label": "fixed:pro", "score": 1, "rationale": "cut off", "judge_cost_usd": 0.004},
            {"item_id": "g_0002", "strategy_label": "fixed:pro", "score": 5, "rationale": "fine", "judge_cost_usd": 0.004},
        ])

        calls = []

        async def fake_run_single(*args, **kwargs):
            calls.append(kwargs["item"]["id"])
            return resp(kwargs["item"]["id"], 1200, 900)

        with patch("eval.scripts.retry_failed_responses.run_single_item", side_effect=fake_run_single):
            stats = await retry_failed("http://fake", "k", temp_dir, golden, attempts=1, rerun_capped_at=2000)

        assert calls == ["g_0001"]
        assert stats["recovered"] == 1
        with open(os.path.join(temp_dir, "judgments.jsonl"), encoding="utf-8") as f:
            remaining = [json.loads(line)["item_id"] for line in f]
        assert remaining == ["g_0002"]
    finally:
        shutil.rmtree(temp_dir)
