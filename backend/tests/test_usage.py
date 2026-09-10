"""Tests for GET /api/v1/usage endpoint."""

from fastapi.testclient import TestClient


def test_usage_accumulates_by_tier(client: TestClient):
    """Verify multiple requests accumulate counts and costs by tier."""
    headers = {"X-API-Key": "test-api-key"}

    # Call on lite tier
    r1 = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Lite prompt", "strategy": "fixed", "tier": "lite"},
    )
    assert r1.status_code == 200

    # Call on pro tier
    r2 = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Pro prompt", "strategy": "fixed", "tier": "pro"},
    )
    assert r2.status_code == 200

    # Query usage
    resp = client.get("/api/v1/usage", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["requests"] == 2
    assert data["total_cost_usd"] > 0.0
    assert "lite" in data["by_tier"]
    assert data["by_tier"]["lite"]["requests"] == 1
    assert "pro" in data["by_tier"]
    assert data["by_tier"]["pro"]["requests"] == 1
