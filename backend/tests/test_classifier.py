"""Tests for classifier routing strategy."""

import json
from fastapi.testclient import TestClient
from app.services.tier_client import GenerateResult
from tests.conftest import FakeTierClient


def test_classifier_selects_tier(client: TestClient, fake_tier_client: FakeTierClient):
    """Verify classifier call selects tier, records classifier attempt, and sums usage."""
    headers = {"X-API-Key": "test-api-key"}

    def custom_handler(model, prompt, system, json_schema, temperature, max_output_tokens):
        if json_schema and "tier" in json_schema.get("properties", {}):
            # Classifier call
            return GenerateResult(
                content=json.dumps({"tier": "standard", "reason": "extraction required"}),
                input_tokens=50,
                output_tokens=15,
                thinking_tokens=0,
            )
        # Completion call
        return GenerateResult(
            content="Extraction completed successfully",
            input_tokens=100,
            output_tokens=40,
            thinking_tokens=0,
        )

    fake_tier_client.handler = custom_handler

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Extract JSON from text", "strategy": "classifier"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["routing"]["tier"] == "standard"
    assert data["routing"]["reason"].startswith("classifier tier=standard: extraction required")

    attempts = data["routing"]["attempts"]
    assert len(attempts) == 2
    assert attempts[0]["role"] == "classifier"
    assert attempts[0]["tier"] == "lite"
    assert attempts[1]["role"] == "completion"
    assert attempts[1]["tier"] == "standard"

    # Usage sums both attempts
    assert data["usage"]["input_tokens"] == 150
    assert data["usage"]["output_tokens"] == 55


def test_classifier_error_falls_back(client: TestClient, fake_tier_client: FakeTierClient):
    """Verify classifier exception gracefully falls back to default_tier with 200 status."""
    headers = {"X-API-Key": "test-api-key"}

    call_idx = 0

    def fail_first_call(model, prompt, system, json_schema, temperature, max_output_tokens):
        nonlocal call_idx
        call_idx += 1
        if call_idx == 1:
            raise RuntimeError("Classifier service unavailable")
        return GenerateResult(
            content="Completion result after fallback",
            input_tokens=40,
            output_tokens=20,
            thinking_tokens=0,
        )

    fake_tier_client.handler = fail_first_call

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Some query", "strategy": "classifier"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["routing"]["tier"] == "lite"
    assert data["routing"]["reason"].startswith("classifier_error: RuntimeError default=lite")


def test_classifier_unknown_tier_falls_back(client: TestClient, fake_tier_client: FakeTierClient):
    """Verify unknown tier in classifier response falls back to default_tier."""
    headers = {"X-API-Key": "test-api-key"}

    def return_unknown_tier(model, prompt, system, json_schema, temperature, max_output_tokens):
        if json_schema and "tier" in json_schema.get("properties", {}):
            return GenerateResult(
                content=json.dumps({"tier": "ultra_expensive", "reason": "overfit"}),
                input_tokens=50,
                output_tokens=15,
                thinking_tokens=0,
            )
        return GenerateResult(
            content="Fallback answer",
            input_tokens=40,
            output_tokens=20,
            thinking_tokens=0,
        )

    fake_tier_client.handler = return_unknown_tier

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Some query", "strategy": "classifier"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["routing"]["tier"] == "lite"
    assert "unknown_tier" in data["routing"]["reason"]


def test_health_lists_strategies(client: TestClient):
    """Verify health endpoint lists all registered strategies."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "fixed" in data["strategies"]
    assert "semantic" in data["strategies"]
    assert "classifier" in data["strategies"]
    assert "cascade" in data["strategies"]
