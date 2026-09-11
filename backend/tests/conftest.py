import os
from typing import Any, Callable, Dict, List, Optional
import pytest

# Set required environment variables before any app module is imported
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("API_KEY", "test-api-key")

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import (
    get_cache_store,
    get_embedder,
    get_ledger,
    get_router_config,
    get_tier_client,
)
from app.main import create_app
from app.rate_limit import limiter
from app.services.cache_store import FakeCacheStore
from app.services.embedder import Embedder, normalize_l2
from app.services.ledger import BudgetLedger
from app.services.router_config import load_router_config
from app.services.tier_client import GenerateResult, UpstreamError, UpstreamTimeout


class FakeTierClient:
    """Test fake for GeminiTierClient."""

    def __init__(self) -> None:
        self.call_count = 0
        self.calls: List[Dict[str, Any]] = []
        self.default_content = "Default test response\nCONFIDENCE: 90"
        self.default_tokens = (100, 200, 0)
        self.finish_reason = "STOP"
        self.raise_upstream_error = False
        self.raise_timeout = False
        # Custom tier-specific response handler: Callable[[model, prompt, ...], GenerateResult]
        self.handler: Optional[Callable[..., GenerateResult]] = None

    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> GenerateResult:
        self.call_count += 1
        self.calls.append({
            "model": model,
            "prompt": prompt,
            "system": system,
            "json_schema": json_schema,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        })

        if self.raise_timeout:
            raise UpstreamTimeout("Simulated upstream timeout")
        if self.raise_upstream_error:
            raise UpstreamError("GoogleAPIError", "Simulated upstream failure")

        if self.handler:
            return self.handler(model, prompt, system, json_schema, temperature, max_output_tokens)

        return GenerateResult(
            content=self.default_content,
            input_tokens=self.default_tokens[0],
            output_tokens=self.default_tokens[1],
            thinking_tokens=self.default_tokens[2],
            finish_reason=self.finish_reason,
        )


class FakeEmbedder(Embedder):
    """Test fake for text embeddings."""

    def __init__(self) -> None:
        self.embed_call_count = 0
        self.batch_call_count = 0
        self.utterance_call_count = 0
        # Map text -> vector
        self.custom_embeddings: Dict[str, List[float]] = {}
        self.default_vector = normalize_l2([1.0] * 768)

    async def embed(self, text: str) -> List[float]:
        self.embed_call_count += 1
        vec = self.custom_embeddings.get(text, self.default_vector)
        return normalize_l2(vec)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        self.batch_call_count += 1
        self.utterance_call_count += len(texts)
        return [await self.embed(t) for t in texts]


@pytest.fixture(autouse=True)
def reset_state():
    """Reset rate limiter and settings cache before each test."""
    limiter.reset()
    get_settings.cache_clear()
    get_router_config.cache_clear()
    get_tier_client.cache_clear()
    get_embedder.cache_clear()
    get_cache_store.cache_clear()
    yield
    limiter.reset()
    get_settings.cache_clear()
    get_router_config.cache_clear()
    get_tier_client.cache_clear()
    get_embedder.cache_clear()
    get_cache_store.cache_clear()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        gcp_project_id="test-project",
        api_key="test-api-key",
        daily_budget_usd=2.0,
        router_config_path="app/router.yaml",
        complete_limits="100/minute",
        max_prompt_chars=20000,
        max_output_tokens=1024,
        cache_enabled=False,
    )


@pytest.fixture
def fake_tier_client() -> FakeTierClient:
    return FakeTierClient()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def fake_cache_store() -> FakeCacheStore:
    return FakeCacheStore()


@pytest.fixture
def test_ledger() -> BudgetLedger:
    ledger = BudgetLedger()
    ledger.reset_for_tests()
    return ledger


@pytest.fixture
def client(
    test_settings: Settings,
    fake_tier_client: FakeTierClient,
    fake_embedder: FakeEmbedder,
    fake_cache_store: FakeCacheStore,
    test_ledger: BudgetLedger,
) -> TestClient:
    """Create FastAPI test client with injected test fakes."""
    app = create_app()

    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_tier_client] = lambda: fake_tier_client
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    app.dependency_overrides[get_cache_store] = lambda: fake_cache_store
    app.dependency_overrides[get_ledger] = lambda: test_ledger

    return TestClient(app)
