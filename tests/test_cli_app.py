"""Drive a whole practice session through the Textual app with its test pilot."""

from __future__ import annotations

import asyncio
import random
from pathlib import Path

from textual.widgets import DataTable, Input, RadioSet, Select, SelectionList, Static

from cli.app import FeedbackScreen, FlagScreen, PracticeApp, QuestionScreen, SetupScreen, SummaryScreen
from engine.store import Store

FIXTURE_CONTENT = Path(__file__).parent / "fixtures" / "content"
SIZE = (110, 60)


def text(app: PracticeApp, selector: str) -> str:
    return str(app.screen.query_one(selector, Static).render())


async def answer_current(app: PracticeApp, pilot, correct: bool) -> str:
    """Answer whatever question is showing, using the keyboard and the mouse; return its type."""
    screen = app.screen
    assert isinstance(screen, QuestionScreen)
    q = screen.question
    if q.type == "single_choice":
        choice = q.answer[0] if correct else next(o.id for o in q.options if o.id not in q.answer)
        await pilot.click(f"#opt-{choice}")
        await pilot.press("ctrl+s")
    elif q.type == "multi_choice":
        # One option too few is refused; the app says how many to choose.
        selection = screen.query_one("#answer", SelectionList)
        selection.select(q.answer[0])
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, QuestionScreen)
        if correct:
            for option in q.answer[1:]:
                selection.select(option)
        else:
            selection.select(next(o.id for o in q.options if o.id not in q.answer))
        await pilot.click("#submit")
    else:
        await pilot.press(*(" ls   -i " if correct else "nope"))
        await pilot.press("enter")
    await pilot.pause()
    assert isinstance(app.screen, FeedbackScreen)
    return q.type


def test_full_session(tmp_path: Path) -> None:
    async def run() -> None:
        store = Store(tmp_path / "results.sqlite")
        app = PracticeApp(store, FIXTURE_CONTENT, rng=random.Random(0))
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, SetupScreen)
            # Defaults: exam 101, "by objective", the first objective with practice questions (101.1).
            assert app.screen.query_one("#objective", Select).value == "101.1"
            await pilot.click("#start")
            await pilot.pause()

            seen, correct_flags = [], []
            for i in range(3):
                correct = i != 1
                seen.append(await answer_current(app, pilot, correct))
                feedback = app.screen
                assert isinstance(feedback, FeedbackScreen)
                assert text(app, "#verdict") == ("✓ Correct" if correct else "✗ Not correct")
                q = feedback.result.question
                expected = q.fill_in.accepted[0] if q.fill_in else ", ".join(q.answer)
                assert expected in text(app, "#correct")
                correct_flags.append(correct)

                if i == 0:
                    # Flag the first question: a link in the note is refused, then a clean note is saved.
                    await pilot.press("f")
                    await pilot.pause()
                    assert isinstance(app.screen, FlagScreen)
                    await pilot.click("#reason-ambiguous")
                    note = app.screen.query_one("#note", Input)
                    note.value = "see https://example.org"
                    await pilot.click("#save")
                    await pilot.pause()
                    assert isinstance(app.screen, FlagScreen)
                    assert "URL" in text(app, "#flag-error")
                    note.value = "Two options look right."
                    # A button ignores presses while its press effect is still showing.
                    await pilot.pause(0.5)
                    await pilot.click("#save")
                    await pilot.pause()
                    assert isinstance(app.screen, FeedbackScreen)

                await pilot.press("n")
                await pilot.pause()

            assert sorted(seen) == ["fill_in", "multi_choice", "single_choice"]
            assert isinstance(app.screen, SummaryScreen)
            assert text(app, "#score") == "Score: 2 / 3 (67%)"
            table = app.screen.query_one("#breakdown", DataTable)
            assert table.row_count == 1 and table.get_row_at(0)[:3] == ["101.1", 2, 3]

            await pilot.press("r")
            await pilot.pause()
            assert isinstance(app.screen, SetupScreen)

        answers = store.answers()
        assert [a["correct"] for a in answers] == correct_flags
        assert {a["question_id"] for a in answers} == {"101-101.1-0001", "101-101.1-0002", "101-101.1-0003"}
        assert [(f.reason, f.note) for f in store.flags()] == [("ambiguous", "Two options look right.")]
        store.close()

    asyncio.run(run())


def test_weak_mode_from_the_setup_screen(tmp_path: Path) -> None:
    async def run() -> None:
        with Store(tmp_path / "results.sqlite") as store:
            app = PracticeApp(store, FIXTURE_CONTENT, rng=random.Random(0))
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                await pilot.click("#mode-weak")
                await pilot.click("#start")
                await pilot.pause()
                screen = app.screen
                assert isinstance(screen, QuestionScreen)
                assert screen.session.mode == "weak"
                assert all(q.pool == "practice" and not q.retired for q in screen.session.questions)
                await pilot.press("escape")
                await pilot.pause()
                assert isinstance(app.screen, SummaryScreen)
                assert text(app, "#score") == "No questions answered."

    asyncio.run(run())


def test_second_exam_is_selectable(tmp_path: Path) -> None:
    async def run() -> None:
        with Store(tmp_path / "results.sqlite") as store:
            app = PracticeApp(store, FIXTURE_CONTENT, rng=random.Random(0))
            async with app.run_test(size=SIZE) as pilot:
                await pilot.pause()
                await pilot.click("#exam-102")
                await pilot.pause()
                assert app.screen.query_one("#exam", RadioSet).pressed_button.id == "exam-102"
                assert app.screen.query_one("#objective", Select).value == "104.1"

    asyncio.run(run())


def test_vim_keys_answer_and_advance(tmp_path: Path) -> None:
    # Keyboard only: j/k/g/G move, Space or l toggles, Enter submits, Enter on feedback goes on.
    async def run() -> None:
        store = Store(tmp_path / "results.sqlite")
        app = PracticeApp(store, FIXTURE_CONTENT, rng=random.Random(0))
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#start")
            await pilot.pause()
            seen = []
            for _ in range(3):
                screen = app.screen
                assert isinstance(screen, QuestionScreen)
                q = screen.question
                ids = [o.id for o in q.options]
                if q.type == "single_choice":
                    # Wander first (G, k) so the test checks that Enter takes the *highlighted* option.
                    await pilot.press("G", "k", "g", *["j"] * ids.index(q.answer[0]), "enter")
                elif q.type == "multi_choice":
                    await pilot.press("G", "g")
                    position = 0
                    for keys, option in zip(["space", "l"] * len(q.answer), q.answer, strict=False):
                        target = ids.index(option)
                        await pilot.press(*["j"] * (target - position), keys)
                        position = target
                    await pilot.press("enter")
                else:
                    await pilot.press(*"jk ls -i", "enter")  # j and k are typed, not navigation
                await pilot.pause()
                feedback = app.screen
                assert isinstance(feedback, FeedbackScreen), q.id
                seen.append((q.type, feedback.result.correct))
                await pilot.press("j", "k", "enter")
                await pilot.pause()
            assert isinstance(app.screen, SummaryScreen)
        types = dict(seen)
        assert types["single_choice"] and types["multi_choice"]
        assert types["fill_in"] is False  # "jk ls -i" proves j/k reach the text box
        store.close()

    asyncio.run(run())


def test_enter_on_a_choose_n_question_needs_n_options(tmp_path: Path) -> None:
    async def run() -> None:
        store = Store(tmp_path / "results.sqlite")
        app = PracticeApp(store, FIXTURE_CONTENT, rng=random.Random(0))
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.click("#start")
            await pilot.pause()
            while app.screen.question.type != "multi_choice":
                await pilot.press(*("x" if app.screen.question.type == "fill_in" else ""), "enter")
                await pilot.pause()
                await pilot.press("enter")  # feedback → next question
                await pilot.pause()
            await pilot.press("space", "enter")  # one option chosen, more needed: refused
            await pilot.pause()
            assert isinstance(app.screen, QuestionScreen)
        assert all(a["question_id"] != app.screen.question.id for a in store.answers())
        store.close()

    asyncio.run(run())
