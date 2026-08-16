"""Prompt / model version comparison — A/B two evaluation runs.

The most common way production AI quietly breaks is a prompt tweak or model
swap that improves one thing and silently regresses another. This module runs
the *same* eval questions through two variants (baseline vs candidate) and
produces a side-by-side diff: per-metric deltas, per-example changes, and a
verdict that a CI job can gate on.

Usage:
    python -m eval_platform.compare \\
        --baseline datasets/ab_baseline.jsonl \\
        --candidate datasets/ab_candidate.jsonl \\
        --html reports/compare.html

Exit code is non-zero if any tracked quality/graph metric regresses by more
than ``--threshold`` — so a bad prompt change can't merge.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .metrics.quality import QUALITY_METRICS
from .report import RunReport
from .runner import run

# Metrics where higher is better vs. where lower is better.
_HIGHER_BETTER = set(QUALITY_METRICS) | {
    "retrieval_completeness_avg",
    "retrieval_precision_avg",
    "full_recall_rate",
}
_LOWER_BETTER = {"latency_p50_ms", "latency_p95_ms", "cost_avg_usd"}


@dataclass
class MetricDelta:
    metric: str
    baseline: float
    candidate: float
    delta: float
    verdict: str  # "improved" | "regressed" | "unchanged"
    higher_better: bool


@dataclass
class ComparisonReport:
    baseline_label: str
    candidate_label: str
    metric_deltas: list[MetricDelta] = field(default_factory=list)
    per_example: list[dict[str, Any]] = field(default_factory=list)
    threshold: float = 0.02
    tracked: tuple[str, ...] = QUALITY_METRICS

    @property
    def regressions(self) -> list[MetricDelta]:
        """Tracked quality/graph metrics that regressed beyond the threshold."""
        return [
            d for d in self.metric_deltas
            if d.metric in self.tracked and d.verdict == "regressed"
            and abs(d.delta) > self.threshold
        ]

    @property
    def passed(self) -> bool:
        return not self.regressions

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    def render(self) -> str:
        lines = [
            "Version comparison — baseline vs candidate",
            "-" * 56,
            f"baseline .... {self.baseline_label}",
            f"candidate ... {self.candidate_label}",
            "-" * 56,
            f"{'metric':<26}{'base':>8}{'cand':>8}{'Δ':>9}  verdict",
        ]
        for d in self.metric_deltas:
            arrow = {"improved": "▲", "regressed": "▼", "unchanged": "="}[d.verdict]
            lines.append(
                f"{d.metric:<26}{d.baseline:>8.3f}{d.candidate:>8.3f}"
                f"{d.delta:>+9.3f}  {arrow} {d.verdict}"
            )
        lines.append("-" * 56)
        if self.passed:
            lines.append(f"COMPARISON GATE: PASS (no tracked metric regressed > {self.threshold})")
        else:
            names = ", ".join(d.metric for d in self.regressions)
            lines.append(f"COMPARISON GATE: FAIL (regressed: {names})")
        return "\n".join(lines)

    def to_html(self) -> str:
        return _render_compare_html(self)


def _verdict(delta: float, higher_better: bool, threshold: float) -> str:
    if abs(delta) <= threshold:
        return "unchanged"
    improved = delta > 0 if higher_better else delta < 0
    return "improved" if improved else "regressed"


def _collect_metrics(report: RunReport) -> dict[str, float]:
    metrics: dict[str, float] = dict(report.quality_avg)
    op = report.operational
    for k in ("latency_p50_ms", "latency_p95_ms", "cost_avg_usd"):
        if k in op:
            metrics[k] = op[k]
    for k in ("retrieval_completeness_avg", "retrieval_precision_avg", "full_recall_rate"):
        if k in report.graph:
            metrics[k] = report.graph[k]
    return metrics


def compare_reports(
    baseline: RunReport,
    candidate: RunReport,
    threshold: float = 0.02,
    baseline_label: str = "baseline",
    candidate_label: str = "candidate",
) -> ComparisonReport:
    """Diff two already-computed :class:`RunReport` objects."""
    base_m = _collect_metrics(baseline)
    cand_m = _collect_metrics(candidate)

    deltas: list[MetricDelta] = []
    for metric in base_m:
        if metric not in cand_m:
            continue
        higher_better = metric not in _LOWER_BETTER
        b, c = base_m[metric], cand_m[metric]
        delta = round(c - b, 4)
        deltas.append(
            MetricDelta(
                metric=metric,
                baseline=b,
                candidate=c,
                delta=delta,
                verdict=_verdict(delta, higher_better, threshold),
                higher_better=higher_better,
            )
        )

    # Per-example quality diff, aligned by id.
    base_by_id = {r.get("id"): r for r in baseline.per_example}
    per_example: list[dict[str, Any]] = []
    for cand_row in candidate.per_example:
        rid = cand_row.get("id")
        base_row = base_by_id.get(rid)
        if base_row is None:
            continue
        metric_diffs: dict[str, dict[str, float]] = {}
        for m in QUALITY_METRICS:
            b = base_row.get("scores", {}).get(m, 0.0)
            c = cand_row.get("scores", {}).get(m, 0.0)
            metric_diffs[m] = {"baseline": b, "candidate": c, "delta": round(c - b, 3)}
        per_example.append(
            {"id": rid, "question": cand_row.get("question"), "metrics": metric_diffs}
        )

    return ComparisonReport(
        baseline_label=baseline_label,
        candidate_label=candidate_label,
        metric_deltas=deltas,
        per_example=per_example,
        threshold=threshold,
        tracked=tuple(QUALITY_METRICS)
        + tuple(m for m in ("retrieval_completeness_avg",) if m in base_m),
    )


def compare_datasets(
    baseline_path: str | Path,
    candidate_path: str | Path,
    judge_name: str = "mock",
    threshold: float = 0.02,
) -> ComparisonReport:
    """Run eval on both datasets with the same judge, then diff them."""
    base = run(baseline_path, judge_name=judge_name)
    cand = run(candidate_path, judge_name=judge_name)
    return compare_reports(
        base,
        cand,
        threshold=threshold,
        baseline_label=str(baseline_path),
        candidate_label=str(candidate_path),
    )


# --------------------------------------------------------------------- HTML

def _cls(verdict: str) -> str:
    return {"improved": "good", "regressed": "bad", "unchanged": "muted"}[verdict]


def _render_compare_html(r: ComparisonReport) -> str:
    metric_rows = []
    for d in r.metric_deltas:
        sign = "+" if d.delta >= 0 else ""
        metric_rows.append(
            f'<tr><td>{html.escape(d.metric.replace("_", " "))}</td>'
            f"<td>{d.baseline:.3f}</td><td>{d.candidate:.3f}</td>"
            f'<td class="{_cls(d.verdict)}">{sign}{d.delta:.3f}</td>'
            f'<td class="{_cls(d.verdict)}">{html.escape(d.verdict)}</td></tr>'
        )
    metric_rows_html = "\n".join(metric_rows)

    ex_rows = []
    for row in r.per_example:
        f = row["metrics"].get("faithfulness", {})
        delta = f.get("delta", 0.0)
        cls = "good" if delta > 0.02 else "bad" if delta < -0.02 else "muted"
        sign = "+" if delta >= 0 else ""
        ex_rows.append(
            f'<tr><td class="id">{html.escape(str(row.get("id","")))}</td>'
            f'<td class="q">{html.escape(str(row.get("question","")))}</td>'
            f'<td>{f.get("baseline",0):.2f}</td><td>{f.get("candidate",0):.2f}</td>'
            f'<td class="{cls}">{sign}{delta:.2f}</td></tr>'
        )
    ex_rows_html = "\n".join(ex_rows)

    gate_cls = "pass" if r.passed else "fail"
    if r.passed:
        gate_text = f"PASS — no tracked metric regressed &gt; {r.threshold}"
    else:
        names = ", ".join(html.escape(d.metric) for d in r.regressions)
        gate_text = f"FAIL — regressed: {names}"

    return _COMPARE_TEMPLATE.format(
        baseline=html.escape(r.baseline_label),
        candidate=html.escape(r.candidate_label),
        gate_cls=gate_cls,
        gate_text=gate_text,
        metric_rows=metric_rows_html,
        ex_rows=ex_rows_html,
    )


_COMPARE_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Version Comparison — Enterprise AI Evaluation</title>
<style>
  :root {{ --bg:#0f1116; --panel:#171a21; --panel2:#1e222b; --border:#2a2f3a;
    --text:#e6e9ef; --muted:#9aa4b2; --good:#35c48b; --bad:#e5544b; --accent:#6ea8fe; }}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}}
  .wrap{{max-width:1000px;margin:0 auto;padding:32px 24px 64px}}
  h1{{font-size:22px;margin:0 0 16px}} h2{{font-size:14px;text-transform:uppercase;
    letter-spacing:.6px;color:var(--muted);margin:28px 0 12px}}
  .ab{{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}}
  .ab div{{background:var(--panel);border:1px solid var(--border);border-radius:10px;
    padding:12px 16px;font-size:13px}} .ab code{{color:var(--accent)}}
  .gate{{padding:14px 18px;border-radius:10px;font-weight:600;margin-bottom:8px;border:1px solid var(--border)}}
  .gate.pass{{background:rgba(53,196,139,.12);color:var(--good);border-color:rgba(53,196,139,.35)}}
  .gate.fail{{background:rgba(229,84,75,.12);color:var(--bad);border-color:rgba(229,84,75,.35)}}
  .table-wrap{{overflow-x:auto;border:1px solid var(--border);border-radius:12px}}
  table{{border-collapse:collapse;width:100%;font-size:13.5px}}
  th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid var(--border)}}
  th{{background:var(--panel2);color:var(--muted);font-weight:600}}
  tr:last-child td{{border-bottom:none}}
  td.id{{font-family:ui-monospace,Menlo,monospace;color:var(--accent);white-space:nowrap}}
  .good{{color:var(--good);font-weight:600}} .bad{{color:var(--bad);font-weight:600}}
  .muted{{color:var(--muted)}}
  @media (prefers-color-scheme: light){{:root{{--bg:#f6f7f9;--panel:#fff;--panel2:#eef1f5;
    --border:#dde1e8;--text:#1a1d23;--muted:#5b6472}}}}
</style></head><body><div class="wrap">
  <h1>Version Comparison</h1>
  <div class="ab">
    <div>Baseline: <code>{baseline}</code></div>
    <div>Candidate: <code>{candidate}</code></div>
  </div>
  <div class="gate {gate_cls}">Comparison gate: {gate_text}</div>
  <h2>Aggregate metric deltas</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>metric</th><th>baseline</th><th>candidate</th><th>Δ</th><th>verdict</th></tr></thead>
    <tbody>{metric_rows}</tbody>
  </table></div>
  <h2>Per-example faithfulness change</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>id</th><th>question</th><th>base</th><th>cand</th><th>Δ</th></tr></thead>
    <tbody>{ex_rows}</tbody>
  </table></div>
</div></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two evaluation runs (A/B).")
    parser.add_argument("--baseline", required=True, help="Baseline JSONL eval set.")
    parser.add_argument("--candidate", required=True, help="Candidate JSONL eval set.")
    parser.add_argument("--judge", default="mock", choices=["mock", "anthropic"])
    parser.add_argument("--threshold", type=float, default=0.02,
                        help="Regression tolerance for a tracked metric.")
    parser.add_argument("--json", dest="as_json", action="store_true")
    parser.add_argument("--html", metavar="PATH", help="Write an HTML diff to PATH.")
    args = parser.parse_args(argv)

    report = compare_datasets(
        args.baseline, args.candidate, judge_name=args.judge, threshold=args.threshold
    )
    print(report.to_json() if args.as_json else report.render())

    if args.html:
        out = Path(args.html)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.to_html(), encoding="utf-8")
        print(f"\nHTML comparison written to {out}")

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
