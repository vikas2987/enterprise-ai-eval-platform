"""Judge-scored quality metrics.

Each metric asks the configured judge to score one criterion for a record.
A record is a dict with keys: ``question``, ``answer``, ``contexts`` (list),
and optionally ``reference``.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..evaluators.judge import Judge

QUALITY_METRICS = ("faithfulness", "groundedness", "answer_relevance")


def score_quality(record: Mapping[str, Any], judge: Judge) -> dict[str, float]:
    """Score all quality metrics for a single record.

    Returns a mapping of metric name -> score in [0, 1].
    """
    question = record.get("question", "")
    answer = record.get("answer", "")
    contexts = record.get("contexts", []) or []
    reference = record.get("reference")

    return {
        metric: judge.score(
            metric,
            question=question,
            answer=answer,
            contexts=contexts,
            reference=reference,
        )
        for metric in QUALITY_METRICS
    }
