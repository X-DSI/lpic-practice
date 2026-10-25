"""A synthetic holdout bank for the mock assembler tests (no LPI-derived wording, no example IDs)."""

from __future__ import annotations

from pathlib import Path

import yaml

# Weights for a synthetic exam: varied like the real ones, summing to 60, in two topics.
HOLDOUT_WEIGHTS = {
    "101.1": 1, "101.2": 2, "101.3": 3, "101.4": 4, "101.5": 5, "101.6": 10, "101.7": 10,
    "103.1": 10, "103.2": 5, "103.3": 4, "103.4": 3, "103.5": 2, "103.6": 1,
}  # fmt: skip


def synthetic_question(qid: str, objective: str, difficulty: int, pool: str = "holdout", status: str = "pass2"):
    return {
        "id": qid,
        "type": "fill_in",
        "difficulty": difficulty,
        "pool": pool,
        "stem": "Synthetic holdout question for the assembler.",
        "fill_in": {"accepted": ["fixture"], "match": "exact"},
        "explanation": "Synthetic explanation.",
        "source": {
            "material": "Fixture material",
            "material_version": "2000-01-01",
            "objective": objective,
            "lesson": 1,
        },
        "review": {"status": status},
    }


def write_holdout_bank(content: Path, surplus: bool = True, split=None, weights: dict[str, int] | None = None) -> Path:
    """Write a synthetic exam 101 under `content`: per objective, `10 × weight` eligible holdout
    questions split across levels like the workflow ADR (or by `split(n)`), plus — with `surplus` —
    one spare eligible question and some that must never be picked (draft, pass1, retired,
    practice)."""
    from engine.assemble import level_split

    split = split or level_split
    weights = weights or HOLDOUT_WEIGHTS
    topics = {}
    for objective, weight in weights.items():
        topics.setdefault(objective.split(".")[0], []).append(
            {"id": objective, "title": f"Fixture objective {objective}", "weight": weight, "lessons": 1}
        )
    exam_dir = content / "101"
    (exam_dir / "questions").mkdir(parents=True, exist_ok=True)
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
    for objective, weight in weights.items():
        levels = [lv for lv, c in split(10 * weight).items() for _ in range(c)]
        questions = [synthetic_question(f"101-{objective}-{i + 1:04d}", objective, lv) for i, lv in enumerate(levels)]
        if surplus:
            extra = [
                synthetic_question(f"101-{objective}-0900", objective, 3),
                synthetic_question(f"101-{objective}-0901", objective, 1, status="draft"),
                synthetic_question(f"101-{objective}-0902", objective, 5, status="pass1"),
                {**synthetic_question(f"101-{objective}-0903", objective, 2), "retired": True},
                synthetic_question(f"101-{objective}-0904", objective, 4, pool="practice"),
            ]
            questions += extra
        doc = {"schema_version": 1, "exam": "101", "objective": objective, "questions": questions}
        (exam_dir / "questions" / f"{objective}.yaml").write_text(
            yaml.safe_dump(doc, sort_keys=False), encoding="utf-8"
        )
    return content
