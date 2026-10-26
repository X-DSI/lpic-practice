---
title: Score like LPI — all-or-nothing items, results on the 200–800 scale with 500 to pass
status: Accepted
date: 2026-10-24
deciders: [X-DSI]
origin: web
supersedes: null
superseded_by: null
review: auto
---

## Context
The engine needs a scoring rule, and the maintainer asked for it to follow LPI's own system where
that is practical. What LPI says publicly, and what it doesn't:

| Aspect | What is known | Source quality |
|---|---|---|
| Score scale | 200–800, 500 is a pass | Official (LPI FAQ, repeated by LPI partners) |
| Pass mark | Set by psychometric studies; the number of correct answers needed "depends on the combination of questions" | Official |
| Raw → scaled conversion | Not published | — |
| Item weighting | Not published; objective weights sum to 60 and set how many questions each objective gets | Official for objectives; items unknown |
| Partial credit on "choose N" items | Not published by LPI; independent prep guides say there is none | Unofficial |
| Fill-in-the-blank | Compared against a fixed list of accepted strings | Unofficial |

So LPI's per-question rule can be matched, but its conversion to a scaled score cannot: it is
equated per exam form from candidate data we don't have. The mock-exam-composition ADR (point 7)
currently estimates a pass with a linear 200–800 mapping, which puts 500 at exactly 50% raw — very
likely more lenient than the real exam.

## Options
- **All-or-nothing items, linear 200–800 mapping** — simplest, but 50% raw "passes", which flatters.
- **All-or-nothing items, piecewise mapping with a conservative pass point** — shows the same
  numbers LPI's score report shows, while refusing to call a weak result a pass.
- **Partial credit on multi-answer items** — rewards near-misses, inflates mock scores, and is
  probably not what LPI does.
- **Raw percentage only** — honest, but doesn't look like the score report candidates will get.

## Decision
1. **Items score 0 or 1.** `single_choice`: the chosen option is the answer. `multi_choice`: the
   chosen set equals the answer set exactly — no more, no fewer; order doesn't matter.
   `fill_in`: the response matches an accepted answer under the question's match mode. The same
   rule applies to CLI practice and mock exams.
2. **Every item counts the same.** Raw score = correct ÷ questions. Because each objective gets
   `weight` questions, its share of the score equals its weight.
3. **Mock results are reported on LPI's scale** with a piecewise-linear mapping through a pass point
   `P` (fraction of questions correct):
   - raw ≤ P: `scaled = 200 + 300 × raw / P`
   - raw > P: `scaled = 500 + 300 × (raw − P) / (1 − P)`
   - rounded to the nearest integer, except that a result below `P` is capped at 499, so rounding
     can never show 500 for a score under the pass point (e.g. 37/57 would otherwise round to 500);
   - `scaled ≥ 500` is shown as a likely pass, which is then always the same as `raw ≥ P`.
4. **`P = 0.65`**, held as one named constant in the engine. This is our assumption, not LPI's
   number: it sits above the 50% a linear mapping implies and errs towards caution. It can be
   changed in one place if better information appears.
5. **The raw percentage is always shown next to the scaled score**, and the scaled score is labelled
   an estimate.
6. This replaces point 7 ("Scoring") of `2026-10-22-mock-exam-composition.md`. The rest of that ADR
   stands.

## Consequences
- One scoring function and one mapping function, shared by CLI and web.
- Picking one of two correct options earns nothing; the results view should still show which options
  were right, so the near-miss is visible as feedback.
- With P = 0.65, a mock passes at 39 of 60 correct (0.65 × 60 = 39.0 → scaled 500).
- When this ADR is accepted, the mock-exam-composition ADR needs a note pointing here for point 7.
  The protocol has no "partially superseded" status yet; see the PR for that question.
