---
title: Terminal practice app — drills, results storage, weak areas and question flagging
status: done
assignee: X-DSI-agent
base_sha: ee19572
adrs:
  - 2026-10-22-technology-stack.md
  - 2026-10-22-mock-exam-composition.md
  - proposed/2026-10-24-lpi-style-scoring.md
  - proposed/2026-10-25-question-generation-workflow.md
plan_pr: 7
impl_pr: 9
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

## Outcome
**Status:** done  
**Commits:** 36bb729..48fe9fc (plus this Outcome) · **PR:** #9 ·
**CI run:** [https://github.com/X-DSI/lpic-practice/actions/runs/40171913544](https://github.com/X-DSI/lpic-practice/actions/runs/40171913544)

Drift check: `git diff ee19572..origin/main` shows only planning PR #7 (this handoff, the
engine-fixes-and-mock-assembler handoff, `docs/STATUS.md` and a changelog fragment). No engine
code, schema or ADR changed, so the plan applies as written. `main` did not move while this was
being implemented, so no merge was needed.

### Verified acceptance criteria
- [x] All tests pass, lint and format clean — `Lint and test engine` job in the CI run above:
      `ruff check .`, `ruff format --check .`, 148 passed on Python 3.12
- [x] `pip install -e ".[dev]"` provides the `lpic` command — the job installs the package, then
      `tests/test_cli_main.py` runs the installed `lpic --help` and `lpic flags export`
- [x] No holdout or retired question can be served in any mode — `tests/test_practice.py`: every
      mode, 20 seeds each, over a bank where every objective also has holdout and retired questions
- [x] Mixed mode draws in proportion to weights, and weak-areas mode prefers the lowest-accuracy and
      unattempted objectives — `tests/test_practice.py`
- [x] Answers are stored and survive a restart; `LPIC_DB` overrides the path — `tests/test_store.py`
- [x] A flag with an over-long note or a URL is rejected; a valid flag appears in
      `lpic flags export` output — `tests/test_store.py`
- [x] A full session (answer each type, see feedback, flag one, reach the summary) works in the
      Textual app — `tests/test_cli_app.py` (Textual `run_test` pilot), including a refused flag
      with a link and a saved one

### Unverified (manual) criteria
- [x] The database layout is recorded as a Proposed ADR —
      `docs/adr/proposed/2026-10-25-results-database.md`

### Not met
- None.

### Deviations
- **PR opened from the maintainer's account.** This session's `gh` and SSH key belong to X-DSI, not
  `X-DSI-agent` (PROTOCOL §2). The maintainer chose to open the PR that way; merging needs the
  ruleset bypass, since nobody can approve their own PR. The branch pushes also came from X-DSI.
- Session logic is a new engine module, `engine/practice.py` (selection per mode, grading and
  storage through `PracticeSession`), so it is testable without the UI. No existing engine
  function changed.
- `lpic practice` validates the content before starting and exits with a message if it is invalid,
  because the loader assumes valid files.

### Decisions within "Implementer may decide"
- **Textual is a main dependency** (`textual>=8.0`), so `pip install -e ".[dev]"` gives a working
  `lpic`.
- **Mixed mode** apportions questions with Sainte-Laguë over the objectives that have practice
  questions: when the count equals the total weight, each objective gets exactly its weight.
- **Weak areas:** objectives never attempted, or below 80 % all-time accuracy, are weak; a drill uses
  the 3 weakest (never attempted first, then lowest accuracy), spread evenly, topped up from the next
  weakest if they run out. If nothing is below 80 %, the 3 lowest are used.
- **Choose-N questions** can only be submitted with exactly N options chosen; the app says how many.
- **Esc** ends a session early and shows the summary of what was answered.
- **URL rule for flag notes:** a scheme (`https://`, `ftp://`, …) or a `www.` host is refused;
  a bare domain such as `example.org` is allowed.
- **Keys:** Ctrl+S submit, `n` next, `f` flag, Esc end session, `r` new session, `q` quit.

### New decisions
- `docs/adr/proposed/2026-10-25-results-database.md` — the results database layout.

### Questions for the planner
- Accept the results-database ADR, or adjust it before the web UI builds on it.
- Is the 80 % / 3-objective weak-area rule what you want, or should it be tuned once real results
  exist?
- Should bare domains in flag notes also be refused?
