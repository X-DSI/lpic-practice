# lpic-practice

A practice suite for the Linux Professional Institute LPIC-1 (101-500, 102-500) and,
later, LPIC-2 (201, 202) exams.

- **Terminal practice** — drill questions by objective, with weak-area targeting.
- **Browser mock exams** — 10 timed mock exams per exam (60 questions, 90 minutes),
  graded from easiest (mock 1) to hardest (mock 10), with per-objective results.

> Status: **early**. The shared engine (`engine/`) loads, grades and scores the question bank;
> the terminal and browser interfaces are not built yet.

## Repository layout

```
lpic-practice/
├── AGENTS.md            # Instructions for every agent (CLAUDE.md points here)
├── CHANGELOG.md         # Assembled from changelog.d/ at release time
├── schemas/             # JSON Schemas — the contract for all content
├── content/
│   ├── 101/             # objectives.yaml, questions/, mocks/
│   ├── 102/
│   └── examples/        # schema examples (IDs 9000+), not exam content
├── sources/             # LPI PDFs — gitignored, never committed
├── tools/               # validate.py and other content tooling
├── docs/
│   ├── PROTOCOL.md      # How planners, implementers and humans work together
│   ├── STATUS.md        # Open handoffs and pending decisions
│   ├── adr/             # Architecture Decision Records
│   ├── handoff/         # Planning → implementation work orders
│   └── difficulty-rubric.md
├── engine/              # Python core: loading, matching, scoring, selection, build
├── tests/               # pytest suite with synthetic fixture banks
├── cli/                 # (planned) Textual terminal practice
└── web/                 # (planned) FastAPI + Jinja + htmx mock exams
```

## Decisions so far

| ADR | Decision |
|---|---|
| [Technology stack](docs/adr/2026-10-22-technology-stack.md) | Python 3.12, Textual CLI, FastAPI + Jinja + htmx web, SQLite |
| [Content format](docs/adr/2026-10-22-content-format-and-question-schema.md) | YAML authoring → JSON, validated by JSON Schema |
| [Mock exam composition](docs/adr/2026-10-22-mock-exam-composition.md) | Weighted, difficulty-ramped mocks built from a holdout bank |
| [Content licensing](docs/adr/2026-10-22-content-licensing-and-sources.md) | Original questions only; LPI materials stay out of the repo |
| [Adopt agent-workflow](docs/adr/2026-10-23-adopt-agent-workflow.md) | Decisions, handoffs and status live in the repo; every change is a PR |
| [MIT license](docs/adr/2026-10-23-mit-license.md) | Code and original content under MIT |

## Development

```bash
pip install -e ".[dev]"
python tools/validate.py            # validate everything under content/
python -m engine.build              # compile content to build/content/<exam>.json
pytest                              # run the tests
ruff check . && ruff format --check .
```

The build output is one JSON file per exam; its layout is documented in `engine/build.py`.

## Contributing

Humans and agents follow the same rules: see [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/PROTOCOL.md](docs/PROTOCOL.md).

## License and attribution

Code and original content: [MIT](LICENSE) © 2026 X-DSI.

Questions are original works keyed to the LPI exam objectives. Source references
point to the [LPI Learning Materials](https://learning.lpi.org), which are licensed
under CC BY-NC-ND 4.0 by Linux Professional Institute Inc. and are not part of this
repository. This project is not affiliated with or endorsed by LPI. LPIC is a
trademark of the Linux Professional Institute.
