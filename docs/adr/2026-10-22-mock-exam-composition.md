---
title: Mock exams are fixed, weight-matched, difficulty-ramped manifests drawn from a holdout pool
status: Accepted
date: 2026-10-22
deciders: [X-DSI]
origin: web
supersedes: null
superseded_by: null
review: auto
---

## Context
Each exam gets 10 mock exams of 60 questions in 90 minutes, from easiest (mock 1) to hardest
(mock 10). Results must show weak areas by objective. For the scores to mean anything, the mocks must
resemble the real exam's topic coverage, and the questions must not be ones already practised in
the terminal.

In LPIC exams, objective weights sum to 60, so a weight is roughly the number of questions that
objective contributes.

## Options
- **Fixed topic mix, ramped difficulty, holdout manifests** — comparable attempts, honest scores.
- **Random 60 from the bank each time** — not comparable between attempts; no difficulty ramp.
- **Harder mocks over-sample hard topics** — confuses "hard exam" with "uneven coverage".
- **Shared pool for practice and mocks** — mock scores inflated by memorisation.

## Decision
1. **Topic mix is fixed; only difficulty ramps.** Every mock contains exactly `weight` questions per
   objective. Mock 10 is harder because its questions are harder, not because it over-samples hard
   topics.
2. **Difficulty mix per mock** follows the table in `docs/difficulty-rubric.md` (mock 1 mostly
   levels 1–2, mock 10 mostly 4–5). The assembler may deviate by at most ±2 per level when the bank
   can't satisfy it exactly.
3. **Mocks are manifests.** A mock file lists 60 question IDs; questions live once in the bank.
   Fixing a question fixes it everywhere.
4. **Holdout pool.** Mock questions have `pool: holdout` and are excluded from CLI drills. After a
   mock is taken, its questions can be unlocked for review.
5. **Unique across mocks.** No question appears in two mocks of the same exam: 600 holdout questions
   per exam, `10 × weight` per objective.
6. **Assembly is deterministic** (seeded) and the resulting manifests are committed, so each mock is
   fixed, reviewable and versioned.
7. **Scoring.** Raw percentage plus per-topic, per-objective, per-type and time-per-question
   breakdowns. A pass estimate uses 500/800 on a linear scale and is labelled as an estimate — LPI's
   real scaling is not public.

## Consequences
- Content target per exam: 600 holdout questions plus a separate practice pool (initial target:
  5 per weight point = 300 per exam; to be revisited).
- Holdout difficulty per objective should roughly follow the overall level split
  (98 / 132 / 144 / 128 / 98 across levels 1–5) so assembly is feasible.
