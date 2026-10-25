"""Textual practice app: setup → question → feedback (→ flag) → … → summary.

Keyboard-first: Tab moves between controls, arrow keys and Enter pick an option, Space toggles a
choice in "choose N" questions, Ctrl+S submits an answer, `n` goes to the next question, `f` flags
the current one and Escape ends the session early. Session logic lives in `engine.practice`.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import cast

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    RadioButton,
    RadioSet,
    Select,
    SelectionList,
    Static,
)

from engine.loader import exams, load_exam
from engine.model import Bank, Question
from engine.practice import DEFAULT_COUNT, MODES, Graded, Mode, PracticeSession, select
from engine.scoring import Score
from engine.selection import practice_pool
from engine.store import FLAG_NOTE_MAX, FLAG_REASONS, FlagError, Store
from engine.validation import CONTENT_DIR

MODE_LABELS: dict[Mode, str] = {
    "objective": "By objective",
    "mixed": "Mixed, weighted like the exam",
    "weak": "Weak areas",
}


def _plain(text: str) -> Content:
    """Question text shown as-is: no Textual markup is interpreted."""
    return Content(text)


def _format_response(response: str | tuple[str, ...]) -> str:
    return response if isinstance(response, str) else ", ".join(response) or "(nothing)"


class PracticeScreen(Screen):
    @property
    def practice(self) -> PracticeApp:
        return cast(PracticeApp, self.app)


class SetupScreen(PracticeScreen):
    BINDINGS = [("ctrl+s", "start", "Start")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Label("Exam")
            with RadioSet(id="exam"):
                for i, exam in enumerate(self.practice.banks):
                    yield RadioButton(exam, value=i == 0, id=f"exam-{exam}")
            yield Label("Mode")
            with RadioSet(id="mode"):
                for mode in MODES:
                    yield RadioButton(MODE_LABELS[mode], value=mode == "objective", id=f"mode-{mode}")
            yield Label("Objective (for “By objective”)")
            yield Select([], id="objective", prompt="Choose an objective")
            yield Label("Questions")
            yield Input(str(DEFAULT_COUNT), id="count", type="integer")
            yield Button("Start", id="start", variant="primary")
            yield Static("", id="error", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_objectives()

    @property
    def bank(self) -> Bank:
        pressed = self.query_one("#exam", RadioSet).pressed_button
        assert pressed is not None and pressed.id is not None
        return self.practice.banks[pressed.id.removeprefix("exam-")]

    @property
    def mode(self) -> Mode:
        pressed = self.query_one("#mode", RadioSet).pressed_button
        assert pressed is not None and pressed.id is not None
        return cast(Mode, pressed.id.removeprefix("mode-"))

    def refresh_objectives(self) -> None:
        bank = self.bank
        options = [
            (Text(f"{o.id}  {o.title}  ({n})"), o.id) for o in bank.objectives if (n := len(practice_pool(bank, o.id)))
        ]
        objective = self.query_one("#objective", Select)
        objective.set_options(options)
        if options:
            objective.value = options[0][1]

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "exam":
            self.refresh_objectives()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.action_start()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_start()

    def action_start(self) -> None:
        error = self.query_one("#error", Static)
        try:
            count = int(self.query_one("#count", Input).value)
        except ValueError:
            count = 0
        if count < 1:
            error.update("Enter how many questions you want (1 or more).")
            return
        objective = self.query_one("#objective", Select).value
        if self.mode == "objective" and not isinstance(objective, str):
            error.update("Choose an objective, or pick another mode.")
            return
        bank, store = self.bank, self.practice.store
        questions = select(
            bank,
            self.mode,
            count,
            objective=objective if isinstance(objective, str) else None,
            accuracy=store.accuracy_by_objective(bank.exam),
            rng=self.practice.rng,
        )
        if not questions:
            error.update(f"Exam {bank.exam} has no practice questions yet.")
            return
        error.update("")
        session = PracticeSession(store, bank.exam, self.mode, questions)
        self.app.push_screen(QuestionScreen(session))


class QuestionScreen(PracticeScreen):
    BINDINGS = [("ctrl+s", "submit", "Submit"), ("escape", "end", "End session")]

    def __init__(self, session: PracticeSession) -> None:
        super().__init__()
        self.session = session
        assert session.current is not None
        self.question: Question = session.current
        self.started = time.monotonic()

    def compose(self) -> ComposeResult:
        q, s = self.question, self.session
        yield Header()
        with VerticalScroll():
            yield Static(
                f"Question {len(s.graded) + 1} of {len(s.questions)} · objective {q.objective}"
                f" · difficulty {q.difficulty}",
                id="progress",
                markup=False,
            )
            yield Markdown(q.stem, id="stem")
            if q.exhibit:
                yield Static(q.exhibit, id="exhibit", markup=False)
            if q.type == "single_choice":
                yield Label("Choose one.")
                with RadioSet(id="answer"):
                    for o in q.options:
                        yield RadioButton(_plain(f"{o.id}) {o.text}"), id=f"opt-{o.id}")
            elif q.type == "multi_choice":
                yield Label(f"Choose {q.select_count}. Space toggles an option.")
                yield SelectionList[str](*((_plain(f"{o.id}) {o.text}"), o.id) for o in q.options), id="answer")
            else:
                yield Label("Type your answer and press Enter.")
                yield Input(id="answer", placeholder="Your answer")
            yield Button("Submit", id="submit", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.started = time.monotonic()
        self.query_one("#answer").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self.action_submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_submit()

    def response(self) -> str | list[str] | None:
        """The current response, or None (after telling the user why) if it can't be submitted."""
        q = self.question
        if q.type == "single_choice":
            pressed = self.query_one("#answer", RadioSet).pressed_button
            if pressed is None or pressed.id is None:
                self.notify("Choose an answer first.", severity="warning")
                return None
            return pressed.id.removeprefix("opt-")
        if q.type == "multi_choice":
            chosen = list(self.query_one("#answer", SelectionList).selected)
            if len(chosen) != q.select_count:
                self.notify(f"Choose exactly {q.select_count} options.", severity="warning")
                return None
            return chosen
        typed = self.query_one("#answer", Input).value
        if not typed.strip():
            self.notify("Type an answer first.", severity="warning")
            return None
        return typed

    def action_submit(self) -> None:
        response = self.response()
        if response is None:
            return
        elapsed_ms = int((time.monotonic() - self.started) * 1000)
        result = self.session.answer(response, elapsed_ms)
        self.app.switch_screen(FeedbackScreen(self.session, result))

    def action_end(self) -> None:
        self.app.switch_screen(SummaryScreen(self.session.finish()))


class FeedbackScreen(PracticeScreen):
    BINDINGS = [("n", "next", "Next"), ("f", "flag", "Flag question"), ("escape", "end", "End session")]

    def __init__(self, session: PracticeSession, result: Graded) -> None:
        super().__init__()
        self.session = session
        self.result = result

    def compose(self) -> ComposeResult:
        q, r = self.result.question, self.result
        yield Header()
        with VerticalScroll():
            yield Static(
                "✓ Correct" if r.correct else "✗ Not correct",
                id="verdict",
                classes="correct" if r.correct else "wrong",
                markup=False,
            )
            yield Static(f"Your answer: {_format_response(r.response)}", id="your-answer", markup=False)
            if q.type == "fill_in":
                assert q.fill_in is not None
                case = "case-sensitive" if q.fill_in.case_sensitive else "not case-sensitive"
                accepted = "\n".join(f"  {a}" for a in q.fill_in.accepted)
                yield Static(
                    f"Accepted answers ({q.fill_in.match} match, {case}):\n{accepted}", id="correct", markup=False
                )
            else:
                yield Static(f"Correct answer: {', '.join(q.answer)}", id="correct", markup=False)
                chosen = set(r.response) if not isinstance(r.response, str) else {r.response}
                for o in q.options:
                    mark = "✓" if o.id in q.answer else "✗"
                    you = "   ← your choice" if o.id in chosen else ""
                    rationale = f"\n     {o.rationale}" if o.rationale else ""
                    yield Static(f"{mark} {o.id}) {o.text}{you}{rationale}", classes="option", markup=False)
            yield Label("Explanation")
            yield Markdown(q.explanation, id="explanation")
            with Horizontal(id="actions"):
                yield Button("Next", id="next", variant="primary")
                yield Button("Flag question", id="flag")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#next").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            self.action_next()
        elif event.button.id == "flag":
            self.action_flag()

    def action_next(self) -> None:
        if self.session.current is not None:
            self.app.switch_screen(QuestionScreen(self.session))
        else:
            self.app.switch_screen(SummaryScreen(self.session.finish()))

    def action_flag(self) -> None:
        def flagged(saved: bool | None) -> None:
            if saved:
                self.notify("Question flagged. Thanks.")

        self.app.push_screen(FlagScreen(self.result.question), flagged)

    def action_end(self) -> None:
        self.app.switch_screen(SummaryScreen(self.session.finish()))


class FlagScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, question: Question) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Flag question {self.question.id}")
            with RadioSet(id="reason"):
                for i, reason in enumerate(FLAG_REASONS):
                    yield RadioButton(reason, value=i == 0, id=f"reason-{reason}")
            yield Input(id="note", placeholder=f"Optional note (at most {FLAG_NOTE_MAX} characters, no links)")
            yield Static("", id="flag-error", markup=False)
            with Horizontal():
                yield Button("Save", id="save", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#reason").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()
        elif event.button.id == "cancel":
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_save()

    def action_save(self) -> None:
        pressed = self.query_one("#reason", RadioSet).pressed_button
        assert pressed is not None and pressed.id is not None
        reason = pressed.id.removeprefix("reason-")
        note = self.query_one("#note", Input).value
        try:
            cast(PracticeApp, self.app).store.add_flag(self.question.id, reason, note)
        except FlagError as exc:
            self.query_one("#flag-error", Static).update(str(exc))
            return
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class SummaryScreen(PracticeScreen):
    BINDINGS = [("r", "restart", "New session"), ("q", "app.quit", "Quit")]

    def __init__(self, score: Score | None) -> None:
        super().__init__()
        self.score = score

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            if self.score is None:
                yield Static("No questions answered.", id="score", markup=False)
            else:
                s = self.score
                yield Static(f"Score: {s.correct} / {s.total} ({s.percent:.0f}%)", id="score", markup=False)
                yield DataTable(id="breakdown", cursor_type="row")
            yield Static("Press r for a new session or q to quit.", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        if self.score is None:
            return
        table = self.query_one("#breakdown", DataTable)
        table.add_columns("Objective", "Correct", "Answered", "%")
        for objective, tally in self.score.by_objective.items():
            table.add_row(objective, tally.correct, tally.total, f"{100 * tally.correct / tally.total:.0f}")
        table.focus()

    def action_restart(self) -> None:
        self.app.pop_screen()


class PracticeApp(App):
    TITLE = "LPIC practice"
    CSS = """
    VerticalScroll { padding: 0 2; }
    Label { margin-top: 1; text-style: bold; }
    #exhibit { border: round $secondary; padding: 0 1; }
    #verdict { text-style: bold; margin-top: 1; }
    #verdict.correct { color: $success; }
    #verdict.wrong { color: $error; }
    .option { margin-top: 1; }
    #error, #flag-error { color: $error; }
    #actions, FlagScreen Horizontal { height: auto; margin-top: 1; }
    Button { margin-right: 2; }
    FlagScreen { align: center middle; }
    #dialog { width: 70; height: auto; border: thick $primary; background: $surface; padding: 1 2; }
    """

    def __init__(self, store: Store, content_dir: Path = CONTENT_DIR, rng: random.Random | None = None) -> None:
        super().__init__()
        self.store = store
        self.banks = {exam: load_exam(exam, content_dir) for exam in exams(content_dir)}
        self.rng = rng or random.Random()

    def on_mount(self) -> None:
        self.push_screen(SetupScreen())
