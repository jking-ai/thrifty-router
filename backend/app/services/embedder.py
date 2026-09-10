"""Embedding service for semantic routing and caching."""

from abc import ABC, abstractmethod
import asyncio
import math
from typing import List, Optional

from google import genai
from google.genai import types

from app.config import Settings


def normalize_l2(vector: List[float]) -> List[float]:
    """Normalize vector to unit length (L2 norm)."""
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return vector
    return [x / norm for x in vector]


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two L2-normalized vectors."""
    if len(v1) != len(v2):
        raise ValueError(f"Vector dimensions mismatch: {len(v1)} vs {len(v2)}")
    return float(sum(a * b for a, b in zip(v1, v2)))


class Embedder(ABC):
    """Abstract interface for text embedding models."""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Embed a single text string returning an L2-normalized vector."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts returning L2-normalized vectors."""
        pass


class VertexEmbedder(Embedder):
    """Production embedder using gemini-embedding-001 on Vertex AI."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(
                vertexai=True,
                project=self._settings.gcp_project_id,
                location=self._settings.gemini_location,
            )
        return self._client

    async def embed(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        if not results:
            raise ValueError("No embedding returned from model")
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        client = self._get_client()
        model_name = self._settings.embedding_model
        dim = self._settings.embedding_dimensions

        config = types.EmbedContentConfig(
            output_dimensionality=dim,
            task_type="SEMANTIC_SIMILARITY",
        )

        def _sync_embed():
            resp = client.models.embed_content(
                model=model_name,
                contents=texts,
                config=config,
            )
            return resp

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, _sync_embed)

        normalized_vectors = []
        if response.embeddings:
            for emb in response.embeddings:
                raw_values = list(emb.values)
                normalized_vectors.append(normalize_l2(raw_values))
        return normalized_vectors
