import secrets
from fastapi import Depends, Header, HTTPException, status
from app.config import Settings, get_settings


async def require_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> str:
    """Validate X-API-Key header using constant-time comparison."""
    if not x_api_key or not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Missing or invalid API key"},
        )

    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Missing or invalid API key"},
        )

    return x_api_key
