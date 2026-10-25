from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from engine.loader import load_exam
from engine.model import Bank

FIXTURE_CONTENT = Path(__file__).parent / "fixtures" / "content"


@pytest.fixture
def bank_101() -> Bank:
    return load_exam("101", FIXTURE_CONTENT)


@pytest.fixture
def content_copy(tmp_path: Path) -> Path:
    """A writable copy of the fixture content tree."""
    dest = tmp_path / "content"
    shutil.copytree(FIXTURE_CONTENT, dest)
    return dest
