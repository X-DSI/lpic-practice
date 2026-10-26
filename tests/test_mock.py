"""Mock sessions in the engine, without HTTP."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from mock_bank import MOCK_ID, correct_response, wrong_response

from engine.loader import load_exam
from engine.mock import GRACE, DeadlinePassed, MockError, MockRunner, clean_response, weak_areas
from engine.scoring import Tally, score
from engine.store import Store

START = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self, moment: datetime = START) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, **delta: float) -> None:
        self.moment += timedelta(**delta)


@pytest.fixture
def runner(mock_bank, tmp_path: Path):
    content, _ = mock_bank
    clock = Clock()
    store = Store(tmp_path / "results.sqlite")
    yield MockRunner(store, [load_exam("101", content)], clock=clock), clock
    store.close()


def test_start_creates_a_resumable_session_with_a_draft_per_question(runner, mock_bank) -> None:
    r, _ = runner
    session_id = r.start(MOCK_ID)
    state = r.state(session_id)
    assert state.session.mode == "mock" and state.session.mock_id == MOCK_ID
    assert state.session.started_at == "2026-10-26T09:00:00+00:00"
    assert state.deadline == START + timedelta(minutes=90)
    assert len(state.drafts) == 60 and state.unanswered == 60
    assert r.store.resumable_session(MOCK_ID).id == session_id
    assert r.start(MOCK_ID) == session_id  # starting again resumes


def test_submit_grades_every_question_in_mock_order(runner, mock_bank) -> None:
    r, clock = runner
    _, questions = mock_bank
    session_id = r.start(MOCK_ID)
    expected = []
    for i, q in enumerate(questions):
        if i % 4 == 3:
            expected.append(False)  # left unanswered
            continue
        response = correct_response(q) if i % 2 == 0 else wrong_response(q)
        r.save(session_id, q["id"], response, marked=False)
        expected.append(i % 2 == 0)
    clock.advance(minutes=30)
    r.submit(session_id)

    answers = r.store.answers(session_id)
    assert [a["question_id"] for a in answers] == [q["id"] for q in questions]
    assert [a["correct"] for a in answers] == expected
    assert all(a["response"] is None for i, a in enumerate(answers) if i % 4 == 3)
    assert r.store.drafts(session_id) == {}
    result = r.result(session_id)
    bank = r.banks["101"]
    assert result.score == score([(bank.question(q["id"]), ok) for q, ok in zip(questions, expected, strict=True)])
    assert result.time_used == timedelta(minutes=30)
    assert r.store.resumable_session(MOCK_ID) is None


def test_save_is_refused_after_the_deadline_and_the_session_is_submitted(runner, mock_bank) -> None:
    r, clock = runner
    _, questions = mock_bank
    session_id = r.start(MOCK_ID)
    r.save(session_id, questions[0]["id"], correct_response(questions[0]), marked=False)
    clock.advance(minutes=90, seconds=GRACE.total_seconds() - 1)
    r.save(session_id, questions[1]["id"], correct_response(questions[1]), marked=False)  # within the grace
    clock.advance(seconds=2)
    with pytest.raises(DeadlinePassed):
        r.save(session_id, questions[2]["id"], correct_response(questions[2]), marked=False)
    result = r.result(session_id)
    assert (result.score.correct, result.score.total) == (2, 60)
    assert result.time_used == timedelta(minutes=90)
    with pytest.raises(MockError):
        r.save(session_id, questions[3]["id"], "b", marked=False)


def test_time_on_screen_is_summed_over_visits(runner, mock_bank) -> None:
    r, clock = runner
    _, questions = mock_bank
    first, second = questions[0]["id"], questions[1]["id"]
    session_id = r.start(MOCK_ID)
    r.view(session_id, first)
    clock.advance(seconds=10)
    r.view(session_id, second)
    clock.advance(seconds=5)
    r.view(session_id, first)
    clock.advance(seconds=7)
    r.submit(session_id)
    times = {a["question_id"]: a["time_taken_ms"] for a in r.store.answers(session_id)}
    assert times[first] == 17_000 and times[second] == 5_000
    assert times[questions[2]["id"]] == 0


def test_history(runner, mock_bank) -> None:
    r, clock = runner
    _, questions = mock_bank
    mock = r.mocks("101")[0]
    assert r.history(mock).attempts == 0 and r.history(mock).best is None
    for correct in (39, 60):
        session_id = r.start(MOCK_ID)
        for q in questions[:correct]:
            r.save(session_id, q["id"], correct_response(q), marked=False)
        r.submit(session_id)
        clock.advance(days=1)
    history = r.history(mock)
    assert (history.attempts, history.best, history.last, history.last_date) == (2, 800, 800, "2026-10-27")
    assert history.resumable is None


def test_marks_and_unanswered_counts(runner, mock_bank) -> None:
    r, _ = runner
    _, questions = mock_bank
    session_id = r.start(MOCK_ID)
    r.save(session_id, questions[0]["id"], "b", marked=True)
    r.save(session_id, questions[1]["id"], [], marked=True)
    state = r.state(session_id)
    assert (state.unanswered, state.marked_count) == (59, 2)


@pytest.mark.parametrize(
    ("index", "response"),
    [(0, ["b"]), (0, "z"), (1, "a"), (1, ["a", "z"]), (2, ["x"]), (3, "q")],
)
def test_malformed_responses_are_refused(runner, mock_bank, index: int, response) -> None:
    r, _ = runner
    _, questions = mock_bank
    session_id = r.start(MOCK_ID)
    with pytest.raises(MockError):
        r.save(session_id, questions[index]["id"], response, marked=False)


def test_unknown_mock_session_and_question(runner) -> None:
    r, _ = runner
    with pytest.raises(MockError):
        r.start("101-mock-09")
    with pytest.raises(MockError):
        r.state(999)
    session_id = r.start(MOCK_ID)
    with pytest.raises(MockError):
        r.save(session_id, "101-101.1-0999", "b", marked=False)
    with pytest.raises(MockError):
        r.question(session_id, 61)


def test_clean_response_turns_blank_into_unanswered(mock_bank) -> None:
    content, questions = mock_bank
    bank = load_exam("101", content)
    assert clean_response(bank.question(questions[0]["id"]), "") is None
    assert clean_response(bank.question(questions[1]["id"]), ["c", "a", "c"]) == ["a", "c"]
    assert clean_response(bank.question(questions[2]["id"]), "   ") is None


def test_weak_areas_are_below_the_pass_point_weakest_first() -> None:
    tallies = {
        "101.1": Tally(1, 2),
        "101.2": Tally(2, 3),
        "101.3": Tally(0, 1),
        "101.4": Tally(13, 20),
        "103.1": Tally(1, 2),
    }
    assert [(w.objective, w.correct, w.total) for w in weak_areas(tallies)] == [
        ("101.3", 0, 1),
        ("101.1", 1, 2),
        ("103.1", 1, 2),
    ]
