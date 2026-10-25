"""Choose questions for CLI practice."""

from __future__ import annotations

from engine.model import Bank, Question


def practice_pool(bank: Bank, objective: str | None = None) -> list[Question]:
    """Questions eligible for CLI drills, sorted by ID: never holdout, never retired.

    With `objective`, only that objective's questions. An objective the exam doesn't have raises
    `ValueError`, so a typo can't silently return an empty drill.
    """
    if objective is not None and objective not in {o.id for o in bank.objectives}:
        raise ValueError(f"exam {bank.exam} has no objective {objective!r}")
    return [
        q
        for q in bank.questions
        if q.pool == "practice" and not q.retired and (objective is None or q.objective == objective)
    ]
