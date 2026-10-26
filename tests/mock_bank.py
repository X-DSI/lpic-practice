"""A synthetic exam 101 with one mock (`101-mock-01`) for the web and mock-session tests.

All three question types, cycling single → multi → fill-in. Every answer key, rationale and
explanation carries an upper-case `SECRET` marker, so a test can scan pages for leaks; fill-in
answers are case-insensitive, so typing the key in lower case is correct without echoing a marker.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from holdout_bank import HOLDOUT_WEIGHTS

MOCK_ID = "101-mock-01"
SECRET = "SECRET"
LEVELS = [1] * 30 + [2] * 20 + [3] * 10  # mock 1's row: 30 / 20 / 10 / 0 / 0


def _question(qid: str, objective: str, difficulty: int, kind: str) -> dict:
    q: dict = {
        "id": qid,
        "type": kind,
        "difficulty": difficulty,
        "pool": "holdout",
        "stem": f"Synthetic {kind} question {qid} for the mock tests.",
        "explanation": f"EXPLANATION-{SECRET} for {qid}.",
        "source": {
            "material": "Fixture material",
            "material_version": "2000-01-01",
            "objective": objective,
            "lesson": 1,
        },
        "review": {"status": "pass2"},
    }
    if kind == "fill_in":
        q["fill_in"] = {"accepted": [f"ACCEPTED-{SECRET}-{qid}"], "match": "exact", "case_sensitive": False}
        return q
    count = 4 if kind == "single_choice" else 5
    q["options"] = [
        {"id": oid, "text": f"Option {oid} of {qid}", "rationale": f"RATIONALE-{SECRET} {oid} {qid}"}
        for oid in "abcde"[:count]
    ]
    q["answer"] = ["b"] if kind == "single_choice" else ["a", "c"]
    if kind == "multi_choice":
        q["select_count"] = 2
    return q


def correct_response(q: dict) -> str | list[str]:
    if q["type"] == "fill_in":
        return q["fill_in"]["accepted"][0].lower()
    return q["answer"][0] if q["type"] == "single_choice" else list(q["answer"])


def wrong_response(q: dict) -> str | list[str]:
    return {"single_choice": "a", "multi_choice": ["a", "b"], "fill_in": "nope"}[q["type"]]


def write_mock_bank(content: Path) -> list[dict]:
    """Write the bank and its one mock under `content`; return the mock's questions in order."""
    kinds = ("single_choice", "multi_choice", "fill_in")
    topics: dict[str, list[dict]] = {}
    for objective, weight in HOLDOUT_WEIGHTS.items():
        topics.setdefault(objective.split(".")[0], []).append(
            {"id": objective, "title": f"Fixture objective {objective}", "weight": weight, "lessons": 1}
        )
    exam_dir = content / "101"
    (exam_dir / "questions").mkdir(parents=True)
    (exam_dir / "mocks").mkdir()
    objectives = {
        "schema_version": 1,
        "exam": "101",
        "certification": "LPIC-1",
        "objectives_version": "1.0",
        "material": {"title": "Fixture material", "version": "2000-01-01"},
        "exam_format": {"questions": 60, "duration_minutes": 90},
        "topics": [{"id": t, "title": f"Fixture topic {t}", "objectives": objs} for t, objs in topics.items()],
    }
    (exam_dir / "objectives.yaml").write_text(yaml.safe_dump(objectives, sort_keys=False), encoding="utf-8")

    questions = []
    for objective, weight in HOLDOUT_WEIGHTS.items():
        batch = [
            _question(
                f"101-{objective}-{i + 1:04d}", objective, LEVELS[len(questions) + i], kinds[(len(questions) + i) % 3]
            )
            for i in range(weight)
        ]
        doc = {"schema_version": 1, "exam": "101", "objective": objective, "questions": batch}
        (exam_dir / "questions" / f"{objective}.yaml").write_text(
            yaml.safe_dump(doc, sort_keys=False), encoding="utf-8"
        )
        questions += batch
    mock = {
        "schema_version": 1,
        "id": MOCK_ID,
        "exam": "101",
        "number": 1,
        "title": "Mock exam 1",
        "duration_minutes": 90,
        "assembly_seed": 1,
        "difficulty_mix": {"1": 30, "2": 20, "3": 10, "4": 0, "5": 0},
        "questions": [q["id"] for q in questions],
    }
    (exam_dir / "mocks" / "mock-01.yaml").write_text(yaml.safe_dump(mock, sort_keys=False), encoding="utf-8")
    return questions
