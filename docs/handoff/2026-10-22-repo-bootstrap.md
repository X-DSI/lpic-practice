---
title: Repo bootstrap — ADRs, schemas, objectives, validator
status: done
assignee: X-DSI
base_sha: null
adrs:
  - 2026-10-22-technology-stack.md
  - 2026-10-22-content-format-and-question-schema.md
  - 2026-10-22-mock-exam-composition.md
  - 2026-10-22-content-licensing-and-sources.md
plan_pr: null
impl_pr: null
review: auto
---

## Goal
Record the first planning session's decisions and lay down the content contract: schemas,
objectives for 101 and 102, a difficulty rubric and a validator.

## Scope
**In:** ADRs for stack, content format, mock composition and licensing; JSON Schemas v1;
`content/101` and `content/102` objectives; difficulty rubric; `tools/validate.py` with examples.  
**Out:** Application code (`engine/`, `cli/`, `web/`), real questions, the YAML → JSON build.

## Acceptance criteria
- [x] The validator exits 0 on `content/` — check: `python tools/validate.py`
- [x] Each exam's objective weights sum to 60 — check: `python tools/validate.py`
- [x] Invalid examples are rejected with clear messages — check: manual

## Constraints
No text from the LPI Learning Materials enters the repository.

## Implementer may decide
Validator internals and error wording.

## Must escalate
Any change to the schemas or ADRs.

## Attached content
`schemas/`, `content/101/objectives.yaml`, `content/102/objectives.yaml`, `content/examples/`,
`docs/difficulty-rubric.md`, `tools/validate.py`.

## Outcome
**Status:** done  
**Commits:** imported from the planning session's local repository · **PR:** see the import PR ·
**CI run:** the `content` job on the import PR

### Verified acceptance criteria
- [x] The validator exits 0 on `content/` — `python tools/validate.py` runs in CI on the import PR
- [x] Each exam's objective weights sum to 60 — checked by the same run

### Unverified (manual) criteria
- [x] Invalid examples are rejected with clear messages — checked on import by breaking a copy of
      the content (bad answer ID, weights summing to 61): the validator exited 1 naming both
      problems. No negative fixtures are committed, so CI does not verify this

### Not met
- None.

### Deviations
- Done in the web planning session, then imported into this repository when it adopted
  agent-workflow. On import, ADRs were renamed to the dated format, `schema/` was renamed to
  `schemas/` (PROTOCOL §10), and the provisional handoff protocol and ADR-0001 were dropped in
  favour of `docs/PROTOCOL.md` and the adopt-agent-workflow ADR.
- Objective weights and lesson counts were extracted from the LPI Learning Materials PDFs (101-500
  material version 2025-03-12; 102-500 material version 2024-12-27) and match the totals of 60.

### New decisions
- None.

### Questions for the planner
- Next likely handoff: build pipeline (YAML → JSON) and `engine/` skeleton with answer matching,
  once the first objective's questions exist.
