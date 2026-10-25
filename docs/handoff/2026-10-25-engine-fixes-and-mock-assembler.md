---
title: Engine fixes, pass2-ready mocks, and the mock assembler
status: done
assignee: X-DSI-agent
base_sha: ee19572
adrs:
  - 2026-10-22-mock-exam-composition.md
  - 2026-10-22-content-format-and-question-schema.md
  - proposed/2026-10-24-lpi-style-scoring.md
  - proposed/2026-10-25-question-generation-workflow.md
plan_pr: 7
impl_pr: 8
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

## Outcome
**Status:** done  
**Commits:** 62dafde..9578e09 (plus this Outcome) · **PR:** #8 ·
**CI run:** [https://github.com/X-DSI/lpic-practice/actions/runs/40171575982](https://github.com/X-DSI/lpic-practice/actions/runs/40171575982)

Drift check: `git diff ee19572..origin/main` touches only planning docs from PR #7 (both 2026-10-25
handoffs, `docs/STATUS.md`, a changelog fragment). `engine/`, `tools/`, `tests/`, `schemas/`,
`content/` and the ADRs this handoff depends on are unchanged.

### Verified acceptance criteria
All evidence is from the `Lint and test engine` and `Validate content` jobs of the CI run above
(86 tests passed on Python 3.12).
- [x] All tests pass, lint and format clean — `pytest`, `ruff check .` and `ruff format --check .`
      steps
- [x] Existing content still validates, strict included — `python tools/validate.py` in
      `Validate content`; both `validate.py` and `validate.py --strict` on the real `content/` in
      `tests/test_validate_cli.py::test_cli_flags_and_exit_code`
- [x] A single-choice response given as a list raises `TypeError` —
      `tests/test_matching.py::test_single_choice_rejects_a_non_string` (list, tuple, set, None)
- [x] Regex fill-in accepts `"ldconfig "` and `" ldconfig"` for pattern `ldconfig`, and still
      rejects `"sudoldconfig"` — `test_regex_ignores_outer_whitespace`,
      `test_regex_still_rejects_other_text` in `tests/test_matching.py`
- [x] `--strict` accepts a mock whose questions are all `pass2`, and rejects one with a `draft` or
      `pass1` question — `tests/test_validate_cli.py::test_strict_*`
- [x] On a synthetic bank the assembler writes 10 mocks that pass `validate --strict`, satisfy every
      constraint and are byte-identical across two runs with the same seed —
      `tests/test_assemble.py::test_writes_ten_mocks_that_pass_strict_validation`,
      `test_every_constraint_holds`, `test_same_seed_gives_byte_identical_files`
- [x] On a bank that is too small (including the real `content/`), the assembler exits non-zero,
      writes nothing, and names the shortfall — `test_objective_shortfall_writes_nothing`,
      `test_level_shortfall_names_the_level`, `test_real_content_today_is_too_small`,
      `test_an_infeasible_difficulty_mix_is_reported`
- [x] The difficulty table the assembler uses equals the table in `docs/difficulty-rubric.md` —
      `tests/test_assemble.py::test_difficulty_table_equals_the_rubric`

### Unverified (manual) criteria
- None.

### Not met
- None.

### Deviations
- None from the plan. Choices left to the implementer:
  - **Algorithm.** The assembler allocates counts per objective, mock and level. It starts from a
    ramp: each objective's questions, sorted by difficulty, are dealt to mocks 1…10. A first-improvement
    local search then swaps levels between mocks, or with an objective's unused questions, until every
    mock is within ±2. If that stalls it applies a few seeded random swaps and descends again, up to
    200 times. Seeded shuffles then pick concrete question IDs and the order inside each mock.
  - **Seed.** `--seed` defaults to 1.
  - **Difficulty table.** It is the constant `engine.assemble.DIFFICULTY_MIX`, checked against the
    rubric by a test, totals row included.
  - **Re-assembly.** The assembler validates content first, but ignores errors in the target exam's
    existing `mocks/` files so stale mocks can be replaced.
  - **Duration.** `duration_minutes` comes from the exam's `exam_format`; each mock's `title` is
    "Mock exam N".
- **Changelog.** One fragment, `.added.md`, covering the new command, the `--strict` change and the
  two fixes, since PROTOCOL §11 asks for one fragment per PR.

### Escalation check
Not triggered. A bank following the workflow ADR's split (`10 × weight` holdout per objective,
levels split by largest remainder, which gives 2 per level for weight 1) assembles within ±2 for the
real 101 and 102 weights:
- `test_the_real_exam_weights_with_the_adr_split_can_be_assembled`, with synthetic questions.
- That split produces bank-wide level totals of 99/141/145/120/95 (101) and 102/137/146/121/94 (102),
  against 98/132/144/128/98. The ±2 tolerance absorbs this.
- In addition, 60 randomly perturbed banks all assembled, each within 0.1 s. The starting ramp alone
  was out of tolerance in every one of them.

### New decisions
- None.

### Questions for the planner
- Per-objective rounding shifts level totals by up to 9 from the rubric's totals row (101, level 2:
  141 vs 132). That's fine with ±2 per mock, but the content PR summaries could report each topic's
  level totals so drift is visible before the bank is complete.
- `Validate content` in CI runs without `--strict`. Once real mocks are committed, it should
  probably run `--strict` too.
