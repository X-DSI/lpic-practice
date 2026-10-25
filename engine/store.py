"""Results storage: practice sessions, answers and question flags in one SQLite database.

Shared by the CLI and, later, the web UI. The layout is recorded in
`docs/adr/proposed/2026-10-25-results-database.md`.

The database path is `$LPIC_DB` if set, else `$XDG_DATA_HOME/lpic-practice/results.sqlite`, else
`~/.local/share/lpic-practice/results.sqlite`.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

SCHEMA_VERSION: Final = 1

FLAG_REASONS: Final = ("wrong-answer", "ambiguous", "typo", "outdated", "other")
FLAG_NOTE_MAX: Final = 200
# Anything that looks like a link: a scheme ("https://", "ftp://") or a "www." host (PROTOCOL §9).
_URL = re.compile(r"[a-z][a-z0-9+.-]*://|\bwww\.", re.IGNORECASE)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY,
    exam        TEXT NOT NULL,
    mode        TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS answers (
    id            INTEGER PRIMARY KEY,
    session_id    INTEGER NOT NULL REFERENCES sessions(id),
    question_id   TEXT NOT NULL,
    exam          TEXT NOT NULL,
    objective     TEXT NOT NULL,
    response      TEXT NOT NULL,
    correct       INTEGER NOT NULL CHECK (correct IN (0, 1)),
    time_taken_ms INTEGER NOT NULL CHECK (time_taken_ms >= 0),
    answered_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS answers_by_objective ON answers (exam, objective);
CREATE TABLE IF NOT EXISTS flags (
    id          INTEGER PRIMARY KEY,
    question_id TEXT NOT NULL,
    reason      TEXT NOT NULL,
    note        TEXT,
    flagged_at  TEXT NOT NULL
);
"""


class FlagError(ValueError):
    """A flag that breaks the rules: unknown reason, over-long note, or a URL in the note."""


@dataclass(frozen=True)
class Flag:
    question_id: str
    reason: str
    note: str | None
    flagged_at: str


@dataclass(frozen=True)
class Accuracy:
    correct: int
    total: int

    @property
    def ratio(self) -> float:
        return self.correct / self.total if self.total else 0.0


def default_db_path() -> Path:
    if override := os.environ.get("LPIC_DB"):
        return Path(override).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home).expanduser() / "lpic-practice" / "results.sqlite"


def now() -> str:
    """Current UTC time as ISO 8601 with seconds, e.g. `2026-10-25T09:30:00+00:00`."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def split_question_id(question_id: str) -> tuple[str, str]:
    """`"101-102.3-0007"` → `("101", "102.3")`."""
    exam, objective, _ = question_id.split("-")
    return exam, objective


def check_flag(reason: str, note: str | None) -> str | None:
    """Return the cleaned note (stripped, `None` if empty), or raise `FlagError`."""
    if reason not in FLAG_REASONS:
        raise FlagError(f"reason must be one of {', '.join(FLAG_REASONS)}")
    note = (note or "").strip() or None
    if note is not None:
        if len(note) > FLAG_NOTE_MAX:
            raise FlagError(f"note is {len(note)} characters; at most {FLAG_NOTE_MAX} allowed")
        if _URL.search(note):
            raise FlagError("note must not contain a URL")
    return note


class Store:
    """One results database. Every write commits immediately, so nothing is lost on exit."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        with self.conn:
            self.conn.executescript(_SCHEMA)
            self.conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
            )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ sessions

    def start_session(self, exam: str, mode: str) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO sessions (exam, mode, started_at) VALUES (?, ?, ?)", (exam, mode, now())
            )
        assert cur.lastrowid is not None
        return cur.lastrowid

    def finish_session(self, session_id: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE sessions SET finished_at = ? WHERE id = ?", (now(), session_id))

    # ------------------------------------------------------------------- answers

    def record_answer(
        self, session_id: int, question_id: str, response: str | Iterable[str], correct: bool, time_taken_ms: int
    ) -> None:
        """Store one answer. A choice response is stored as a JSON list, a typed one as a JSON string."""
        exam, objective = split_question_id(question_id)
        value = response if isinstance(response, str) else sorted(response)
        with self.conn:
            self.conn.execute(
                "INSERT INTO answers (session_id, question_id, exam, objective, response, correct, time_taken_ms,"
                " answered_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, question_id, exam, objective, json.dumps(value), int(correct), time_taken_ms, now()),
            )

    def answers(self, session_id: int | None = None) -> list[dict]:
        sql = "SELECT question_id, response, correct, time_taken_ms, answered_at, session_id FROM answers"
        rows = (
            self.conn.execute(sql + " WHERE session_id = ? ORDER BY id", (session_id,))
            if session_id is not None
            else self.conn.execute(sql + " ORDER BY id")
        )
        return [
            {
                "question_id": qid,
                "response": json.loads(response),
                "correct": bool(correct),
                "time_taken_ms": ms,
                "answered_at": at,
                "session_id": sid,
            }
            for qid, response, correct, ms, at, sid in rows
        ]

    def accuracy_by_objective(self, exam: str) -> dict[str, Accuracy]:
        """All-time accuracy per objective for one exam. Objectives never attempted are absent."""
        rows = self.conn.execute(
            "SELECT objective, SUM(correct), COUNT(*) FROM answers"
            " WHERE exam = ? GROUP BY objective ORDER BY objective",
            (exam,),
        )
        return {objective: Accuracy(correct, total) for objective, correct, total in rows}

    # --------------------------------------------------------------------- flags

    def add_flag(self, question_id: str, reason: str, note: str | None = None) -> Flag:
        """Store a flag after `check_flag`; raises `FlagError` if it breaks the rules."""
        flag = Flag(question_id, reason, check_flag(reason, note), now())
        with self.conn:
            self.conn.execute(
                "INSERT INTO flags (question_id, reason, note, flagged_at) VALUES (?, ?, ?, ?)",
                (flag.question_id, flag.reason, flag.note, flag.flagged_at),
            )
        return flag

    def flags(self) -> list[Flag]:
        rows = self.conn.execute("SELECT question_id, reason, note, flagged_at FROM flags ORDER BY id")
        return [Flag(*row) for row in rows]
