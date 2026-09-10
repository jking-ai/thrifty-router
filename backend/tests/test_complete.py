"""Tests for POST /api/v1/complete endpoint under fixed strategy."""

from fastapi.testclient import TestClient
from tests.conftest import FakeTierClient


def test_fixed_returns_contract_shape(client: TestClient, fake_tier_client: FakeTierClient):
    """Verify fixed strategy returns complete response matching contract shape."""
    headers = {"X-API-Key": "test-api-key"}
    payload = {
        "prompt": "Hello world",
        "system": "You are helpful",
        "strategy": "fixed",
        "tier": "lite",
        "temperature": 0.2,
        "max_output_tokens": 512,
    }

    resp = client.post("/api/v1/complete", headers=headers, json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["request_id"].startswith("req_")
    assert data["output"] == fake_tier_client.default_content
    assert data["routing"]["strategy"] == "fixed"
    assert data["routing"]["tier"] == "lite"
    assert data["routing"]["model"] == "gemini-3.1-flash-lite"
    assert data["routing"]["reason"] == "caller-specified"

    attempts = data["routing"]["attempts"]
    assert len(attempts) == 1
    att = attempts[0]
    assert att["role"] == "completion"
    assert att["tier"] == "lite"
    assert att["model"] == "gemini-3.1-flash-lite"
    assert att["accepted"] is True
    assert att["reject_reason"] is None
    assert att["cost_usd"] > 0.0

    usage = data["usage"]
    assert usage["input_tokens"] == att["input_tokens"]
    assert usage["output_tokens"] == att["output_tokens"]
    assert usage["total_cost_usd"] == att["cost_usd"]

    assert data["latency_ms"] >= 0
    assert data["cache"]["hit"] is False


def test_fixed_missing_tier_400(client: TestClient):
    """Verify fixed strategy without tier returns 400 TIER_REQUIRED."""
    headers = {"X-API-Key": "test-api-key"}
    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Hello", "strategy": "fixed"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "TIER_REQUIRED"


def test_unknown_tier_400(client: TestClient):
    """Verify unknown tier returns 400 UNKNOWN_TIER."""
    headers = {"X-API-Key": "test-api-key"}
    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Hello", "strategy": "fixed", "tier": "ultra"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "UNKNOWN_TIER"


def test_unknown_strategy_400(client: TestClient):
    """Verify unknown strategy returns 400 STRATEGY_NOT_AVAILABLE."""
    headers = {"X-API-Key": "test-api-key"}
    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Hello", "strategy": "random_guess", "tier": "lite"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "STRATEGY_NOT_AVAILABLE"


def test_prompt_too_long_413(client: TestClient):
    """Verify prompts exceeding MAX_PROMPT_CHARS return 413 PROMPT_TOO_LONG."""
    headers = {"X-API-Key": "test-api-key"}
    huge_prompt = "A" * 20001
    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": huge_prompt, "strategy": "fixed", "tier": "lite"},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"]["code"] == "PROMPT_TOO_LONG"


def test_json_schema_passthrough(client: TestClient, fake_tier_client: FakeTierClient):
    """Verify json_schema parameter is forwarded to model client."""
    headers = {"X-API-Key": "test-api-key"}
    schema = {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    }
    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "What is the capital?", "strategy": "fixed", "tier": "lite", "json_schema": schema},
    )
    assert resp.status_code == 200
    assert len(fake_tier_client.calls) == 1
    assert fake_tier_client.calls[0]["json_schema"] == schema
