"""Strategy registry and request routing orchestrator."""

import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from app.models.requests import CompleteRequest
from app.models.responses import Attempt
from app.services.cost import cost_for_tier
from app.services.embedder import Embedder
from app.services.strategies.cascade import CascadeRouter
from app.services.strategies.classifier import ClassifierRouter
from app.services.strategies.semantic import SemanticRouteMatcher
from app.services.tier_client import GeminiTierClient


class RouterOrchestrator:
    """Orchestrates strategy execution and model completion across tiers."""

    def __init__(
        self,
        router_config: Dict[str, Any],
        tier_client: GeminiTierClient,
        embedder: Embedder,
        prompts_dir: str,
    ) -> None:
        self._config = router_config
        self._tier_client = tier_client
        self._embedder = embedder
        self._prompts_dir = prompts_dir

        self._tiers = router_config["tiers"]
        self._tiers_by_name = {t["name"]: t for t in self._tiers}
        self._default_tier = router_config["default_tier"]

        # Strategy handlers
        self._semantic_matcher: Optional[SemanticRouteMatcher] = None
        if "semantic" in router_config and "routes" in router_config["semantic"]:
            self._semantic_matcher = SemanticRouteMatcher(
                routes_config=router_config["semantic"]["routes"],
                embedder=embedder,
            )

        self._classifier_router: Optional[ClassifierRouter] = None
        if "classifier" in router_config:
            self._classifier_router = ClassifierRouter(
                tier_client=tier_client,
                tiers_config=self._tiers,
                classifier_config=router_config["classifier"],
                prompts_dir=prompts_dir,
            )

        self._cascade_router: Optional[CascadeRouter] = None
        if "cascade" in router_config:
            self._cascade_router = CascadeRouter(
                tier_client=tier_client,
                tiers_config=self._tiers,
                cascade_config=router_config["cascade"],
                prompts_dir=prompts_dir,
            )

    def get_available_strategies(self) -> List[str]:
        """Return list of all registered strategies."""
        strategies = ["fixed"]
        if self._semantic_matcher is not None:
            strategies.append("semantic")
        if self._classifier_router is not None:
            strategies.append("classifier")
        if self._cascade_router is not None:
            strategies.append("cascade")
        return strategies

    async def execute(
        self, req: CompleteRequest, max_output_tokens: int
    ) -> Tuple[str, str, str, str, List[Attempt]]:
        """Execute the chosen routing strategy.

        Returns:
            Tuple of (chosen_tier, model_name, raw_output, routing_reason, attempts)
        """
        strat = req.strategy
        available = self.get_available_strategies()
        if strat not in available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "STRATEGY_NOT_AVAILABLE", "message": f"Strategy '{strat}' is not available"},
            )

        tokens_cap = req.max_output_tokens or max_output_tokens

        # 1. FIXED STRATEGY
        if strat == "fixed":
            if not req.tier:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "TIER_REQUIRED", "message": "Tier is required when strategy is fixed"},
                )
            if req.tier not in self._tiers_by_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "UNKNOWN_TIER", "message": f"Unknown tier: {req.tier}"},
                )

            tier_cfg = self._tiers_by_name[req.tier]
            model = tier_cfg["model"]
            reason = "caller-specified"

            start_time = time.perf_counter()
            res = await self._tier_client.generate(
                model=model,
                prompt=req.prompt,
                system=req.system,
                json_schema=req.json_schema,
                temperature=req.temperature,
                max_output_tokens=tokens_cap,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            cost_usd = cost_for_tier(
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                thinking_tokens=res.thinking_tokens,
                tier_config=tier_cfg,
            )

            attempt = Attempt(
                role="completion",
                tier=req.tier,
                model=model,
                latency_ms=latency_ms,
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                thinking_tokens=res.thinking_tokens,
                cost_usd=cost_usd,
                accepted=True,
                reject_reason=None,
            )
            return req.tier, model, res.content, reason, [attempt]

        # 2. SEMANTIC STRATEGY
        if strat == "semantic":
            sem_cfg = self._config.get("semantic", {})
            threshold = float(sem_cfg.get("threshold", 0.60))

            chosen_tier, reason = await self._semantic_matcher.match(
                prompt=req.prompt,
                threshold=threshold,
                default_tier=self._default_tier,
            )

            tier_cfg = self._tiers_by_name[chosen_tier]
            model = tier_cfg["model"]

            start_time = time.perf_counter()
            res = await self._tier_client.generate(
                model=model,
                prompt=req.prompt,
                system=req.system,
                json_schema=req.json_schema,
                temperature=req.temperature,
                max_output_tokens=tokens_cap,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            cost_usd = cost_for_tier(
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                thinking_tokens=res.thinking_tokens,
                tier_config=tier_cfg,
            )

            attempt = Attempt(
                role="completion",
                tier=chosen_tier,
                model=model,
                latency_ms=latency_ms,
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                thinking_tokens=res.thinking_tokens,
                cost_usd=cost_usd,
                accepted=True,
                reject_reason=None,
            )
            return chosen_tier, model, res.content, reason, [attempt]

        # 3. CLASSIFIER STRATEGY
        if strat == "classifier":
            chosen_tier, reason, cls_attempt = await self._classifier_router.classify(
                prompt=req.prompt,
                default_tier=self._default_tier,
            )

            tier_cfg = self._tiers_by_name[chosen_tier]
            model = tier_cfg["model"]

            start_time = time.perf_counter()
            res = await self._tier_client.generate(
                model=model,
                prompt=req.prompt,
                system=req.system,
                json_schema=req.json_schema,
                temperature=req.temperature,
                max_output_tokens=tokens_cap,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            cost_usd = cost_for_tier(
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                thinking_tokens=res.thinking_tokens,
                tier_config=tier_cfg,
            )

            comp_attempt = Attempt(
                role="completion",
                tier=chosen_tier,
                model=model,
                latency_ms=latency_ms,
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                thinking_tokens=res.thinking_tokens,
                cost_usd=cost_usd,
                accepted=True,
                reject_reason=None,
            )

            attempts = [cls_attempt, comp_attempt] if cls_attempt else [comp_attempt]
            return chosen_tier, model, res.content, reason, attempts

        # 4. CASCADE STRATEGY
        if strat == "cascade":
            tier_name, model, output, reason, attempts = await self._cascade_router.execute(
                prompt=req.prompt,
                system=req.system,
                json_schema=req.json_schema,
                temperature=req.temperature,
                max_output_tokens=tokens_cap,
            )
            return tier_name, model, output, reason, attempts

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "STRATEGY_NOT_AVAILABLE", "message": f"Unknown strategy {strat}"},
        )
