"""Typed, read-only views of the question bank. Field meanings follow the content-format ADR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

QuestionType = Literal["single_choice", "multi_choice", "fill_in"]
Pool = Literal["practice", "holdout"]
MatchMode = Literal["exact", "normalized", "regex"]


@dataclass(frozen=True)
class Option:
    id: str
    text: str
    rationale: str | None = None


@dataclass(frozen=True)
class FillIn:
    accepted: tuple[str, ...]
    match: MatchMode
    case_sensitive: bool = True


@dataclass(frozen=True)
class Question:
    id: str
    type: QuestionType
    difficulty: int
    pool: Pool
    objective: str
    stem: str
    explanation: str
    review_status: str
    options: tuple[Option, ...] = ()
    answer: tuple[str, ...] = ()
    select_count: int | None = None
    fill_in: FillIn | None = None
    exhibit: str | None = None
    tags: tuple[str, ...] = ()
    retired: bool = False

    @property
    def topic(self) -> str:
        """Topic ID, e.g. "103" for objective "103.4"."""
        return self.objective.split(".", 1)[0]


@dataclass(frozen=True)
class Objective:
    id: str
    title: str
    weight: int
    lessons: int

    @property
    def topic(self) -> str:
        return self.id.split(".", 1)[0]


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    objectives: tuple[Objective, ...]


@dataclass(frozen=True)
class MockExam:
    id: str
    number: int
    duration_minutes: int
    questions: tuple[str, ...]


@dataclass(frozen=True)
class Bank:
    """One exam's objectives, questions and mock manifests."""

    exam: str
    exam_code: str | None
    certification: str
    topics: tuple[Topic, ...]
    questions: tuple[Question, ...]
    mocks: tuple[MockExam, ...]

    @property
    def objectives(self) -> tuple[Objective, ...]:
        return tuple(o for t in self.topics for o in t.objectives)

    def question(self, question_id: str) -> Question:
        for q in self.questions:
            if q.id == question_id:
                return q
        raise KeyError(question_id)
