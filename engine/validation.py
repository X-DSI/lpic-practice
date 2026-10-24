"""Content validation: JSON Schemas plus the semantic rules in the ADRs on content format and
mock exam composition (docs/adr/2026-10-22-*.md).

`validate()` returns a list of error strings; `tools/validate.py` is the command-line wrapper.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"
CONTENT_DIR = REPO_ROOT / "content"
EXAMS = ("101", "102", "201", "202")
EXAM_TOTAL_WEIGHT = 60
MIX_TOLERANCE = 2  # mock-exam-composition ADR: assembler may deviate by at most ±2 per level
EXAMPLE_ID_FLOOR = 9000


def load_schema(name: str) -> Draft202012Validator:
    with open(SCHEMA_DIR / name, encoding="utf-8") as fh:
        schema = json.load(fh)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


VALIDATORS = {
    "objectives": load_schema("objectives.schema.json"),
    "questions": load_schema("question-file.schema.json"),
    "mock": load_schema("mock-exam.schema.json"),
}


class Report:
    """Collects errors, naming each file relative to `root` (the directory holding `content/`)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.errors: list[str] = []

    def rel(self, path: Path) -> Path:
        return path.relative_to(self.root)

    def error(self, path: Path, msg: str) -> None:
        self.errors.append(f"{self.rel(path)}: {msg}")


def load_yaml(path: Path, report: Report):
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        report.error(path, f"YAML parse error: {exc}")
        return None


def schema_check(kind: str, data, path: Path, report: Report) -> bool:
    errs = sorted(VALIDATORS[kind].iter_errors(data), key=lambda e: [str(p) for p in e.absolute_path])
    for e in errs:
        parts = list(e.absolute_path)
        loc = "/".join(str(p) for p in parts) or "(root)"
        # Name the question by its id rather than its list index, when possible.
        if kind == "questions" and len(parts) >= 2 and parts[0] == "questions":
            q = data["questions"][parts[1]]
            qid = q.get("id", f"#{parts[1]}") if isinstance(q, dict) else f"#{parts[1]}"
            loc = "/".join([qid] + [str(p) for p in parts[2:]]) or qid
        if e.validator == "not":
            msg = "fields not allowed for this question type " + _type_hint(e.instance)
        elif e.validator == "additionalProperties":
            msg = e.message
        elif e.validator in ("minItems", "maxItems"):
            limit = "at least" if e.validator == "minItems" else "at most"
            msg = f"has {len(e.instance)} item(s); needs {limit} {e.validator_value}"
        else:
            msg = e.message if len(e.message) <= 120 else e.message[:117] + "..."
        report.error(path, f"schema: {loc}: {msg}")
    return not errs


def _type_hint(instance) -> str:
    rules = {
        "single_choice": "(single_choice cannot have fill_in or select_count)",
        "multi_choice": "(multi_choice cannot have fill_in)",
        "fill_in": "(fill_in cannot have options, answer or select_count)",
    }
    return rules.get(instance.get("type"), "") if isinstance(instance, dict) else ""


def classify(path: Path, content_dir: Path) -> str | None:
    rel = path.relative_to(content_dir).parts
    if path.name == "objectives.yaml":
        return "objectives"
    if "mocks" in rel:
        return "mock"
    if "questions" in rel or rel[0] == "examples":
        return "questions"
    return None


# ---------------------------------------------------------------- objectives


def check_objectives(data, path: Path, report: Report) -> dict[str, int]:
    """Return {objective_id: weight} for the exam."""
    weights: dict[str, int] = {}
    if path.parent.name != data["exam"]:
        report.error(path, f"exam '{data['exam']}' does not match directory '{path.parent.name}'")
    for topic in data["topics"]:
        for obj in topic["objectives"]:
            if not obj["id"].startswith(topic["id"] + "."):
                report.error(path, f"objective {obj['id']} is listed under topic {topic['id']}")
            if obj["id"] in weights:
                report.error(path, f"duplicate objective {obj['id']}")
            weights[obj["id"]] = obj["weight"]
    total = sum(weights.values())
    expected = data["exam_format"]["questions"]
    if total != EXAM_TOTAL_WEIGHT or total != expected:
        report.error(path, f"objective weights sum to {total}; expected {EXAM_TOTAL_WEIGHT}")
    return weights


# ----------------------------------------------------------------- questions


def check_question_file(data, path: Path, report: Report, is_example: bool) -> list[dict]:
    if not is_example:
        if path.parent.parent.name != data["exam"]:
            report.error(path, f"exam '{data['exam']}' does not match directory '{path.parent.parent.name}'")
    if path.stem != data["objective"]:
        report.error(path, f"objective '{data['objective']}' does not match file name '{path.stem}'")

    prefix = f"{data['exam']}-{data['objective']}-"
    for q in data["questions"]:
        qid = q["id"]
        where = f"question {qid}"
        if not qid.startswith(prefix):
            report.error(path, f"{where}: id must start with '{prefix}'")
        number = int(qid.rsplit("-", 1)[1])
        if is_example and number < EXAMPLE_ID_FLOOR:
            report.error(path, f"{where}: example IDs must be >= {EXAMPLE_ID_FLOOR}")
        if not is_example and number >= EXAMPLE_ID_FLOOR:
            report.error(path, f"{where}: IDs >= {EXAMPLE_ID_FLOOR} are reserved for examples")
        if q["source"]["objective"] != data["objective"]:
            report.error(path, f"{where}: source.objective differs from file objective")

        if q["type"] in ("single_choice", "multi_choice"):
            opt_ids = [o["id"] for o in q["options"]]
            dupes = [i for i, n in Counter(opt_ids).items() if n > 1]
            if dupes:
                report.error(path, f"{where}: duplicate option ids {dupes}")
            missing = [a for a in q["answer"] if a not in opt_ids]
            if missing:
                report.error(path, f"{where}: answer refers to missing options {missing}")
            if q["type"] == "multi_choice" and q["select_count"] != len(q["answer"]):
                report.error(path, f"{where}: select_count {q['select_count']} != {len(q['answer'])} answers")
            texts = [o["text"].strip() for o in q["options"]]
            if len(set(texts)) != len(texts):
                report.error(path, f"{where}: two options have identical text")

        if q["type"] == "fill_in" and q["fill_in"]["match"] == "regex":
            for pattern in q["fill_in"]["accepted"]:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    report.error(path, f"{where}: invalid regex {pattern!r}: {exc}")

        if q["review"]["status"] == "approved":
            stages = {h["stage"] for h in q["review"].get("history", []) if h["result"] != "rejected"}
            for needed in ("pass1", "pass2", "human"):
                if needed not in stages:
                    report.error(path, f"{where}: approved but review history lacks '{needed}'")
    return data["questions"]


# --------------------------------------------------------------------- mocks


def check_mock(data, path: Path, report: Report, bank: dict[str, dict], weights: dict[str, int], strict: bool) -> None:
    expected_id = f"{data['exam']}-mock-{data['number']:02d}"
    if data["id"] != expected_id:
        report.error(path, f"id '{data['id']}' should be '{expected_id}'")
    if path.stem != f"mock-{data['number']:02d}":
        report.error(path, f"file name should be mock-{data['number']:02d}.yaml")

    mix = {int(k): v for k, v in data["difficulty_mix"].items()}
    if sum(mix.values()) != len(data["questions"]):
        report.error(path, f"difficulty_mix sums to {sum(mix.values())}, not {len(data['questions'])}")

    per_objective: Counter[str] = Counter()
    per_level: Counter[int] = Counter()
    for qid in data["questions"]:
        q = bank.get(qid)
        if q is None:
            report.error(path, f"{qid}: not found in the {data['exam']} question bank")
            continue
        if q["pool"] != "holdout":
            report.error(path, f"{qid}: mock questions must have pool 'holdout'")
        if q.get("retired"):
            report.error(path, f"{qid}: question is retired")
        if strict and q["review"]["status"] != "approved":
            report.error(path, f"{qid}: not approved (status '{q['review']['status']}')")
        per_objective[q["source"]["objective"]] += 1
        per_level[q["difficulty"]] += 1

    for obj, w in weights.items():
        if per_objective[obj] != w:
            report.error(path, f"objective {obj}: {per_objective[obj]} questions, weight is {w}")
    for level in range(1, 6):
        if abs(per_level[level] - mix[level]) > MIX_TOLERANCE:
            report.error(
                path, f"difficulty {level}: {per_level[level]} questions, target {mix[level]} (±{MIX_TOLERANCE})"
            )


# ------------------------------------------------------------------ validate


def validate(content_dir: Path = CONTENT_DIR, strict: bool = False) -> tuple[list[str], str]:
    """Validate everything under `content_dir`.

    Returns `(errors, summary)`: the list of problems (empty when valid) and a one-line summary of
    what was checked.
    """
    content_dir = content_dir.resolve()
    report = Report(content_dir.parent)
    all_files = sorted(content_dir.rglob("*.yaml"))

    weights: dict[str, dict[str, int]] = {}
    banks: dict[str, dict[str, dict]] = {e: {} for e in EXAMS}
    seen_ids: dict[str, Path] = {}
    mocks: list[tuple[Path, dict]] = []
    checked = 0

    # Objectives and questions always load fully, so mocks and ID uniqueness can be checked.
    for path in all_files:
        kind = classify(path, content_dir)
        if kind is None:
            report.error(path, "unrecognised content location")
            continue
        data = load_yaml(path, report)
        if data is None:
            continue
        if kind == "mock":
            mocks.append((path, data))
            continue
        if not schema_check(kind, data, path, report):
            continue
        checked += 1
        if kind == "objectives":
            weights[data["exam"]] = check_objectives(data, path, report)
        else:
            is_example = path.relative_to(content_dir).parts[0] == "examples"
            for q in check_question_file(data, path, report, is_example):
                if q["id"] in seen_ids:
                    report.error(path, f"duplicate id {q['id']} (also in {report.rel(seen_ids[q['id']])})")
                seen_ids[q["id"]] = path
                if not is_example:
                    banks[data["exam"]][q["id"]] = q

    for path, data in mocks:
        checked += 1
        if not schema_check("mock", data, path, report):
            continue
        exam = data["exam"]
        if exam not in weights:
            report.error(path, f"no objectives.yaml found for exam {exam}")
            continue
        check_mock(data, path, report, banks[exam], weights[exam], strict)

    n_questions = sum(len(b) for b in banks.values())
    summary = f"{checked} file(s) valid; {n_questions} bank question(s), {len(seen_ids) - n_questions} example(s)"
    return report.errors, summary
