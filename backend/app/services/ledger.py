"""In-process daily budget ledger and usage tracker."""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, Optional


class BudgetLedger:
    """Thread-safe in-process daily budget tracker and usage accumulator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current_date = self._utc_today()
        self._requests = 0
        self._total_cost_usd = 0.0
        self._by_tier: Dict[str, Dict[str, Any]] = {}
        self._cache_lookups = 0
        self._cache_hits_exact = 0
        self._cache_hits_semantic = 0

    def _utc_today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _check_rollover_locked(self) -> None:
        today = self._utc_today()
        if today != self._current_date:
            self._current_date = today
            self._requests = 0
            self._total_cost_usd = 0.0
            self._by_tier.clear()
            self._cache_lookups = 0
            self._cache_hits_exact = 0
            self._cache_hits_semantic = 0

    def check_budget(self, daily_budget_usd: float) -> bool:
        """Check if today's accumulated cost has reached or exceeded daily budget.

        Returns True if budget is available, False if exceeded.
        """
        with self._lock:
            self._check_rollover_locked()
            return self._total_cost_usd < daily_budget_usd

    def record_request_cost(self, tier: str, cost_usd: float) -> None:
        """Record a completed request cost and increment tier usage."""
        with self._lock:
            self._check_rollover_locked()
            self._requests += 1
            self._total_cost_usd = round(self._total_cost_usd + cost_usd, 6)
            if tier not in self._by_tier:
                self._by_tier[tier] = {"requests": 0, "cost_usd": 0.0}
            self._by_tier[tier]["requests"] += 1
            self._by_tier[tier]["cost_usd"] = round(self._by_tier[tier]["cost_usd"] + cost_usd, 6)

    def record_cache_lookup(self, hit_kind: Optional[str]) -> None:
        """Record cache lookup and hit statistics."""
        with self._lock:
            self._check_rollover_locked()
            self._cache_lookups += 1
            if hit_kind == "exact":
                self._cache_hits_exact += 1
            elif hit_kind == "semantic":
                self._cache_hits_semantic += 1

    def get_usage(self, daily_budget_usd: float) -> Dict[str, Any]:
        """Return usage snapshot formatted for GET /api/v1/usage."""
        with self._lock:
            self._check_rollover_locked()
            return {
                "date": self._current_date,
                "requests": self._requests,
                "total_cost_usd": self._total_cost_usd,
                "daily_budget_usd": daily_budget_usd,
                "by_tier": {
                    t: {"requests": v["requests"], "cost_usd": v["cost_usd"]}
                    for t, v in self._by_tier.items()
                },
                "cache": {
                    "lookups": self._cache_lookups,
                    "hits_exact": self._cache_hits_exact,
                    "hits_semantic": self._cache_hits_semantic,
                },
            }

    def reset_for_tests(self) -> None:
        """Helper for test isolation."""
        with self._lock:
            self._current_date = self._utc_today()
            self._requests = 0
            self._total_cost_usd = 0.0
            self._by_tier.clear()
            self._cache_lookups = 0
            self._cache_hits_exact = 0
            self._cache_hits_semantic = 0
