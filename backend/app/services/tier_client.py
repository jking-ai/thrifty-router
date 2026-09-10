"""Gemini client wrapping google-genai Vertex AI backend."""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from app.config import Settings


@dataclass
class GenerateResult:
    """Standardized output from a Gemini completion call."""

    content: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    finish_reason: str = "STOP"


class UpstreamError(Exception):
    """Raised when upstream model call fails."""

    def __init__(self, exception_class: str, message: str):
        super().__init__(message)
        self.exception_class = exception_class


class UpstreamTimeout(Exception):
    """Raised when upstream model call exceeds timeout."""

    pass


class GeminiTierClient:
    """Client for generating completions across Gemini tiers."""

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

    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> GenerateResult:
        """Call Gemini model via Vertex AI backend with timeout and error mapping."""
        timeout = float(self._settings.gemini_timeout_seconds)

        # Build GenerateContentConfig
        config_args: Dict[str, Any] = {
            "temperature": temperature,
        }
        if max_output_tokens is not None:
            config_args["max_output_tokens"] = max_output_tokens
        if system:
            config_args["system_instruction"] = system
        if json_schema:
            config_args["response_mime_type"] = "application/json"
            config_args["response_schema"] = json_schema

        config = types.GenerateContentConfig(**config_args)
        client = self._get_client()

        def _sync_call():
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )

        try:
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_call),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise UpstreamTimeout("Upstream Gemini request timed out")
        except Exception as exc:
            raise UpstreamError(
                exception_class=exc.__class__.__name__,
                message=str(exc),
            )

        # Extract usage and tokens
        input_tokens = 0
        output_tokens = 0
        thinking_tokens = 0
        if response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            thinking_tokens = getattr(response.usage_metadata, "thoughts_token_count", 0) or 0

        # Extract text content and finish reason
        content = ""
        finish_reason = "STOP"
        if response.candidates and len(response.candidates) > 0:
            cand = response.candidates[0]
            if cand.finish_reason:
                finish_reason = str(cand.finish_reason.name if hasattr(cand.finish_reason, "name") else cand.finish_reason)
            if cand.content and cand.content.parts:
                parts_text = [p.text for p in cand.content.parts if hasattr(p, "text") and p.text]
                content = "".join(parts_text)
        elif response.text:
            content = response.text

        return GenerateResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            finish_reason=finish_reason,
        )
