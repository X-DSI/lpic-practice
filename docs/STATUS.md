# Status

> This file will be generated from handoff frontmatter once agent-workflow's `status-generate`
> workflow exists. Until then it is updated by hand in each PR.

**Protocol version:** 0.2.0 (agent-workflow `v0.0.1-alpha`)

## Maintainer actions pending

- [x] Protect `main` with a ruleset (PR required, 0 approvals, Code Owner review, no force pushes or
      deletions) — active since 2026-10-23.
- [x] Add `Validate content` and `Lint and test engine` to the ruleset's required status checks
      (2026-10-26).
- [x] Confirm the ruleset's bypass list contains only the maintainer (2026-10-26).
- [x] Turn on auto-merge and automatic branch deletion.
- [x] Invite the agent machine account (`X-DSI-agent`) as a collaborator with the **Write** role.
- [x] ~~Ask `learning@lpi.org` about publishing original questions~~ — not needed: the bank uses
      original wording only (maintainer, 2026-10-26).

## Open handoffs

- [Web mock exam](handoff/2026-10-26-web-mock-exam.md) (in progress, X-DSI-agent) — timed mocks, LPI-style results, weak
  areas and holdout review (`lpic serve`).

Done: [Content build and engine core](handoff/2026-10-23-build-and-engine-core.md) (PR #5),
[Engine fixes, pass2-ready mocks, and the mock assembler](handoff/2026-10-25-engine-fixes-and-mock-assembler.md) (PR #8),
[Terminal practice app](handoff/2026-10-25-practice-cli.md) (PR #9; its Outcome has questions for the planner).

## Proposed ADRs awaiting acceptance

| ADR | Needed by |
|---|---|
| [Results database v2 — mock sessions, resumable drafts and holdout sign-off](adr/proposed/2026-10-26-results-database-v2.md) | web mock exam handoff |

## Question bank

| Exam | Objectives done | Questions | Target |
|---|---|---|---|
| 101 | all topics complete (101–104); 10 mocks assembled (seed 1) | 900 (600 holdout, 300 practice) | 900 (600 holdout, 300 practice) |
| 102 | — | 0 | 900 |
