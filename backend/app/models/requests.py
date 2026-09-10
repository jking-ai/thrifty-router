"""Request models for Thrifty Router API."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class CompleteRequest(BaseModel):
    """Payload for POST /api/v1/complete."""

    prompt: str = Field(..., min_length=1, description="User prompt text")
    system: Optional[str] = Field(None, max_length=4000, description="Optional system instructions")
    strategy: str = Field("fixed", description="Routing strategy: fixed, semantic, classifier, cascade")
    tier: Optional[str] = Field(None, description="Tier name (required for fixed strategy)")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_output_tokens: Optional[int] = Field(None, ge=1, description="Maximum output tokens")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="Optional JSON schema for structured output")
    use_cache: bool = Field(True, description="Whether to check and write to semantic cache")
