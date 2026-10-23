---
title: Python monorepo with a Textual CLI, a FastAPI + htmx web UI and SQLite
status: Accepted
date: 2026-10-22
deciders: [X-DSI]
origin: web
supersedes: null
superseded_by: null
review: auto
---

## Context
The suite has two interfaces — terminal practice and a browser mock exam — over the same question
bank and the same scoring logic. It is a single-user tool run locally. Logic (answer matching,
scoring, weak-area analysis) must be identical in both interfaces, or results will disagree.

## Options
- **Python monorepo: Textual CLI, FastAPI + Jinja2 + htmx web, shared engine** — one language and
  one dependency tree; no frontend build step.
- **Next.js / React frontend** — second language and build toolchain; scoring would be duplicated in
  TS or exposed via an API contract. Revisit if the results dashboard needs heavy client-side
  interactivity, or if the app goes multi-user/public.
- **Svelte / TS built to static files** — lighter than Next.js but still adds a build step; not
  needed yet.
- **Separate repos for CLI and web** — schema and engine would drift between repos.
- **Anki for practice** — good spaced repetition; poor at timed, weighted mock exams and
  fill-in-the-blank command answers. An Anki export may be added later.

## Decision
One repository holds schema, content, engine and both interfaces:

| Part | Choice |
|---|---|
| Content authoring | YAML, compiled to JSON |
| Content contract | JSON Schema (draft 2020-12) |
| Engine (shared core) | Python 3.12 package, `engine/` |
| Terminal practice | Python + Textual (`cli/`) |
| Mock exam UI | FastAPI + Jinja2 templates + htmx, served locally (`web/`) |
| Results storage | SQLite, one local database shared by CLI and web |
| Tests / CI | pytest + GitHub Actions; content validated on every push |
| Docs | Markdown in the repo |

The browser needs JavaScript only for the 90-minute countdown timer and small UI touches; htmx
handles partial page swaps.

## Consequences
- One runtime (`python`), one dependency tree, no frontend build step.
- `lpic serve` (planned) starts the web UI; `lpic practice` (planned) the TUI.
- The interface layer is replaceable: a future SPA can call the same engine via an API without
  changing content or engine.
