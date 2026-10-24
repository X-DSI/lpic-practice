"""`tools/validate.py` keeps its flags, output and exit codes (CI and AGENTS.md call it)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from engine.validation import validate

ROOT = Path(__file__).resolve().parent.parent


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate.py"), *args], capture_output=True, text=True, check=False
    )


def test_cli_flags_and_exit_code() -> None:
    for args in ((), ("--strict",)):
        result = run(*args)
        assert result.returncode == 0, result.stdout
        assert result.stdout.startswith("OK: ")


def test_validate_reports_errors_relative_to_the_content_parent(content_copy: Path) -> None:
    path = content_copy / "101" / "questions" / "101.2.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace('objective: "101.2"\n', 'objective: "101.3"\n', 1))
    errors, _ = validate(content_copy)
    assert errors
    assert all(e.startswith("content/101/questions/101.2.yaml: ") for e in errors)
