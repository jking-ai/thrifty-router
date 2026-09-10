"""Cost calculation utilities for Gemini tier usage."""

from typing import Any, Dict


def calculate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int,
    price_per_m_input_usd: float,
    price_per_m_output_usd: float,
) -> float:
    """Calculate attempt cost in USD rounded to 6 decimal places.

    Thinking tokens are explicitly billed at the output rate.
    Formula:
        (input_tokens * price_in + (output_tokens + thinking_tokens) * price_out) / 1_000_000
    """
    in_cost = (input_tokens * price_per_m_input_usd) / 1_000_000.0
    out_cost = ((output_tokens + thinking_tokens) * price_per_m_output_usd) / 1_000_000.0
    total = in_cost + out_cost
    return round(total, 6)


def cost_for_tier(
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int,
    tier_config: Dict[str, Any],
) -> float:
    """Calculate cost for given tokens and tier configuration dictionary."""
    return calculate_cost_usd(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        price_per_m_input_usd=tier_config["price_per_m_input_usd"],
        price_per_m_output_usd=tier_config["price_per_m_output_usd"],
    )
