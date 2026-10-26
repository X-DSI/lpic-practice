from __future__ import annotations

import re
import shutil
from collections import Counter
from pathlib import Path

import pytest
import yaml
from holdout_bank import HOLDOUT_WEIGHTS, write_holdout_bank

from engine.assemble import DIFFICULTY_MIX, TOLERANCE, AssemblyError, assemble, level_split, main
from engine.loader import load_exam
from engine.model import Bank, Objective, Question, Topic
from engine.validation import MOCK_READY_STATUSES, validate

ROOT = Path(__file__).resolve().parent.parent


def run(content: Path, *args: str) -> int:
    return main(["101", "--content-dir", str(content), *args])


def mock_files(content: Path) -> list[Path]:
    mocks = content / "101" / "mocks"
    return sorted(mocks.glob("*.yaml")) if mocks.exists() else []


# --- the difficulty table


def test_difficulty_table_equals_the_rubric() -> None:
    text = (ROOT / "docs" / "difficulty-rubric.md").read_text(encoding="utf-8")
    section = text[text.index("## Difficulty mix per mock exam") :]
    rows = re.findall(r"^\| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", section, re.MULTILINE)
    table = {int(r[0]): tuple(int(c) for c in r[1:]) for r in rows}
    assert table == DIFFICULTY_MIX
    totals = re.search(r"^\| \*\*Total\*\* \| (.+) \|$", section, re.MULTILINE).group(1)
    assert [int(c.strip(" *")) for c in totals.split("|")] == [sum(r[i] for r in table.values()) for i in range(5)]


def test_level_split_follows_the_workflow_adr() -> None:
    assert level_split(10) == {1: 2, 2: 2, 3: 2, 4: 2, 5: 2}  # "for weight 1 that is 2 per level"
    assert level_split(600) == {1: 98, 2: 132, 3: 144, 4: 128, 5: 98}
    assert all(sum(level_split(n).values()) == n for n in range(1, 101))


# --- a bank that can fill the mocks


def test_writes_ten_mocks_that_pass_strict_validation(holdout_content: Path) -> None:
    assert run(holdout_content, "--seed", "7") == 0
    files = mock_files(holdout_content)
    assert [f.name for f in files] == [f"mock-{k:02d}.yaml" for k in range(1, 11)]
    errors, _ = validate(holdout_content, strict=True)
    assert errors == []


def test_every_constraint_holds(holdout_content: Path) -> None:
    assert run(holdout_content, "--seed", "7") == 0
    bank = load_exam("101", holdout_content)
    seen: set[str] = set()
    for k, path in enumerate(mock_files(holdout_content), start=1):
        mock = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert mock["id"] == f"101-mock-{k:02d}" and mock["number"] == k
        assert mock["assembly_seed"] == 7
        assert mock["duration_minutes"] == 90
        assert mock["difficulty_mix"] == {str(lv): DIFFICULTY_MIX[k][lv - 1] for lv in range(1, 6)}

        questions = [bank.question(qid) for qid in mock["questions"]]
        assert len(questions) == len(set(mock["questions"])) == 60
        assert Counter(q.objective for q in questions) == Counter(HOLDOUT_WEIGHTS)
        for q in questions:
            assert q.pool == "holdout" and not q.retired and q.review_status in MOCK_READY_STATUSES
        levels = Counter(q.difficulty for q in questions)
        for lv in range(1, 6):
            assert abs(levels[lv] - DIFFICULTY_MIX[k][lv - 1]) <= TOLERANCE, (k, lv, levels)

        assert seen.isdisjoint(mock["questions"]), f"mock {k} reuses a question"
        seen.update(mock["questions"])
        # Not grouped by objective: the first ten questions span several objectives.
        assert len({q.objective for q in questions[:10]}) > 3


def test_same_seed_gives_byte_identical_files(tmp_path: Path) -> None:
    first = write_holdout_bank(tmp_path / "a")
    second = write_holdout_bank(tmp_path / "b")
    assert run(first, "--seed", "3") == 0
    assert run(second, "--seed", "3") == 0
    assert [f.read_bytes() for f in mock_files(first)] == [f.read_bytes() for f in mock_files(second)]
    # Re-assembling over existing mocks gives the same files again.
    before = [f.read_bytes() for f in mock_files(first)]
    assert run(first, "--seed", "3") == 0
    assert [f.read_bytes() for f in mock_files(first)] == before


def test_a_different_seed_gives_different_mocks(tmp_path: Path) -> None:
    first = write_holdout_bank(tmp_path / "a")
    second = write_holdout_bank(tmp_path / "b")
    assert run(first, "--seed", "1") == 0
    assert run(second, "--seed", "2") == 0
    assert [f.read_bytes() for f in mock_files(first)] != [f.read_bytes() for f in mock_files(second)]


def test_default_seed(holdout_content: Path) -> None:
    assert run(holdout_content) == 0
    assert yaml.safe_load(mock_files(holdout_content)[0].read_text(encoding="utf-8"))["assembly_seed"] == 1


def test_exact_adr_split_without_surplus_assembles(tmp_path: Path) -> None:
    content = write_holdout_bank(tmp_path / "content", surplus=False)
    assert run(content) == 0
    errors, _ = validate(content, strict=True)
    assert errors == []


@pytest.mark.parametrize("exam", ["101", "102"])
def test_the_real_exam_weights_with_the_adr_split_can_be_assembled(tmp_path: Path, exam: str) -> None:
    # The escalation check in the handoff: a bank following the workflow ADR's per-objective split
    # (10 × weight, levels split like the rubric) must fit the table within ±2. Only the weights are
    # taken from the real objectives; the questions are synthetic.
    real = yaml.safe_load((ROOT / "content" / exam / "objectives.yaml").read_text(encoding="utf-8"))
    weights = {o["id"]: o["weight"] for t in real["topics"] for o in t["objectives"]}
    content = write_holdout_bank(tmp_path / "content", surplus=False, weights=weights)
    assert run(content) == 0


# --- banks that cannot


def test_objective_shortfall_writes_nothing(holdout_content: Path, capsys) -> None:
    path = holdout_content / "101" / "questions" / "101.3.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["questions"] = doc["questions"][:20]  # 30 eligible needed for weight 3
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    assert run(holdout_content) == 1
    assert mock_files(holdout_content) == []
    out = capsys.readouterr().out
    assert "nothing written" in out
    assert "objective 101.3: 20 eligible holdout question(s)" in out and "needs 30" in out


def test_level_shortfall_names_the_level(tmp_path: Path, capsys) -> None:
    content = write_holdout_bank(tmp_path / "content", surplus=False, split=lambda n: {1: n, 2: 0, 3: 0, 4: 0, 5: 0})
    assert run(content) == 1
    assert mock_files(content) == []
    out = capsys.readouterr().out
    assert "difficulty 5: 0 eligible holdout question(s); the mocks need at least 84" in out


def test_ineligible_questions_do_not_count(holdout_content: Path, capsys) -> None:
    # Demote every eligible 101.1 question but one to draft: the surplus draft/pass1/retired/practice
    # questions must not make up the difference.
    path = holdout_content / "101" / "questions" / "101.1.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for q in doc["questions"]:
        if q["id"] != "101-101.1-0001":
            q["review"]["status"] = "draft" if q["pool"] == "holdout" else q["review"]["status"]
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    assert run(holdout_content) == 1
    assert "objective 101.1: 1 eligible holdout question(s)" in capsys.readouterr().out


def test_an_infeasible_difficulty_mix_is_reported() -> None:
    # Enough questions at every level for the lower bounds, but 130 at level 1 with nothing spare:
    # the mocks can take at most 118 (98 + 10 × 2), so some mock must be over.
    objectives = tuple(Objective(f"101.{i}", "Fixture", 10, 1) for i in range(1, 7))
    totals = {1: 130, 2: 120, 3: 130, 4: 110, 5: 110}
    levels = [lv for lv, n in totals.items() for _ in range(n)]
    questions = [
        Question(
            f"101-{objectives[i % 6].id}-{i:04d}",
            "fill_in",
            lv,
            "holdout",
            objectives[i % 6].id,
            "Synthetic.",
            "x",
            "pass2",
        )
        for i, lv in enumerate(levels)
    ]  # dealt round-robin: exactly 100 per objective
    bank = Bank("101", None, "LPIC-1", (Topic("101", "Fixture", objectives),), tuple(questions), ())
    with pytest.raises(AssemblyError) as exc:
        assemble(bank)
    assert any(
        re.match(r"mock \d\d: difficulty 1 would have \d+ question\(s\), target \d+ \(±2\)", p)
        for p in exc.value.problems
    )


def test_the_real_101_bank_fills_ten_mocks(tmp_path: Path) -> None:
    content = tmp_path / "content"
    shutil.copytree(ROOT / "content", content)
    assert main(["101", "--content-dir", str(content)]) == 0
    assert len(mock_files(content)) == 10
    errors, _ = validate(content, strict=True)
    assert errors == []


def test_the_real_102_bank_today_is_too_small(tmp_path: Path, capsys) -> None:
    content = tmp_path / "content"
    shutil.copytree(ROOT / "content", content)
    before = sorted(p.relative_to(content) for p in content.rglob("*"))
    assert main(["102", "--content-dir", str(content)]) == 1
    assert sorted(p.relative_to(content) for p in content.rglob("*")) == before
    out = capsys.readouterr().out
    assert "nothing written" in out
    # Which objectives are short changes as the bank grows, so check the shape of the report
    # rather than naming one. Remove this test once the 102 bank can fill all 10 mocks.
    shortfalls = re.findall(r"objective (\d{3}\.\d+): (\d+) eligible holdout question\(s\) .*?; needs (\d+)", out)
    assert shortfalls, out
    assert all(int(have) < int(need) for _, have, need in shortfalls), out


def test_invalid_content_writes_nothing(holdout_content: Path, capsys) -> None:
    path = holdout_content / "101" / "objectives.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("weight: 10", "weight: 9", 1), encoding="utf-8")
    assert run(holdout_content) == 1
    assert mock_files(holdout_content) == []
    assert "content is invalid" in capsys.readouterr().out


def test_unknown_exam(holdout_content: Path, capsys) -> None:
    assert main(["202", "--content-dir", str(holdout_content)]) == 1
    assert "no objectives.yaml" in capsys.readouterr().out
