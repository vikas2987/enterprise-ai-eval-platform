"""LLM-as-judge implementations.

A ``Judge`` scores a single criterion (e.g. "faithfulness") for one
evaluation record and returns a float in [0.0, 1.0].

Two judges ship out of the box:

* ``MockJudge`` — deterministic, offline, dependency-free. It uses simple
  lexical-overlap heuristics so the platform is fully runnable without an
  API key. Good enough to demo the pipeline and to unit-test the plumbing.
* ``AnthropicJudge`` — a real LLM judge that prompts a model with a rubric
  and parses back a score. Requires ``anthropic`` and ``ANTHROPIC_API_KEY``.

Swap in your own judge by implementing the ``Judge`` protocol.
"""

from __future__ import annotations

import os
import re
from typing import Protocol, Sequence


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _overlap(a: str, b: str) -> float:
    """Fraction of tokens in ``a`` that also appear in ``b`` (0..1)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta:
        return 0.0
    return len(ta & tb) / len(ta)


class Judge(Protocol):
    """Anything that can score a criterion for one record."""

    def score(
        self,
        criterion: str,
        *,
        question: str,
        answer: str,
        contexts: Sequence[str],
        reference: str | None = None,
    ) -> float:
        ...


class MockJudge:
    """Offline heuristic judge — no API key required.

    The heuristics are intentionally simple but directionally meaningful:
    an answer that reuses the retrieved context scores higher on
    faithfulness/groundedness; an answer that addresses the question scores
    higher on relevance. This lets the whole pipeline run in CI and demos.
    """

    def score(
        self,
        criterion: str,
        *,
        question: str,
        answer: str,
        contexts: Sequence[str],
        reference: str | None = None,
    ) -> float:
        joined_context = " ".join(contexts)
        if criterion in ("faithfulness", "groundedness"):
            # How much of the answer is supported by the retrieved context.
            base = _overlap(answer, joined_context)
        elif criterion == "answer_relevance":
            # How well the answer engages with the question (+ reference if any).
            target = f"{question} {reference or ''}"
            base = _overlap(answer, target)
        else:
            base = _overlap(answer, joined_context)
        # Squash to a realistic band so demo numbers look plausible (~0.7-0.98).
        return round(min(1.0, 0.65 + 0.35 * base), 3)


class AnthropicJudge:
    """Real LLM-as-judge backed by the Anthropic API.

    Prompts the model with a rubric and asks for a single score in [0, 1].
    Import and network are lazy so the package works without the dependency.
    """

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:  # pragma: no cover - optional dep
            raise ImportError(
                "AnthropicJudge requires the 'anthropic' package. "
                "Install it with: pip install anthropic"
            ) from exc
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("Set ANTHROPIC_API_KEY to use AnthropicJudge.")
        from anthropic import Anthropic

        self._client = Anthropic()
        self._model = model

    _RUBRICS = {
        "faithfulness": (
            "Score how faithful the ANSWER is to the CONTEXT. 1.0 means every "
            "claim is supported by the context; 0.0 means it contradicts or "
            "invents information not in the context."
        ),
        "groundedness": (
            "Score how well each statement in the ANSWER can be traced to the "
            "CONTEXT. 1.0 = fully grounded and citable; 0.0 = ungrounded."
        ),
        "answer_relevance": (
            "Score how directly the ANSWER addresses the QUESTION. "
            "1.0 = fully answers it; 0.0 = off-topic or evasive."
        ),
    }

    def score(
        self,
        criterion: str,
        *,
        question: str,
        answer: str,
        contexts: Sequence[str],
        reference: str | None = None,
    ) -> float:
        rubric = self._RUBRICS.get(criterion, self._RUBRICS["faithfulness"])
        prompt = (
            f"You are a strict evaluation judge.\n{rubric}\n\n"
            f"QUESTION:\n{question}\n\n"
            f"CONTEXT:\n{' '.join(contexts)}\n\n"
            f"ANSWER:\n{answer}\n\n"
            "Respond with ONLY a number between 0 and 1 (two decimals)."
        )
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=8,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        match = re.search(r"[01](?:\.\d+)?", text)
        return float(match.group()) if match else 0.0


def get_judge(name: str = "mock") -> Judge:
    """Factory: ``mock`` (default, offline) or ``anthropic`` (real LLM)."""
    name = name.lower()
    if name == "mock":
        return MockJudge()
    if name == "anthropic":
        return AnthropicJudge()
    raise ValueError(f"Unknown judge: {name!r}. Use 'mock' or 'anthropic'.")
