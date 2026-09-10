"""Tests for cascade routing strategy."""

import json
from fastapi.testclient import TestClient
from app.services.tier_client import GenerateResult
from tests.conftest import FakeTierClient


def test_accepts_first_tier(client: TestClient, fake_tier_client: FakeTierClient):
    """When first tier produces valid output >= min_confidence, accept immediately."""
    headers = {"X-API-Key": "test-api-key"}
    fake_tier_client.default_content = "42\nCONFIDENCE: 90"

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "What is 40 + 2?", "strategy": "cascade"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["output"] == "42"
    assert data["routing"]["tier"] == "lite"
    assert data["routing"]["reason"] == "cascade accepted at lite"

    attempts = data["routing"]["attempts"]
    assert len(attempts) == 1
    assert attempts[0]["accepted"] is True
    assert attempts[0]["reject_reason"] is None


def test_escalates_on_low_confidence(client: TestClient, fake_tier_client: FakeTierClient):
    """When first tier returns confidence < min_confidence (e.g. 40 < 70), escalate to standard."""
    headers = {"X-API-Key": "test-api-key"}
    call_count = 0

    def cascade_handler(model, prompt, system, json_schema, temperature, max_output_tokens):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return GenerateResult("Low confidence answer\nCONFIDENCE: 40", 50, 20, 0)
        return GenerateResult("High confidence answer\nCONFIDENCE: 85", 80, 30, 0)

    fake_tier_client.handler = cascade_handler

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Difficult algebra problem", "strategy": "cascade"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["output"] == "High confidence answer"
    assert data["routing"]["tier"] == "standard"
    assert data["routing"]["reason"] == "cascade escalated 1x accepted at standard"

    attempts = data["routing"]["attempts"]
    assert len(attempts) == 2
    assert attempts[0]["accepted"] is False
    assert attempts[0]["reject_reason"] == "low_confidence:40"
    assert attempts[1]["accepted"] is True


def test_escalates_on_missing_confidence_line(client: TestClient, fake_tier_client: FakeTierClient):
    """When text response lacks CONFIDENCE: <n> line, reject with no_confidence_line."""
    headers = {"X-API-Key": "test-api-key"}
    call_count = 0

    def missing_line_handler(model, prompt, system, json_schema, temperature, max_output_tokens):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return GenerateResult("Answer without confidence line", 50, 20, 0)
        return GenerateResult("Second answer\nCONFIDENCE: 95", 80, 30, 0)

    fake_tier_client.handler = missing_line_handler

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Some question", "strategy": "cascade"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["routing"]["attempts"][0]["reject_reason"] == "no_confidence_line"


def test_escalates_on_schema_invalid(client: TestClient, fake_tier_client: FakeTierClient):
    """When json_schema is provided, reject if output violates schema and escalate."""
    headers = {"X-API-Key": "test-api-key"}
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "integer"}},
        "required": ["answer"],
    }
    call_count = 0

    def schema_handler(model, prompt, system, json_schema, temperature, max_output_tokens):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return GenerateResult(json.dumps({"answer": "not an int"}), 50, 20, 0)
        return GenerateResult(json.dumps({"answer": 42}), 80, 30, 0)

    fake_tier_client.handler = schema_handler

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Parse number", "strategy": "cascade", "json_schema": schema},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["routing"]["tier"] == "standard"
    first_attempt = data["routing"]["attempts"][0]
    assert first_attempt["accepted"] is False
    assert first_attempt["reject_reason"].startswith("schema_invalid:")


def test_escalates_on_max_tokens_finish(client: TestClient, fake_tier_client: FakeTierClient):
    """When finish_reason is MAX_TOKENS, reject and escalate."""
    headers = {"X-API-Key": "test-api-key"}
    call_count = 0

    def finish_handler(model, prompt, system, json_schema, temperature, max_output_tokens):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return GenerateResult("Truncated output...", 50, 100, 0, finish_reason="MAX_TOKENS")
        return GenerateResult("Complete output\nCONFIDENCE: 90", 80, 50, 0, finish_reason="STOP")

    fake_tier_client.handler = finish_handler

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Long essay", "strategy": "cascade"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["routing"]["attempts"][0]["reject_reason"] == "finish_reason:MAX_TOKENS"


def test_final_tier_no_suffix_and_always_accepted(client: TestClient, fake_tier_client: FakeTierClient):
    """Final tier (pro) never receives confidence suffix and is accepted regardless of confidence line."""
    headers = {"X-API-Key": "test-api-key"}
    calls = []

    def three_tier_handler(model, prompt, system, json_schema, temperature, max_output_tokens):
        calls.append({"model": model, "system": system})
        # lite rejects
        if "flash-lite" in model:
            return GenerateResult("Lite\nCONFIDENCE: 20", 50, 20, 0)
        # standard rejects
        if "flash" in model and "lite" not in model:
            return GenerateResult("Standard\nCONFIDENCE: 30", 50, 20, 0)
        # pro output has no confidence line at all
        return GenerateResult("Pro answer without confidence line", 100, 50, 0)

    fake_tier_client.handler = three_tier_handler

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Deep analysis", "strategy": "cascade"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["routing"]["tier"] == "pro"
    # Verify pro call had no CONFIDENCE suffix in system
    pro_call = calls[-1]
    assert "CONFIDENCE: <0-100>" not in (pro_call["system"] or "")
    assert data["output"] == "Pro answer without confidence line"


def test_max_escalations_cap(client: TestClient, fake_tier_client: FakeTierClient):
    """Verify max_escalations caps escalation count."""
    headers = {"X-API-Key": "test-api-key"}

    # router.yaml has max_escalations: 2. We test that 3 attempts occur (lite, standard, pro)
    fake_tier_client.default_content = "Still low confidence\nCONFIDENCE: 10"

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Impossible problem", "strategy": "cascade"},
    )
    assert resp.status_code == 200
    data = resp.json()

    attempts = data["routing"]["attempts"]
    assert len(attempts) >= 2
    last_attempt = attempts[-1]
    assert last_attempt["accepted"] is True
    assert "max_escalations" in data["routing"]["reason"] or "last_tier" in data["routing"]["reason"]


def test_usage_sums_all_attempts(client: TestClient, fake_tier_client: FakeTierClient):
    """Verify token usage and cost sum across all cascade attempts."""
    headers = {"X-API-Key": "test-api-key"}
    call_count = 0

    def multi_handler(model, prompt, system, json_schema, temperature, max_output_tokens):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return GenerateResult("Attempt 1\nCONFIDENCE: 20", 100, 50, 0)
        return GenerateResult("Attempt 2\nCONFIDENCE: 90", 200, 100, 0)

    fake_tier_client.handler = multi_handler

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Multi attempt query", "strategy": "cascade"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["usage"]["input_tokens"] == 300
    assert data["usage"]["output_tokens"] == 150
    assert data["usage"]["total_cost_usd"] > 0.0


def test_health_lists_cascade(client: TestClient):
    """Verify cascade is in health endpoint strategies list."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert "cascade" in resp.json()["strategies"]
