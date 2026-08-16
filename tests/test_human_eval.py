"""Tests for the human-evaluation / judge-calibration workflow."""

from __future__ import annotations

from eval_platform.human_eval import (
    agreement,
    export_for_labeling,
    load_labels,
)
from eval_platform.report import RunReport


def _report() -> RunReport:
    return RunReport(
        n_examples=2,
        quality_avg={"faithfulness": 0.9, "groundedness": 0.9, "answer_relevance": 0.9},
        operational={},
        per_example=[
            {"id": "r1", "question": "q1",
             "scores": {"faithfulness": 0.90, "groundedness": 0.90, "answer_relevance": 0.90}},
            {"id": "r2", "question": "q2",
             "scores": {"faithfulness": 0.70, "groundedness": 0.70, "answer_relevance": 0.70}},
        ],
    )


def test_export_writes_blank_human_columns(tmp_path):
    records = [
        {"id": "r1", "answer": "a1", "contexts": ["c1"]},
        {"id": "r2", "answer": "a2", "contexts": ["c2"]},
    ]
    out = export_for_labeling(_report(), records, tmp_path / "label.csv")
    text = out.read_text(encoding="utf-8")
    assert "judge_faithfulness" in text
    assert "human_faithfulness" in text
    # Judge score is populated, human score is blank.
    assert "0.900" in text


def test_round_trip_labels_and_agreement(tmp_path):
    csv_path = tmp_path / "labels.csv"
    csv_path.write_text(
        "id,human_faithfulness,human_groundedness,human_answer_relevance\n"
        "r1,0.90,0.90,0.90\n"
        "r2,0.70,0.70,0.70\n",
        encoding="utf-8",
    )
    labels = load_labels(csv_path)
    assert labels["r1"]["faithfulness"] == 0.90

    report = agreement(_report(), labels)
    assert report.n_examples == 2
    # Judge exactly matches human here -> zero error, perfect calibration.
    faith = next(a for a in report.per_metric if a.metric == "faithfulness")
    assert faith.mae == 0.0
    assert faith.verdict == "well-calibrated"


def test_partial_labels_are_tolerated(tmp_path):
    csv_path = tmp_path / "labels.csv"
    csv_path.write_text(
        "id,human_faithfulness,human_groundedness,human_answer_relevance\n"
        "r1,0.80,,\n",  # only faithfulness labeled
        encoding="utf-8",
    )
    labels = load_labels(csv_path)
    assert labels == {"r1": {"faithfulness": 0.80}}
    report = agreement(_report(), labels)
    faith = next(a for a in report.per_metric if a.metric == "faithfulness")
    assert faith.n == 1
    assert round(faith.mae, 2) == 0.10
