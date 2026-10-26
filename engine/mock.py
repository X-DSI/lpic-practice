"""Mock exam sessions without a UI: start or resume, save drafts, enforce the deadline, submit,
and report results (mock-exam-composition, LPI-style scoring and results-database-v2 ADRs).

A session's deadline is `started_at` + the mock's `duration_minutes`; it is derived, never stored.
Saves are accepted until the deadline plus `GRACE`. After that the session is submitted as it
stands and the save is refused, so an unanswered question counts as wrong.

Time on screen (`time_taken_ms`) is measured on the server between page views of the same session
and summed per question. It is kept in memory: the v2 database has nowhere to keep it during an
exam, so a server restart in the middle of a mock forgets the time measured before the restart.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from typing import Final

from engine.matching import is_correct
from engine.model import Bank, MockExam, Question
from engine.scoring import PASS_POINT, Score, Tally, score
from engine.store import Draft, Session, Store, timestamp

MODE: Final = "mock"
GRACE: Final = timedelta(seconds=5)

Clock = Callable[[], datetime]
Response = str | list[str] | None


def utc_now() -> datetime:
    return datetime.now(UTC)


class MockError(Exception):
    """A request the session can't accept: unknown session or question, or a malformed response."""


class SessionFinished(MockError):
    """The session has already been submitted; nothing more can be saved."""


class DeadlinePassed(SessionFinished):
    """The save came after the deadline; the session has been submitted."""


@dataclass(frozen=True)
class MockState:
    session: Session
    mock: MockExam
    deadline: datetime
    drafts: dict[str, Draft]

    @property
    def finished(self) -> bool:
        return self.session.finished_at is not None

    def answered(self, question_id: str) -> bool:
        draft = self.drafts.get(question_id)
        return draft is not None and draft.response not in (None, "", [])

    def marked(self, question_id: str) -> bool:
        draft = self.drafts.get(question_id)
        return draft is not None and draft.marked

    @property
    def unanswered(self) -> int:
        return sum(not self.answered(q) for q in self.mock.questions)

    @property
    def marked_count(self) -> int:
        return sum(self.marked(q) for q in self.mock.questions)


@dataclass(frozen=True)
class WeakArea:
    objective: str
    correct: int
    total: int


@dataclass(frozen=True)
class MockResult:
    session: Session
    mock: MockExam
    score: Score
    answers: list[dict]
    time_used: timedelta
    weak_areas: list[WeakArea]


@dataclass(frozen=True)
class MockHistory:
    """What the mock list shows for one mock."""

    mock: MockExam
    attempts: int
    best: int | None
    last: int | None
    last_date: str | None
    resumable: Session | None


@dataclass
class _Timer:
    """Per-session on-screen time: the question being viewed since when, and the totals so far."""

    current: str | None = None
    since: datetime | None = None
    totals: dict[str, int] = field(default_factory=dict)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def clean_response(question: Question, response: Response) -> Response:
    """Normalise a submitted response, or raise `MockError` if it can't be an answer to `question`.
    An empty response means "unanswered" and becomes `None`."""
    if response is None:
        return None
    option_ids = {o.id for o in question.options}
    if question.type == "single_choice":
        if not isinstance(response, str):
            raise MockError(f"{question.id}: choose one option")
        if response == "":
            return None
        if response not in option_ids:
            raise MockError(f"{question.id}: no option {response!r}")
        return response
    if question.type == "multi_choice":
        if isinstance(response, str):
            raise MockError(f"{question.id}: choose options as a list")
        chosen = sorted(set(response))
        if not chosen:
            return None
        if unknown := [r for r in chosen if r not in option_ids]:
            raise MockError(f"{question.id}: no option(s) {unknown}")
        return chosen
    if not isinstance(response, str):
        raise MockError(f"{question.id}: type an answer")
    return response if response.strip() else None


class MockRunner:
    """Mock sessions over one results store and one or more exam banks."""

    def __init__(self, store: Store, banks: Iterable[Bank], clock: Clock = utc_now, grace: timedelta = GRACE) -> None:
        self.store = store
        self.banks = {b.exam: b for b in banks}
        self.clock = clock
        self.grace = grace
        self._timers: dict[int, _Timer] = {}

    # ------------------------------------------------------------------ lookups

    def mocks(self, exam: str) -> tuple[MockExam, ...]:
        return self.banks[exam].mocks

    def mock(self, mock_id: str) -> tuple[Bank, MockExam]:
        exam = mock_id.split("-", 1)[0]
        bank = self.banks.get(exam)
        for mock in bank.mocks if bank else ():
            if mock.id == mock_id:
                return bank, mock
        raise MockError(f"no mock {mock_id!r}")

    def question(self, session_id: int, number: int) -> Question:
        """Question `number` (1-based, in the mock's order) of a session."""
        state = self.state(session_id)
        if not 1 <= number <= len(state.mock.questions):
            raise MockError(f"no question {number} in {state.mock.id}")
        bank, _ = self.mock(state.mock.id)
        return bank.question(state.mock.questions[number - 1])

    def state(self, session_id: int) -> MockState:
        session = self.store.session(session_id)
        if session is None or session.mode != MODE or session.mock_id is None:
            raise MockError(f"no mock session {session_id}")
        _, mock = self.mock(session.mock_id)
        deadline = parse_time(session.started_at) + timedelta(minutes=mock.duration_minutes)
        return MockState(session, mock, deadline, self.store.drafts(session_id))

    def remaining(self, state: MockState) -> timedelta:
        return max(timedelta(0), state.deadline - self.clock())

    def history(self, mock: MockExam) -> MockHistory:
        finished = [s for s in self.store.mock_sessions(mock.id) if s.finished_at]
        scores = [self._score(s.id).scaled for s in finished]
        return MockHistory(
            mock=mock,
            attempts=len(finished),
            best=max(scores) if scores else None,
            last=scores[-1] if scores else None,
            last_date=finished[-1].finished_at[:10] if finished else None,
            resumable=self.store.resumable_session(mock.id),
        )

    def finished_sessions(self, mock: MockExam) -> list[Session]:
        return [s for s in self.store.mock_sessions(mock.id) if s.finished_at]

    # ---------------------------------------------------------------- lifecycle

    def start(self, mock_id: str) -> int:
        """Resume the mock's unfinished session, or start a new one. A new session gets an empty
        draft per question, so it is resumable from the first moment."""
        bank, mock = self.mock(mock_id)
        if resumable := self.store.resumable_session(mock_id):
            self.check_deadline(resumable.id)
            if not self.state(resumable.id).finished:
                return resumable.id
        started = self.clock()
        session_id = self.store.start_session(bank.exam, MODE, mock_id=mock_id, started_at=timestamp(started))
        for question_id in mock.questions:
            self.store.save_draft(session_id, question_id, None, False, timestamp(started))
        return session_id

    def view(self, session_id: int, question_id: str) -> None:
        """Note that `question_id` is now on screen, closing the previous view's time."""
        timer = self._timers.setdefault(session_id, _Timer())
        moment = self.clock()
        self._close_view(timer, moment)
        timer.current, timer.since = question_id, moment

    def _close_view(self, timer: _Timer, moment: datetime) -> None:
        if timer.current is not None and timer.since is not None:
            elapsed = max(0, int((moment - timer.since).total_seconds() * 1000))
            timer.totals[timer.current] = timer.totals.get(timer.current, 0) + elapsed
        timer.current = timer.since = None

    def check_deadline(self, session_id: int) -> bool:
        """Submit the session if its deadline (plus grace) has passed. Returns whether it is finished."""
        state = self.state(session_id)
        if not state.finished and self.clock() > state.deadline + self.grace:
            self.submit(session_id)
            return True
        return state.finished

    def save(self, session_id: int, question_id: str, response: Response, marked: bool) -> None:
        """Save the in-progress answer and mark for one question."""
        state = self.state(session_id)
        if state.finished:
            raise SessionFinished(f"session {session_id} is already submitted")
        if question_id not in state.mock.questions:
            raise MockError(f"{question_id} is not in {state.mock.id}")
        if self.check_deadline(session_id):
            raise DeadlinePassed(f"the deadline for session {session_id} has passed; it has been submitted")
        bank, _ = self.mock(state.mock.id)
        cleaned = clean_response(bank.question(question_id), response)
        self.store.save_draft(session_id, question_id, cleaned, marked, timestamp(self.clock()))

    def submit(self, session_id: int) -> None:
        """Grade every question from its draft and store the answers, in the mock's order, in one
        transaction. Unanswered questions are stored with `response` null and count as wrong."""
        state = self.state(session_id)
        if state.finished:
            return
        bank, mock = self.mock(state.mock.id)
        moment = self.clock()
        timer = self._timers.pop(session_id, _Timer())
        self._close_view(timer, moment)
        rows = []
        for question_id in mock.questions:
            draft = state.drafts.get(question_id)
            response = draft.response if draft else None
            correct = response is not None and is_correct(bank.question(question_id), response)
            rows.append((question_id, response, correct, timer.totals.get(question_id, 0)))
        finished_at = min(moment, state.deadline)
        self.store.submit_mock(session_id, rows, timestamp(finished_at))

    # ------------------------------------------------------------------ results

    def _graded(self, session_id: int) -> tuple[list[dict], list[tuple[Question, bool]]]:
        state = self.state(session_id)
        bank, _ = self.mock(state.mock.id)
        answers = self.store.answers(session_id)
        return answers, [(bank.question(a["question_id"]), a["correct"]) for a in answers]

    def _score(self, session_id: int) -> Score:
        return score(self._graded(session_id)[1])

    def result(self, session_id: int) -> MockResult:
        state = self.state(session_id)
        if not state.finished:
            raise MockError(f"session {session_id} has not been submitted")
        answers, graded = self._graded(session_id)
        result = score(graded)
        assert state.session.finished_at is not None
        used = parse_time(state.session.finished_at) - parse_time(state.session.started_at)
        return MockResult(
            session=state.session,
            mock=state.mock,
            score=result,
            answers=answers,
            time_used=min(used, timedelta(minutes=state.mock.duration_minutes)),
            weak_areas=weak_areas(result.by_objective),
        )


def weak_areas(by_objective: dict[str, Tally]) -> list[WeakArea]:
    """Objectives scored below the pass point, weakest first (then by objective ID)."""
    weak = [
        WeakArea(o, t.correct, t.total) for o, t in by_objective.items() if Fraction(t.correct, t.total) < PASS_POINT
    ]
    return sorted(weak, key=lambda w: (Fraction(w.correct, w.total), w.objective))
