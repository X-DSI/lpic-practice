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
    for command in ("practice", "serve", "flags", "reviews"):
        assert command in result.stdout


def test_lpic_flags_export_with_an_empty_database(tmp_path: Path) -> None:
    db = tmp_path / "results.sqlite"
    result = subprocess.run(
        [lpic(), "flags", "export"], capture_output=True, text=True, check=True, env={"LPIC_DB": str(db), "PATH": ""}
    )
    assert result.stdout == "[]\n"
    assert db.exists()


def test_lpic_serve_and_reviews_export_help() -> None:
    serve = subprocess.run([lpic(), "serve", "--help"], capture_output=True, text=True, check=True).stdout
    assert "--host" in serve and "127.0.0.1" in serve and "--port" in serve
    reviews = subprocess.run([lpic(), "reviews", "--help"], capture_output=True, text=True, check=True).stdout
    assert "export" in reviews


def test_lpic_reviews_export_with_an_empty_database(tmp_path: Path) -> None:
    db = tmp_path / "results.sqlite"
    result = subprocess.run(
        [lpic(), "reviews", "export"], capture_output=True, text=True, check=True, env={"LPIC_DB": str(db), "PATH": ""}
    )
    assert result.stdout == "[]\n"
