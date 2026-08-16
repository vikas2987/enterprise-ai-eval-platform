"""GraphRAG retrieval metrics: completeness and precision.

Judge-scored quality metrics tell you whether an answer is faithful to what
was retrieved. They *cannot* tell you whether retrieval found everything it
should have. In Graph-RAG (and multi-hop RAG generally), an answer can be
perfectly faithful to the two nodes that were retrieved while silently missing
a third relevant node — the single most dangerous failure mode for a finance
or legal agent, because the answer *looks* confident and grounded.

These metrics are *measured*, not judged. Each record may carry:

* ``retrieved_nodes`` — the graph/document node ids the agent actually pulled.
* ``relevant_nodes``  — the gold set of node ids that *should* have been pulled.

From those two sets we compute, per record:

* **retrieval_completeness** = |retrieved ∩ relevant| / |relevant|  (recall)
  — "did we retrieve *all* the relevant nodes?"  This is the headline metric.
* **retrieval_precision**    = |retrieved ∩ relevant| / |retrieved|
  — "how much of what we retrieved was actually relevant?" (noise / cost proxy)

Records without both fields are ignored, so the metric is fully backward
compatible with datasets that don't carry graph annotations.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

GRAPH_METRICS = ("retrieval_completeness", "retrieval_precision")


def _as_set(value: Any) -> set[str]:
    if not value:
        return set()
    return {str(v) for v in value}


def score_graph_record(record: Mapping[str, Any]) -> dict[str, float] | None:
    """Score GraphRAG retrieval for one record.

    Returns a mapping with ``retrieval_completeness`` and
    ``retrieval_precision`` in [0, 1], or ``None`` if the record carries no
    graph annotations (both ``retrieved_nodes`` and ``relevant_nodes``).
    """
    if "retrieved_nodes" not in record or "relevant_nodes" not in record:
        return None

    retrieved = _as_set(record.get("retrieved_nodes"))
    relevant = _as_set(record.get("relevant_nodes"))
    hits = retrieved & relevant

    completeness = len(hits) / len(relevant) if relevant else 1.0
    precision = len(hits) / len(retrieved) if retrieved else 0.0

    return {
        "retrieval_completeness": round(completeness, 3),
        "retrieval_precision": round(precision, 3),
    }


def aggregate_graph(records: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    """Aggregate GraphRAG retrieval metrics across a run.

    Returns an empty dict when no record carries graph annotations, so callers
    can cheaply detect "this run has no GraphRAG data" and skip the section.
    The ``full_recall_rate`` is the fraction of graph-annotated records for
    which retrieval was *complete* (completeness == 1.0) — a blunt, honest
    "how often did we get everything?" number that reads well on a dashboard.
    """
    completeness: list[float] = []
    precision: list[float] = []

    for rec in records:
        scored = score_graph_record(rec)
        if scored is None:
            continue
        completeness.append(scored["retrieval_completeness"])
        precision.append(scored["retrieval_precision"])

    if not completeness:
        return {}

    n = len(completeness)
    full = sum(1 for c in completeness if c >= 1.0)
    return {
        "retrieval_completeness_avg": round(sum(completeness) / n, 3),
        "retrieval_precision_avg": round(sum(precision) / n, 3),
        "full_recall_rate": round(full / n, 3),
        "graph_examples": float(n),
    }
