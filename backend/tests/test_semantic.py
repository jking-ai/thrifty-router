"""Tests for semantic routing strategy."""

import re
from fastapi.testclient import TestClient
from app.services.embedder import normalize_l2
from tests.conftest import FakeEmbedder


def test_embedder_normalizes():
    """Verify L2 normalization produces unit vectors."""
    raw = [3.0, 4.0]
    norm = normalize_l2(raw)
    assert pytest_approx(norm[0], 0.6)
    assert pytest_approx(norm[1], 0.8)


def pytest_approx(val, target, tol=1e-5):
    return abs(val - target) < tol


def test_picks_route_above_threshold(client: TestClient, fake_embedder: FakeEmbedder):
    """When prompt embedding aligns with a route utterance >= 0.60, select that route's tier."""
    headers = {"X-API-Key": "test-api-key"}
    prompt_text = "Design a distributed multi-agent system in Go"

    # Set prompt vector and target utterance vector to produce similarity 0.900
    # Vector 1: [0.9, sqrt(1-0.9^2), 0...], Vector 2: [1.0, 0, 0...] -> dot product = 0.9
    v_utterance = [1.0] + [0.0] * 767
    v_prompt = [0.9, (1.0 - 0.9**2)**0.5] + [0.0] * 766

    fake_embedder.custom_embeddings[prompt_text] = v_prompt
    # Associate with one utterance in complex_reasoning_and_code route
    target_utterance = "Architect a distributed multi-agent system in Go using ADK with inspect-and-repair gates"
    fake_embedder.custom_embeddings[target_utterance] = v_utterance

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": prompt_text, "strategy": "semantic"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["routing"]["tier"] == "pro"
    assert "semantic route=complex_reasoning_and_code score=0.900" in data["routing"]["reason"]


def test_falls_back_below_threshold(client: TestClient, fake_embedder: FakeEmbedder):
    """When best similarity is below threshold (e.g. 0.300), fall back to default_tier (lite)."""
    headers = {"X-API-Key": "test-api-key"}
    prompt_text = "Completely unrelated prompt"

    v_utterance = [1.0] + [0.0] * 767
    v_prompt = [0.3, (1.0 - 0.3**2)**0.5] + [0.0] * 766

    fake_embedder.custom_embeddings[prompt_text] = v_prompt
    fake_embedder.default_vector = v_utterance

    resp = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": prompt_text, "strategy": "semantic"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["routing"]["tier"] == "lite"
    reason = data["routing"]["reason"]
    assert re.match(r"^semantic no_match best=\S+ score=0\.300 default=lite$", reason)


def test_route_embeddings_built_once(client: TestClient, fake_embedder: FakeEmbedder):
    """Verify route utterance embeddings are computed lazily once across requests."""
    headers = {"X-API-Key": "test-api-key"}

    r1 = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "First prompt", "strategy": "semantic"},
    )
    assert r1.status_code == 200
    first_utterance_calls = fake_embedder.utterance_call_count
    assert first_utterance_calls >= 24  # At least 8 utterances * 3 tiers

    r2 = client.post(
        "/api/v1/complete",
        headers=headers,
        json={"prompt": "Second prompt", "strategy": "semantic"},
    )
    assert r2.status_code == 200
    # Utterance calls should NOT increase on second request
    assert fake_embedder.utterance_call_count == first_utterance_calls
