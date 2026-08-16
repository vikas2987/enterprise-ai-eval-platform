"""Tests for GraphRAG retrieval metrics."""

from __future__ import annotations

from eval_platform.metrics.graph import aggregate_graph, score_graph_record


def test_full_retrieval_scores_one():
    rec = {
        "retrieved_nodes": ["a", "b", "c"],
        "relevant_nodes": ["a", "b", "c"],
    }
    scored = score_graph_record(rec)
    assert scored == {"retrieval_completeness": 1.0, "retrieval_precision": 1.0}


def test_missing_relevant_node_lowers_completeness():
    rec = {
        "retrieved_nodes": ["a", "b"],
        "relevant_nodes": ["a", "b", "c"],
    }
    scored = score_graph_record(rec)
    assert scored is not None
    assert scored["retrieval_completeness"] == round(2 / 3, 3)
    assert scored["retrieval_precision"] == 1.0


def test_noise_lowers_precision_not_completeness():
    rec = {
        "retrieved_nodes": ["a", "b", "x"],  # x is irrelevant noise
        "relevant_nodes": ["a", "b"],
    }
    scored = score_graph_record(rec)
    assert scored["retrieval_completeness"] == 1.0
    assert scored["retrieval_precision"] == round(2 / 3, 3)


def test_records_without_graph_annotations_are_skipped():
    assert score_graph_record({"question": "no nodes here"}) is None


def test_aggregate_returns_empty_when_no_graph_data():
    assert aggregate_graph([{"question": "q"}, {"question": "q2"}]) == {}


def test_aggregate_full_recall_rate():
    records = [
        {"retrieved_nodes": ["a"], "relevant_nodes": ["a"]},          # complete
        {"retrieved_nodes": ["a"], "relevant_nodes": ["a", "b"]},     # 0.5
    ]
    agg = aggregate_graph(records)
    assert agg["graph_examples"] == 2.0
    assert agg["full_recall_rate"] == 0.5
    assert agg["retrieval_completeness_avg"] == 0.75
