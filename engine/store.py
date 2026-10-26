"""Results storage: practice and mock sessions, answers, mock drafts, question flags and holdout
reviews in one SQLite database.

Shared by the CLI and the web UI. The layout is schema version 2, recorded in
`docs/adr/proposed/2026-10-26-results-database-v2.md` (which supersedes
`docs/adr/2026-10-25-results-database.md`). A version 1 database is migrated in place on open.

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

SCHEMA_VERSION: Final = 2

REVIEW_VERDICTS: Final = ("approved",)

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

# Version 2: which mock a session was, in-progress mock answers, and holdout sign-off.
_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS drafts (
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    question_id TEXT NOT NULL,
    response    TEXT,
    marked      INTEGER NOT NULL DEFAULT 0 CHECK (marked IN (0, 1)),
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (session_id, question_id)
);
CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY,
    question_id TEXT NOT NULL,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    verdict     TEXT NOT NULL,
    reviewed_at TEXT NOT NULL
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
class Review:
    question_id: str
    verdict: str
    reviewed_at: str


@dataclass(frozen=True)
class Session:
    id: int
    exam: str
    mode: str
    mock_id: str | None
    started_at: str
    finished_at: str | None


@dataclass(frozen=True)
class Draft:
    response: str | list[str] | None
    marked: bool


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
    return timestamp(datetime.now(UTC))


def timestamp(moment: datetime) -> str:
    """`moment` as the database's timestamp format (UTC, ISO 8601, seconds)."""
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def _response_json(response: str | Iterable[str] | None) -> str:
    """A choice response as a sorted JSON list, a typed one as a JSON string, no answer as `null`."""
    if response is None or isinstance(response, str):
        return json.dumps(response)
    return json.dumps(sorted(response))


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
        self._migrate()

    @property
    def schema_version(self) -> int:
        (value,) = self.conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        return int(value)

    def _migrate(self) -> None:
        """Bring the database up to `SCHEMA_VERSION`. Version 1 → 2 adds `sessions.mock_id`, `drafts`
        and `reviews`; existing rows are untouched. A fresh database goes through the same steps."""
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(sessions)")}
        with self.conn:
            if "mock_id" not in columns:
                self.conn.execute("ALTER TABLE sessions ADD COLUMN mock_id TEXT")
            self.conn.executescript(_SCHEMA_V2)
            self.conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version' AND CAST(value AS INTEGER) < ?",
                (str(SCHEMA_VERSION), SCHEMA_VERSION),
            )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ sessions

    def start_session(self, exam: str, mode: str, mock_id: str | None = None, started_at: str | None = None) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO sessions (exam, mode, mock_id, started_at) VALUES (?, ?, ?, ?)",
                (exam, mode, mock_id, started_at or now()),
            )
        assert cur.lastrowid is not None
        return cur.lastrowid

    def finish_session(self, session_id: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE sessions SET finished_at = ? WHERE id = ?", (now(), session_id))

    def session(self, session_id: int) -> Session | None:
        row = self.conn.execute(
            "SELECT id, exam, mode, mock_id, started_at, finished_at FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return Session(*row) if row else None

    def mock_sessions(self, mock_id: str) -> list[Session]:
        """Every session of one mock, oldest first."""
        rows = self.conn.execute(
            "SELECT id, exam, mode, mock_id, started_at, finished_at FROM sessions WHERE mock_id = ? ORDER BY id",
            (mock_id,),
        )
        return [Session(*row) for row in rows]

    def resumable_session(self, mock_id: str) -> Session | None:
        """The latest unfinished session of `mock_id` that has drafts (results-database-v2 ADR)."""
        row = self.conn.execute(
            "SELECT id, exam, mode, mock_id, started_at, finished_at FROM sessions s"
            " WHERE mock_id = ? AND finished_at IS NULL"
            " AND EXISTS (SELECT 1 FROM drafts d WHERE d.session_id = s.id) ORDER BY id DESC LIMIT 1",
            (mock_id,),
        ).fetchone()
        return Session(*row) if row else None

    # -------------------------------------------------------------- mock drafts

    def save_draft(
        self,
        session_id: int,
        question_id: str,
        response: str | Iterable[str] | None,
        marked: bool,
        updated_at: str | None = None,
    ) -> None:
        """Create or overwrite the in-progress answer to one mock question."""
        with self.conn:
            self.conn.execute(
                "INSERT INTO drafts (session_id, question_id, response, marked, updated_at) VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (session_id, question_id) DO UPDATE SET"
                " response = excluded.response, marked = excluded.marked, updated_at = excluded.updated_at",
                (session_id, question_id, _response_json(response), int(marked), updated_at or now()),
            )

    def drafts(self, session_id: int) -> dict[str, Draft]:
        rows = self.conn.execute("SELECT question_id, response, marked FROM drafts WHERE session_id = ?", (session_id,))
        return {qid: Draft(json.loads(response) if response else None, bool(marked)) for qid, response, marked in rows}

    def submit_mock(
        self,
        session_id: int,
        answers: Iterable[tuple[str, str | Iterable[str] | None, bool, int]],
        finished_at: str | None = None,
    ) -> None:
        """In one transaction: write one answer per `(question_id, response, correct, time_taken_ms)`
        in the given order, delete the session's drafts, and set `finished_at`."""
        at = finished_at or now()
        with self.conn:
            for question_id, response, correct, time_taken_ms in answers:
                exam, objective = split_question_id(question_id)
                self.conn.execute(
                    "INSERT INTO answers (session_id, question_id, exam, objective, response, correct,"
                    " time_taken_ms, answered_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (session_id, question_id, exam, objective, _response_json(response), int(correct), time_taken_ms)
                    + (at,),
                )
            self.conn.execute("DELETE FROM drafts WHERE session_id = ?", (session_id,))
            self.conn.execute("UPDATE sessions SET finished_at = ? WHERE id = ?", (at, session_id))

    # ------------------------------------------------------------------- answers

    def record_answer(
        self, session_id: int, question_id: str, response: str | Iterable[str], correct: bool, time_taken_ms: int
    ) -> None:
        """Store one answer. A choice response is stored as a JSON list, a typed one as a JSON string."""
        exam, objective = split_question_id(question_id)
        with self.conn:
            self.conn.execute(
                "INSERT INTO answers (session_id, question_id, exam, objective, response, correct, time_taken_ms,"
                " answered_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, question_id, exam, objective, _response_json(response), int(correct), time_taken_ms)
                + (now(),),
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

    # ------------------------------------------------------------------- reviews

    def add_review(self, question_id: str, session_id: int, verdict: str = "approved") -> bool:
        """Record a "looks right" verdict. One per question per session: a repeat is ignored and
        returns `False`."""
        if verdict not in REVIEW_VERDICTS:
            raise ValueError(f"verdict must be one of {', '.join(REVIEW_VERDICTS)}")
        with self.conn:
            if self.conn.execute(
                "SELECT 1 FROM reviews WHERE question_id = ? AND session_id = ?", (question_id, session_id)
            ).fetchone():
                return False
            self.conn.execute(
                "INSERT INTO reviews (question_id, session_id, verdict, reviewed_at) VALUES (?, ?, ?, ?)",
                (question_id, session_id, verdict, now()),
            )
        return True

    def reviews(self, session_id: int | None = None) -> list[Review]:
        sql = "SELECT question_id, verdict, reviewed_at FROM reviews"
        rows = (
            self.conn.execute(sql + " WHERE session_id = ? ORDER BY id", (session_id,))
            if session_id is not None
            else self.conn.execute(sql + " ORDER BY id")
        )
        return [Review(*row) for row in rows]
