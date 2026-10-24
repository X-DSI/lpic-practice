"""Compile the YAML question bank to one JSON file per exam.

Usage:
    python -m engine.build [--content-dir content] [--out-dir build/content]

Validates all content first. If anything is invalid it prints the problems, exits 1 and writes
nothing. Otherwise it writes `<out-dir>/<exam>.json` for every exam with an `objectives.yaml`:

    {
      "format_version": 1,
      "exam": "101",
      "objectives": { ...content/101/objectives.yaml, as is... },
      "questions": [ ...every question from content/101/questions/*.yaml, sorted by id... ],
      "mocks": [ ...content/101/mocks/*.yaml, sorted by number... ]
    }

Keys are sorted and the output is UTF-8 with two-space indentation and a trailing newline, so the
same content always produces byte-identical files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.loader import exams, read_exam_data
from engine.validation import CONTENT_DIR, REPO_ROOT, validate

OUT_DIR = REPO_ROOT / "build" / "content"
FORMAT_VERSION = 1


class BuildError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"{len(errors)} validation problem(s)")
        self.errors = errors


def render(exam: str, content_dir: Path = CONTENT_DIR) -> str:
    document = {"format_version": FORMAT_VERSION, "exam": exam, **read_exam_data(exam, content_dir)}
    return json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def build(content_dir: Path = CONTENT_DIR, out_dir: Path = OUT_DIR) -> list[Path]:
    """Validate, then write one JSON file per exam. Returns the written paths."""
    errors, _ = validate(content_dir)
    if errors:
        raise BuildError(errors)
    # Render everything before writing anything.
    rendered = {exam: render(exam, content_dir) for exam in exams(content_dir)}
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for exam, text in rendered.items():
        path = out_dir / f"{exam}.json"
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--content-dir", type=Path, default=CONTENT_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    try:
        written = build(args.content_dir, args.out_dir)
    except BuildError as exc:
        print(f"FAIL: {len(exc.errors)} problem(s); nothing written\n")
        for e in exc.errors:
            print(f"  ✗ {e}")
        return 1
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
