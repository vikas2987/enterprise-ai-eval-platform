# Metric definitions

All quality scores are in `[0.0, 1.0]`, higher is better.

## Quality metrics (judge-scored)

| Metric | Question it answers | Score of 1.0 means | Score of 0.0 means |
|---|---|---|---|
| **faithfulness** | Is the answer true to the context? | Every claim is supported by the retrieved context | The answer contradicts or invents facts |
| **groundedness** | Can the answer be traced to sources? | Every statement is citable to the context | Nothing is grounded |
| **answer_relevance** | Does it address the question? | Fully answers the question asked | Off-topic or evasive |

## Operational metrics (measured)

| Metric | Definition |
|---|---|
| **latency_p50_ms / latency_p95_ms** | Median and 95th-percentile end-to-end response time per query |
| **cost_avg_usd** | Mean estimated cost per query |
| **cost_total_usd** | Total estimated cost across the run |

## GraphRAG retrieval metrics (measured)

Quality metrics judge the answer against *what was retrieved*. They cannot see
what retrieval **missed**. In Graph-RAG and multi-hop RAG, an answer can be
perfectly faithful to two retrieved nodes while silently missing a third
relevant one — a dangerous, invisible failure for a finance or legal agent.
These metrics measure retrieval itself, from node-id sets on each record.

| Metric | Definition | Answers |
|---|---|---|
| **retrieval_completeness** | `|retrieved ∩ relevant| / |relevant|` (recall) | "Did we retrieve *all* the relevant nodes?" |
| **retrieval_precision** | `|retrieved ∩ relevant| / |retrieved|` | "How much of what we retrieved was actually relevant?" |
| **full_recall_rate** (aggregate) | Fraction of graph-annotated records with completeness = 1.0 | "How often did we get *everything*?" |

Records without both `retrieved_nodes` and `relevant_nodes` are ignored, so
these metrics are opt-in and backward compatible.

## Human calibration (judge ↔ human)

An LLM judge is not ground truth. `human_eval.py` exports a labeling CSV, takes
human scores back, and reports agreement per metric:

| Metric | Definition |
|---|---|
| **MAE** | Mean absolute error between judge and human scores |
| **correlation** | Pearson correlation between judge and human scores |
| **verdict** | `well-calibrated` (MAE ≤ 0.10, corr ≥ 0.7) · `acceptable` (MAE ≤ 0.20) · `needs-recalibration` |

Use it to spot metrics where the judge drifts from human judgment before you
trust it in production.

## Dataset format

Each line of a `.jsonl` eval set is one record:

```json
{
  "id": "fin-001",
  "domain": "finance",
  "question": "What are the payment terms in the vendor agreement?",
  "contexts": ["Section 4.1: Fees are invoiced annually in advance. Net 30..."],
  "retrieved_nodes": ["saas-agreement#4.1", "saas-agreement#4.3"],
  "relevant_nodes": ["saas-agreement#4.1", "saas-agreement#4.3"],
  "answer": "Fees are invoiced annually in advance and due net 30...",
  "reference": "Net 30, annual advance billing, 1.5%/month late interest.",
  "latency_ms": 640,
  "cost_usd": 0.0041
}
```

- `question`, `contexts`, `answer` are **required**.
- `reference` is optional (used by answer-relevance and for human review).
- `retrieved_nodes`, `relevant_nodes` are optional (enable GraphRAG metrics).
- `latency_ms`, `cost_usd` are optional (captured when your agent answered).
- `id`, `domain` are optional labels used in reports.
