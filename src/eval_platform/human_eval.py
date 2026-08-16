"""Human-in-the-loop evaluation & judge calibration.

An LLM judge scales, but it is not ground truth. The discipline that keeps it
honest is simple: periodically sample its scores, have a human label the same
examples blind, and measure how well the judge agrees with the human. If
agreement drifts, you re-tune the rubric before you trust the judge again.

This module operationalizes that workflow in three steps:

1. ``export_for_labeling`` — write a CSV of examples (question, answer, context)
   with the judge's scores and *blank* human columns for a reviewer to fill.
2. A human opens the CSV and fills ``human_faithfulness`` etc. in [0, 1].
3. ``agreement`` — load the filled CSV and report, per metric, the mean
   absolute error and Pearson correlation between judge and human, plus a
   calibration verdict.

Zero dependencies — uses only the standard library so it runs anywhere.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .metrics.quality import QUALITY_METRICS
from .report import RunReport
from .runner import load_dataset, run

_JUDGE_PREFIX = "judge_"
_HUMAN_PREFIX = "human_"


# ------------------------------------------------------------------- export

def export_for_labeling(
    report: RunReport,
    records: Iterable[Mapping[str, Any]],
    path: str | Path,
) -> Path:
    """Write a labeling CSV: judge scores populated, human columns blank."""
    by_id = {r.get("id"): r for r in records}
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = (
        ["id", "question", "answer", "contexts"]
        + [f"{_JUDGE_PREFIX}{m}" for m in QUALITY_METRICS]
        + [f"{_HUMAN_PREFIX}{m}" for m in QUALITY_METRICS]
        + ["notes"]
    )
    with open(out, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in report.per_example:
            rid = row.get("id")
            src = by_id.get(rid, {})
            contexts = src.get("contexts", []) or []
            record = {
                "id": rid,
                "question": row.get("question", ""),
                "answer": src.get("answer", ""),
                "contexts": " | ".join(str(c) for c in contexts),
                "notes": "",
            }
            for m in QUALITY_METRICS:
                record[f"{_JUDGE_PREFIX}{m}"] = f"{row.get('scores', {}).get(m, 0.0):.3f}"
                record[f"{_HUMAN_PREFIX}{m}"] = ""  # reviewer fills this in
            writer.writerow(record)
    return out


# --------------------------------------------------------------- load labels

def load_labels(path: str | Path) -> dict[str, dict[str, float]]:
    """Read a filled labeling CSV → {id: {metric: human_score}}.

    Rows with no human score for a metric are simply omitted for that metric,
    so a partially-labeled CSV still works.
    """
    labels: dict[str, dict[str, float]] = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rid = row.get("id")
            if not rid:
                continue
            per_metric: dict[str, float] = {}
            for m in QUALITY_METRICS:
                raw = (row.get(f"{_HUMAN_PREFIX}{m}") or "").strip()
                if raw:
                    try:
                        per_metric[m] = float(raw)
                    except ValueError:
                        continue
            if per_metric:
                labels[rid] = per_metric
    return labels


# ----------------------------------------------------------------- agreement

def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson correlation; None if undefined (n<2 or zero variance)."""
    n = len(xs)
    if n < 2:
        return None
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


@dataclass
class MetricAgreement:
    metric: str
    n: int
    mae: float
    correlation: float | None

    @property
    def verdict(self) -> str:
        # Calibration heuristic: judge is trustworthy for this metric when it
        # tracks the human closely (low error) and moves with them (high corr).
        if self.n < 2:
            return "insufficient-data"
        if self.mae <= 0.10 and (self.correlation is None or self.correlation >= 0.7):
            return "well-calibrated"
        if self.mae <= 0.20:
            return "acceptable"
        return "needs-recalibration"


@dataclass
class AgreementReport:
    per_metric: list[MetricAgreement]
    n_examples: int

    def render(self) -> str:
        lines = [
            "Judge ↔ human calibration",
            "-" * 56,
            f"labeled examples ... {self.n_examples}",
            f"{'metric':<20}{'n':>4}{'MAE':>8}{'corr':>8}  verdict",
        ]
        for a in self.per_metric:
            corr = "n/a" if a.correlation is None else f"{a.correlation:.2f}"
            lines.append(f"{a.metric:<20}{a.n:>4}{a.mae:>8.3f}{corr:>8}  {a.verdict}")
        return "\n".join(lines)


def agreement(report: RunReport, labels: Mapping[str, Mapping[str, float]]) -> AgreementReport:
    """Compare judge scores to human labels, per metric."""
    judge_by_id = {r.get("id"): r.get("scores", {}) for r in report.per_example}

    per_metric: list[MetricAgreement] = []
    labeled_ids: set[str] = set()
    for metric in QUALITY_METRICS:
        judge_vals: list[float] = []
        human_vals: list[float] = []
        for rid, human_scores in labels.items():
            if metric not in human_scores or rid not in judge_by_id:
                continue
            if metric not in judge_by_id[rid]:
                continue
            judge_vals.append(float(judge_by_id[rid][metric]))
            human_vals.append(float(human_scores[metric]))
            labeled_ids.add(rid)
        if not judge_vals:
            per_metric.append(MetricAgreement(metric, 0, 0.0, None))
            continue
        mae = _mean([abs(j - h) for j, h in zip(judge_vals, human_vals)])
        corr = _pearson(judge_vals, human_vals)
        per_metric.append(MetricAgreement(metric, len(judge_vals), round(mae, 3), corr))

    return AgreementReport(per_metric=per_metric, n_examples=len(labeled_ids))


# ----------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Human evaluation & judge calibration.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_exp = sub.add_parser("export", help="Write a labeling CSV for a dataset.")
    p_exp.add_argument("--dataset", required=True)
    p_exp.add_argument("--judge", default="mock", choices=["mock", "anthropic"])
    p_exp.add_argument("--out", required=True, help="Output CSV path.")

    p_agr = sub.add_parser("agreement", help="Score judge↔human agreement from a filled CSV.")
    p_agr.add_argument("--dataset", required=True)
    p_agr.add_argument("--labels", required=True, help="Filled labeling CSV.")
    p_agr.add_argument("--judge", default="mock", choices=["mock", "anthropic"])

    args = parser.parse_args(argv)

    if args.cmd == "export":
        records = load_dataset(args.dataset)
        report = run(args.dataset, judge_name=args.judge)
        out = export_for_labeling(report, records, args.out)
        print(f"Wrote {len(report.per_example)} rows to {out}")
        print("Fill the human_* columns in [0,1], then run the 'agreement' command.")
        return 0

    if args.cmd == "agreement":
        report = run(args.dataset, judge_name=args.judge)
        labels = load_labels(args.labels)
        if not labels:
            print("No human labels found in the CSV (human_* columns are empty).")
            return 1
        print(agreement(report, labels).render())
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
