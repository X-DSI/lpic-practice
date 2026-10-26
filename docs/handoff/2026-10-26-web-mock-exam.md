---
title: Web mock exam — timed 60-question mocks, LPI-style results, weak areas and holdout review
status: done
assignee: X-DSI-agent
base_sha: 44313cf
adrs:
  - 2026-10-22-technology-stack.md
  - 2026-10-22-mock-exam-composition.md
  - 2026-10-24-lpi-style-scoring.md
  - 2026-10-25-question-generation-workflow.md
  - proposed/2026-10-26-results-database-v2.md
plan_pr: 16
impl_pr: 17
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
**Status:** done  
**Commits:** 91bd2df..8315d2b (plus this Outcome) · **PR:** #17 ·
**CI run:** [https://github.com/X-DSI/lpic-practice/actions/runs/40345082188](https://github.com/X-DSI/lpic-practice/actions/runs/40345082188)

Drift check: `git diff 44313cf..origin/main` covers PR #15 (the 10 committed 101 mocks,
`validate --strict` in CI, a test tweak in `tests/test_assemble.py`) and PR #16 (this handoff and
the proposed results-database-v2 ADR). Nothing this work depends on changed in a conflicting way.
The mocks this handoff expected are now present.

### Verified acceptance criteria
Evidence is the `Lint and test engine` and `Validate content` jobs of the CI run above (222 tests
passed on Python 3.12).
- [x] All tests pass, lint and format clean — `pytest`, `ruff check .` and `ruff format --check .`
      steps
- [x] `pip install -e ".[dev]"` provides `lpic serve` and `lpic reviews export` — the install step,
      then `tests/test_cli_main.py`, which runs the installed `lpic --help`, `lpic serve --help` and
      `lpic reviews export`
- [x] **Full mock on a fixture bank** —
      `tests/test_web_mock.py::test_full_mock`:
  - start, answer all three types, change one answer, mark one, submit;
  - the results page shows `engine.scoring`'s scaled score and raw percentage for those answers;
  - `answers` has exactly one row per question, in mock order.
- [x] **No leaks before submit** — the same test scans every page and partial served before submit:
      no key, rationale or explanation.
- [x] **Resume** — `test_resume_on_a_new_app_instance`: a new app on the same database resumes with
      the same answers, marks and deadline.
- [x] **Deadline** — `test_deadline_is_enforced_by_the_server` and
      `test_a_mock_left_past_its_deadline_is_submitted_on_the_next_request`, with an injected clock:
  - a save after the deadline is refused and the session submitted;
  - unanswered questions count as wrong.
- [x] **Review** — `tests/test_web_review.py` and `tests/test_store.py::test_reviews`:
  - "Looks right" writes one `reviews` row;
  - flags with a URL or a note over 200 characters are refused;
  - both appear in `lpic reviews export` / `lpic flags export`.
- [x] **Migration** — `tests/test_store.py::test_a_v1_database_opens_as_v2_with_its_rows_intact`:
      a v1 database built with the v1 SQL, with sessions, answers and a flag, opens as v2 with all rows
      intact, and the CLI's calls still work on it.
- [x] **CLI practice tests unchanged** — `tests/test_practice.py` and `tests/test_cli_app.py` are not
      modified in this PR and pass in the run above.

### Unverified (manual) criteria
- [ ] With the committed 101 mocks, `lpic serve` lists mocks 1–10 and a mock can be taken end to end
      in a browser — **for the maintainer.**
  - What's done so far:
    - `tests/test_web_mock.py::test_the_real_101_mocks_load` checks in CI that the list names all 10
      real mocks.
    - The implementer ran `lpic serve` on the real 101 content and drove headless Chromium through
      list → start → answer and mark by keyboard → htmx autosave → navigate → submit → results →
      review → "Looks right" → a refused flag. Every step worked, with no JavaScript errors.
  - Not CI evidence, and no screenshots are attached: they would show holdout questions.

### Not met
- None.

### Deviations
- **Time on screen does not survive a restart.** The v2 ADR's `drafts` table has no column for it,
  so `time_taken_ms` is measured on the server between page views and kept in memory per session.
  A server restart mid-mock forgets the time measured before the restart. Answers, marks and the
  deadline are unaffected because they come from the database. No column was added, per "Must
  escalate"; see the question below.
- **Every new session gets an empty draft per question at start.** That makes it "a session with
  drafts and no `finished_at`", so it can be resumed from the first second, and the navigator can be
  drawn from the drafts.
- **A mock left past its deadline is submitted on the next request that touches it**, including
  the mock list, so it shows as an attempt rather than a stale Resume.
- **Choices left to the implementer:**
  - grace period 5 s;
  - one review page per finished session;
  - keyboard shortcuts a–h, m, n, p;
  - forms parsed with `urllib.parse`, so `python-multipart` is not needed;
  - pages before submit only receive a key-free `QuestionView`.
- **Bug found in the browser run, fixed.** Question IDs contain dots, which broke htmx targets like
  `#actions-101-102.3-0003`. The review now targets `closest .review-actions`, with a regression test.

### New decisions
- None.

### Questions for the planner
- **Time on screen.** Should results-database-v2 gain a time column on `drafts`, for example
  `time_ms INTEGER NOT NULL DEFAULT 0`, so on-screen time survives a restart? That would be a change
  to the Proposed ADR before it is accepted.
- **ADR acceptance.** results-database-v2 is still `Proposed`. When it's accepted, set
  `superseded_by` on `2026-10-25-results-database.md`.
- **httpx deprecation.** Starlette now warns that `TestClient` with `httpx` is deprecated in favour
  of `httpx2`. The dev dependency may need to move to `httpx2` when the handoff's "`httpx` may be
  added" is revisited.
