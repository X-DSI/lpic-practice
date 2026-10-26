# lpic-practice

A practice suite for the Linux Professional Institute LPIC-1 (101-500, 102-500) and,
later, LPIC-2 (201, 202) exams.

- **Terminal practice** — drill questions by objective, with weak-area targeting.
- **Browser mock exams** — 10 timed mock exams per exam (60 questions, 90 minutes),
  graded from easiest (mock 1) to hardest (mock 10), with per-objective results.

> Status: **early**. The shared engine (`engine/`) loads, grades and scores the question bank,
> `lpic practice` drills it in the terminal, and `lpic serve` runs the timed mock exams in a browser.

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
├── engine/              # Python core: loading, matching, scoring, selection, build, mock assembly
├── tests/               # pytest suite with synthetic fixture banks
├── cli/                 # Textual terminal practice (the `lpic` command)
└── web/                 # FastAPI + Jinja + htmx mock exams (`lpic serve`)
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
python -m engine.assemble 101       # assemble content/101/mocks/mock-01…10.yaml from the holdout bank
pytest                              # run the tests
ruff check . && ruff format --check .
```

## Practising

```bash
lpic practice                       # drill by objective, a weighted mix, or weak areas
lpic flags export > flags.yaml      # questions you flagged while studying, for the planner
```

Results and flags are kept in `~/.local/share/lpic-practice/results.sqlite` (or under
`$XDG_DATA_HOME`); set `LPIC_DB` to use another file. Practice uses only practice questions, never
the holdout pool reserved for mock exams.

## Mock exams

```bash
lpic serve                          # open http://127.0.0.1:8000/ and pick a mock
lpic reviews export > reviews.yaml  # holdout questions you signed off as "looks right", for the planner
```

Each mock is 60 questions in 90 minutes, as in the real exam, with no feedback until you submit.
Answers save as you go, so a refresh or a restart resumes with the same deadline; at the deadline
the mock is submitted for you. The results page shows an estimated 200–800 score, the raw
percentage and your weak areas. Afterwards, review each question: **Looks right** signs it off,
**Flag** sends it back like a flag from `lpic practice`. The server listens on 127.0.0.1 only and
has no login.

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
