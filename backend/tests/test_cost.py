"""Tests for exact token cost calculation."""

from app.services.cost import calculate_cost_usd, cost_for_tier


def test_thinking_tokens_billed_as_output():
    """Verify thinking tokens are charged at the output rate.

    10,000 in, 1,000 out, 500 thinking on pro ($2.00 in / $12.00 out):
    - Input cost: 10,000 * $2.00 / 1M = $0.020000
    - Output + Thinking cost: (1,000 + 500) * $12.00 / 1M = 1,500 * $12.00 / 1M = $0.018000
    - Total cost: $0.038000
    """
    tier_pro = {
        "price_per_m_input_usd": 2.00,
        "price_per_m_output_usd": 12.00,
    }
    cost = cost_for_tier(
        input_tokens=10000,
        output_tokens=1000,
        thinking_tokens=500,
        tier_config=tier_pro,
    )
    assert cost == 0.038


def test_cost_rounding_six_decimals():
    """Verify costs round cleanly to 6 decimal places."""
    cost = calculate_cost_usd(
        input_tokens=120,
        output_tokens=340,
        thinking_tokens=0,
        price_per_m_input_usd=0.25,
        price_per_m_output_usd=1.50,
    )
    # (120*0.25 + 340*1.50) / 1M = (30 + 510) / 1M = 540 / 1M = 0.000540
    assert cost == 0.00054
