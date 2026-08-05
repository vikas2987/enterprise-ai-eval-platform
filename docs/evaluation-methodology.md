# Evaluation methodology

This document explains *why* the platform measures what it measures. The guiding
principle: **for enterprise AI, evaluation and trust are the product.** A finance
or legal team will not adopt an agent whose answers they cannot verify, so the
metrics here are chosen to answer one question — *can we trust this in production?*

## The problem with BLEU / ROUGE

BLEU and ROUGE measure n-gram overlap with a reference string. They were designed
for machine translation and summarization, and they break down for enterprise RAG
and agents because:

- A correct answer can be phrased many valid ways (low overlap, still correct).
- A fluent, wrong, *hallucinated* answer can score well on overlap.
- They say nothing about whether the answer is **grounded in the retrieved source**.

For enterprise use we care less about surface similarity and more about *trust*:
is the answer supported by the evidence, and does it actually answer the question?

## The four questions that matter

1. **Faithfulness** — does the answer stay true to the retrieved context, or does
   it invent/contradict? This is the primary hallucination guard.
2. **Groundedness** — can each statement be traced back to a source? This is what
   makes an answer *auditable*, which enterprise teams require.
3. **Answer relevance** — does the response actually address the question, or is it
   evasive/off-topic?
4. **Operational reality** — latency and cost at production volume. An accurate
   agent that is too slow or too expensive still fails in production.

## LLM-as-judge

Qualitative metrics are scored by an LLM judge prompted with an explicit rubric,
returning a calibrated score in [0, 1]. This scales far better than manual review
and is more meaningful than lexical overlap. Two safeguards matter:

- **Rubric prompts** keep the judge consistent and criterion-specific.
- **Human calibration** (roadmap) — periodically sample judge scores against human
  labels to keep the judge honest. Never treat the judge as ground truth without
  spot-checking.

The platform ships a dependency-free `MockJudge` so the whole pipeline runs offline
and in CI; swap in a real LLM judge for production evaluation.

## Regression gates

Every run applies a threshold to a chosen metric (default: faithfulness ≥ 0.80).
Wired into CI, this **blocks a prompt or model change that quietly makes quality
worse** — the single most common way production AI silently degrades.
