"""Application configuration via pydantic-settings."""

from functools import lru_cache
from typing import List, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Cloud Platform
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"

    # Vertex AI / Gemini
    gemini_location: str = "global"
    gemini_timeout_seconds: int = 60

    # Authentication
    api_key: str = ""

    # CORS
    allowed_origins: List[str] = []

    # API Documentation
    docs_enabled: bool = False

    # Router configuration
    router_config_path: str = "app/router.yaml"

    # Rate limiting & Budget guardrails
    daily_budget_usd: float = 2.0
    complete_limits: str = "10/minute;200/day"
    max_prompt_chars: int = 20000
    # Gemini 3.x counts thinking tokens against this budget; 1024 truncated most
    # pro-tier answers on the golden set (thinking alone ran up to ~2000 tokens).
    max_output_tokens: int = 8192

    # Embedding configuration (Phase 2 & Phase 4)
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    # Semantic Cache configuration (Phase 4)
    cache_enabled: bool = False
    firestore_database: str = "(default)"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str], object]) -> List[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if not v_str:
                return []
            if v_str.startswith("[") and v_str.endswith("]"):
                import json
                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    @model_validator(mode="after")
    def validate_required_fields(self) -> "Settings":
        """Raise a clear error at startup if required fields are missing."""
        missing = []
        if not self.gcp_project_id:
            missing.append("GCP_PROJECT_ID")
        if not self.api_key:
            missing.append("API_KEY")
        if missing:
            raise ValueError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Set them in your .env file or environment before starting the server."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
