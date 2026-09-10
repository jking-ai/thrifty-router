"""Completion endpoint orchestrating cache, strategies, and cost ledger."""

import asyncio
import json
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.auth import require_api_key
from app.config import Settings, get_settings
from app.dependencies import (
    get_cache_manager,
    get_ledger,
    get_router_orchestrator,
    get_tier_client,
)
from app.models.requests import CompleteRequest
from app.models.responses import (
    Attempt,
    CacheInfo,
    CompleteResponse,
    Routing,
    Usage,
)
from app.rate_limit import COMPLETE_LIMITS, get_client_ip, get_complete_limits, limiter
from app.services.cache import SemanticCacheManager
from app.services.ledger import BudgetLedger
from app.services.router import RouterOrchestrator
from app.services.tier_client import GeminiTierClient, UpstreamError, UpstreamTimeout

router = APIRouter(tags=["Completion"])


def log_request(
    request_id: str,
    strategy: str,
    tier: str,
    model: str,
    http_status: int,
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int,
    total_cost_usd: float,
    latency_ms: int,
    attempts_count: int,
    client_ip: str,
    error_code: Optional[str] = None,
    cache_hit: Optional[str] = None,
    cache_similarity: Optional[float] = None,
) -> None:
    """Print one JSON log line to stdout per request contract."""
    payload: Dict[str, Any] = {
        "event": "complete",
        "request_id": request_id,
        "strategy": strategy,
        "tier": tier,
        "model": model,
        "status": http_status,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "total_cost_usd": total_cost_usd,
        "latency_ms": latency_ms,
        "attempts": attempts_count,
        "client_ip": client_ip,
    }
    if error_code:
        payload["error_code"] = error_code
    if cache_hit:
        payload["cache_hit"] = cache_hit
        payload["cache_similarity"] = cache_similarity
    print(json.dumps(payload), flush=True)


@router.post("/complete", response_model=CompleteResponse)
@limiter.limit(get_complete_limits)
async def complete(
    request: Request,
    req: CompleteRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    settings: Settings = Depends(get_settings),
    ledger: BudgetLedger = Depends(get_ledger),
    orchestrator: RouterOrchestrator = Depends(get_router_orchestrator),
    cache_mgr: SemanticCacheManager = Depends(get_cache_manager),
    tier_client: GeminiTierClient = Depends(get_tier_client),
) -> CompleteResponse:
    """Execute completion request through cache, routing strategy, and cost tracking."""
    req_start = time.perf_counter()
    request_id = f"req_{secrets.token_hex(6)}"
    client_ip = get_client_ip(request)

    # 1. Prompt length validation
    if len(req.prompt) > settings.max_prompt_chars:
        latency_ms = int((time.perf_counter() - req_start) * 1000)
        log_request(
            request_id=request_id,
            strategy=req.strategy,
            tier=req.tier or "unknown",
            model="unknown",
            http_status=413,
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            total_cost_usd=0.0,
            latency_ms=latency_ms,
            attempts_count=0,
            client_ip=client_ip,
            error_code="PROMPT_TOO_LONG",
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "PROMPT_TOO_LONG", "message": f"Prompt exceeds maximum character length {settings.max_prompt_chars}"},
        )

    # 2. Budget check before any model call
    if not ledger.check_budget(settings.daily_budget_usd):
        latency_ms = int((time.perf_counter() - req_start) * 1000)
        log_request(
            request_id=request_id,
            strategy=req.strategy,
            tier=req.tier or "unknown",
            model="unknown",
            http_status=429,
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            total_cost_usd=0.0,
            latency_ms=latency_ms,
            attempts_count=0,
            client_ip=client_ip,
            error_code="DAILY_BUDGET_EXCEEDED",
        )
        return JSONResponse(
            status_code=429,
            content={
                "detail": {
                    "code": "DAILY_BUDGET_EXCEEDED",
                    "message": f"Daily budget ceiling of ${settings.daily_budget_usd:.2f} reached. Request halted.",
                }
            },
        )

    # 3. Cache lookup if applicable
    cached_embedding = None
    if cache_mgr.should_cache(req.use_cache, req.temperature):
        cached_doc, hit_kind, similarity, cached_embedding = await cache_mgr.lookup(
            prompt=req.prompt,
            system=req.system,
            json_schema=req.json_schema,
        )
        if hit_kind is not None and cached_doc is not None:
            latency_ms = int((time.perf_counter() - req_start) * 1000)
            ledger.record_cache_lookup(hit_kind)

            reason_str = "cache hit exact" if hit_kind == "exact" else f"cache hit semantic similarity={similarity:.3f}"
            tier_name = cached_doc.get("tier", "standard")
            model_name = cached_doc.get("model", "")

            log_request(
                request_id=request_id,
                strategy=req.strategy,
                tier=tier_name,
                model=model_name,
                http_status=200,
                input_tokens=0,
                output_tokens=0,
                thinking_tokens=0,
                total_cost_usd=0.0,
                latency_ms=latency_ms,
                attempts_count=0,
                client_ip=client_ip,
                cache_hit=hit_kind,
                cache_similarity=similarity,
            )

            return CompleteResponse(
                request_id=request_id,
                output=cached_doc.get("output", ""),
                routing=Routing(
                    strategy=req.strategy,
                    tier=tier_name,
                    model=model_name,
                    reason=reason_str,
                    attempts=[],
                ),
                usage=Usage(
                    input_tokens=0,
                    output_tokens=0,
                    thinking_tokens=0,
                    total_cost_usd=0.0,
                ),
                cache=CacheInfo(
                    hit=True,
                    kind=hit_kind,
                    similarity=similarity,
                ),
                latency_ms=latency_ms,
            )

    # 4. Strategy execution
    try:
        tier_name, model_name, raw_output, routing_reason, attempts = await orchestrator.execute(
            req=req,
            max_output_tokens=settings.max_output_tokens,
        )
    except UpstreamTimeout as exc:
        latency_ms = int((time.perf_counter() - req_start) * 1000)
        log_request(
            request_id=request_id,
            strategy=req.strategy,
            tier=req.tier or "unknown",
            model="unknown",
            http_status=504,
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            total_cost_usd=0.0,
            latency_ms=latency_ms,
            attempts_count=0,
            client_ip=client_ip,
            error_code="UPSTREAM_TIMEOUT",
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"code": "UPSTREAM_TIMEOUT", "message": str(exc)},
        )
    except UpstreamError as exc:
        latency_ms = int((time.perf_counter() - req_start) * 1000)
        log_request(
            request_id=request_id,
            strategy=req.strategy,
            tier=req.tier or "unknown",
            model="unknown",
            http_status=502,
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            total_cost_usd=0.0,
            latency_ms=latency_ms,
            attempts_count=0,
            client_ip=client_ip,
            error_code="UPSTREAM_ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "UPSTREAM_ERROR", "message": f"{exc.exception_class}: {str(exc)}"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        latency_ms = int((time.perf_counter() - req_start) * 1000)
        err_msg = f"{exc.__class__.__name__}: {str(exc)}"
        log_request(
            request_id=request_id,
            strategy=req.strategy,
            tier=req.tier or "unknown",
            model="unknown",
            http_status=502,
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            total_cost_usd=0.0,
            latency_ms=latency_ms,
            attempts_count=0,
            client_ip=client_ip,
            error_code="UPSTREAM_ERROR",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "UPSTREAM_ERROR", "message": err_msg},
        )

    # 5. Sum usage and update budget ledger
    total_in = sum(a.input_tokens for a in attempts)
    total_out = sum(a.output_tokens for a in attempts)
    total_think = sum(a.thinking_tokens for a in attempts)
    total_cost = round(sum(a.cost_usd for a in attempts), 6)

    ledger.record_request_cost(tier_name, total_cost)

    # Record cache miss in ledger if caching was attempted
    if cache_mgr.should_cache(req.use_cache, req.temperature):
        ledger.record_cache_lookup(None)
        # Background write after miss for accepted attempt
        accepted_attempt = any(a.accepted for a in attempts)
        if accepted_attempt:
            background_tasks.add_task(
                cache_mgr.write,
                prompt=req.prompt,
                system=req.system,
                json_schema=req.json_schema,
                output=raw_output,
                tier=tier_name,
                model=model_name,
                strategy=req.strategy,
                prompt_embedding=cached_embedding,
            )

    latency_ms = int((time.perf_counter() - req_start) * 1000)

    log_request(
        request_id=request_id,
        strategy=req.strategy,
        tier=tier_name,
        model=model_name,
        http_status=200,
        input_tokens=total_in,
        output_tokens=total_out,
        thinking_tokens=total_think,
        total_cost_usd=total_cost,
        latency_ms=latency_ms,
        attempts_count=len(attempts),
        client_ip=client_ip,
    )

    return CompleteResponse(
        request_id=request_id,
        output=raw_output,
        routing=Routing(
            strategy=req.strategy,
            tier=tier_name,
            model=model_name,
            reason=routing_reason,
            attempts=attempts,
        ),
        usage=Usage(
            input_tokens=total_in,
            output_tokens=total_out,
            thinking_tokens=total_think,
            total_cost_usd=total_cost,
        ),
        cache=CacheInfo(hit=False, kind=None, similarity=None),
        latency_ms=latency_ms,
    )
