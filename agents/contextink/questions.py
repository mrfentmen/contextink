"""Minimal clarifying questions: rank by information gain, ask only what's needed.

The whole point: never ask everything, never ask nothing. Rank the gaps by how much
each answer would narrow the plan, and ask only the top few. Pure rules, no model.
"""

from __future__ import annotations

WEIGHTS = {"target": 3, "referent": 3, "success": 2, "scope": 1}


def information_gain(gap: dict) -> int:
    return WEIGHTS.get(gap.get("kind"), 1)


def rank_questions(gaps: list[dict]) -> list[dict]:
    return sorted(gaps, key=lambda g: -information_gain(g))


def minimal_questions(gaps: list[dict], max_n: int = 3) -> list[str]:
    ranked = rank_questions(gaps)
    return [g["question"] for g in ranked[:max_n]]
