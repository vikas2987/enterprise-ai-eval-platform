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

## Dataset format

Each line of a `.jsonl` eval set is one record:

```json
{
  "id": "ex-1",
  "question": "What is the payment term in the vendor agreement?",
  "contexts": ["The vendor agreement states payment is due net 30..."],
  "answer": "Payment is due within 30 days (net 30).",
  "reference": "Net 30 from invoice receipt.",
  "latency_ms": 610,
  "cost_usd": 0.0038
}
```

- `question`, `contexts`, `answer` are required.
- `reference` is optional (used by answer-relevance and for human review).
- `latency_ms`, `cost_usd` are optional (captured when your agent answered).
