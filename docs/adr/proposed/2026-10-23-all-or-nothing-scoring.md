---
title: Score every question all-or-nothing, including multiple-answer questions
status: Proposed
date: 2026-10-23
deciders: [X-DSI]
origin: web
supersedes: null
superseded_by: null
review: auto
---

## Context
The engine needs a scoring rule before it can grade anything. Single-choice and fill-in questions
are naturally right or wrong, but `multi_choice` ("choose two") could award partial credit. LPI does
not publish how it scores individual items. Mock scores are meant to estimate exam readiness
(mock-exam-composition ADR), so the rule should not flatter the candidate.

## Options
- **All-or-nothing** — a multi-choice answer scores 1 only if the selected set equals the answer
  set exactly. Simple, conservative, and matches how candidates are told to treat these items.
- **Partial credit** (e.g. correct picks minus wrong picks, floored at 0) — rewards near-misses,
  which inflates mock scores and hides the exact gap the weak-area report should expose.
- **Partial credit in practice, all-or-nothing in mocks** — two rules to explain and test; drills
  and mocks would disagree on what "correct" means.

## Decision
Every question scores 0 or 1. A `multi_choice` answer is correct only when the set of selected
option IDs equals the set in `answer` — no more, no fewer. Order does not matter. The same rule
applies in CLI practice and in mock exams.

## Consequences
- Scoring is one function shared by both interfaces, with no weighting per item.
- A candidate who picks one of two correct options gets no credit; the results view should show
  which options were right, so the near-miss is still visible as feedback.
- If LPI ever documents partial credit, a superseding ADR changes one function.
