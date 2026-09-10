"""Response models for Thrifty Router API."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class Attempt(BaseModel):
    """Metadata for a single tier or classifier execution attempt."""

    role: str = Field(..., description="'completion', 'classifier', or 'verifier'")
    tier: str = Field(..., description="Tier name executed")
    model: str = Field(..., description="Vertex AI model identifier")
    latency_ms: int = Field(..., description="Wall time in milliseconds for this attempt")
    input_tokens: int = Field(0, description="Input tokens used")
    output_tokens: int = Field(0, description="Output tokens generated")
    thinking_tokens: int = Field(0, description="Thinking tokens generated")
    cost_usd: float = Field(0.0, description="Cost in USD for this attempt")
    accepted: bool = Field(True, description="Whether this attempt was accepted")
    reject_reason: Optional[str] = Field(None, description="Reason if rejected")


class Routing(BaseModel):
    """Routing decisions and attempt history."""

    strategy: str = Field(..., description="Strategy used")
    tier: str = Field(..., description="Final chosen tier")
    model: str = Field(..., description="Final chosen model")
    reason: str = Field(..., description="Human-readable routing decision reason")
    attempts: List[Attempt] = Field(default_factory=list, description="List of all execution attempts")


class Usage(BaseModel):
    """Aggregated token usage and cost."""

    input_tokens: int = Field(0, description="Total input tokens")
    output_tokens: int = Field(0, description="Total output tokens")
    thinking_tokens: int = Field(0, description="Total thinking tokens")
    total_cost_usd: float = Field(0.0, description="Total cost in USD across all attempts")


class CacheInfo(BaseModel):
    """Cache hit status and similarity."""

    hit: bool = Field(False, description="Whether cache returned the result")
    kind: Optional[str] = Field(None, description="'exact', 'semantic', or null")
    similarity: Optional[float] = Field(None, description="Cosine similarity score if semantic hit")


class CompleteResponse(BaseModel):
    """Response payload for POST /api/v1/complete."""

    request_id: str = Field(..., description="Unique request ID with req_ prefix")
    output: str = Field(..., description="Generated text response")
    routing: Routing = Field(..., description="Routing details and attempts")
    usage: Usage = Field(..., description="Aggregated token usage and cost")
    cache: CacheInfo = Field(default_factory=CacheInfo, description="Semantic cache status")
    latency_ms: int = Field(..., description="Total wall time for request in milliseconds")


class HealthResponse(BaseModel):
    """Response payload for GET /api/v1/health."""

    status: str = "ok"
    tiers: List[str]
    strategies: List[str]
    version: str = "dev"


class TierInfo(BaseModel):
    """Tier definition metadata."""

    name: str
    model: str
    price_per_m_input_usd: float
    price_per_m_output_usd: float
    description: Optional[str] = None


class TiersResponse(BaseModel):
    """Response payload for GET /api/v1/tiers."""

    default_tier: str
    tiers: List[TierInfo]


class TierUsage(BaseModel):
    """Usage stats for a specific tier."""

    requests: int = 0
    cost_usd: float = 0.0


class CacheUsage(BaseModel):
    """Cache lookup statistics."""

    lookups: int = 0
    hits_exact: int = 0
    hits_semantic: int = 0


class UsageResponse(BaseModel):
    """Response payload for GET /api/v1/usage."""

    date: str
    requests: int
    total_cost_usd: float
    daily_budget_usd: float
    by_tier: Dict[str, TierUsage]
    cache: Optional[CacheUsage] = None
