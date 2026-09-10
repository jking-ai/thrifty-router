"""Usage statistics and daily budget consumption endpoint."""

from fastapi import APIRouter, Depends

from app.auth import require_api_key
from app.config import Settings, get_settings
from app.dependencies import get_ledger
from app.models.responses import UsageResponse
from app.services.ledger import BudgetLedger

router = APIRouter(tags=["Usage"])


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    _: str = Depends(require_api_key),
    ledger: BudgetLedger = Depends(get_ledger),
    settings: Settings = Depends(get_settings),
) -> UsageResponse:
    """Return process-local request counts and costs accumulated today."""
    raw = ledger.get_usage(daily_budget_usd=settings.daily_budget_usd)
    return UsageResponse(**raw)
