# Status

> This file will be generated from handoff frontmatter once agent-workflow's `status-generate`
> workflow exists. Until then it is updated by hand in each PR.

**Protocol version:** 0.2.0 (agent-workflow `v0.0.1-alpha`)

## Maintainer actions pending

- [x] Protect `main` with a ruleset (PR required, 0 approvals, Code Owner review, no force pushes or
      deletions) — active since 2026-10-23.
- [ ] Add `Validate content` and `Lint and test engine` to the ruleset's required status checks.
      Only `commit-identity / Commit identity` is required today, so invalid content or failing
      tests could still merge.
- [ ] Confirm the ruleset's bypass list contains only the maintainer (not visible to the agent
      account).
- [x] Turn on auto-merge and automatic branch deletion.
- [x] Invite the agent machine account (`X-DSI-agent`) as a collaborator with the **Write** role.
- [ ] Ask `learning@lpi.org` whether publishing original questions keyed to their objectives is
      acceptable (open question in the content-licensing ADR).

## Open handoffs

None.

Done: [Content build and engine core](handoff/2026-10-23-build-and-engine-core.md) (PR #5),
[Engine fixes, pass2-ready mocks, and the mock assembler](handoff/2026-10-25-engine-fixes-and-mock-assembler.md) (PR #8),
[Terminal practice app](handoff/2026-10-25-practice-cli.md) (PR #9; its Outcome has questions for the planner).

## Proposed ADRs awaiting acceptance

| ADR | Needed by |
|---|---|
| [Score like LPI — all-or-nothing items, 200–800 scale, 500 to pass](adr/proposed/2026-10-24-lpi-style-scoring.md) | build-and-engine-core handoff |
| [Results database: sessions, answers and flags in one SQLite file](adr/proposed/2026-10-25-results-database.md) | web UI |
| [Generate questions in topic-sized batches, checked by the writer and an independent agent, signed off in use](adr/proposed/2026-10-25-question-generation-workflow.md) | every content PR |

## Question bank

| Exam | Objectives done | Questions | Target |
|---|---|---|---|
| 101 | topics 101 and 102 complete (101.1–101.3, 102.1–102.6); topic 103 in progress | 300 (200 holdout, 100 practice) | 900 (600 holdout, 300 practice) |
| 102 | — | 0 | 900 |
