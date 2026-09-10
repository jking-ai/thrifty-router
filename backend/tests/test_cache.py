"""Tests for semantic cache with exact and vector lookups."""

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import (
    get_cache_store,
    get_embedder,
    get_ledger,
    get_tier_client,
)
from app.main import create_app
from app.services.cache import compute_hashes
from app.services.cache_store import FakeCacheStore
from app.services.ledger import BudgetLedger
from tests.conftest import FakeEmbedder, FakeTierClient


def create_cache_client(
    fake_tier_client: FakeTierClient,
    fake_embedder: FakeEmbedder,
    fake_cache_store: FakeCacheStore,
    test_ledger: BudgetLedger,
    cache_enabled: bool = True,
) -> TestClient:
    settings = Settings(
        gcp_project_id="test-project",
        api_key="test-api-key",
        daily_budget_usd=2.0,
        router_config_path="app/router.yaml",
        complete_limits="100/minute",
        max_prompt_chars=20000,
        max_output_tokens=1024,
        cache_enabled=cache_enabled,
    )
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_tier_client] = lambda: fake_tier_client
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    app.dependency_overrides[get_cache_store] = lambda: fake_cache_store
    app.dependency_overrides[get_ledger] = lambda: test_ledger
    return TestClient(app)


def test_exact_hit(fake_tier_client, fake_embedder, fake_cache_store, test_ledger):
    """Second identical call returns exact cache hit, 0 cost, unchanged model calls."""
    client = create_cache_client(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, cache_enabled=True)
    headers = {"X-API-Key": "test-api-key"}
    payload = {"prompt": "What is the capital of Canada?", "strategy": "fixed", "tier": "lite", "temperature": 0.2}

    # Request 1: Cache miss, writes to store
    r1 = client.post("/api/v1/complete", headers=headers, json=payload)
    assert r1.status_code == 200
    assert r1.json()["cache"]["hit"] is False
    assert fake_tier_client.call_count == 1
    assert fake_cache_store.write_count == 1

    # Request 2: Cache hit exact
    r2 = client.post("/api/v1/complete", headers=headers, json=payload)
    assert r2.status_code == 200
    data = r2.json()

    assert data["cache"]["hit"] is True
    assert data["cache"]["kind"] == "exact"
    assert data["cache"]["similarity"] == 1.0
    assert data["routing"]["attempts"] == []
    assert data["routing"]["reason"] == "cache hit exact"
    assert data["usage"]["total_cost_usd"] == 0.0
    assert fake_tier_client.call_count == 1  # Not incremented!
    assert list(fake_cache_store.hit_counts.values())[0] == 1


def test_semantic_hit_above_threshold(fake_tier_client, fake_embedder, fake_cache_store, test_ledger):
    """When query is semantically similar (>= 0.95), return semantic cache hit."""
    client = create_cache_client(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, cache_enabled=True)
    headers = {"X-API-Key": "test-api-key"}

    p1 = "What is the capital of France?"
    p2 = "What's the capital city of France?"

    v1 = [1.0] + [0.0] * 767
    v2 = [0.97, (1.0 - 0.97**2)**0.5] + [0.0] * 766

    fake_embedder.custom_embeddings[p1] = v1
    fake_embedder.custom_embeddings[p2] = v2

    # Prime cache with p1
    r1 = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": p1, "strategy": "fixed", "tier": "lite", "temperature": 0.2},
    )
    assert r1.status_code == 200
    assert fake_tier_client.call_count == 1

    # Call with p2
    r2 = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": p2, "strategy": "fixed", "tier": "lite", "temperature": 0.2},
    )
    assert r2.status_code == 200
    data = r2.json()

    assert data["cache"]["hit"] is True
    assert data["cache"]["kind"] == "semantic"
    assert abs(data["cache"]["similarity"] - 0.97) < 0.01
    assert data["routing"]["attempts"] == []
    assert data["routing"]["reason"].startswith("cache hit semantic similarity=0.970")
    assert fake_tier_client.call_count == 1


def test_semantic_miss_below_threshold(fake_tier_client, fake_embedder, fake_cache_store, test_ledger):
    """When similarity is 0.90 (< 0.95), treat as cache miss and invoke model."""
    client = create_cache_client(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, cache_enabled=True)
    headers = {"X-API-Key": "test-api-key"}

    p1 = "Tell me about quantum computing"
    p2 = "Tell me about classical computing"

    v1 = [1.0] + [0.0] * 767
    v2 = [0.90, (1.0 - 0.90**2)**0.5] + [0.0] * 766

    fake_embedder.custom_embeddings[p1] = v1
    fake_embedder.custom_embeddings[p2] = v2

    client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": p1, "strategy": "fixed", "tier": "lite", "temperature": 0.2},
    )
    assert fake_tier_client.call_count == 1

    r2 = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": p2, "strategy": "fixed", "tier": "lite", "temperature": 0.2},
    )
    assert r2.status_code == 200
    assert r2.json()["cache"]["hit"] is False
    assert fake_tier_client.call_count == 2


def test_semantic_prefilter_excludes_other_system(fake_tier_client, fake_embedder, fake_cache_store, test_ledger):
    """Same prompt with different system instruction produces a cache miss."""
    client = create_cache_client(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, cache_enabled=True)
    headers = {"X-API-Key": "test-api-key"}

    client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Translate 'hello'", "system": "To French", "strategy": "fixed", "tier": "lite", "temperature": 0.2},
    )
    assert fake_tier_client.call_count == 1

    r2 = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Translate 'hello'", "system": "To Spanish", "strategy": "fixed", "tier": "lite", "temperature": 0.2},
    )
    assert r2.status_code == 200
    assert r2.json()["cache"]["hit"] is False
    assert fake_tier_client.call_count == 2


def test_high_temperature_skips_cache(fake_tier_client, fake_embedder, fake_cache_store, test_ledger):
    """Requests with temperature > 0.3 skip cache lookup and write."""
    client = create_cache_client(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, cache_enabled=True)
    headers = {"X-API-Key": "test-api-key"}

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Creative story", "temperature": 0.9, "strategy": "fixed", "tier": "lite"},
    )
    assert resp.status_code == 200
    assert resp.json()["cache"]["hit"] is False
    assert fake_cache_store.write_count == 0


def test_use_cache_false_skips_cache(fake_tier_client, fake_embedder, fake_cache_store, test_ledger):
    """use_cache=false skips cache check and storage."""
    client = create_cache_client(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, cache_enabled=True)
    headers = {"X-API-Key": "test-api-key"}

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Query", "use_cache": False, "strategy": "fixed", "tier": "lite"},
    )
    assert resp.status_code == 200
    assert fake_cache_store.write_count == 0


def test_cache_disabled_response_shape(client: TestClient, fake_cache_store):
    """When CACHE_ENABLED=false, response includes empty cache envelope and store is not called."""
    headers = {"X-API-Key": "test-api-key"}
    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Query", "strategy": "fixed", "tier": "lite"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cache"] == {"hit": False, "kind": None, "similarity": None}
    assert fake_cache_store.write_count == 0


def test_write_after_miss(fake_tier_client, fake_embedder, fake_cache_store, test_ledger):
    """Verify document written after miss has 24h TTL and contract fields."""
    client = create_cache_client(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, cache_enabled=True)
    headers = {"X-API-Key": "test-api-key"}

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Cache write test", "strategy": "fixed", "tier": "lite"},
    )
    assert resp.status_code == 200
    assert fake_cache_store.write_count == 1

    doc = list(fake_cache_store.docs.values())[0]
    required_keys = ["key", "system_hash", "schema_hash", "prompt_embedding", "prompt_preview", "output", "tier", "model", "strategy", "created_at", "expires_at", "hit_count"]
    for k in required_keys:
        assert k in doc

    time_diff = doc["expires_at"] - doc["created_at"]
    assert abs(time_diff.total_seconds() - 86400) < 5


def test_expired_doc_is_miss(fake_tier_client, fake_embedder, fake_cache_store, test_ledger):
    """Expired document in store is treated as a miss."""
    client = create_cache_client(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, cache_enabled=True)
    headers = {"X-API-Key": "test-api-key"}
    prompt = "Expired question"

    key, sys_h, sch_h = compute_hashes(prompt, None, None)
    expired_doc = {
        "key": key,
        "system_hash": sys_h,
        "schema_hash": sch_h,
        "prompt_embedding": [1.0] * 768,
        "prompt_preview": prompt,
        "output": "Old answer",
        "tier": "lite",
        "model": "model",
        "strategy": "fixed",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=48),
        "expires_at": datetime.now(timezone.utc) - timedelta(hours=24),
        "hit_count": 0,
    }
    fake_cache_store.docs[key] = expired_doc

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": prompt, "strategy": "fixed", "tier": "lite"},
    )
    assert resp.status_code == 200
    assert resp.json()["cache"]["hit"] is False


def test_store_error_is_miss_and_logged(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, capsys):
    """When cache store throws an error, proceed with completion and log error."""
    fake_cache_store.raise_on_lookup = True
    client = create_cache_client(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, cache_enabled=True)
    headers = {"X-API-Key": "test-api-key"}

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Error test", "strategy": "fixed", "tier": "lite"},
    )
    assert resp.status_code == 200
    captured = capsys.readouterr()
    assert "cache_error" in captured.out


def test_usage_cache_counters(fake_tier_client, fake_embedder, fake_cache_store, test_ledger):
    """Verify /usage reports lookups, exact hits, and semantic hits."""
    client = create_cache_client(fake_tier_client, fake_embedder, fake_cache_store, test_ledger, cache_enabled=True)
    headers = {"X-API-Key": "test-api-key"}

    # 1. Miss
    client.post("/api/v1/complete", headers=headers, json={"prompt": "Count test", "strategy": "fixed", "tier": "lite"})
    # 2. Exact hit
    client.post("/api/v1/complete", headers=headers, json={"prompt": "Count test", "strategy": "fixed", "tier": "lite"})

    resp = client.get("/api/v1/usage", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    cache_stats = data["cache"]
    assert cache_stats["lookups"] == 2
    assert cache_stats["hits_exact"] == 1
    assert cache_stats["hits_semantic"] == 0
