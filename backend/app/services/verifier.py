"""Output verifier for cascade strategy."""

from dataclasses import dataclass
import json
import re
from typing import Any, Dict, Optional, Tuple
import jsonschema

CONFIDENCE_REGEX = re.compile(r"^CONFIDENCE:\s*(\d{1,3})\s*$", re.IGNORECASE)


@dataclass
class VerificationResult:
    """Outcome of cascade verification."""

    accepted: bool
    reject_reason: Optional[str] = None
    cleaned_output: str = ""


class Verifier:
    """Verifies completions using deterministic rules and confidence extraction."""

    @staticmethod
    def verify(
        raw_output: str,
        finish_reason: str,
        json_schema: Optional[Dict[str, Any]],
        min_confidence: int = 70,
        is_final_tier: bool = False,
    ) -> VerificationResult:
        """Apply verification rules in order.

        Rules:
        1. finish_reason is STOP -> else finish_reason:<value>
        2. Output non-empty after strip -> else empty_output
        3. If json_schema present: validate JSON against schema -> else schema_invalid:<msg>
        4. If json_schema absent:
           - If is_final_tier: always accept, no confidence line needed
           - Else: check last line for CONFIDENCE: <n>, verify >= min_confidence
        """
        # Rule 1: finish reason
        if finish_reason.upper() != "STOP":
            return VerificationResult(
                accepted=False,
                reject_reason=f"finish_reason:{finish_reason}",
                cleaned_output=raw_output,
            )

        # Rule 2: non-empty
        stripped = raw_output.strip()
        if not stripped:
            return VerificationResult(
                accepted=False,
                reject_reason="empty_output",
                cleaned_output=raw_output,
            )

        # Rule 3: JSON schema validation
        if json_schema is not None:
            try:
                parsed_json = json.loads(raw_output)
            except Exception as e:
                msg = str(e)[:120]
                return VerificationResult(
                    accepted=False,
                    reject_reason=f"schema_invalid:JSON decode error: {msg}"[:120],
                    cleaned_output=raw_output,
                )

            try:
                validator = jsonschema.Draft202012Validator(json_schema)
                errors = sorted(validator.iter_errors(parsed_json), key=lambda e: e.path)
                if errors:
                    first_err = errors[0].message[:120]
                    return VerificationResult(
                        accepted=False,
                        reject_reason=f"schema_invalid:{first_err}"[:120],
                        cleaned_output=raw_output,
                    )
            except Exception as e:
                msg = str(e)[:120]
                return VerificationResult(
                    accepted=False,
                    reject_reason=f"schema_invalid:{msg}"[:120],
                    cleaned_output=raw_output,
                )

            return VerificationResult(
                accepted=True,
                reject_reason=None,
                cleaned_output=raw_output,
            )

        # Rule 4: Text mode confidence verification
        if is_final_tier:
            # Final tier is always accepted and never receives confidence suffix
            cleaned = Verifier.strip_confidence_line(raw_output)
            return VerificationResult(
                accepted=True,
                reject_reason=None,
                cleaned_output=cleaned,
            )

        # Check last line
        lines = [line.strip() for line in raw_output.strip().splitlines() if line.strip()]
        if not lines:
            return VerificationResult(
                accepted=False,
                reject_reason="empty_output",
                cleaned_output=raw_output,
            )

        last_line = lines[-1]
        match = CONFIDENCE_REGEX.match(last_line)
        cleaned = Verifier.strip_confidence_line(raw_output)

        if not match:
            return VerificationResult(
                accepted=False,
                reject_reason="no_confidence_line",
                cleaned_output=cleaned,
            )

        conf_val = int(match.group(1))
        if conf_val < 0 or conf_val > 100:
            return VerificationResult(
                accepted=False,
                reject_reason=f"low_confidence:{conf_val}",
                cleaned_output=cleaned,
            )

        if conf_val < min_confidence:
            return VerificationResult(
                accepted=False,
                reject_reason=f"low_confidence:{conf_val}",
                cleaned_output=cleaned,
            )

        return VerificationResult(
            accepted=True,
            reject_reason=None,
            cleaned_output=cleaned,
        )

    @staticmethod
    def strip_confidence_line(output: str) -> str:
        """Strip trailing CONFIDENCE: <n> line from output."""
        lines = output.splitlines()
        while lines and (not lines[-1].strip() or CONFIDENCE_REGEX.match(lines[-1].strip())):
            lines.pop()
        return "\n".join(lines).strip()
