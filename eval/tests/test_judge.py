import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from eval.judge import score_single_response


@pytest.mark.asyncio
async def test_parses_score_and_null_on_error():
    """Verify judge correctly parses numeric score, and returns score: null on gateway error."""
    mock_client = AsyncMock()

    # Successful call returning JSON score 4
    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.json.return_value = {
        "output": json.dumps({"score": 4, "rationale": "High quality"}),
        "usage": {"total_cost_usd": 0.005},
    }

    item = {"id": "g_0001", "prompt": "P", "rubric": "R"}
    resp_entry = {
        "item_id": "g_0001",
        "strategy_label": "cascade",
        "response": {"output": "Candidate answer"},
    }

    mock_client.post.return_value = ok_resp
    judg = await score_single_response(
        client=mock_client,
        base_url="http://fake",
        api_key="key",
        template="{prompt} {rubric} {reference} {answer}",
        item=item,
        resp_entry=resp_entry,
    )
    assert judg["score"] == 4
    assert judg["rationale"] == "High quality"
    assert judg["judge_cost_usd"] == 0.005

    # Error call returning 500
    err_resp = MagicMock()
    err_resp.status_code = 500
    mock_client.post.return_value = err_resp
    err_judg = await score_single_response(
        client=mock_client,
        base_url="http://fake",
        api_key="key",
        template="{prompt} {rubric} {reference} {answer}",
        item=item,
        resp_entry=resp_entry,
    )
    assert err_judg["score"] is None
