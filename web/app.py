"""The web mock exam: list mocks, take one under exam conditions, see the result, review questions.

`create_app()` builds the FastAPI app; `lpic serve` runs it with uvicorn on 127.0.0.1. Pages are
rendered on the server. htmx saves each change as it happens; a small script draws the countdown
and submits at the deadline. The server enforces the deadline on its own (see `engine.mock`).

Before submit, templates only ever receive `QuestionView`, which carries no answer key, rationale
or explanation.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from engine.loader import exams, load_exam
from engine.mock import Clock, MockError, MockRunner, SessionFinished, utc_now
from engine.model import Bank, Question
from engine.scoring import PASS_POINT
from engine.store import FLAG_NOTE_MAX, FLAG_REASONS, FlagError, Store, default_db_path
from engine.validation import CONTENT_DIR

HERE = Path(__file__).parent
CODE = re.compile(r"`([^`\n]+)`")


def inline_markdown(text: str) -> Markup:
    """Escape `text`, then render `code` spans and line breaks. Enough for question stems."""
    escaped = str(escape(text))
    escaped = CODE.sub(lambda m: f"<code>{m.group(1)}</code>", escaped)
    return Markup(escaped.replace("\n", "<br>"))


@dataclass(frozen=True)
class QuestionView:
    """What a question page may show before submit: no key, rationale or explanation."""

    id: str
    type: str
    stem: str
    exhibit: str | None
    options: tuple[tuple[str, str], ...]
    select_count: int | None

    @classmethod
    def of(cls, q: Question) -> QuestionView:
        return cls(q.id, q.type, q.stem, q.exhibit, tuple((o.id, o.text) for o in q.options), q.select_count)


async def read_form(request: Request) -> dict[str, list[str]]:
    """Parse an `application/x-www-form-urlencoded` body (no python-multipart needed)."""
    return parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)


def redirect(url: str, request: Request | None = None) -> Response:
    """A 303 redirect; for an htmx request, an `HX-Redirect` so the whole page moves."""
    if request is not None and request.headers.get("HX-Request"):
        return Response(status_code=200, headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=303)


def minutes_seconds(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def create_app(content_dir: Path = CONTENT_DIR, db_path: Path | None = None, clock: Clock = utc_now) -> FastAPI:
    """The app for the mocks under `content_dir`, storing results in `db_path` (default: the user's
    results database). Content is assumed valid; `lpic serve` checks `validate --strict` first."""
    banks: dict[str, Bank] = {}
    for exam in exams(content_dir):
        bank = load_exam(exam, content_dir)
        if bank.mocks:
            banks[exam] = bank
    holder: dict[str, MockRunner] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Opened here, inside the event loop's thread; every endpoint is async and runs there too.
        store = Store(db_path or default_db_path())
        holder["runner"] = MockRunner(store, banks.values(), clock=clock)
        try:
            yield
        finally:
            store.close()

    app = FastAPI(title="lpic-practice mock exams", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters["md"] = inline_markdown
    templates.env.filters["mmss"] = minutes_seconds
    templates.env.globals.update(flag_reasons=FLAG_REASONS, flag_note_max=FLAG_NOTE_MAX)

    def runner() -> MockRunner:
        return holder["runner"]

    def page(request: Request, name: str, status_code: int = 200, **context: object) -> HTMLResponse:
        return templates.TemplateResponse(request, name, context, status_code=status_code)

    def not_found(request: Request, message: str) -> HTMLResponse:
        return page(request, "error.html", status_code=404, message=message)

    def objective_titles(bank: Bank) -> dict[str, str]:
        return {o.id: o.title for o in bank.objectives} | {t.id: t.title for t in bank.topics}

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    # ------------------------------------------------------------------ mock list

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> Response:
        r = runner()
        listing = []
        for _, bank in sorted(banks.items()):
            rows = []
            for mock in bank.mocks:
                if (resumable := r.store.resumable_session(mock.id)) is not None:
                    r.check_deadline(resumable.id)  # a mock left past its deadline is submitted now
                rows.append((r.history(mock), r.finished_sessions(mock)))
            listing.append((bank, rows))
        return page(request, "index.html", listing=listing)

    @app.post("/mocks/{mock_id}/start")
    async def start(request: Request, mock_id: str) -> Response:
        try:
            session_id = runner().start(mock_id)
        except MockError as exc:
            return not_found(request, str(exc))
        return redirect(f"/sessions/{session_id}/questions/1")

    # ------------------------------------------------------------- taking a mock

    def nav_context(session_id: int, number: int) -> dict[str, object]:
        state = runner().state(session_id)
        return {
            "state": state,
            "session_id": session_id,
            "number": number,
            "navigator": [
                (i, state.answered(qid), state.marked(qid)) for i, qid in enumerate(state.mock.questions, start=1)
            ],
        }

    @app.get("/sessions/{session_id}/questions/{number}", response_class=HTMLResponse)
    async def question_page(request: Request, session_id: int, number: int) -> Response:
        r = runner()
        try:
            if r.check_deadline(session_id):
                return redirect(f"/sessions/{session_id}/results")
            question = r.question(session_id, number)
        except MockError as exc:
            return not_found(request, str(exc))
        r.view(session_id, question.id)
        context = nav_context(session_id, number)
        state = r.state(session_id)
        draft = state.drafts.get(question.id)
        return page(
            request,
            "question.html",
            question=QuestionView.of(question),
            response=draft.response if draft else None,
            marked=bool(draft and draft.marked),
            total=len(state.mock.questions),
            remaining=int(r.remaining(state).total_seconds()),
            deadline=state.deadline.isoformat(),
            **context,
        )

    async def save_from_form(request: Request, session_id: int, number: int) -> tuple[dict[str, list[str]], str]:
        r = runner()
        question = r.question(session_id, number)
        form = await read_form(request)
        values = form.get("response", [])
        response: str | list[str] | None
        if question.type == "multi_choice":
            response = values
        else:
            response = values[0] if values else None
        r.save(session_id, question.id, response, marked=form.get("marked", [""])[0] == "1")
        return form, question.id

    @app.post("/sessions/{session_id}/questions/{number}")
    async def save_and_move(request: Request, session_id: int, number: int) -> Response:
        """The question form without JavaScript: save, then go where the pressed button says."""
        try:
            form, _ = await save_from_form(request, session_id, number)
        except SessionFinished:
            return redirect(f"/sessions/{session_id}/results")
        except MockError as exc:
            return not_found(request, str(exc))
        go = form.get("go", ["next"])[0]
        total = len(runner().state(session_id).mock.questions)
        if go == "submit":
            return redirect(f"/sessions/{session_id}/submit")
        target = {"prev": number - 1, "next": number + 1}.get(go) or (int(go) if go.isdigit() else number)
        return redirect(f"/sessions/{session_id}/questions/{min(max(target, 1), total)}")

    @app.post("/sessions/{session_id}/questions/{number}/save", response_class=HTMLResponse)
    async def autosave(request: Request, session_id: int, number: int) -> Response:
        """htmx: save on every change and return the refreshed navigator."""
        try:
            await save_from_form(request, session_id, number)
        except SessionFinished:
            return redirect(f"/sessions/{session_id}/results", request)
        except MockError as exc:
            return not_found(request, str(exc))
        return page(request, "_navigator.html", saved=True, **nav_context(session_id, number))

    @app.get("/sessions/{session_id}/submit", response_class=HTMLResponse)
    async def confirm_submit(request: Request, session_id: int) -> Response:
        r = runner()
        try:
            if r.check_deadline(session_id):
                return redirect(f"/sessions/{session_id}/results")
            state = r.state(session_id)
        except MockError as exc:
            return not_found(request, str(exc))
        return page(
            request,
            "submit.html",
            state=state,
            session_id=session_id,
            remaining=int(r.remaining(state).total_seconds()),
            deadline=state.deadline.isoformat(),
        )

    @app.post("/sessions/{session_id}/submit")
    async def submit(request: Request, session_id: int) -> Response:
        try:
            runner().submit(session_id)
        except MockError as exc:
            return not_found(request, str(exc))
        return redirect(f"/sessions/{session_id}/results")

    # --------------------------------------------------------- results and review

    @app.get("/sessions/{session_id}/results", response_class=HTMLResponse)
    async def results(request: Request, session_id: int) -> Response:
        r = runner()
        try:
            if not r.check_deadline(session_id):
                return redirect(f"/sessions/{session_id}/questions/1")
            result = r.result(session_id)
        except MockError as exc:
            return not_found(request, str(exc))
        bank, _ = r.mock(result.mock.id)
        return page(
            request,
            "results.html",
            result=result,
            session_id=session_id,
            titles=objective_titles(bank),
            pass_percent=float(PASS_POINT * 100),
        )

    def review_item(session_id: int, question_id: str) -> dict[str, object]:
        r = runner()
        state = r.state(session_id)
        bank, _ = r.mock(state.mock.id)
        answer = next(a for a in r.store.answers(session_id) if a["question_id"] == question_id)
        return {
            "session_id": session_id,
            "number": state.mock.questions.index(question_id) + 1,
            "q": bank.question(question_id),
            "answer": answer,
            "approved": any(rv.question_id == question_id for rv in r.store.reviews(session_id)),
            "flags": [f for f in r.store.flags() if f.question_id == question_id],
        }

    def finished_or_none(request: Request, session_id: int) -> HTMLResponse | None:
        try:
            if not runner().check_deadline(session_id):
                return page(request, "error.html", status_code=403, message="Submit the mock before reviewing it.")
        except MockError as exc:
            return not_found(request, str(exc))
        return None

    @app.get("/sessions/{session_id}/review", response_class=HTMLResponse)
    async def review(request: Request, session_id: int) -> Response:
        if (refusal := finished_or_none(request, session_id)) is not None:
            return refusal
        state = runner().state(session_id)
        items = [review_item(session_id, qid) for qid in state.mock.questions]
        return page(request, "review.html", state=state, session_id=session_id, items=items)

    @app.post("/sessions/{session_id}/review/{question_id}/approve", response_class=HTMLResponse)
    async def approve(request: Request, session_id: int, question_id: str) -> Response:
        if (refusal := finished_or_none(request, session_id)) is not None:
            return refusal
        if question_id not in runner().state(session_id).mock.questions:
            return not_found(request, f"{question_id} is not in this mock")
        runner().store.add_review(question_id, session_id)
        return review_response(request, session_id, question_id)

    @app.post("/sessions/{session_id}/review/{question_id}/flag", response_class=HTMLResponse)
    async def flag(request: Request, session_id: int, question_id: str) -> Response:
        if (refusal := finished_or_none(request, session_id)) is not None:
            return refusal
        if question_id not in runner().state(session_id).mock.questions:
            return not_found(request, f"{question_id} is not in this mock")
        form = await read_form(request)
        reason, note = form.get("reason", [""])[0], form.get("note", [""])[0]
        try:
            runner().store.add_flag(question_id, reason, note)
        except FlagError as exc:
            return review_response(request, session_id, question_id, error=str(exc), note=note, reason=reason)
        return review_response(request, session_id, question_id)

    def review_response(
        request: Request, session_id: int, question_id: str, error: str | None = None, **form: str
    ) -> Response:
        if request.headers.get("HX-Request"):
            # htmx swaps only 2xx responses, so a refused flag is still a 200 that shows the error.
            return page(request, "_review_actions.html", error=error, form=form, **review_item(session_id, question_id))
        if error:
            return page(request, "error.html", status_code=400, message=f"Flag refused: {error}")
        return redirect(f"/sessions/{session_id}/review#{question_id}")

    return app
