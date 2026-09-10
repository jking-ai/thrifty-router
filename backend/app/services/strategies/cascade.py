"""Cascade routing strategy with cost-free verification and escalation."""

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from app.models.responses import Attempt
from app.services.cost import cost_for_tier
from app.services.tier_client import GeminiTierClient, UpstreamError, UpstreamTimeout
from app.services.verifier import Verifier


class CascadeRouter:
    """Executes requests starting at the cheapest tier and escalating upon verification failure."""

    def __init__(
        self,
        tier_client: GeminiTierClient,
        tiers_config: List[Dict[str, Any]],
        cascade_config: Dict[str, Any],
        prompts_dir: str,
    ) -> None:
        self._tier_client = tier_client
        self._tiers_config = tiers_config
        self._tiers_by_name = {t["name"]: t for t in tiers_config}
        self._start_tier = cascade_config.get("start_tier", "lite")
        self._min_confidence = int(cascade_config.get("min_confidence", 70))
        self._max_escalations = int(cascade_config.get("max_escalations", len(tiers_config) - 1))

        suffix_path = os.path.join(prompts_dir, "cascade_confidence_suffix.txt")
        with open(suffix_path, "r", encoding="utf-8") as f:
            self._confidence_suffix = f.read().strip()

        # Find starting index in tier table
        start_idx = 0
        for i, t in enumerate(tiers_config):
            if t["name"] == self._start_tier:
                start_idx = i
                break
        self._escalation_tiers = tiers_config[start_idx:]

    async def execute(
        self,
        prompt: str,
        system: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
    ) -> Tuple[str, str, str, str, List[Attempt]]:
        """Execute cascade loop across tiers.

        Returns:
            Tuple of (final_tier, final_model, final_output, reason, attempts_list)
        """
        attempts: List[Attempt] = []
        escalations = 0
        total_tiers = len(self._escalation_tiers)

        for idx, tier_cfg in enumerate(self._escalation_tiers):
            tier_name = tier_cfg["name"]
            model = tier_cfg["model"]
            is_final_tier = (idx == total_tiers - 1)

            # Build system prompt: append confidence suffix in text mode for non-final tiers
            call_system = system
            if json_schema is None and not is_final_tier:
                if call_system:
                    call_system = f"{call_system}\n\n{self._confidence_suffix}"
                else:
                    call_system = self._confidence_suffix

            start_time = time.perf_counter()
            try:
                res = await self._tier_client.generate(
                    model=model,
                    prompt=prompt,
                    system=call_system,
                    json_schema=json_schema,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
            except Exception as exc:
                # Upstream error on this attempt
                # Any earlier attempts should be accessible by the caller
                raise exc

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            cost_usd = cost_for_tier(
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                thinking_tokens=res.thinking_tokens,
                tier_config=tier_cfg,
            )

            # Run verifier
            verdict = Verifier.verify(
                raw_output=res.content,
                finish_reason=res.finish_reason,
                json_schema=json_schema,
                min_confidence=self._min_confidence,
                is_final_tier=is_final_tier,
            )

            attempt = Attempt(
                role="completion",
                tier=tier_name,
                model=model,
                latency_ms=latency_ms,
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                thinking_tokens=res.thinking_tokens,
                cost_usd=cost_usd,
                accepted=verdict.accepted,
                reject_reason=verdict.reject_reason,
            )
            attempts.append(attempt)

            # Check acceptance or termination conditions
            if verdict.accepted:
                if escalations == 0:
                    reason = f"cascade accepted at {tier_name}"
                elif escalations >= self._max_escalations:
                    reason = f"cascade escalated {escalations}x max_escalations accepted at {tier_name}"
                elif is_final_tier:
                    reason = f"cascade escalated {escalations}x last_tier accepted at {tier_name}"
                else:
                    reason = f"cascade escalated {escalations}x accepted at {tier_name}"
                return tier_name, model, verdict.cleaned_output, reason, attempts

            # If not accepted, check if cap reached
            if escalations >= self._max_escalations:
                attempt.accepted = True
                reason = f"cascade escalated {escalations}x max_escalations accepted at {tier_name}"
                return tier_name, model, verdict.cleaned_output, reason, attempts

            # If not accepted, check if last tier reached
            if is_final_tier:
                attempt.accepted = True
                reason = f"cascade escalated {escalations}x last_tier accepted at {tier_name}"
                return tier_name, model, verdict.cleaned_output, reason, attempts

            escalations += 1

        # Fallback (should not be reached due to final tier handling)
        last_attempt = attempts[-1]
        last_attempt.accepted = True
        return last_attempt.tier, last_attempt.model, "", "cascade fallback", attempts
