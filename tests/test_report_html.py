"""Tests for the HTML dashboard and GraphRAG-aware reporting."""

from __future__ import annotations

from eval_platform.runner import run


def test_html_dashboard_is_self_contained():
    report = run("datasets/enterprise_finance_legal.jsonl", judge_name="mock")
    html = report.to_html()
    assert html.startswith("<!doctype html>")
    # Self-contained: no external stylesheet or script references.
    assert "http://" not in html and "https://" not in html
    assert "<style>" in html
    # Gate + a known example id are rendered.
    assert "Regression gate" in html
    assert "fin-001" in html


def test_graph_metrics_surface_in_report():
    report = run("datasets/enterprise_finance_legal.jsonl", judge_name="mock")
    assert "retrieval_completeness_avg" in report.graph
    assert "GraphRAG" in report.render()
    # One record (fin-017) has an intentional retrieval gap, so not full recall.
    assert report.graph["full_recall_rate"] < 1.0


def test_report_without_graph_data_omits_section():
    report = run("datasets/example_eval_set.jsonl", judge_name="mock")
    assert report.graph == {}
    assert "GraphRAG" not in report.render()
