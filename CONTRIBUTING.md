# Contributing

Humans and AI agents follow the same rules here:
**[docs/PROTOCOL.md](docs/PROTOCOL.md)** (from [X-DSI/agent-workflow](https://github.com/X-DSI/agent-workflow)).

The short version:

1. Open an issue or a `plan/` PR for anything non-trivial, so the decision is recorded as an ADR.
2. Do the work on a branch and open a pull request. Nothing is pushed straight to `main`.
3. Add a fragment to `changelog.d/` if behaviour changes.
4. Use your own git identity, and don't add AI co-author trailers.

Changes to agent instructions, the protocol, decided ADRs or CI workflows always need a maintainer's
review. Everything else merges once CI is green.
