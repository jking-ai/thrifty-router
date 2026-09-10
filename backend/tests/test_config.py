"""Tests for router configuration loading and validation."""

import os
import tempfile
import pytest
import yaml

from app.services.router_config import load_router_config


def test_router_yaml_loads_three_tiers():
    """Verify default router.yaml loads lite, standard, and pro tiers."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "app", "router.yaml")
    cfg = load_router_config(config_path)

    assert "tiers" in cfg
    tier_names = [t["name"] for t in cfg["tiers"]]
    assert tier_names == ["lite", "standard", "pro"]
    assert cfg["default_tier"] == "lite"


def test_router_yaml_missing_default_tier_raises():
    """Verify loading fails with ValueError if default_tier is missing."""
    invalid_yaml = {
        "tiers": [
            {
                "name": "lite",
                "model": "gemini-3.1-flash-lite-preview",
                "price_per_m_input_usd": 0.25,
                "price_per_m_output_usd": 1.50,
            }
        ]
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
        yaml.dump(invalid_yaml, tmp)
        tmp_path = tmp.name

    try:
        with pytest.raises(ValueError, match="default_tier"):
            load_router_config(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_router_yaml_semantic_routes_valid():
    """Verify semantic routes have unique names and >= 8 utterances per tier."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "app", "router.yaml")
    cfg = load_router_config(config_path)

    assert "semantic" in cfg
    routes = cfg["semantic"]["routes"]
    assert len(routes) >= 3

    route_names = set()
    utterance_count_by_tier = {}

    for r in routes:
        assert r["name"] not in route_names, f"Duplicate route name: {r['name']}"
        route_names.add(r["name"])

        tier = r["tier"]
        utterance_count_by_tier[tier] = utterance_count_by_tier.get(tier, 0) + len(r["utterances"])

    for tier in ["lite", "standard", "pro"]:
        count = utterance_count_by_tier.get(tier, 0)
        assert count >= 8, f"Tier '{tier}' has only {count} utterances; expected at least 8"
