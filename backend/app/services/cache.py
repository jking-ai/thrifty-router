"""Semantic cache manager orchestrating exact and vector lookups."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.cache_store import CacheStore
from app.services.embedder import Embedder

logger = logging.getLogger("thrifty_router.cache")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_prompt(prompt: str) -> str:
    """Strip, collapse internal whitespace runs to one space, and lowercase."""
    return WHITESPACE_RE.sub(" ", prompt.strip()).lower()


def canonical_json(data: Any) -> str:
    """Produce deterministic canonical JSON string."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def compute_hashes(
    prompt: str,
    system: Optional[str],
    json_schema: Optional[Dict[str, Any]],
) -> Tuple[str, str, str]:
    """Compute (exact_key, system_hash, schema_hash)."""
    norm_prompt = normalize_prompt(prompt)
    sys_str = system or ""
    schema_str = canonical_json(json_schema) if json_schema is not None else "null"

    raw_key = f"{norm_prompt}\x1f{sys_str}\x1f{schema_str}"
    key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    system_hash = hashlib.sha256(sys_str.encode("utf-8")).hexdigest()
    schema_hash = hashlib.sha256(schema_str.encode("utf-8")).hexdigest()

    return key, system_hash, schema_hash


class SemanticCacheManager:
    """Manages exact and vector caching for router completions."""

    def __init__(
        self,
        store: CacheStore,
        embedder: Embedder,
        cache_config: Dict[str, Any],
        enabled: bool = False,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._config = cache_config
        self._enabled = enabled
        self._threshold = float(cache_config.get("similarity_threshold", 0.95))
        self._ttl_hours = int(cache_config.get("ttl_hours", 24))
        self._max_temperature = float(cache_config.get("max_temperature", 0.3))

    def should_cache(self, use_cache: bool, temperature: float) -> bool:
        """Check whether caching is active for this request."""
        return self._enabled and use_cache and (temperature <= self._max_temperature)

    async def lookup(
        self,
        prompt: str,
        system: Optional[str],
        json_schema: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[float], Optional[List[float]]]:
        """Perform exact then semantic lookup.

        Returns:
            Tuple of (doc, kind, similarity, prompt_embedding)
        """
        key, system_hash, schema_hash = compute_hashes(prompt, system, json_schema)
        prompt_embedding = None

        try:
            # 1. Exact lookup
            exact_doc = await self._store.get_exact(key)
            if exact_doc:
                await self._store.increment_hit_count(key)
                return exact_doc, "exact", 1.0, None
        except Exception as exc:
            print(json.dumps({"event": "cache_error", "stage": "lookup", "error": f"{exc.__class__.__name__}: {str(exc)}"}))
            return None, None, None, None

        # 2. Semantic lookup
        try:
            prompt_embedding = await self._embedder.embed(prompt)
            nearest = await self._store.find_nearest(
                prompt_embedding=prompt_embedding,
                system_hash=system_hash,
                schema_hash=schema_hash,
                similarity_threshold=self._threshold,
            )
            if nearest:
                doc, sim = nearest
                doc_key = doc.get("key", key)
                await self._store.increment_hit_count(doc_key)
                return doc, "semantic", round(sim, 3), prompt_embedding
        except Exception as exc:
            print(json.dumps({"event": "cache_error", "stage": "lookup", "error": f"{exc.__class__.__name__}: {str(exc)}"}))
            return None, None, None, prompt_embedding

        return None, None, None, prompt_embedding

    async def write(
        self,
        prompt: str,
        system: Optional[str],
        json_schema: Optional[Dict[str, Any]],
        output: str,
        tier: str,
        model: str,
        strategy: str,
        prompt_embedding: Optional[List[float]] = None,
    ) -> None:
        """Write completed output to cache store without raising on failure."""
        try:
            key, system_hash, schema_hash = compute_hashes(prompt, system, json_schema)
            if prompt_embedding is None:
                prompt_embedding = await self._embedder.embed(prompt)

            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(hours=self._ttl_hours)

            doc = {
                "key": key,
                "system_hash": system_hash,
                "schema_hash": schema_hash,
                "prompt_embedding": prompt_embedding,
                "prompt_preview": prompt[:200],
                "output": output,
                "tier": tier,
                "model": model,
                "strategy": strategy,
                "created_at": now,
                "expires_at": expires_at,
                "hit_count": 0,
            }
            await self._store.write_doc(doc)
        except Exception as exc:
            print(json.dumps({"event": "cache_error", "stage": "write", "error": f"{exc.__class__.__name__}: {str(exc)}"}))
