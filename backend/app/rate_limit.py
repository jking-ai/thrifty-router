"""Per-IP rate limiting via slowapi."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


def get_client_ip(request: Request) -> str:
    """Resolve the real client IP, honoring X-Forwarded-For from Cloud Run.

    The leftmost entry is the original client IP.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


COMPLETE_LIMITS = "10/minute;200/day"


def get_complete_limits() -> str:
    """Return configured rate limit dynamically from env or settings."""
    import os
    if "COMPLETE_LIMITS" in os.environ:
        return os.environ["COMPLETE_LIMITS"]
    from app.config import get_settings
    try:
        return get_settings().complete_limits
    except Exception:
        return COMPLETE_LIMITS


limiter = Limiter(key_func=get_client_ip, headers_enabled=False)


def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Return JSON 429 when rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": {
                "code": "RATE_LIMITED",
                "message": (
                    f"Rate limit exceeded: {exc.detail}. "
                    "Please slow down and try again shortly."
                ),
            }
        },
        headers={"Retry-After": "60"},
    )
