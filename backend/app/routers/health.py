"""Health check endpoint."""

from typing import Any, Dict
from fastapi import APIRouter, Depends

from app.dependencies import get_router_config, get_router_orchestrator
from app.models.responses import HealthResponse
from app.services.router import RouterOrchestrator

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    config: Dict[str, Any] = Depends(get_router_config),
    orchestrator: RouterOrchestrator = Depends(get_router_orchestrator),
) -> HealthResponse:
    """Return service health status, available tiers, and supported strategies."""
    tier_names = [t["name"] for t in config["tiers"]]
    strategies = orchestrator.get_available_strategies()
    return HealthResponse(
        status="ok",
        tiers=tier_names,
        strategies=strategies,
        version="dev",
    )
