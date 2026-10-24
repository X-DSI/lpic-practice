# Status

> This file will be generated from handoff frontmatter once agent-workflow's `status-generate`
> workflow exists. Until then it is updated by hand in each PR.

**Protocol version:** 0.2.0 (agent-workflow `v0.0.1-alpha`)

## Maintainer actions pending

- [x] Protect `main` with a ruleset (PR required, 0 approvals, Code Owner review, no force pushes or
      deletions) — active since 2026-10-23.
- [ ] Add `Validate content` to the ruleset's required status checks. Only
      `commit-identity / Commit identity` is required today, so invalid content could still merge.
- [ ] Confirm the ruleset's bypass list contains only the maintainer (not visible to the agent
      account).
- [x] Turn on auto-merge and automatic branch deletion.
- [x] Invite the agent machine account (`X-DSI-agent`) as a collaborator with the **Write** role.
- [ ] Ask `learning@lpi.org` whether publishing original questions keyed to their objectives is
      acceptable (open question in the content-licensing ADR).

## Open handoffs

| Handoff | Status | Assignee |
|---|---|---|
| [Content build and engine core](handoff/2026-10-23-build-and-engine-core.md) | in-progress | X-DSI-agent |

## Proposed ADRs awaiting acceptance

| ADR | Needed by |
|---|---|
| [Score like LPI — all-or-nothing items, 200–800 scale, 500 to pass](adr/proposed/2026-10-24-lpi-style-scoring.md) | build-and-engine-core handoff |
