"""Tests for API Key authentication middleware."""

from fastapi.testclient import TestClient


def test_missing_key_401(client: TestClient):
    """Verify missing X-API-Key returns 401 with standard UNAUTHORIZED envelope."""
    resp = client.post(
        "/api/v1/complete",
        json={"prompt": "Hello", "strategy": "fixed", "tier": "lite"},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"]["code"] == "UNAUTHORIZED"
    assert "Missing or invalid API key" in data["detail"]["message"]


def test_wrong_key_401(client: TestClient):
    """Verify wrong X-API-Key returns 401."""
    resp = client.post(
        "/api/v1/complete",
        headers={"X-API-Key": "incorrect-key"},
        json={"prompt": "Hello", "strategy": "fixed", "tier": "lite"},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"]["code"] == "UNAUTHORIZED"


def test_health_and_tiers_no_auth(client: TestClient):
    """Verify GET /api/v1/health and GET /api/v1/tiers do not require authentication."""
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    tiers_resp = client.get("/api/v1/tiers")
    assert tiers_resp.status_code == 200
    assert "tiers" in tiers_resp.json()
