---
title: Content build (YAML → JSON) and engine core — loading, answer matching, practice pool
status: open
assignee: agent:any
base_sha: 39155d7
adrs:
  - 2026-10-22-technology-stack.md
  - 2026-10-22-content-format-and-question-schema.md
  - 2026-10-22-mock-exam-composition.md
  - proposed/2026-10-23-all-or-nothing-scoring.md
plan_pr: 3
impl_pr: null
review: auto
---

## Goal
Give the project its first application code: a shared Python engine that loads the validated
question bank, compiles it to JSON for the interfaces, grades an answer to any question type, and
returns the practice pool. The CLI and web UI will be thin layers over this.

## Scope
**In:**
- A `pyproject.toml` making `engine/` an installable Python 3.12 package, with `pytest` and `ruff`
  as dev dependencies.
- **Loading** — read `content/<exam>/objectives.yaml` and `content/<exam>/questions/*.yaml` into
  typed objects (dataclasses or similar). `content/examples/` is not part of any exam bank.
- **Build** — a command that runs the existing validation, then writes one JSON file per exam to
  `build/content/<exam>.json` containing that exam's objectives, questions and mock manifests. It
  exits non-zero and writes nothing if validation fails.
- **Answer matching** — one function that takes a question and a response and returns correct or
  not, for all three types:
  - `single_choice`: the one selected option ID equals `answer[0]`.
  - `multi_choice`: all-or-nothing set equality (proposed scoring ADR).
  - `fill_in`, per `fill_in.match` and `fill_in.case_sensitive` (default `true`):
    - `exact` — string equality.
    - `normalized` — trim both ends and collapse internal runs of whitespace to one space, on both
      the response and each accepted answer, then compare.
    - `regex` — each accepted entry is a pattern that must match the **whole** response
      (`re.fullmatch`); `case_sensitive: false` adds `re.IGNORECASE`.
- **Practice pool** — a function returning the questions eligible for CLI drills for an exam,
  optionally filtered by objective: excludes `pool: holdout` and `retired: true`.
- Tests for all of the above, and a CI job running `ruff` and `pytest`.

**Out:** the Textual CLI, the web UI, SQLite, the mock assembler, results/weak-area reports,
running `verify` blocks in containers, and any content generation.

## Acceptance criteria
- [ ] `pip install -e ".[dev]"` installs the engine and dev tools — check: `pip install -e ".[dev]"`
- [ ] All tests pass — check: `pytest`
- [ ] Code is lint- and format-clean — check: `ruff check . && ruff format --check .`
- [ ] Existing content still validates — check: `python tools/validate.py`
- [ ] Single-, multi- and fill-in matching behave as specified, including: multi-choice subset and
      superset are wrong; `" ls   -i "` matches accepted `"ls -i"` under `normalized`; `"LS -I"`
      does not unless `case_sensitive: false`; a regex accepted answer does not match a response
      that merely contains it — check: `pytest tests/test_matching.py`
- [ ] Build writes `build/content/101.json` and `build/content/102.json`, and two consecutive builds
      produce byte-identical files — check: `pytest tests/test_build.py`
- [ ] Build exits non-zero and writes no files when content is invalid — check:
      `pytest tests/test_build.py`
- [ ] The practice pool never contains holdout or retired questions — check:
      `pytest tests/test_selection.py`
- [ ] CI runs `ruff` and `pytest` on pull requests — check: the impl PR's CI run shows both

## Constraints
- Runtime dependencies are limited to `pyyaml` and `jsonschema`. The engine **must not** import
  Textual, FastAPI or anything UI-related.
- `build/` stays git-ignored; never commit build output.
- `python tools/validate.py` keeps working with the same flags and exit codes, because CI and
  AGENTS.md call it.
- Tests use small fixture banks under `tests/`, not the real `content/` tree. Fixture questions must
  be obviously synthetic (no LPI-derived wording) and must not use the example IDs.
- Adding the CI job edits `.github/workflows/ci.yml`, which is code-owned: say so in the PR
  description, since it needs the maintainer's approval.

## Implementer may decide
- Package-internal module names and structure, and whether the build is `python -m engine.build`, a
  `tools/build.py` script, or both.
- Whether validation logic moves into `engine/` (with `tools/validate.py` becoming a thin wrapper)
  or stays where it is.
- The exact JSON layout of `build/content/<exam>.json`, as long as it's documented in a docstring or
  the README and sorted keys make it deterministic.

## Must escalate
- Any change to `schemas/` or to an Accepted ADR.
- Any change to the meaning of existing content files.
- Adding a runtime dependency beyond those listed.
- If the scoring ADR is still `Proposed` when you finish, implement it anyway and flag it in the
  Outcome; if it has been rejected, stop and ask.

## Attached content
None.
