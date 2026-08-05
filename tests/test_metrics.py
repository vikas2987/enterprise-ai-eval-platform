"""Unit tests for the evaluation platform."""

from __future__ import annotations

from eval_platform.evaluators.judge import MockJudge, get_judge
from eval_platform.metrics import aggregate_operational, score_quality
from eval_platform.metrics.quality import QUALITY_METRICS
from eval_platform.runner import run


def test_mock_judge_scores_in_range():
    judge = MockJudge()
    score = judge.score(
        "faithfulness",
        question="What is net 30?",
        answer="Payment due within 30 days.",
        contexts=["Payment is due within 30 days of invoice."],
    )
    assert 0.0 <= score <= 1.0


def test_grounded_answer_beats_ungrounded():
    judge = MockJudge()
    ctx = ["The liability cap is the trailing twelve months of fees."]
    grounded = judge.score(
        "groundedness",
        question="What is the liability cap?",
        answer="The liability cap is the trailing twelve months of fees.",
        contexts=ctx,
    )
    ungrounded = judge.score(
        "groundedness",
        question="What is the liability cap?",
        answer="Bananas are yellow and grow on trees.",
        contexts=ctx,
    )
    assert grounded > ungrounded


def test_score_quality_returns_all_metrics():
    record = {
        "question": "Is there auto-renewal?",
        "answer": "Yes, it auto-renews annually.",
        "contexts": ["The agreement auto-renews for one-year terms."],
    }
    scores = score_quality(record, MockJudge())
    assert set(scores) == set(QUALITY_METRICS)


def test_operational_aggregation():
    records = [
        {"latency_ms": 100, "cost_usd": 0.01},
        {"latency_ms": 300, "cost_usd": 0.03},
    ]
    op = aggregate_operational(records)
    assert op["latency_p50_ms"] == 200.0
    assert op["cost_total_usd"] == 0.04


def test_full_run_passes_gate_on_example_set():
    report = run("datasets/example_eval_set.jsonl", judge_name="mock")
    assert report.n_examples == 5
    assert report.gate_passed  # mock judge on grounded answers clears 0.80


def test_get_judge_factory():
    assert isinstance(get_judge("mock"), MockJudge)
