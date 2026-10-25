from __future__ import annotations

from pathlib import Path

from engine.loader import exams
from engine.model import Bank, FillIn, Option

FIXTURE_CONTENT = Path(__file__).parent / "fixtures" / "content"


def test_exams_found() -> None:
    assert exams(FIXTURE_CONTENT) == ["101", "102"]


def test_load_exam(bank_101: Bank) -> None:
    assert bank_101.exam == "101"
    assert [t.id for t in bank_101.topics] == ["101", "103"]
    assert sum(o.weight for o in bank_101.objectives) == 60
    assert [q.id for q in bank_101.questions] == sorted(q.id for q in bank_101.questions)
    assert bank_101.mocks == ()

    single = bank_101.question("101-101.1-0001")
    assert single.answer == ("b",)
    assert single.options[0] == Option("a", "Fixture option A")
    assert single.topic == "101"

    regex = bank_101.question("101-101.2-0001")
    assert regex.fill_in == FillIn((r"ls\s+-i", r"ls\s+--inode"), "regex", True)
    assert bank_101.question("101-101.1-0005").retired
