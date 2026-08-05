"""Worked example: evaluate a (mock) RAG agent end-to-end.

This shows the pattern you'd use to wire a real agent into the platform:
1. Run your agent to produce answers over a set of questions.
2. Capture the retrieved contexts, latency, and cost per query.
3. Score the run with the evaluation platform.

Here we fake the agent with canned outputs so the example runs offline.
Run it with:  python examples/evaluate_rag_agent.py
"""

from __future__ import annotations

from eval_platform.runner import run


def main() -> None:
    # In a real integration you would build this list by calling your agent;
    # here we simply point at the bundled example dataset.
    report = run(
        "datasets/example_eval_set.jsonl",
        judge_name="mock",              # swap to "anthropic" with an API key
        gate_metric="faithfulness",
        gate_threshold=0.80,
    )

    print(report.render())
    print("\nPer-example faithfulness:")
    for row in report.per_example:
        print(f"  {row['id']}: {row['scores']['faithfulness']:.2f}  {row['question']}")


if __name__ == "__main__":
    main()
