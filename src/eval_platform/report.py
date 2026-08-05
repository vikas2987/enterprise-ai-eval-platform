"""Reporting and regression gates."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class RunReport:
    n_examples: int
    quality_avg: dict[str, float]
    operational: dict[str, float]
    per_example: list[dict[str, Any]] = field(default_factory=list)
    gate_metric: str = "faithfulness"
    gate_threshold: float = 0.80

    @property
    def gate_value(self) -> float:
        return self.quality_avg.get(self.gate_metric, 0.0)

    @property
    def gate_passed(self) -> bool:
        return self.gate_value >= self.gate_threshold

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def render(self) -> str:
        lines = [
            "Enterprise AI Evaluation Platform — run report",
            "-" * 48,
            f"examples evaluated ......... {self.n_examples}",
        ]
        for name, value in self.quality_avg.items():
            label = f"{name} (avg)".ljust(26, ".")
            lines.append(f"{label} {value:.2f}")
        op = self.operational
        lines.append(
            "latency p50 / p95 (ms) ..... "
            f"{op.get('latency_p50_ms', 0):.0f} / {op.get('latency_p95_ms', 0):.0f}"
        )
        lines.append(f"est. cost (avg, USD) ....... {op.get('cost_avg_usd', 0):.4f}")
        lines.append("-" * 48)
        status = "PASS" if self.gate_passed else "FAIL"
        lines.append(
            f"REGRESSION GATE: {status} "
            f"(min {self.gate_metric} {self.gate_value:.2f} "
            f">= {self.gate_threshold:.2f})"
        )
        return "\n".join(lines)
