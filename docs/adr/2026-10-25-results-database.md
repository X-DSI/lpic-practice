---
title: Store practice results and question flags in one local SQLite database with a fixed layout
status: Accepted
date: 2026-10-25
deciders: [X-DSI]
origin: code
supersedes: null
superseded_by: null
review: auto
---

## Context
The terminal practice app records every answer and every question flag, and the web UI will read
and write the same data later (technology-stack ADR: one local SQLite database shared by CLI and
web). Weak-area drills need per-objective accuracy across sessions. The question-generation
workflow ADR makes flags the fix list that goes back to the planner. Whatever layout the CLI
writes first is what the web UI inherits, so it needs to be written down.

## Options
- **Three tables (sessions, answers, flags) plus a `meta` table with a schema version** — one row
  per event, queries stay simple, and later changes can be migrated by version.
- **One wide table of events** — fewer tables, but sessions and flags have different fields, so most
  columns would be empty.
- **JSON lines files** — no database, but weak-area queries and a future web UI would have to
  re-read everything.

## Decision
`engine/store.py` owns the database. Its path is `$LPIC_DB`, else
`$XDG_DATA_HOME/lpic-practice/results.sqlite`, else `~/.local/share/lpic-practice/results.sqlite`.
Every write commits immediately. Timestamps are UTC ISO 8601 strings with seconds
(`2026-10-25T09:30:00+00:00`).

| Table | Columns | Notes |
|---|---|---|
| `meta` | `key` TEXT PK, `value` TEXT | `schema_version` = `1` |
| `sessions` | `id` INTEGER PK, `exam`, `mode`, `started_at`, `finished_at` (NULL until finished) | `mode`: `objective`, `mixed` or `weak` for practice; the web UI adds its own modes |
| `answers` | `id` INTEGER PK, `session_id` → `sessions.id`, `question_id`, `exam`, `objective`, `response`, `correct` (0/1), `time_taken_ms`, `answered_at` | `response` is JSON: a string for `single_choice` and `fill_in`, a sorted list for `multi_choice`. `exam` and `objective` are copied from the question ID so accuracy queries need no content. Index on `(exam, objective)` |
| `flags` | `id` INTEGER PK, `question_id`, `reason`, `note` (NULL if none), `flagged_at` | `reason` ∈ `wrong-answer`, `ambiguous`, `typo`, `outdated`, `other`; `note` at most 200 characters, no URLs (PROTOCOL §9), checked before insert |

- Answers are append-only. Accuracy is computed from all answers ever given, per exam and objective.
- Flags are append-only. `lpic flags export` prints them as YAML (`question_id`, `reason`, `note`,
  `flagged_at`) for the planner.
- A change to this layout bumps `schema_version` and is recorded in a superseding ADR, with
  `engine/store.py` migrating older databases on open.

## Consequences
- The web UI can reuse `engine/store.py` as is. Mock-exam sessions go in the same tables with their
  own `mode`.
- Weak-area selection is a single grouped query.
- Results stay on the user's machine; syncing or backup is out of scope.
- Copying `exam` and `objective` into `answers` duplicates what the question ID already says. If a
  question ever moved objective, which question-ID permanence rules out, old answers would keep the
  old objective.
