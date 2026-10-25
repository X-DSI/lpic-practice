"""`lpic` command-line entry point.

    lpic practice              drill practice questions in the terminal
    lpic flags export          print every question flag as YAML

The results database is `$LPIC_DB`, else `$XDG_DATA_HOME/lpic-practice/results.sqlite`, else
`~/.local/share/lpic-practice/results.sqlite`.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

from engine.store import Store, default_db_path
from engine.validation import CONTENT_DIR, validate


def cmd_practice(args: argparse.Namespace) -> int:
    errors, _ = validate(args.content_dir)
    if errors:
        print(f"Content is invalid ({len(errors)} problem(s)); run `python tools/validate.py`.", file=sys.stderr)
        return 1
    # Imported here so `lpic flags export` and `--help` don't pay for loading Textual.
    from cli.app import PracticeApp

    with Store() as store:
        PracticeApp(store, args.content_dir).run()
    return 0


def cmd_flags_export(args: argparse.Namespace) -> int:
    with Store() as store:
        flags = [asdict(f) for f in store.flags()]
    sys.stdout.write(yaml.safe_dump(flags, sort_keys=False, allow_unicode=True) if flags else "[]\n")
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="lpic",
        description="LPIC exam practice in the terminal.",
        epilog=f"Results database: {default_db_path()} (set LPIC_DB to change it).",
    )
    commands = ap.add_subparsers(dest="command", required=True)

    practice = commands.add_parser("practice", help="drill practice questions (Textual app)")
    practice.add_argument("--content-dir", type=Path, default=CONTENT_DIR, help=argparse.SUPPRESS)
    practice.set_defaults(func=cmd_practice)

    flags = commands.add_parser("flags", help="work with question flags")
    flag_commands = flags.add_subparsers(dest="flags_command", required=True)
    export = flag_commands.add_parser("export", help="print all flags as YAML to stdout")
    export.set_defaults(func=cmd_flags_export)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
