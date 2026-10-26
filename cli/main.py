"""`lpic` command-line entry point.

    lpic practice              drill practice questions in the terminal
    lpic serve                 take the mock exams in a browser (http://127.0.0.1:8000)
    lpic flags export          print every question flag as YAML
    lpic reviews export        print every holdout sign-off ("looks right") as YAML

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


def cmd_serve(args: argparse.Namespace) -> int:
    errors, _ = validate(args.content_dir, strict=True)
    if errors:
        print(
            f"Content is invalid ({len(errors)} problem(s)); run `python tools/validate.py --strict`.", file=sys.stderr
        )
        return 1
    # Imported here so the other commands don't pay for loading FastAPI.
    import uvicorn

    from web.app import create_app

    app = create_app(args.content_dir, default_db_path())
    print(f"Mock exams at http://{args.host}:{args.port}/ (Ctrl+C to stop)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_reviews_export(args: argparse.Namespace) -> int:
    with Store() as store:
        reviews = [asdict(r) for r in store.reviews()]
    sys.stdout.write(yaml.safe_dump(reviews, sort_keys=False, allow_unicode=True) if reviews else "[]\n")
    return 0


def cmd_flags_export(args: argparse.Namespace) -> int:
    with Store() as store:
        flags = [asdict(f) for f in store.flags()]
    sys.stdout.write(yaml.safe_dump(flags, sort_keys=False, allow_unicode=True) if flags else "[]\n")
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="lpic",
        description="LPIC exam practice: terminal drills and browser mock exams.",
        epilog=f"Results database: {default_db_path()} (set LPIC_DB to change it).",
    )
    commands = ap.add_subparsers(dest="command", required=True)

    practice = commands.add_parser("practice", help="drill practice questions (Textual app)")
    practice.add_argument("--content-dir", type=Path, default=CONTENT_DIR, help=argparse.SUPPRESS)
    practice.set_defaults(func=cmd_practice)

    serve = commands.add_parser("serve", help="take the mock exams in a browser (FastAPI app)")
    serve.add_argument("--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="port to listen on (default 8000)")
    serve.add_argument("--content-dir", type=Path, default=CONTENT_DIR, help=argparse.SUPPRESS)
    serve.set_defaults(func=cmd_serve)

    flags = commands.add_parser("flags", help="work with question flags")
    flag_commands = flags.add_subparsers(dest="flags_command", required=True)
    export = flag_commands.add_parser("export", help="print all flags as YAML to stdout")
    export.set_defaults(func=cmd_flags_export)

    reviews = commands.add_parser("reviews", help="work with holdout sign-offs from mock reviews")
    review_commands = reviews.add_subparsers(dest="reviews_command", required=True)
    reviews_export = review_commands.add_parser("export", help="print all reviews as YAML to stdout")
    reviews_export.set_defaults(func=cmd_reviews_export)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
