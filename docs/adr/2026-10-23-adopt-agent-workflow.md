---
title: Adopt the agent-workflow protocol for this project
status: Accepted
date: 2026-10-23
deciders: [X-DSI]
origin: code
supersedes: null
superseded_by: null
review: auto
---

## Context
lpic-practice will be planned in chat sessions and implemented by coding agents. Without a shared
record, decisions made in one session are invisible to the next, and the maintainer ends up copying
context between tools.

## Options
- **No formal process** — least ceremony, but decisions live only in chat transcripts.
- **A long CLAUDE.md** — reaches one agent only and mixes instructions with decisions.
- **Adopt X-DSI/agent-workflow** — the repo is the shared memory, PRs are the transport, and CI
  enforces the mechanical rules; costs a few files and a pinned dependency on that repo.

## Decision
Adopt agent-workflow, pinned to `v0.0.1-alpha` (protocol 0.2.0). The project keeps a copy of
`docs/PROTOCOL.md`, records decisions under `docs/adr/`, hands work over through `docs/handoff/`,
gates rule-bearing paths with `.github/CODEOWNERS`, and calls agent-workflow's reusable
`commit-identity` workflow from CI.

## Consequences
- Every change arrives as a pull request; decisions are recorded as ADRs when made.
- Protocol and workflow updates are pulled in deliberately by bumping the pinned tag (later via
  `copier update`).
- The maintainer must configure the `main` ruleset (PR required, Code Owners review, required CI)
  and an agent machine account before the guardrails are fully in force.
