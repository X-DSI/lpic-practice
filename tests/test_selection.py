from __future__ import annotations

import pytest

from engine.model import Bank
from engine.selection import practice_pool


def test_practice_pool_excludes_holdout_and_retired(bank_101: Bank) -> None:
    pool = practice_pool(bank_101)
    assert [q.id for q in pool] == ["101-101.1-0001", "101-101.1-0002", "101-101.1-0003", "101-101.2-0001"]
    assert all(q.pool == "practice" and not q.retired for q in pool)


def test_the_fixture_has_holdout_and_retired_questions_to_exclude(bank_101: Bank) -> None:
    assert any(q.pool == "holdout" for q in bank_101.questions)
    assert any(q.retired for q in bank_101.questions)


def test_practice_pool_by_objective(bank_101: Bank) -> None:
    assert [q.id for q in practice_pool(bank_101, "101.2")] == ["101-101.2-0001"]
    assert practice_pool(bank_101, "101.3") == []


def test_practice_pool_rejects_unknown_objective(bank_101: Bank) -> None:
    with pytest.raises(ValueError):
        practice_pool(bank_101, "999.9")
