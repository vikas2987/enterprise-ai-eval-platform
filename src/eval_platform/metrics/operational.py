"""Operational metrics: latency and cost.

These are *measured*, not judged. Each record may carry a ``latency_ms``
and a ``cost_usd`` field (captured when the agent produced the answer).
This module aggregates them across a run.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def aggregate_operational(records: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    """Aggregate latency and cost across all records in a run."""
    latencies = [float(r["latency_ms"]) for r in records if r.get("latency_ms") is not None]
    costs = [float(r["cost_usd"]) for r in records if r.get("cost_usd") is not None]

    return {
        "latency_p50_ms": round(_percentile(latencies, 0.50), 1),
        "latency_p95_ms": round(_percentile(latencies, 0.95), 1),
        "cost_avg_usd": round(sum(costs) / len(costs), 4) if costs else 0.0,
        "cost_total_usd": round(sum(costs), 4),
    }
