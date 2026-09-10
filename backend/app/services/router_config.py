"""Router configuration loading and validation."""

import os
import re
from typing import Any, Dict, List
import yaml

TIER_NAME_REGEX = re.compile(r"^[a-z][a-z0-9_]{0,15}$")


def load_router_config(config_path: str) -> Dict[str, Any]:
    """Load and validate router.yaml configuration file."""
    if not os.path.exists(config_path):
        raise ValueError(f"Router configuration file not found at: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("router.yaml must contain a top-level mapping")

    # Validate tiers
    if "tiers" not in data:
        raise ValueError("router.yaml missing required key: tiers")
    tiers = data["tiers"]
    if not isinstance(tiers, list) or len(tiers) == 0:
        raise ValueError("router.yaml 'tiers' must be a non-empty list")

    tier_names = set()
    for tier in tiers:
        if not isinstance(tier, dict):
            raise ValueError("Each tier entry in router.yaml must be a mapping")
        for req in ["name", "model", "price_per_m_input_usd", "price_per_m_output_usd"]:
            if req not in tier:
                raise ValueError(f"Tier in router.yaml missing required key: {req}")

        name = tier["name"]
        if not TIER_NAME_REGEX.match(name):
            raise ValueError(f"Invalid tier name '{name}'; must match ^[a-z][a-z0-9_]{{0,15}}$")
        if name in tier_names:
            raise ValueError(f"Duplicate tier name '{name}' in router.yaml")
        tier_names.add(name)

    # Validate default_tier
    if "default_tier" not in data:
        raise ValueError("router.yaml missing required key: default_tier")
    default_tier = data["default_tier"]
    if default_tier not in tier_names:
        raise ValueError(
            f"default_tier '{default_tier}' must be one of the defined tiers: {list(tier_names)}"
        )

    # Validate semantic block if present
    if "semantic" in data and isinstance(data["semantic"], dict):
        sem = data["semantic"]
        if "threshold" in sem:
            if not (0.0 <= float(sem["threshold"]) <= 1.0):
                raise ValueError("semantic.threshold must be between 0.0 and 1.0")
        if "routes" in sem:
            if not isinstance(sem["routes"], list) or len(sem["routes"]) == 0:
                raise ValueError("semantic.routes must be a non-empty list")
            route_names = set()
            for r in sem["routes"]:
                if not isinstance(r, dict) or "name" not in r or "tier" not in r or "utterances" not in r:
                    raise ValueError("Each semantic route must have name, tier, and utterances")
                if r["name"] in route_names:
                    raise ValueError(f"Duplicate semantic route name: {r['name']}")
                route_names.add(r["name"])
                if r["tier"] not in tier_names:
                    raise ValueError(f"Semantic route '{r['name']}' references unknown tier: {r['tier']}")
                if not isinstance(r["utterances"], list) or len(r["utterances"]) == 0:
                    raise ValueError(f"Semantic route '{r['name']}' must have at least one utterance")

    # Validate classifier block if present
    if "classifier" in data and isinstance(data["classifier"], dict):
        cls_tier = data["classifier"].get("tier")
        if cls_tier and cls_tier not in tier_names:
            raise ValueError(f"classifier.tier '{cls_tier}' not found in tiers")

    # Validate cascade block if present
    if "cascade" in data and isinstance(data["cascade"], dict):
        cas = data["cascade"]
        start_tier = cas.get("start_tier")
        if start_tier and start_tier not in tier_names:
            raise ValueError(f"cascade.start_tier '{start_tier}' not found in tiers")
        if "min_confidence" in cas:
            if not (0 <= int(cas["min_confidence"]) <= 100):
                raise ValueError("cascade.min_confidence must be between 0 and 100")
        if "max_escalations" in cas:
            if not (0 <= int(cas["max_escalations"]) <= len(tiers) - 1):
                raise ValueError("cascade.max_escalations out of valid range")

    return data
