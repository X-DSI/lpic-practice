---
title: Terminal practice app — drills, results storage, weak areas and question flagging
status: open
assignee: agent:any
base_sha: ee19572
adrs:
  - 2026-10-22-technology-stack.md
  - 2026-10-22-mock-exam-composition.md
  - proposed/2026-10-24-lpi-style-scoring.md
  - proposed/2026-10-25-question-generation-workflow.md
plan_pr: 7
impl_pr: null
review: auto
---

## Goal
Give the maintainer a terminal app to study with: drill practice questions by objective, a weighted
mix, or weak areas; get feedback with rationales after each answer; and flag questions that look
wrong so they come back to the planner as a fix list.

## Scope
**In:**
- An `lpic` command (a console entry point in `pyproject.toml`) with:
  - `lpic practice` — a Textual app. Choose the exam (101 / 102), a mode, and a question count
    (default 10):
    - **objective** — questions from one chosen objective;
    - **mixed** — questions drawn across objectives in proportion to their weights;
    - **weak areas** — questions from the objectives with the lowest accuracy so far; objectives
      with no attempts count as weak.
  - `lpic flags export` — prints all flags as YAML to stdout (see below).
- **Questions come only from `engine.selection.practice_pool`** — never holdout, never retired.
- **Answering** all three types: choose one, choose N (the app says how many), type an answer.
  Grading uses `engine.matching.is_correct`.
- **Feedback after each answer**: correct or not, the correct option(s) or accepted answer, the
  rationale for every option, and the explanation.
- **End-of-session summary**: score and per-objective breakdown via `engine.scoring` (raw
  percentage; no 200–800 scale for practice).
- **Results storage** in SQLite, in a new `engine/store.py` so the web UI can share it later:
  every answer (question ID, response, correct, time taken, timestamp, session). Default path
  `$XDG_DATA_HOME/lpic-practice/results.sqlite` (falling back to `~/.local/share/…`), overridable
  with `LPIC_DB`.
- **Flagging** from the feedback screen: a reason from a fixed list — `wrong-answer`, `ambiguous`,
  `typo`, `outdated`, `other` — and an optional note of at most 200 characters with no URLs
  (PROTOCOL §9). Stored in the same database. `lpic flags export` emits a list of
  `{question_id, reason, note, flagged_at}`.
- Tests, and a **Proposed ADR** (`docs/adr/proposed/`) recording the database layout, since the
  web UI will build on it.

**Out:** mock exams and the web UI, the 200–800 scale in practice, spaced repetition, syncing
results anywhere, any change to how questions are written.

## Acceptance criteria
- [ ] All tests pass, lint and format clean — check: `pytest && ruff check . && ruff format --check .`
- [ ] `pip install -e ".[dev]"` provides the `lpic` command — check: `lpic --help`
- [ ] No holdout or retired question can be served in any mode — check: `pytest tests/test_practice.py`
- [ ] Mixed mode draws in proportion to weights, and weak-areas mode prefers the lowest-accuracy and
      unattempted objectives — check: `pytest tests/test_practice.py`
- [ ] Answers are stored and survive a restart; `LPIC_DB` overrides the path — check:
      `pytest tests/test_store.py`
- [ ] A flag with an over-long note or a URL is rejected; a valid flag appears in
      `lpic flags export` output — check: `pytest tests/test_store.py`
- [ ] A full session (answer each type, see feedback, flag one, reach the summary) works in the
      Textual app — check: `pytest tests/test_cli_app.py` (Textual's `run_test` pilot)
- [ ] The database layout is recorded as a Proposed ADR — check: manual

## Constraints
- `engine/` must not import Textual; the app lives in `cli/`. Session logic (selection, grading,
  storage) is testable without the UI.
- Textual is the only new runtime dependency.
- Tests use synthetic fixture banks and a temporary database, never the real `content/` or the
  user's database.
- Another implementer is working on engine fixes and the mock assembler in parallel (handoff
  `2026-10-25-engine-fixes-and-mock-assembler.md`). Don't modify `engine/matching.py`,
  `engine/validation.py` or `tools/validate.py`; expect to merge `main` if `pyproject.toml`,
  `AGENTS.md`, `README.md` or `docs/STATUS.md` change under you.
- Add the new commands to the AGENTS.md command table and the README.

## Implementer may decide
- Screen layout, key bindings and styling (keyboard-first; it should be usable without a mouse).
- Database table design (recorded in the Proposed ADR), the weak-area threshold and how many
  objectives it picks.
- Whether Textual is a main dependency or an optional `cli` extra.

## Must escalate
- Any change to `schemas/`, to an Accepted ADR, or to the public behaviour of existing engine
  functions.

## Attached content
None. The real practice pool is small for now (5 questions for 102.3); the topic 101 batch is being
written in parallel.
