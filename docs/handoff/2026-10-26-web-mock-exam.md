---
title: Web mock exam — timed 60-question mocks, LPI-style results, weak areas and holdout review
status: open
assignee: X-DSI-agent
base_sha: 44313cf
adrs:
  - 2026-10-22-technology-stack.md
  - 2026-10-22-mock-exam-composition.md
  - 2026-10-24-lpi-style-scoring.md
  - 2026-10-25-question-generation-workflow.md
  - proposed/2026-10-26-results-database-v2.md
plan_pr: 16
impl_pr: null
review: auto
---

## Goal
Let the maintainer take the 10 committed mock exams in a browser, under exam conditions (60
questions, 90 minutes, no feedback until the end). Then show an LPI-style result with weak areas,
and let him review each holdout question so it can be signed off or flagged.

## Scope
**In:**
- **`lpic serve [--host 127.0.0.1] [--port 8000]`**: a FastAPI + Jinja2 + htmx app in a new `web/`
  package, bound to localhost by default, with no login. Mocks are read from `content/<exam>/mocks/`
  and questions through `engine.loader`. The app refuses to start if the content does not pass
  `validate --strict`, the same pattern as `lpic practice`.
- **Mock list**: each exam that has mocks lists mock 1–10. Each mock shows:
  - its difficulty ramp (easiest to hardest);
  - the number of attempts, the best and the last scaled score, and the date;
  - **Start**, or **Resume** when it has an unfinished session.
- **Taking a mock**:
  - One question per page in the mock's order, with Previous/Next and a 1–60 navigator showing
    which questions are answered and which are marked for review.
  - Answers can be changed until submit. All three question types: choose one, choose N (the page
    says how many), and type an answer.
  - A countdown from the server-side deadline (`started_at` + `duration_minutes`).
  - Every change is saved to `drafts` at once, so a refresh, a closed tab or a server restart
    resumes where he left off with the same deadline.
  - **Submit** asks for confirmation and states how many questions are unanswered or marked.
  - At the deadline the mock is submitted automatically. The server also enforces the deadline:
    after it, saves are refused and the next request submits.
  - **No correctness, keys, rationales or explanations are shown before submit.**
- **Results page**:
  - Scaled score from `engine.scoring` (labelled an estimate), raw percentage next to it, and
    "likely pass" / "below the pass mark" at 500 (scoring ADR points 3–5).
  - Breakdown per topic and per objective (correct / total) and time used.
  - **Weak areas**: objectives below `engine.scoring.PASS_POINT`, weakest first, with a hint to drill them
    with `lpic practice` → weak areas.
- **Review after submit**:
  - Each question with its exhibit, options, his answer, the correct answer, every rationale and
    the explanation.
  - Per question: **Looks right** (writes a `reviews` row) or **Flag** (same reasons and note rules
    as the CLI, written through `Store.add_flag`).
  - The review stays available from the mock list for every finished session.
- **Store changes** per the proposed results-database-v2 ADR:
  - `mock_id`, `drafts` and `reviews`;
  - submit in one transaction;
  - v1 → v2 migration on open;
  - `lpic reviews export` (YAML: `question_id`, `verdict`, `reviewed_at`).
- **Static files**: htmx vendored into `web/static/` at a pinned version, with its license, so it
  works offline (no CDN). Keep JavaScript to the countdown and small touches; the server renders
  pages.
- **Docs**: add `lpic serve` and `lpic reviews export` to the AGENTS.md command table and the README.
  Add a changelog fragment.

**Out:** practice drills in the web UI, accounts or remote hosting, editing content from the UI,
exam 102 mocks (none exist yet), charts and history graphs, and changes to scoring or assembly.

## Acceptance criteria
- [ ] All tests pass, lint and format clean — check: `pytest && ruff check . && ruff format --check .`
- [ ] `pip install -e ".[dev]"` provides `lpic serve` and `lpic reviews export` — check: `lpic --help`
- [ ] **Full mock on a fixture bank:**
  - start, answer all three types, change one answer, mark one, submit;
  - the results page shows the same scaled score and raw percentage as `engine.scoring` for those
    answers;
  - `answers` has exactly one row per question.

  Check: `pytest tests/test_web_mock.py` (FastAPI `TestClient`).
- [ ] No key, rationale or explanation appears in any response before submit. The test scans
      every page and partial served during a mock — check: `pytest tests/test_web_mock.py`
- [ ] **Resume:** after drafts are saved, a new app instance on the same database resumes the
      session with its answers, marks and deadline — check: `pytest tests/test_web_mock.py`
- [ ] **Deadline:** with an injected clock, a save after the deadline is refused and the session
      is submitted, and unanswered questions count as wrong — check: `pytest tests/test_web_mock.py`
- [ ] **Review:** "Looks right" writes a `reviews` row. A flag with a URL or a note over 200
      characters is refused. Both appear in their exports — check:
      `pytest tests/test_web_review.py tests/test_store.py`
- [ ] **Migration:** a v1 database (as the CLI writes it today) opens as v2 with all its rows
      intact — check: `pytest tests/test_store.py`
- [ ] The CLI practice tests still pass unchanged — check: `pytest tests/test_practice.py tests/test_cli_app.py`
- [ ] With the committed 101 mocks (PR #15), `lpic serve` lists mocks 1–10 and a mock can be taken
      end to end in a browser — check: manual (maintainer)

## Constraints
- `engine/` must not import FastAPI, Jinja2 or Textual. Session logic (start, save draft, submit,
  deadline, results) lives in the engine (for example `engine/mock.py`) and is testable without HTTP.
- New runtime dependencies: `fastapi`, `jinja2`, `uvicorn` only. `httpx` may be added to `dev` for
  `TestClient`.
- Tests use synthetic fixture banks and a temporary database. They never use the real `content/`
  holdout text or the user's database. The one exception is a smoke test that the real 101 mocks
  load.
- Bind to `127.0.0.1` by default. Don't add authentication.
- Don't change `schemas/`, the scoring constant or the assembler.

## Implementer may decide
- Page layout, styling, keyboard shortcuts (it should be usable without a mouse) and module layout
  inside `web/`.
- How the countdown is drawn and refreshed, and the grace period for the server-side deadline
  (a few seconds).
- How time on screen is measured for `time_taken_ms`. A server-side measure between page loads is
  enough.
- Whether a finished session's review is one long page or paged.

## Must escalate
- Any change to `schemas/`, the scoring rules, or an Accepted ADR.
- Any database change beyond the results-database-v2 ADR. If the ADR doesn't fit the implementation,
  stop and say why, rather than adding columns.

## Attached content
None. The real mocks arrive with PR #15 (`content/101/mocks/mock-01.yaml` … `mock-10.yaml`).

## Outcome
