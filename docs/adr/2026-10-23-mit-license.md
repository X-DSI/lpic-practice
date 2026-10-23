---
title: License the code and original content under MIT
status: Accepted
date: 2026-10-23
deciders: [X-DSI]
origin: code
supersedes: null
superseded_by: null
review: auto
---

## Context
The content-licensing ADR (`2026-10-22-content-licensing-and-sources.md`) left the project's own
license open. The repository already carries an MIT `LICENSE` from its initial commit, and is
public. LPI material is never committed, so the license covers only the project's own code and
original questions.

## Options
- **MIT for code and content** — simplest, permissive, already in place.
- **MIT for code, CC BY 4.0 for content** — a content-specific license, but two licenses to explain.
- **No license yet** — all rights reserved; nobody can reuse anything.

## Decision
All code and original content in this repository is licensed under MIT (`LICENSE`, © X-DSI). This
settles the "license not yet chosen" point of the content-licensing ADR; its other rules stand.

## Consequences
- Others may reuse the questions and tooling with attribution.
- The license does not extend to the LPI Learning Materials, which stay out of the repository.
- The open question to `learning@lpi.org` remains open; if LPI objects, a superseding ADR decides
  what to change.
