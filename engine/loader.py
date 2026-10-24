"""Read one exam's content from `content/<exam>/`.

The loader does not validate: run `engine.validation.validate()` first (the build does), since it
assumes schema-valid files. `content/examples/` is never part of an exam bank.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from engine.model import Bank, FillIn, MockExam, Objective, Option, Question, Topic
from engine.validation import CONTENT_DIR


def _read(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def exams(content_dir: Path = CONTENT_DIR) -> list[str]:
    """Exam IDs that have an `objectives.yaml`, sorted."""
    return sorted(p.parent.name for p in content_dir.glob("*/objectives.yaml"))


def read_exam_data(exam: str, content_dir: Path = CONTENT_DIR) -> dict[str, Any]:
    """The exam's content as plain data: objectives, questions sorted by ID, mocks sorted by number."""
    exam_dir = content_dir / exam
    questions = [q for path in sorted(exam_dir.glob("questions/*.yaml")) for q in _read(path)["questions"]]
    mocks = [_read(path) for path in sorted(exam_dir.glob("mocks/*.yaml"))]
    return {
        "objectives": _read(exam_dir / "objectives.yaml"),
        "questions": sorted(questions, key=lambda q: q["id"]),
        "mocks": sorted(mocks, key=lambda m: m["number"]),
    }


def question_from_data(q: dict[str, Any]) -> Question:
    fill_in = q.get("fill_in")
    return Question(
        id=q["id"],
        type=q["type"],
        difficulty=q["difficulty"],
        pool=q["pool"],
        objective=q["source"]["objective"],
        stem=q["stem"],
        explanation=q["explanation"],
        review_status=q["review"]["status"],
        options=tuple(Option(o["id"], o["text"], o.get("rationale")) for o in q.get("options", [])),
        answer=tuple(q.get("answer", [])),
        select_count=q.get("select_count"),
        fill_in=(
            FillIn(tuple(fill_in["accepted"]), fill_in["match"], fill_in.get("case_sensitive", True))
            if fill_in
            else None
        ),
        exhibit=q.get("exhibit"),
        tags=tuple(q.get("tags", [])),
        retired=q.get("retired", False),
    )


def bank_from_data(exam: str, data: dict[str, Any]) -> Bank:
    objectives = data["objectives"]
    topics = tuple(
        Topic(
            t["id"],
            t["title"],
            tuple(Objective(o["id"], o["title"], o["weight"], o["lessons"]) for o in t["objectives"]),
        )
        for t in objectives["topics"]
    )
    mocks = tuple(MockExam(m["id"], m["number"], m["duration_minutes"], tuple(m["questions"])) for m in data["mocks"])
    return Bank(
        exam=exam,
        exam_code=objectives.get("exam_code"),
        certification=objectives["certification"],
        topics=topics,
        questions=tuple(question_from_data(q) for q in data["questions"]),
        mocks=mocks,
    )


def load_exam(exam: str, content_dir: Path = CONTENT_DIR) -> Bank:
    """Load one exam's bank as typed objects."""
    return bank_from_data(exam, read_exam_data(exam, content_dir))
