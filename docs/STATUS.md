# Status

> This file will be generated from handoff frontmatter once agent-workflow's `status-generate`
> workflow exists. Until then it is updated by hand in each PR.

**Protocol version:** 0.2.0 (agent-workflow `v0.0.1-alpha`)

## Maintainer actions pending

- [ ] Protect `main` with a ruleset: require a pull request with 0 approvals, **Require review from
      Code Owners**, require the `ci` checks, block force pushes and deletions, bypass for the
      maintainer only.
- [ ] Turn on auto-merge and automatic branch deletion.
- [ ] Invite the agent machine account as a collaborator with the **Write** role.
- [ ] Ask `learning@lpi.org` whether publishing original questions keyed to their objectives is
      acceptable (open question in the content-licensing ADR).

## Open handoffs

| Handoff | Status | Assignee |
|---|---|---|
| [Content build and engine core](handoff/2026-10-23-build-and-engine-core.md) | open | agent:any |

## Proposed ADRs awaiting acceptance

| ADR | Needed by |
|---|---|
| [Score every question all-or-nothing](adr/proposed/2026-10-23-all-or-nothing-scoring.md) | build-and-engine-core handoff |
