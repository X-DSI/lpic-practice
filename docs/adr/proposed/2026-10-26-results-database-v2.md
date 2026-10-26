---
title: Results database v2 — mock sessions, resumable drafts and holdout sign-off
status: Proposed
date: 2026-10-26
deciders: [X-DSI]
origin: web
supersedes: 2026-10-25-results-database.md
superseded_by: null
review: auto
---

## Context
The web mock exam needs three things the v1 layout (`2026-10-25-results-database.md`) can't hold:

- **Which mock a session was.** The results page and the mock list ("taken twice, best 612") need
  the mock ID, not just a mode.
- **Answers that change during the exam.** In a mock you can go back and change an answer before
  submitting. The `answers` table is append-only and feeds per-objective accuracy, so writing every
  change there would count one question several times. The work in progress also has to survive a
  page refresh or a server restart during a 90-minute exam.
- **Holdout sign-off.** The question-generation workflow ADR (point 8) says holdout questions are
  reviewed on the results screen after a mock, and that this review moves them to `approved`. The
  "looks right" verdict must be stored so it can go back to the planner, the same way flags do.

## Options
- **Extend the database (schema v2): a `mock_id` column, a `drafts` table and a `reviews` table** —
  one store for everything, migrated in place on open.
- **Keep drafts in server memory** — no schema change for drafts, but a restart loses a running exam.
- **Encode the mock in `sessions.mode` (e.g. `mock-03`)** — no column, but the mode field would
  carry two meanings and queries would parse strings.
- **Write sign-off straight into the content YAML from the web UI** — no export step, but the UI
  would edit the repository, and content changes must go through PRs.

## Decision
Schema version **2**. Everything in v1 stays as it is, plus:

| Change | Columns | Notes |
|---|---|---|
| `sessions.mock_id` (new nullable column) | TEXT | e.g. `101-mock-03`; NULL for practice. Mock sessions use `mode` = `mock` |
| `drafts` (new table) | `session_id` → `sessions.id`, `question_id`, `response` (JSON or NULL), `marked` (0/1), `updated_at`; PK `(session_id, question_id)` | In-progress mock answers. Overwritten freely. Deleted for a session when it is submitted |
| `reviews` (new table) | `id` INTEGER PK, `question_id`, `session_id` → `sessions.id`, `verdict`, `reviewed_at` | Append-only. `verdict` is `approved` for now. One "looks right" per question per session |

- **Submitting a mock** writes one `answers` row per question, in the mock's order, then deletes the
  session's drafts and sets `finished_at`, in one transaction. An unanswered question is stored with
  `response` = JSON `null` and `correct` = 0. `time_taken_ms` is the time the question was on screen,
  summed over visits.
- **Mock answers count towards per-objective accuracy** like practice answers, so the CLI's
  weak-areas drill picks up what a mock revealed.
- **A session with drafts and no `finished_at` is resumable.** The deadline is `started_at` plus
  the mock's `duration_minutes`. It is derived, not stored.
- **Sign-off goes back through an export.** `lpic reviews export` prints the reviews as YAML
  (`question_id`, `verdict`, `reviewed_at`), like `lpic flags export`. The planner adds the `human`
  history entry and sets `approved` in a content PR. A question that is both flagged and approved
  counts as flagged until the planner resolves it.
- `engine/store.py` migrates a v1 database to v2 on open and sets `schema_version` = `2`.

## Consequences
- One database, still owned by `engine/store.py`. The CLI keeps working unchanged against v2.
- A running mock survives refreshes, closed tabs and server restarts.
- Holdout questions reach `approved` only through a PR, so the repository stays the only source of
  content.
- This supersedes `2026-10-25-results-database.md`. When it is accepted, that ADR's
  `superseded_by` is set to this file.
