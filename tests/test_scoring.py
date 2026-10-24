from __future__ import annotations

from fractions import Fraction

import pytest

from engine.model import Bank, Question
from engine.scoring import PASS_POINT, is_pass, scaled_score, score


def test_pass_point_is_065() -> None:
    assert PASS_POINT == Fraction(65, 100)


@pytest.mark.parametrize(
    ("correct", "scaled", "passes"),
    [(0, 200, False), (38, 492, False), (39, 500, True), (40, 514, True), (60, 800, True)],
)
def test_scaled_score_out_of_60(correct: int, scaled: int, passes: bool) -> None:
    assert scaled_score(correct, 60) == scaled
    assert is_pass(correct, 60) is passes
    assert (scaled >= 500) is passes


def test_scaled_score_is_monotonic_and_agrees_with_pass_for_many_totals() -> None:
    for total in range(1, 301):
        previous = 199
        for correct in range(total + 1):
            scaled = scaled_score(correct, total)
            assert 200 <= scaled <= 800
            assert scaled >= previous
            assert (scaled >= 500) is is_pass(correct, total), (correct, total)
            previous = scaled


def test_just_below_the_pass_point_never_rounds_up_to_500() -> None:
    # 37/57 = 0.649..., which maps to 499.6 before rounding: still a fail, so it stays below 500.
    assert not is_pass(37, 57)
    assert scaled_score(37, 57) == 499
    assert scaled_score(38, 57) >= 500


@pytest.mark.parametrize(("correct", "total"), [(1, 0), (-1, 60), (61, 60)])
def test_scaled_score_rejects_impossible_counts(correct: int, total: int) -> None:
    with pytest.raises(ValueError):
        scaled_score(correct, total)


def synthetic(objective: str, n: int) -> Question:
    return Question(
        id=f"101-{objective}-{n:04d}",
        type="single_choice",
        difficulty=1,
        pool="holdout",
        objective=objective,
        stem="Synthetic question.",
        explanation="Synthetic explanation.",
        review_status="draft",
    )


def sixty_results(correct: int) -> list[tuple[Question, bool]]:
    """60 synthetic results over six objectives in two topics, the first `correct` of them right."""
    objectives = ["101.1", "101.2", "101.3", "103.1", "103.2", "103.3"]
    questions = [synthetic(objectives[i % 6], i) for i in range(60)]
    return [(q, i < correct) for i, q in enumerate(questions)]


@pytest.mark.parametrize(
    ("correct", "scaled", "passes"), [(0, 200, False), (38, 492, False), (39, 500, True), (60, 800, True)]
)
def test_score_sixty_questions(correct: int, scaled: int, passes: bool) -> None:
    result = score(sixty_results(correct))
    assert (result.correct, result.total) == (correct, 60)
    assert result.raw == Fraction(correct, 60)
    assert result.scaled == scaled
    assert result.likely_pass is passes


def test_breakdowns_add_up_to_totals() -> None:
    result = score(sixty_results(41))
    assert set(result.by_objective) == {"101.1", "101.2", "101.3", "103.1", "103.2", "103.3"}
    assert set(result.by_topic) == {"101", "103"}
    for breakdown in (result.by_objective, result.by_topic):
        assert sum(t.total for t in breakdown.values()) == result.total == 60
        assert sum(t.correct for t in breakdown.values()) == result.correct == 41
    assert result.by_topic["101"].total == 30


def test_score_from_the_fixture_bank(bank_101: Bank) -> None:
    graded = [(q, q.pool == "practice") for q in bank_101.questions]
    result = score(graded)
    assert result.total == len(bank_101.questions) == 7
    assert result.by_objective["101.1"].total == 5
    assert result.by_objective["101.2"].correct == 1
    assert result.percent == pytest.approx(500 / 7)


def test_score_rejects_no_results() -> None:
    with pytest.raises(ValueError):
        score([])
