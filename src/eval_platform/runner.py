"""Evaluation runner — orchestrates a full run over a dataset.

Usage:
    python -m eval_platform.runner --dataset datasets/example_eval_set.jsonl
    python -m eval_platform.runner --dataset my.jsonl --judge anthropic \\
        --gate-metric faithfulness --gate-threshold 0.85
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .evaluators.judge import get_judge
from .metrics import aggregate_operational, score_quality
from .metrics.quality import QUALITY_METRICS
from .report import RunReport


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSONL eval set (one record per line)."""
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        raise ValueError(f"No records found in {path}")
    return records


def run(
    dataset_path: str | Path,
    judge_name: str = "mock",
    gate_metric: str = "faithfulness",
    gate_threshold: float = 0.80,
) -> RunReport:
    records = load_dataset(dataset_path)
    judge = get_judge(judge_name)

    per_example: list[dict[str, Any]] = []
    totals = {m: 0.0 for m in QUALITY_METRICS}

    for rec in records:
        scores = score_quality(rec, judge)
        for m, v in scores.items():
            totals[m] += v
        per_example.append(
            {"id": rec.get("id"), "question": rec.get("question"), "scores": scores}
        )

    n = len(records)
    quality_avg = {m: round(totals[m] / n, 3) for m in QUALITY_METRICS}
    operational = aggregate_operational(records)

    return RunReport(
        n_examples=n,
        quality_avg=quality_avg,
        operational=operational,
        per_example=per_example,
        gate_metric=gate_metric,
        gate_threshold=gate_threshold,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an enterprise AI evaluation.")
    parser.add_argument("--dataset", required=True, help="Path to a JSONL eval set.")
    parser.add_argument("--judge", default="mock", choices=["mock", "anthropic"])
    parser.add_argument("--gate-metric", default="faithfulness")
    parser.add_argument("--gate-threshold", type=float, default=0.80)
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Emit the full report as JSON.")
    args = parser.parse_args(argv)

    report = run(
        args.dataset,
        judge_name=args.judge,
        gate_metric=args.gate_metric,
        gate_threshold=args.gate_threshold,
    )

    print(report.to_json() if args.as_json else report.render())
    # Non-zero exit on gate failure so CI can block a regression.
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    sys.exit(main())
