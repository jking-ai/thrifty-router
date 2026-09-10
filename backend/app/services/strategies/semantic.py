"""Semantic routing strategy using embedding cosine similarity."""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from app.services.embedder import Embedder, cosine_similarity


# Process-level cache for route embeddings: embedder_id -> embedded_routes
_GLOBAL_ROUTE_CACHE: Dict[int, List[Tuple[str, str, List[List[float]]]]] = {}
_CACHE_LOCK = asyncio.Lock()


class SemanticRouteMatcher:
    """Pre-computes and holds route utterance embeddings lazily in memory."""

    def __init__(self, routes_config: List[Dict[str, Any]], embedder: Embedder) -> None:
        self._routes_config = routes_config
        self._embedder = embedder
        # List of (route_name, tier, List[embedding])
        self._embedded_routes: List[Tuple[str, str, List[List[float]]]] = []

    async def _ensure_initialized(self) -> None:
        embedder_key = id(self._embedder)
        if embedder_key in _GLOBAL_ROUTE_CACHE:
            self._embedded_routes = _GLOBAL_ROUTE_CACHE[embedder_key]
            return

        async with _CACHE_LOCK:
            if embedder_key in _GLOBAL_ROUTE_CACHE:
                self._embedded_routes = _GLOBAL_ROUTE_CACHE[embedder_key]
                return

            embedded = []
            for r in self._routes_config:
                name = r["name"]
                tier = r["tier"]
                utterances = r["utterances"]
                embeddings = await self._embedder.embed_batch(utterances)
                embedded.append((name, tier, embeddings))
            _GLOBAL_ROUTE_CACHE[embedder_key] = embedded
            self._embedded_routes = embedded

    async def match(
        self, prompt: str, threshold: float, default_tier: str
    ) -> Tuple[str, str]:
        """Match prompt against semantic routes.

        Returns:
            Tuple of (chosen_tier, reason_string)
        """
        await self._ensure_initialized()
        prompt_vec = await self._embedder.embed(prompt)

        best_score = -1.0
        best_route_name = ""
        best_route_tier = default_tier

        for name, tier, utterances_vecs in self._embedded_routes:
            # Score per route is max cosine similarity over its utterances
            route_score = max(cosine_similarity(prompt_vec, u_vec) for u_vec in utterances_vecs)
            if route_score > best_score:
                best_score = route_score
                best_route_name = name
                best_route_tier = tier

        formatted_score = f"{best_score:.3f}"

        if best_score >= threshold:
            reason = f"semantic route={best_route_name} score={formatted_score}"
            return best_route_tier, reason
        else:
            reason = (
                f"semantic no_match best={best_route_name} score={formatted_score} default={default_tier}"
            )
            return default_tier, reason
