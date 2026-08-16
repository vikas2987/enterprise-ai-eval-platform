"""Reporting: terminal scorecard, JSON, HTML dashboard, and regression gates."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class RunReport:
    n_examples: int
    quality_avg: dict[str, float]
    operational: dict[str, float]
    per_example: list[dict[str, Any]] = field(default_factory=list)
    gate_metric: str = "faithfulness"
    gate_threshold: float = 0.80
    graph: dict[str, float] = field(default_factory=dict)
    dataset: str = ""
    judge: str = ""

    # ------------------------------------------------------------------ gates
    @property
    def gate_value(self) -> float:
        return self.quality_avg.get(self.gate_metric, 0.0)

    @property
    def gate_passed(self) -> bool:
        return self.gate_value >= self.gate_threshold

    # ---------------------------------------------------------------- exports
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def render(self) -> str:
        """Terminal scorecard."""
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

        if self.graph:
            g = self.graph
            lines.append("-" * 48)
            lines.append("GraphRAG retrieval (nodes)")
            lines.append(
                "  completeness (avg) ....... "
                f"{g.get('retrieval_completeness_avg', 0):.2f}"
            )
            lines.append(
                "  precision (avg) .......... "
                f"{g.get('retrieval_precision_avg', 0):.2f}"
            )
            lines.append(
                "  full-recall rate ......... "
                f"{g.get('full_recall_rate', 0):.0%}"
            )

        lines.append("-" * 48)
        status = "PASS" if self.gate_passed else "FAIL"
        lines.append(
            f"REGRESSION GATE: {status} "
            f"(min {self.gate_metric} {self.gate_value:.2f} "
            f">= {self.gate_threshold:.2f})"
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------- HTML
    def to_html(self) -> str:
        """Render a self-contained HTML dashboard (no external assets)."""
        return _render_html(self)


# ---------------------------------------------------------------------- HTML

def _score_class(v: float) -> str:
    if v >= 0.85:
        return "good"
    if v >= 0.70:
        return "warn"
    return "bad"


def _metric_card(label: str, value: str, cls: str = "") -> str:
    return (
        f'<div class="card {cls}">'
        f'<div class="card-value">{html.escape(value)}</div>'
        f'<div class="card-label">{html.escape(label)}</div>'
        f"</div>"
    )


def _render_html(r: RunReport) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # --- metric cards ---
    cards: list[str] = []
    for name, value in r.quality_avg.items():
        cards.append(_metric_card(name.replace("_", " "), f"{value:.2f}", _score_class(value)))
    op = r.operational
    cards.append(_metric_card("latency p50 (ms)", f"{op.get('latency_p50_ms', 0):.0f}"))
    cards.append(_metric_card("latency p95 (ms)", f"{op.get('latency_p95_ms', 0):.0f}"))
    cards.append(_metric_card("avg cost (USD)", f"${op.get('cost_avg_usd', 0):.4f}"))
    if r.graph:
        g = r.graph
        cards.append(
            _metric_card(
                "retrieval completeness",
                f"{g.get('retrieval_completeness_avg', 0):.2f}",
                _score_class(g.get("retrieval_completeness_avg", 0)),
            )
        )
        cards.append(
            _metric_card(
                "full-recall rate",
                f"{g.get('full_recall_rate', 0):.0%}",
                _score_class(g.get("full_recall_rate", 0)),
            )
        )
    cards_html = "\n".join(cards)

    # --- gate banner ---
    gate_cls = "pass" if r.gate_passed else "fail"
    gate_text = "PASS" if r.gate_passed else "FAIL"
    gate_html = (
        f'<div class="gate {gate_cls}">Regression gate: {gate_text} '
        f"&nbsp;·&nbsp; {html.escape(r.gate_metric)} "
        f"{r.gate_value:.2f} ≥ {r.gate_threshold:.2f}</div>"
    )

    # --- per-example table ---
    metric_names = list(r.quality_avg.keys())
    header_cells = "".join(f"<th>{html.escape(m.replace('_', ' '))}</th>" for m in metric_names)
    has_graph_rows = any("graph" in row for row in r.per_example)
    if has_graph_rows:
        header_cells += "<th>retrieval<br>completeness</th>"

    rows: list[str] = []
    for row in r.per_example:
        scores = row.get("scores", {})
        cells = [
            f'<td class="id">{html.escape(str(row.get("id", "")))}</td>',
            f'<td class="q">{html.escape(str(row.get("question", "")))}</td>',
        ]
        for m in metric_names:
            v = scores.get(m, 0.0)
            cells.append(f'<td class="score {_score_class(v)}">{v:.2f}</td>')
        if has_graph_rows:
            ginfo = row.get("graph")
            if ginfo:
                c = ginfo.get("retrieval_completeness", 0.0)
                cells.append(f'<td class="score {_score_class(c)}">{c:.2f}</td>')
            else:
                cells.append('<td class="score na">—</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    rows_html = "\n".join(rows)

    meta_bits = []
    if r.dataset:
        meta_bits.append(f"dataset <code>{html.escape(r.dataset)}</code>")
    if r.judge:
        meta_bits.append(f"judge <code>{html.escape(r.judge)}</code>")
    meta_bits.append(f"{r.n_examples} examples")
    meta_line = " &nbsp;·&nbsp; ".join(meta_bits)

    return _HTML_TEMPLATE.format(
        generated=generated,
        meta_line=meta_line,
        gate_html=gate_html,
        cards_html=cards_html,
        header_cells=header_cells,
        rows_html=rows_html,
    )


_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Enterprise AI Evaluation — Run Report</title>
<style>
  :root {{
    --bg: #0f1116; --panel: #171a21; --panel2: #1e222b; --border: #2a2f3a;
    --text: #e6e9ef; --muted: #9aa4b2; --good: #35c48b; --warn: #e0a63a; --bad: #e5544b;
    --accent: #6ea8fe;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 32px 24px 64px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; letter-spacing: .2px; }}
  .meta {{ color: var(--muted); font-size: 13px; margin-bottom: 24px; }}
  .meta code {{ background: var(--panel2); padding: 1px 6px; border-radius: 5px; color: var(--accent); }}
  .gate {{ padding: 14px 18px; border-radius: 10px; font-weight: 600; margin-bottom: 24px;
    border: 1px solid var(--border); }}
  .gate.pass {{ background: rgba(53,196,139,.12); color: var(--good); border-color: rgba(53,196,139,.35); }}
  .gate.fail {{ background: rgba(229,84,75,.12); color: var(--bad); border-color: rgba(229,84,75,.35); }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr));
    gap: 12px; margin-bottom: 28px; }}
  .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px; }}
  .card-value {{ font-size: 26px; font-weight: 700; }}
  .card-label {{ color: var(--muted); font-size: 12px; margin-top: 4px; text-transform: uppercase;
    letter-spacing: .4px; }}
  .card.good .card-value {{ color: var(--good); }}
  .card.warn .card-value {{ color: var(--warn); }}
  .card.bad .card-value {{ color: var(--bad); }}
  h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: .6px; color: var(--muted);
    margin: 0 0 12px; }}
  .table-wrap {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 12px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ background: var(--panel2); color: var(--muted); font-weight: 600; white-space: nowrap; }}
  tr:last-child td {{ border-bottom: none; }}
  td.id {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; color: var(--accent); white-space: nowrap; }}
  td.q {{ color: var(--text); min-width: 280px; }}
  td.score {{ text-align: center; font-variant-numeric: tabular-nums; font-weight: 600; width: 92px; }}
  td.score.good {{ color: var(--good); }}
  td.score.warn {{ color: var(--warn); }}
  td.score.bad {{ color: var(--bad); }}
  td.score.na {{ color: var(--muted); font-weight: 400; }}
  footer {{ color: var(--muted); font-size: 12px; margin-top: 28px; }}
  @media (prefers-color-scheme: light) {{
    :root {{ --bg: #f6f7f9; --panel: #fff; --panel2: #eef1f5; --border: #dde1e8;
      --text: #1a1d23; --muted: #5b6472; }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>Enterprise AI Evaluation — Run Report</h1>
    <div class="meta">{meta_line} &nbsp;·&nbsp; generated {generated}</div>
    {gate_html}
    <div class="cards">
      {cards_html}
    </div>
    <h2>Per-example scores</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>id</th><th>question</th>{header_cells}</tr></thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
    <footer>Enterprise AI Evaluation Platform · scores in [0,1], higher is better ·
      green ≥ 0.85, amber ≥ 0.70, red &lt; 0.70.</footer>
  </div>
</body>
</html>
"""
