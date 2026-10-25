"""`tools/validate.py` keeps its flags, output and exit codes (CI and AGENTS.md call it)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from engine.assemble import main as assemble_main
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


# --- --strict: mock questions must be pass2 or approved


def set_status(content: Path, qid: str, status: str) -> None:
    objective = qid.split("-")[1]
    path = content / "101" / "questions" / f"{objective}.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for q in doc["questions"]:
        if q["id"] == qid:
            q["review"]["status"] = status
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def first_mock_question(content: Path) -> str:
    return yaml.safe_load((content / "101" / "mocks" / "mock-01.yaml").read_text(encoding="utf-8"))["questions"][0]


def test_strict_accepts_a_mock_of_pass2_questions(holdout_content: Path) -> None:
    assert assemble_main(["101", "--content-dir", str(holdout_content)]) == 0
    assert validate(holdout_content, strict=True)[0] == []


@pytest.mark.parametrize("status", ["draft", "pass1"])
def test_strict_rejects_a_mock_with_a_draft_or_pass1_question(holdout_content: Path, status: str) -> None:
    assert assemble_main(["101", "--content-dir", str(holdout_content)]) == 0
    qid = first_mock_question(holdout_content)
    set_status(holdout_content, qid, status)
    assert validate(holdout_content)[0] == []  # fine without --strict
    errors, _ = validate(holdout_content, strict=True)
    assert errors == [f"content/101/mocks/mock-01.yaml: {qid}: not pass2 or approved (status '{status}')"]


def test_strict_flag_on_the_command_line(holdout_content: Path, tmp_path: Path) -> None:
    help_text = run("--help").stdout
    assert "--strict" in help_text and "pass2 or approved" in help_text
