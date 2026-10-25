"""The installed `lpic` command (from `pip install -e ".[dev]"`)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def lpic() -> str:
    path = shutil.which("lpic")
    assert path is not None, 'the `lpic` command is missing; run `pip install -e ".[dev]"`'
    return path


def test_lpic_help() -> None:
    result = subprocess.run([lpic(), "--help"], capture_output=True, text=True, check=True)
    assert "practice" in result.stdout and "flags" in result.stdout


def test_lpic_flags_export_with_an_empty_database(tmp_path: Path) -> None:
    db = tmp_path / "results.sqlite"
    result = subprocess.run(
        [lpic(), "flags", "export"], capture_output=True, text=True, check=True, env={"LPIC_DB": str(db), "PATH": ""}
    )
    assert result.stdout == "[]\n"
    assert db.exists()
