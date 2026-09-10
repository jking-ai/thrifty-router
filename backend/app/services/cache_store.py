"""Cache store abstraction and Firestore vector search implementation."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple

from app.services.embedder import cosine_similarity


class CacheStore(ABC):
    """Abstract interface for cache persistence and vector search."""

    @abstractmethod
    async def get_exact(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve document by exact SHA256 key."""
        pass

    @abstractmethod
    async def find_nearest(
        self,
        prompt_embedding: List[float],
        system_hash: str,
        schema_hash: str,
        similarity_threshold: float,
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """Find nearest semantic neighbor meeting threshold and matching hashes.

        Returns (document, similarity) or None.
        """
        pass

    @abstractmethod
    async def write_doc(self, doc: Dict[str, Any]) -> None:
        """Write a cache document."""
        pass

    @abstractmethod
    async def increment_hit_count(self, key: str) -> None:
        """Increment hit count for a cached document."""
        pass


class FakeCacheStore(CacheStore):
    """In-memory cache store for tests."""

    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}
        self.hit_counts: Dict[str, int] = {}
        self.write_count = 0
        self.raise_on_lookup = False

    async def get_exact(self, key: str) -> Optional[Dict[str, Any]]:
        if self.raise_on_lookup:
            raise RuntimeError("Fake lookup failure")
        doc = self.docs.get(key)
        if not doc:
            return None
        # Check expiration
        expires_at = doc.get("expires_at")
        if expires_at and expires_at < datetime.now(timezone.utc):
            return None
        return doc

    async def find_nearest(
        self,
        prompt_embedding: List[float],
        system_hash: str,
        schema_hash: str,
        similarity_threshold: float,
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        if self.raise_on_lookup:
            raise RuntimeError("Fake lookup failure")
        best_doc = None
        best_sim = -1.0
        now = datetime.now(timezone.utc)

        for doc in self.docs.values():
            expires_at = doc.get("expires_at")
            if expires_at and expires_at < now:
                continue
            if doc.get("system_hash") != system_hash or doc.get("schema_hash") != schema_hash:
                continue
            doc_emb = doc.get("prompt_embedding")
            if not doc_emb:
                continue
            sim = cosine_similarity(prompt_embedding, doc_emb)
            if sim > best_sim:
                best_sim = sim
                best_doc = doc

        if best_sim >= similarity_threshold and best_doc is not None:
            return best_doc, best_sim
        return None

    async def write_doc(self, doc: Dict[str, Any]) -> None:
        key = doc["key"]
        self.docs[key] = doc
        self.hit_counts[key] = doc.get("hit_count", 0)
        self.write_count += 1

    async def increment_hit_count(self, key: str) -> None:
        if key in self.docs:
            self.docs[key]["hit_count"] = self.docs[key].get("hit_count", 0) + 1
            self.hit_counts[key] = self.docs[key]["hit_count"]


class FirestoreCacheStore(CacheStore):
    """Production Firestore cache store with native vector search."""

    def __init__(self, project_id: str, database: str = "(default)", collection_name: str = "thrifty_cache") -> None:
        from google.cloud import firestore
        self._db = firestore.AsyncClient(project=project_id, database=database)
        self._collection_name = collection_name

    async def get_exact(self, key: str) -> Optional[Dict[str, Any]]:
        doc_ref = self._db.collection(self._collection_name).document(key)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict()
        expires_at = data.get("expires_at")
        if expires_at and expires_at < datetime.now(timezone.utc):
            return None
        return data

    async def find_nearest(
        self,
        prompt_embedding: List[float],
        system_hash: str,
        schema_hash: str,
        similarity_threshold: float,
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        from google.cloud.firestore_v1.vector import Vector
        from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

        distance_threshold = 1.0 - similarity_threshold
        collection = self._db.collection(self._collection_name)

        query = (
            collection.where("system_hash", "==", system_hash)
            .where("schema_hash", "==", schema_hash)
            .find_nearest(
                vector_field="prompt_embedding",
                query_vector=Vector(prompt_embedding),
                distance_measure=DistanceMeasure.COSINE,
                limit=1,
                distance_result_field="distance",
                distance_threshold=distance_threshold,
            )
        )

        results = [doc async for doc in query.stream()]
        if not results:
            return None

        hit_doc = results[0]
        data = hit_doc.to_dict()
        now = datetime.now(timezone.utc)
        expires_at = data.get("expires_at")
        if expires_at and expires_at < now:
            return None

        distance = data.get("distance", 1.0)
        similarity = round(1.0 - float(distance), 3)
        return data, similarity

    async def write_doc(self, doc: Dict[str, Any]) -> None:
        from google.cloud.firestore_v1.vector import Vector
        data = dict(doc)
        if isinstance(data.get("prompt_embedding"), list):
            data["prompt_embedding"] = Vector(data["prompt_embedding"])
        key = doc["key"]
        doc_ref = self._db.collection(self._collection_name).document(key)
        await doc_ref.set(data)

    async def increment_hit_count(self, key: str) -> None:
        from google.cloud import firestore
        doc_ref = self._db.collection(self._collection_name).document(key)
        await doc_ref.update({"hit_count": firestore.Increment(1)})
