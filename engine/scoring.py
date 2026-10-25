"""Turn graded results into LPI-style scores (proposed LPI-style scoring ADR).

Every item counts the same, so raw = correct ÷ questions. The scaled score is an *estimate* on
LPI's 200–800 scale, mapped piecewise-linearly through the pass point `PASS_POINT`:

- raw ≤ P: scaled = 200 + 300 × raw / P
- raw > P: scaled = 500 + 300 × (raw − P) / (1 − P)

All arithmetic is exact (`Fraction`). The scaled score is rounded half up, and a result below the
pass point is capped at 499, so `scaled >= 500` and `likely_pass` always agree.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Final

from engine.model import Question

# Our assumption, not LPI's published number: deliberately above the 50% a linear mapping implies.
PASS_POINT: Final = Fraction(13, 20)  # 0.65

SCALE_MIN: Final = 200
SCALE_PASS: Final = 500
SCALE_MAX: Final = 800


@dataclass
class Tally:
    correct: int = 0
    total: int = 0


@dataclass
class Score:
    correct: int
    total: int
    scaled: int
    likely_pass: bool
    by_objective: dict[str, Tally] = field(default_factory=dict)
    by_topic: dict[str, Tally] = field(default_factory=dict)

    @property
    def raw(self) -> Fraction:
        return Fraction(self.correct, self.total)

    @property
    def percent(self) -> float:
        """Raw score as a percentage; always show it next to the scaled estimate."""
        return float(self.raw * 100)


def is_pass(correct: int, total: int) -> bool:
    return Fraction(correct, total) >= PASS_POINT


def scaled_score(correct: int, total: int) -> int:
    """Estimated LPI scaled score (200–800) for `correct` out of `total`."""
    if total <= 0 or not 0 <= correct <= total:
        raise ValueError(f"need 0 <= correct <= total and total > 0, got {correct}/{total}")
    raw = Fraction(correct, total)
    span = SCALE_PASS - SCALE_MIN, SCALE_MAX - SCALE_PASS
    if raw <= PASS_POINT:
        exact = SCALE_MIN + span[0] * raw / PASS_POINT
    else:
        exact = SCALE_PASS + span[1] * (raw - PASS_POINT) / (1 - PASS_POINT)
    scaled = math.floor(exact + Fraction(1, 2))
    if raw < PASS_POINT:
        scaled = min(scaled, SCALE_PASS - 1)
    return scaled


def score(results: Iterable[tuple[Question, bool]]) -> Score:
    """Score `(question, correct)` pairs, with breakdowns by objective and by topic."""
    by_objective: dict[str, Tally] = {}
    by_topic: dict[str, Tally] = {}
    correct = total = 0
    for question, ok in results:
        for key, tallies in ((question.objective, by_objective), (question.topic, by_topic)):
            tally = tallies.setdefault(key, Tally())
            tally.total += 1
            tally.correct += int(ok)
        total += 1
        correct += int(ok)
    if total == 0:
        raise ValueError("cannot score an empty set of results")
    return Score(
        correct=correct,
        total=total,
        scaled=scaled_score(correct, total),
        likely_pass=is_pass(correct, total),
        by_objective=dict(sorted(by_objective.items())),
        by_topic=dict(sorted(by_topic.items())),
    )
