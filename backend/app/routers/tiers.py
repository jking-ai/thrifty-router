"""Tiers specification endpoint."""

from typing import Any, Dict
from fastapi import APIRouter, Depends

from app.dependencies import get_router_config
from app.models.responses import TierInfo, TiersResponse

router = APIRouter(tags=["Tiers"])


@router.get("/tiers", response_model=TiersResponse)
async def list_tiers(config: Dict[str, Any] = Depends(get_router_config)) -> TiersResponse:
    """Return configured model tiers, pricing, and default tier."""
    tiers_list = [
        TierInfo(
            name=t["name"],
            model=t["model"],
            price_per_m_input_usd=t["price_per_m_input_usd"],
            price_per_m_output_usd=t["price_per_m_output_usd"],
            description=t.get("description"),
        )
        for t in config["tiers"]
    ]
    return TiersResponse(
        default_tier=config["default_tier"],
        tiers=tiers_list,
    )
