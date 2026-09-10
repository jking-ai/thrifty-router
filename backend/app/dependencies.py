"""FastAPI dependency providers for services and singletons."""

from functools import lru_cache
import os
from typing import Any, Dict

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.cache import SemanticCacheManager
from app.services.cache_store import CacheStore, FirestoreCacheStore
from app.services.embedder import Embedder, VertexEmbedder
from app.services.ledger import BudgetLedger
from app.services.router import RouterOrchestrator
from app.services.router_config import load_router_config
from app.services.tier_client import GeminiTierClient

# Process-level singletons
_LEDGER_SINGLETON = BudgetLedger()


def get_ledger() -> BudgetLedger:
    """Return in-process BudgetLedger singleton."""
    return _LEDGER_SINGLETON


@lru_cache
def get_router_config() -> Dict[str, Any]:
    """Load and return router configuration."""
    settings = get_settings()
    # If path is relative, resolve relative to backend root
    path = settings.router_config_path
    if not os.path.isabs(path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, path)
    return load_router_config(path)


def get_tier_client(settings: Settings = Depends(get_settings)) -> GeminiTierClient:
    """Return Gemini tier client."""
    return GeminiTierClient(settings=settings)


def get_embedder(settings: Settings = Depends(get_settings)) -> Embedder:
    """Return embedder instance."""
    return VertexEmbedder(settings=settings)


def get_cache_store(settings: Settings = Depends(get_settings)) -> CacheStore:
    """Return cache store instance."""
    return FirestoreCacheStore(
        project_id=settings.gcp_project_id,
        database=settings.firestore_database,
    )


def get_cache_manager(
    settings: Settings = Depends(get_settings),
    store: CacheStore = Depends(get_cache_store),
    embedder: Embedder = Depends(get_embedder),
    config: Dict[str, Any] = Depends(get_router_config),
) -> SemanticCacheManager:
    """Return SemanticCacheManager instance."""
    cache_config = config.get("cache", {})
    return SemanticCacheManager(
        store=store,
        embedder=embedder,
        cache_config=cache_config,
        enabled=settings.cache_enabled,
    )


def get_router_orchestrator(
    config: Dict[str, Any] = Depends(get_router_config),
    tier_client: GeminiTierClient = Depends(get_tier_client),
    embedder: Embedder = Depends(get_embedder),
) -> RouterOrchestrator:
    """Return RouterOrchestrator instance."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompts_dir = os.path.join(base_dir, "prompts")
    return RouterOrchestrator(
        router_config=config,
        tier_client=tier_client,
        embedder=embedder,
        prompts_dir=prompts_dir,
    )
