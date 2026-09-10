"""Main FastAPI application entrypoint."""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import complete, health, tiers, usage


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Thrifty Router API",
        description="Cost-optimized Gemini tier routing gateway with semantic caching and evaluation harness.",
        version="1.0.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    # State and rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins if settings.allowed_origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers under /api/v1
    app.include_router(health.router)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(tiers.router, prefix="/api/v1")
    app.include_router(usage.router, prefix="/api/v1")
    app.include_router(complete.router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/api/v1/health")

    return app


app = create_app()
