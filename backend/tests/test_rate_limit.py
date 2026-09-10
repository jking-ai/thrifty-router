"""Tests for per-IP rate limiting."""

from fastapi.testclient import TestClient
from app.config import Settings, get_settings
from app.main import create_app
from app.rate_limit import limiter


def test_complete_rate_limited_429(
    test_settings: Settings,
    fake_tier_client,
    fake_embedder,
    fake_cache_store,
    test_ledger,
    monkeypatch,
):
    """With COMPLETE_LIMITS='2/minute', third request from same IP returns 429."""
    limiter.reset()
    monkeypatch.setenv("COMPLETE_LIMITS", "2/minute")
    get_settings.cache_clear()
    custom_settings = Settings(
        gcp_project_id="test-project",
        api_key="test-key",
        daily_budget_usd=2.0,
        router_config_path="app/router.yaml",
        complete_limits="2/minute",
        max_prompt_chars=20000,
        max_output_tokens=1024,
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: custom_settings
    from app.dependencies import get_tier_client, get_embedder, get_cache_store, get_ledger
    app.dependency_overrides[get_tier_client] = lambda: fake_tier_client
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    app.dependency_overrides[get_cache_store] = lambda: fake_cache_store
    app.dependency_overrides[get_ledger] = lambda: test_ledger

    local_client = TestClient(app)
    headers = {"X-API-Key": "test-key", "X-Forwarded-For": "203.0.113.195"}
    payload = {"prompt": "Test prompt", "strategy": "fixed", "tier": "lite"}

    # Request 1: OK
    r1 = local_client.post("/api/v1/complete", headers=headers, json=payload)
    assert r1.status_code == 200

    # Request 2: OK
    r2 = local_client.post("/api/v1/complete", headers=headers, json=payload)
    assert r2.status_code == 200

    # Request 3: 429 RATE_LIMITED
    r3 = local_client.post("/api/v1/complete", headers=headers, json=payload)
    assert r3.status_code == 429
    assert r3.headers.get("Retry-After") == "60"
    data = r3.json()
    assert data["detail"]["code"] == "RATE_LIMITED"
