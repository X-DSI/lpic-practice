---
title: Engine fixes, pass2-ready mocks, and the mock assembler
status: in-progress
assignee: X-DSI-agent
base_sha: ee19572
adrs:
  - 2026-10-22-mock-exam-composition.md
  - 2026-10-22-content-format-and-question-schema.md
  - proposed/2026-10-24-lpi-style-scoring.md
  - proposed/2026-10-25-question-generation-workflow.md
plan_pr: 7
impl_pr: null
review: auto
---

## Goal
Fix two answer-matching gaps found on the first real batch, let mocks use questions that passed
both checks, and build the assembler that turns the holdout bank into the 10 graded mock exams.

## Scope
**In:**
- **Matching fixes** in `engine/matching.py`:
  - `single_choice`: a response that is not a `str` raises `TypeError`, as `multi_choice` and
    `fill_in` already do for the wrong type. (Today a list like `["b"]` is silently wrong.)
  - `regex` fill-in: strip leading and trailing whitespace from the response before `re.fullmatch`.
    Internal whitespace is left alone; patterns handle it with `\s+`.
- **`--strict`** in `tools/validate.py` / `engine/validation.py`: mock questions must have
  `review.status` of `pass2` **or** `approved` (workflow ADR point 9), instead of `approved` only.
  Update the help text and the AGENTS.md command table.
- **Mock assembler**: `python -m engine.assemble <exam> [--seed N]` writes
  `content/<exam>/mocks/mock-01.yaml` … `mock-10.yaml`, valid against `schemas/mock-exam.schema.json`,
  following the mock-exam-composition ADR:
  - each mock has exactly `weight` questions from every objective (60 in total);
  - no question appears in more than one mock of the same exam;
  - eligible questions: `pool: holdout`, not `retired`, `review.status` `pass2` or `approved`;
  - each mock's difficulty counts are within ±2 per level of the table in
    `docs/difficulty-rubric.md`, and `difficulty_mix` records that table's row;
  - the same bank and seed always produce byte-identical files, and `assembly_seed` records the seed.
  - If the bank cannot satisfy every constraint, the assembler exits non-zero, writes **no** files,
    and prints what is missing per objective and difficulty level.
- Tests for all of the above.

**Out:** generating questions, committing assembled mocks for the real bank (it is far from
complete), the web UI, results storage.

## Acceptance criteria
- [ ] All tests pass, lint and format clean — check: `pytest && ruff check . && ruff format --check .`
- [ ] Existing content still validates, strict included — check:
      `python tools/validate.py && python tools/validate.py --strict`
- [ ] A single-choice response given as a list raises `TypeError` — check: `pytest tests/test_matching.py`
- [ ] Regex fill-in accepts `"ldconfig "` and `" ldconfig"` for pattern `ldconfig`, and still rejects
      `"sudoldconfig"` — check: `pytest tests/test_matching.py`
- [ ] `--strict` accepts a mock whose questions are all `pass2`, and rejects one with a `draft` or
      `pass1` question — check: `pytest tests/test_validate_cli.py`
- [ ] On a synthetic fixture bank with enough holdout questions, the assembler writes 10 mocks that
      pass `validate --strict`, satisfy every constraint above, and are byte-identical across two runs
      with the same seed — check: `pytest tests/test_assemble.py`
- [ ] On a bank that is too small (including the real `content/` today), the assembler exits non-zero,
      writes nothing, and names the shortfall — check: `pytest tests/test_assemble.py`
- [ ] The difficulty table the assembler uses equals the table in `docs/difficulty-rubric.md` — check:
      `pytest tests/test_assemble.py`

## Constraints
- No new runtime dependencies (no ILP solver). A deterministic greedy or backtracking search is fine.
- The difficulty table has one source of truth. Either parse it from `docs/difficulty-rubric.md` or
  keep a constant with a test that compares it to the document.
- Do not change `schemas/`.
- Fixture banks are synthetic, under `tests/`, and don't use example IDs (9000+).
- Another implementer is working on the practice CLI in parallel (handoff
  `2026-10-25-practice-cli.md`). Don't touch `cli/` or `engine/store.py`; expect to merge `main` if
  `pyproject.toml`, `AGENTS.md`, `README.md` or `docs/STATUS.md` change under you.

## Implementer may decide
- The search algorithm, module layout, and the order of questions inside a mock (it must be
  deterministic; avoid grouping all of one objective together if easy).
- Whether `--seed` has a default, and what it is.

## Must escalate
- Any change to `schemas/` or to an Accepted ADR.
- If the ±2 tolerance or the difficulty table make assembly infeasible even for a bank that follows
  the workflow ADR's per-objective split, stop and report the numbers.

## Attached content
None.
