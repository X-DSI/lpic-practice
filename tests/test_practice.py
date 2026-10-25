from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

import pytest

from engine.model import Bank, FillIn, Objective, Question, Topic
from engine.practice import WEAK_OBJECTIVES, PracticeSession, apportion, select, weak_objectives
from engine.store import Accuracy, Store

WEIGHTS = {"101.1": 1, "101.2": 2, "101.3": 3, "103.1": 4}


def question(objective: str, n: int, pool: str = "practice", retired: bool = False) -> Question:
    return Question(
        id=f"101-{objective}-{n:04d}",
        type="fill_in",
        difficulty=1,
        pool=pool,  # type: ignore[arg-type]
        objective=objective,
        stem="Synthetic question.",
        explanation="Synthetic explanation.",
        review_status="pass2",
        fill_in=FillIn(("x",), "exact"),
        retired=retired,
    )


def make_bank(practice_per_objective: int = 20) -> Bank:
    """Every objective has practice questions plus holdout and retired ones that must never be served."""
    questions = []
    for objective in WEIGHTS:
        questions += [question(objective, i) for i in range(practice_per_objective)]
        questions += [question(objective, 100 + i, pool="holdout") for i in range(10)]
        questions += [question(objective, 200 + i, retired=True) for i in range(5)]
    topics = (
        Topic("101", "Synthetic topic", tuple(Objective(o, o, w, 1) for o, w in WEIGHTS.items() if o < "102")),
        Topic("103", "Synthetic topic", (Objective("103.1", "103.1", WEIGHTS["103.1"], 1),)),
    )
    return Bank("101", "fixture", "LPIC-1", topics, tuple(sorted(questions, key=lambda q: q.id)), ())


@pytest.fixture
def bank() -> Bank:
    return make_bank()


# --- never holdout or retired


@pytest.mark.parametrize("mode", ["objective", "mixed", "weak"])
@pytest.mark.parametrize("seed", range(20))
def test_no_holdout_or_retired_in_any_mode(bank: Bank, mode: str, seed: int) -> None:
    accuracy = {"101.3": Accuracy(1, 10)} if seed % 2 else {}
    questions = select(
        bank,
        mode,
        200,
        objective="101.2",
        accuracy=accuracy,
        rng=random.Random(seed),  # type: ignore[arg-type]
    )
    assert questions
    assert all(q.pool == "practice" and not q.retired for q in questions)
    assert len({q.id for q in questions}) == len(questions)


def test_objective_mode(bank: Bank) -> None:
    questions = select(bank, "objective", 5, objective="101.3", rng=random.Random(1))
    assert len(questions) == 5
    assert {q.objective for q in questions} == {"101.3"}
    # Asking for more than the pool holds returns the whole practice pool.
    assert len(select(bank, "objective", 500, objective="101.3", rng=random.Random(1))) == 20


def test_objective_mode_needs_an_objective(bank: Bank) -> None:
    with pytest.raises(ValueError):
        select(bank, "objective", 5)


# --- mixed: proportional to weights


def test_apportion_matches_weights_exactly_when_count_is_the_total_weight() -> None:
    assert apportion(WEIGHTS, {o: 50 for o in WEIGHTS}, 10) == WEIGHTS
    assert apportion(WEIGHTS, {o: 50 for o in WEIGHTS}, 20) == {o: 2 * w for o, w in WEIGHTS.items()}


def test_apportion_respects_availability() -> None:
    assert apportion(WEIGHTS, {"101.1": 50, "101.2": 50, "101.3": 50, "103.1": 1}, 10) == {
        "101.1": 2,
        "101.2": 3,
        "101.3": 4,
        "103.1": 1,
    }
    assert apportion(WEIGHTS, {"101.3": 2}, 10) == {"101.3": 2}


@pytest.mark.parametrize("count", [5, 10, 17, 40])
def test_mixed_mode_draws_in_proportion_to_weights(bank: Bank, count: int) -> None:
    questions = select(bank, "mixed", count, rng=random.Random(count))
    assert len(questions) == count
    per_objective = Counter(q.objective for q in questions)
    total_weight = sum(WEIGHTS.values())
    for objective, weight in WEIGHTS.items():
        assert abs(per_objective[objective] - count * weight / total_weight) < 1


def test_mixed_mode_is_shuffled_but_reproducible(bank: Bank) -> None:
    first = select(bank, "mixed", 10, rng=random.Random(7))
    assert [q.id for q in first] == [q.id for q in select(bank, "mixed", 10, rng=random.Random(7))]
    assert [q.objective for q in first] != sorted(q.objective for q in first)


# --- weak areas


def test_weak_areas_prefer_unattempted_then_lowest_accuracy(bank: Bank) -> None:
    accuracy = {"101.1": Accuracy(9, 10), "101.2": Accuracy(2, 10), "101.3": Accuracy(5, 10)}
    assert weak_objectives(WEIGHTS, accuracy) == ["103.1", "101.2", "101.3"]
    questions = select(bank, "weak", 9, accuracy=accuracy, rng=random.Random(0))
    assert Counter(q.objective for q in questions) == {"103.1": 3, "101.2": 3, "101.3": 3}


def test_weak_areas_skip_strong_objectives(bank: Bank) -> None:
    accuracy = {"101.1": Accuracy(10, 10), "101.2": Accuracy(9, 10), "101.3": Accuracy(3, 10), "103.1": Accuracy(8, 8)}
    assert weak_objectives(WEIGHTS, accuracy) == ["101.3"]
    assert {q.objective for q in select(bank, "weak", 10, accuracy=accuracy, rng=random.Random(0))} == {"101.3"}


def test_weak_areas_with_no_history_treat_every_objective_as_weak(bank: Bank) -> None:
    assert len(weak_objectives(WEIGHTS, {})) == WEAK_OBJECTIVES


def test_weak_areas_when_all_strong_still_target_the_lowest(bank: Bank) -> None:
    accuracy = {o: Accuracy(10, 10) for o in WEIGHTS} | {"101.2": Accuracy(9, 10)}
    assert weak_objectives(WEIGHTS, accuracy)[0] == "101.2"


def test_weak_areas_top_up_from_the_next_weakest(bank: Bank) -> None:
    small = make_bank(practice_per_objective=2)
    accuracy = {"101.1": Accuracy(0, 4), "101.2": Accuracy(9, 10), "101.3": Accuracy(10, 10), "103.1": Accuracy(10, 10)}
    questions = select(small, "weak", 4, accuracy=accuracy, rng=random.Random(0))
    assert Counter(q.objective for q in questions) == {"101.1": 2, "101.2": 2}


# --- sessions


def test_session_grades_stores_and_scores(bank: Bank, tmp_path: Path) -> None:
    questions = select(bank, "mixed", 4, rng=random.Random(3))
    with Store(tmp_path / "db.sqlite") as store:
        session = PracticeSession(store, "101", "mixed", questions)
        for i, q in enumerate(questions):
            assert session.current == q
            result = session.answer("x" if i % 2 == 0 else "wrong", 1000)
            assert result.correct is (i % 2 == 0)
        assert session.current is None
        with pytest.raises(RuntimeError):
            session.answer("x", 1)
        score = session.finish()
        assert score is not None and (score.correct, score.total) == (2, 4)
        assert sum(t.total for t in score.by_objective.values()) == 4
        assert [a["question_id"] for a in store.answers(session.session_id)] == [q.id for q in questions]


def test_session_finished_early_without_answers(bank: Bank, tmp_path: Path) -> None:
    with Store(tmp_path / "db.sqlite") as store:
        session = PracticeSession(store, "101", "objective", select(bank, "objective", 3, objective="101.1"))
        assert session.finish() is None


def test_session_needs_questions(tmp_path: Path) -> None:
    with Store(tmp_path / "db.sqlite") as store, pytest.raises(ValueError):
        PracticeSession(store, "101", "mixed", [])


def test_engine_does_not_import_textual() -> None:
    import subprocess
    import sys

    code = (
        "import sys, pkgutil, importlib, engine\n"
        "for m in pkgutil.iter_modules(engine.__path__): importlib.import_module(f'engine.{m.name}')\n"
        "assert not any(name.split('.')[0] == 'textual' for name in sys.modules), 'engine imported textual'\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
