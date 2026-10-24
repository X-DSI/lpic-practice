#!/usr/bin/env python3
"""Validate all LPIC content against the JSON Schemas plus the semantic rules in the ADRs
on content format and mock exam composition (docs/adr/2026-10-22-*.md).

Usage:
    python tools/validate.py              # validate everything under content/
    python tools/validate.py --strict     # also require mock questions to be approved

Exit code 0 when everything is valid, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Runs without installing the package: make the repository's `engine` importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.validation import validate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="require approved status for mock questions")
    args = ap.parse_args(argv)

    errors, summary = validate(strict=args.strict)
    if errors:
        print(f"FAIL: {len(errors)} problem(s)\n")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    print(f"OK: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
