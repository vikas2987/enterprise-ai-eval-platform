"""Tests for the version-comparison (A/B) module."""

from __future__ import annotations

from eval_platform.compare import compare_datasets, compare_reports
from eval_platform.report import RunReport


def _report(faithfulness: float, latency: float) -> RunReport:
    return RunReport(
        n_examples=1,
        quality_avg={"faithfulness": faithfulness, "groundedness": faithfulness,
                     "answer_relevance": faithfulness},
        operational={"latency_p50_ms": latency, "latency_p95_ms": latency,
                     "cost_avg_usd": 0.004},
        per_example=[{"id": "x", "question": "q",
                      "scores": {"faithfulness": faithfulness,
                                 "groundedness": faithfulness,
                                 "answer_relevance": faithfulness}}],
    )


def test_quality_regression_is_flagged():
    base = _report(0.90, 700)
    cand = _report(0.80, 700)
    cmp = compare_reports(base, cand, threshold=0.02)
    assert not cmp.passed
    assert any(d.metric == "faithfulness" and d.verdict == "regressed"
               for d in cmp.metric_deltas)


def test_lower_latency_counts_as_improved():
    base = _report(0.90, 900)
    cand = _report(0.90, 600)
    cmp = compare_reports(base, cand, threshold=0.02)
    lat = next(d for d in cmp.metric_deltas if d.metric == "latency_p50_ms")
    assert lat.verdict == "improved"  # lower is better


def test_small_change_within_threshold_is_unchanged():
    base = _report(0.90, 700)
    cand = _report(0.905, 700)
    cmp = compare_reports(base, cand, threshold=0.02)
    fai = next(d for d in cmp.metric_deltas if d.metric == "faithfulness")
    assert fai.verdict == "unchanged"
    assert cmp.passed


def test_compare_datasets_end_to_end_catches_regression():
    cmp = compare_datasets(
        "datasets/ab_baseline.jsonl",
        "datasets/ab_candidate.jsonl",
        judge_name="mock",
    )
    # Candidate is faster but quality regressed -> gate must fail.
    assert not cmp.passed
    assert cmp.to_html().startswith("<!doctype html>")
