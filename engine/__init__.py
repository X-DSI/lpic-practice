"""lpic-practice engine: the shared core behind the CLI and the web UI.

- `engine.loader` reads the question bank into typed objects (`engine.model`).
- `engine.matching` grades one response; `engine.scoring` turns results into LPI-style scores.
- `engine.selection` returns the practice pool; `engine.build` compiles content to JSON.
- `engine.validation` checks content against the schemas and the semantic rules.
"""
