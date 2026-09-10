"""Tests for eval runner execution and error handling."""

import json
import os
import shutil
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from eval.run_eval import execute_eval_run, run_single_item


@pytest.mark.asyncio
async def test_records_error_lines_and_continues():
    """Verify gateway 502 errors are captured in error field and runner continues."""
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 502
    mock_resp.json.return_value = {"detail": {"code": "UPSTREAM_ERROR", "message": "Failed"}}
    mock_client.post.return_value = mock_resp

    item = {"id": "g_0001", "prompt": "Test prompt"}
    result = await run_single_item(
        client=mock_client,
        base_url="http://fake",
        api_key="key",
        item=item,
        strategy_label="fixed:lite",
    )

    assert result["item_id"] == "g_0001"
    assert result["response"] is None
    assert result["error"]["code"] == "UPSTREAM_ERROR"


@pytest.mark.asyncio
async def test_spend_ceiling_aborts():
    """Verify runner aborts once total spend reaches max_spend_usd ceiling."""
    temp_dir = tempfile.mkdtemp()
    temp_golden = os.path.join(temp_dir, "test_golden.jsonl")

    # Write 5 test items
    with open(temp_golden, "w", encoding="utf-8") as f:
        for i in range(1, 6):
            f.write(json.dumps({
                "id": f"g_{i:04d}",
                "category": "doc_qa",
                "expected_tier": "lite",
                "prompt": f"Prompt {i}",
                "rubric": "Rubric",
                "reviewed": True,
                "source": "seed:test"
            }) + "\n")

    # Mock gateway returning $1.00 cost per item
    async def mock_run_single(*args, **kwargs):
        return {
            "item_id": kwargs["item"]["id"],
            "strategy_label": kwargs["strategy_label"],
            "request_id": "req_123",
            "response": {
                "output": "Answer",
                "usage": {"total_cost_usd": 1.0}
            },
            "error": None,
            "latency_ms": 100
        }

    try:
        with patch("eval.run_eval.run_single_item", side_effect=mock_run_single):
            await execute_eval_run(
                base_url="http://fake",
                api_key="key",
                strategies=["fixed:lite"],
                limit=5,
                max_spend_usd=2.5,
                out_dir=temp_dir,
                golden_set_path=temp_golden,
            )

        responses_file = os.path.join(temp_dir, "responses.jsonl")
        with open(responses_file, "r", encoding="utf-8") as rf:
            lines = [json.loads(line) for line in rf if line.strip()]

        # $1.0 + $1.0 + $1.0 = $3.0 >= $2.5 -> exactly 3 lines produced before abort
        assert len(lines) == 3
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_cache_replay_hit_rate():
    """Verify cache replay experiment measures second pass hit rate."""
    temp_dir = tempfile.mkdtemp()
    temp_golden = os.path.join(temp_dir, "test_golden.jsonl")

    with open(temp_golden, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "id": "g_0001",
            "category": "doc_qa",
            "expected_tier": "lite",
            "prompt": "Prompt 1",
            "rubric": "Rubric",
            "reviewed": True,
            "source": "seed:test"
        }) + "\n")

    call_count = 0

    async def mock_replay(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        is_second_pass = (call_count > 1)
        item = kwargs.get("item") if "item" in kwargs else args[3]
        strat = kwargs.get("strategy_label") if "strategy_label" in kwargs else args[4]
        return {
            "item_id": item["id"],
            "strategy_label": strat,
            "request_id": "req_123",
            "response": {
                "output": "Answer",
                "cache": {"hit": is_second_pass, "kind": "exact" if is_second_pass else None},
                "usage": {"total_cost_usd": 0.0 if is_second_pass else 0.001}
            },
            "error": None,
            "latency_ms": 50
        }

    try:
        with patch("eval.run_eval.run_single_item", side_effect=mock_replay):
            await execute_eval_run(
                base_url="http://fake",
                api_key="key",
                strategies=["fixed:lite"],
                limit=1,
                max_spend_usd=1.0,
                out_dir=temp_dir,
                golden_set_path=temp_golden,
                cache_replay=True,
            )

        cache_meta = os.path.join(temp_dir, "cache_replay.json")
        with open(cache_meta, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["cache_hit_rate_second_pass"] == 1.0
    finally:
        shutil.rmtree(temp_dir)
