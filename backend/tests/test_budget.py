"""Tests for in-process daily budget enforcement."""

from fastapi.testclient import TestClient
from app.config import Settings, get_settings
from app.dependencies import (
    get_cache_store,
    get_embedder,
    get_ledger,
    get_tier_client,
)
from app.main import create_app
from app.services.ledger import BudgetLedger


def test_budget_exceeded_429_before_model_call(
    fake_tier_client,
    fake_embedder,
    fake_cache_store,
):
    """Verify exceeding daily budget blocks execution before calling Gemini."""
    tiny_budget_settings = Settings(
        gcp_project_id="test-project",
        api_key="test-key",
        daily_budget_usd=0.0001,
        router_config_path="app/router.yaml",
        complete_limits="100/minute",
        max_prompt_chars=20000,
        max_output_tokens=1024,
    )
    test_ledger = BudgetLedger()
    test_ledger.reset_for_tests()

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tiny_budget_settings
    app.dependency_overrides[get_tier_client] = lambda: fake_tier_client
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    app.dependency_overrides[get_cache_store] = lambda: fake_cache_store
    app.dependency_overrides[get_ledger] = lambda: test_ledger

    local_client = TestClient(app)
    headers = {"X-API-Key": "test-key"}
    payload = {"prompt": "First request", "strategy": "fixed", "tier": "lite"}

    # Request 1: succeeds and incurs cost > 0.0001
    r1 = local_client.post("/api/v1/complete", headers=headers, json=payload)
    assert r1.status_code == 200
    assert fake_tier_client.call_count == 1

    # Request 2: rejected with 429 DAILY_BUDGET_EXCEEDED, model call count remains 1
    r2 = local_client.post("/api/v1/complete", headers=headers, json=payload)
    assert r2.status_code == 429
    assert "Retry-After" not in r2.headers
    data = r2.json()
    assert data["detail"]["code"] == "DAILY_BUDGET_EXCEEDED"
    assert fake_tier_client.call_count == 1
