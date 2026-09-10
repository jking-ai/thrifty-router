"""Classifier routing strategy using a fast LLM call."""

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from app.models.responses import Attempt
from app.services.cost import cost_for_tier
from app.services.tier_client import GeminiTierClient


class ClassifierRouter:
    """Routes prompts by asking a cheap tier to classify prompt difficulty."""

    def __init__(
        self,
        tier_client: GeminiTierClient,
        tiers_config: List[Dict[str, Any]],
        classifier_config: Dict[str, Any],
        prompts_dir: str,
    ) -> None:
        self._tier_client = tier_client
        self._tiers_config = tiers_config
        self._tiers_by_name = {t["name"]: t for t in tiers_config}
        self._classifier_tier_name = classifier_config.get("tier", "lite")
        self._classifier_tier = self._tiers_by_name[self._classifier_tier_name]

        # Load template
        template_path = os.path.join(prompts_dir, "classifier_template.txt")
        with open(template_path, "r", encoding="utf-8") as f:
            self._template = f.read()

        # Build tier descriptions string
        desc_lines = []
        for t in tiers_config:
            desc = t.get("description") or t["name"]
            desc_lines.append(f"- {t['name']}: {t['model']} ({desc})")
        self._tier_descriptions = "\n".join(desc_lines)

        # Build dynamic JSON schema
        self._response_schema = {
            "type": "object",
            "properties": {
                "tier": {
                    "type": "string",
                    "enum": [t["name"] for t in tiers_config],
                },
                "reason": {"type": "string"},
            },
            "required": ["tier", "reason"],
        }

    async def classify(
        self, prompt: str, default_tier: str
    ) -> Tuple[str, str, Optional[Attempt]]:
        """Classify prompt difficulty and select tier.

        Returns:
            Tuple of (chosen_tier, reason_string, classifier_attempt)
        """
        truncated_prompt = prompt[:4000]
        rendered_prompt = self._template.replace(
            "{tier_descriptions}", self._tier_descriptions
        ).replace("{prompt}", truncated_prompt)

        start_time = time.perf_counter()
        attempt = None

        try:
            res = await self._tier_client.generate(
                model=self._classifier_tier["model"],
                prompt=rendered_prompt,
                json_schema=self._response_schema,
                temperature=0.0,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            cost_usd = cost_for_tier(
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                thinking_tokens=res.thinking_tokens,
                tier_config=self._classifier_tier,
            )

            attempt = Attempt(
                role="classifier",
                tier=self._classifier_tier_name,
                model=self._classifier_tier["model"],
                latency_ms=latency_ms,
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                thinking_tokens=res.thinking_tokens,
                cost_usd=cost_usd,
                accepted=True,
                reject_reason=None,
            )

            # Parse JSON
            data = json.loads(res.content)
            selected_tier = data.get("tier")
            raw_reason = str(data.get("reason", "")).strip()[:200]

            if selected_tier not in self._tiers_by_name:
                reason = f"classifier_error: unknown_tier default={default_tier}"
                return default_tier, reason, attempt

            reason = f"classifier tier={selected_tier}: {raw_reason}"
            return selected_tier, reason, attempt

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            err_class = exc.__class__.__name__
            # Create attempt with zero tokens if failed before response
            attempt = Attempt(
                role="classifier",
                tier=self._classifier_tier_name,
                model=self._classifier_tier["model"],
                latency_ms=latency_ms,
                input_tokens=0,
                output_tokens=0,
                thinking_tokens=0,
                cost_usd=0.0,
                accepted=True,
                reject_reason=None,
            )
            reason = f"classifier_error: {err_class} default={default_tier}"
            return default_tier, reason, attempt
