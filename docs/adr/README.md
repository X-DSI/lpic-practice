# Architecture Decision Records

Decisions about lpic-practice. Format and rules: [`docs/PROTOCOL.md` §5](../PROTOCOL.md#5-architecture-decision-records).
Accepted decisions live here; proposals live in [`proposed/`](proposed/).

| Date | Decision | Status |
|---|---|---|
| 2026-10-22 | [Python monorepo with a Textual CLI, a FastAPI + htmx web UI and SQLite](2026-10-22-technology-stack.md) | Accepted |
| 2026-10-22 | [Author content as YAML validated by JSON Schema, one question file per objective](2026-10-22-content-format-and-question-schema.md) | Accepted |
| 2026-10-22 | [Mock exams are fixed, weight-matched, difficulty-ramped manifests drawn from a holdout pool](2026-10-22-mock-exam-composition.md) | Accepted |
| 2026-10-22 | [Original questions only; LPI Learning Materials never enter the repository](2026-10-22-content-licensing-and-sources.md) | Accepted |
| 2026-10-23 | [Adopt the agent-workflow protocol for this project](2026-10-23-adopt-agent-workflow.md) | Accepted |
| 2026-10-23 | [License the code and original content under MIT](2026-10-23-mit-license.md) | Accepted |
| 2026-10-24 | [Score like LPI — all-or-nothing items, 200–800 scale, 500 to pass](2026-10-24-lpi-style-scoring.md) | Accepted |
| 2026-10-25 | [Generate questions in topic-sized batches, checked by the writer and an independent agent, signed off in use](2026-10-25-question-generation-workflow.md) | Accepted |
| 2026-10-25 | [Store practice results and question flags in one local SQLite database](2026-10-25-results-database.md) | Accepted |
