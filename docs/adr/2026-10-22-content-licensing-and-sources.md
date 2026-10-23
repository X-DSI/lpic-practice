---
title: Original questions only; LPI Learning Materials never enter the repository
status: Accepted
date: 2026-10-22
deciders: [X-DSI]
origin: web
supersedes: null
superseded_by: null
review: auto
---

## Context
The question bank is derived from study of the LPI Learning Materials, which are licensed
**CC BY-NC-ND 4.0**. This project is non-commercial, which satisfies NC. **ND (NoDerivatives)**
separately forbids *sharing* adapted versions of the material. The repository is intended to be
public.

Facts, commands and exam objectives are not copyrightable; LPI's wording, exercises and
explanations are.

## Options
Not recorded when this decision was made in the planning session.

## Decision
- LPI PDFs and any text extracted from them live only in `sources/`, which is gitignored, or in the
  private claude.ai Project. They are never committed.
- Every question, option, rationale and explanation is written originally. LPI's Guided and
  Explorational Exercises are not copied or closely paraphrased, even with attribution.
- Each question carries a `source` reference (material, version, objective, lesson) so it can be
  checked against the lesson without reproducing it.
- The README carries attribution to LPI and a non-affiliation notice.
- Open question: confirm with `learning@lpi.org` that publishing original questions keyed to their
  objectives is acceptable. Until answered, the repo may stay private.
- The project's own license (code and original content) is not yet chosen.

## Consequences
- Verification pass 1 includes an originality check: if a question reads like a restatement of an
  exercise, it is rewritten.
- Anyone cloning the repo must obtain the LPI materials themselves to follow the source references.
