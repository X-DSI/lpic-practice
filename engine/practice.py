"""Practice sessions without a UI: choose questions, grade answers, store results, summarise.

Every question comes from `engine.selection.practice_pool`, so holdout and retired questions are
never served, whatever the mode:

- **objective** — questions from one objective.
- **mixed** — questions spread across objectives in proportion to their weights (Sainte-Laguë
  apportionment over the objectives that have practice questions).
- **weak** — questions from the weakest objectives: never attempted first, then lowest accuracy.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Final, Literal

from engine.matching import is_correct
from engine.model import Bank, Question
from engine.scoring import Score, score
from engine.selection import practice_pool
from engine.store import Accuracy, Store

Mode = Literal["objective", "mixed", "weak"]
MODES: Final[tuple[Mode, ...]] = ("objective", "mixed", "weak")
DEFAULT_COUNT: Final = 10

# Weak areas: objectives below this accuracy (or never attempted) are weak; drills use the
# WEAK_OBJECTIVES weakest of them, topped up from the next weakest if they run out of questions.
WEAK_THRESHOLD: Final = 0.8
WEAK_OBJECTIVES: Final = 3


def _by_objective(bank: Bank) -> dict[str, list[Question]]:
    pools: dict[str, list[Question]] = {}
    for q in practice_pool(bank):
        pools.setdefault(q.objective, []).append(q)
    return pools


def apportion(weights: Mapping[str, int], available: Mapping[str, int], count: int) -> dict[str, int]:
    """Split `count` across objectives in proportion to `weights`, never beyond `available`.

    Sainte-Laguë: each next question goes to the objective with the highest weight / (2n + 1),
    where n is how many it has so far; ties go to the lower objective ID. When `count` equals the
    total weight and every objective has enough questions, each gets exactly its weight.
    """
    taken = {o: 0 for o in weights if available.get(o, 0) > 0}
    for _ in range(min(count, sum(available.get(o, 0) for o in taken))):
        open_ = [o for o in sorted(taken) if taken[o] < available[o]]
        best = max(open_, key=lambda o: Fraction(weights[o], 2 * taken[o] + 1))
        taken[best] += 1
    return {o: n for o, n in taken.items() if n}


def _draw(pools: Mapping[str, list[Question]], counts: Mapping[str, int], rng: random.Random) -> list[Question]:
    drawn = [q for o in sorted(counts) for q in rng.sample(pools[o], counts[o])]
    rng.shuffle(drawn)
    return drawn


def select_objective(bank: Bank, objective: str, count: int, rng: random.Random) -> list[Question]:
    pool = practice_pool(bank, objective)
    return rng.sample(pool, min(count, len(pool)))


def select_mixed(bank: Bank, count: int, rng: random.Random) -> list[Question]:
    pools = _by_objective(bank)
    weights = {o.id: o.weight for o in bank.objectives}
    return _draw(pools, apportion(weights, {o: len(qs) for o, qs in pools.items()}, count), rng)


def rank_weak(objectives: Iterable[str], accuracy: Mapping[str, Accuracy]) -> list[str]:
    """Weakest first: never attempted, then lowest accuracy, then fewer attempts, then ID."""

    def key(objective: str) -> tuple[int, float, int, str]:
        acc = accuracy.get(objective)
        if acc is None or acc.total == 0:
            return (0, 0.0, 0, objective)
        return (1, acc.ratio, acc.total, objective)

    return sorted(objectives, key=key)


def weak_objectives(objectives: Iterable[str], accuracy: Mapping[str, Accuracy]) -> list[str]:
    """The objectives a weak-areas drill draws from, weakest first (at most WEAK_OBJECTIVES)."""
    ranked = rank_weak(objectives, accuracy)
    weak = [o for o in ranked if o not in accuracy or accuracy[o].total == 0 or accuracy[o].ratio < WEAK_THRESHOLD]
    # When nothing is below the threshold, the lowest-accuracy objectives are still the best target.
    return (weak or ranked)[:WEAK_OBJECTIVES]


def select_weak(bank: Bank, count: int, accuracy: Mapping[str, Accuracy], rng: random.Random) -> list[Question]:
    pools = _by_objective(bank)
    ranked = rank_weak(pools, accuracy)
    chosen = weak_objectives(pools, accuracy)
    # Top up from the next weakest objectives if the chosen ones can't fill the session.
    for objective in ranked:
        if sum(len(pools[o]) for o in chosen) >= count:
            break
        if objective not in chosen:
            chosen.append(objective)
    equal = {o: 1 for o in chosen}
    return _draw(pools, apportion(equal, {o: len(pools[o]) for o in chosen}, count), rng)


def select(
    bank: Bank,
    mode: Mode,
    count: int = DEFAULT_COUNT,
    *,
    objective: str | None = None,
    accuracy: Mapping[str, Accuracy] | None = None,
    rng: random.Random | None = None,
) -> list[Question]:
    """Questions for one practice session; fewer than `count` if the pool is smaller."""
    if count < 1:
        raise ValueError("count must be at least 1")
    rng = rng or random.Random()
    if mode == "objective":
        if objective is None:
            raise ValueError("objective mode needs an objective")
        return select_objective(bank, objective, count, rng)
    if mode == "mixed":
        return select_mixed(bank, count, rng)
    if mode == "weak":
        return select_weak(bank, count, accuracy or {}, rng)
    raise ValueError(f"unknown mode {mode!r}")


@dataclass(frozen=True)
class Graded:
    question: Question
    response: str | tuple[str, ...]
    correct: bool


@dataclass
class PracticeSession:
    """One drill: grades each answer, stores it at once, and summarises at the end."""

    store: Store
    exam: str
    mode: Mode
    questions: list[Question]
    graded: list[Graded] = field(default_factory=list)
    session_id: int = 0

    def __post_init__(self) -> None:
        if not self.questions:
            raise ValueError("no practice questions to drill")
        self.session_id = self.store.start_session(self.exam, self.mode)

    @property
    def current(self) -> Question | None:
        """The next unanswered question, or None when the session is complete."""
        return self.questions[len(self.graded)] if len(self.graded) < len(self.questions) else None

    def answer(self, response: str | Iterable[str], time_taken_ms: int) -> Graded:
        question = self.current
        if question is None:
            raise RuntimeError("the session is already complete")
        response = response if isinstance(response, str) else tuple(sorted(response))
        result = Graded(question, response, is_correct(question, response))
        self.store.record_answer(self.session_id, question.id, response, result.correct, time_taken_ms)
        self.graded.append(result)
        return result

    def finish(self) -> Score | None:
        """Close the session and score what was answered; None if nothing was answered."""
        self.store.finish_session(self.session_id)
        return score((g.question, g.correct) for g in self.graded) if self.graded else None
