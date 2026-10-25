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

None. [Content build and engine core](handoff/2026-10-23-build-and-engine-core.md) is done
(PR #5); its Outcome has questions for the planner.

## Proposed ADRs awaiting acceptance

| ADR | Needed by |
|---|---|
| [Score like LPI — all-or-nothing items, 200–800 scale, 500 to pass](adr/proposed/2026-10-24-lpi-style-scoring.md) | build-and-engine-core handoff |
| [Generate questions one objective per PR, two recorded checks, human sign-off](adr/proposed/2026-10-25-question-generation-workflow.md) | every content PR |

## Question bank

| Exam | Objectives done | Questions | Target |
|---|---|---|---|
| 101 | 102.3 (in review) | 15 (10 holdout, 5 practice) | 900 (600 holdout, 300 practice) |
| 102 | — | 0 | 900 |
