from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cli.main import main
from engine.store import FLAG_NOTE_MAX, FLAG_REASONS, Accuracy, Draft, FlagError, Store, default_db_path


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "results.sqlite"


def test_answers_survive_a_restart(db: Path) -> None:
    with Store(db) as store:
        session = store.start_session("101", "objective")
        store.record_answer(session, "101-101.1-0001", "b", True, 4200)
        store.record_answer(session, "101-101.1-0002", ["c", "a"], False, 9000)
        store.record_answer(session, "101-101.1-0003", " ls  -i ", True, 1500)
        store.finish_session(session)

    with Store(db) as reopened:
        answers = reopened.answers()
        assert [(a["question_id"], a["response"], a["correct"], a["time_taken_ms"]) for a in answers] == [
            ("101-101.1-0001", "b", True, 4200),
            ("101-101.1-0002", ["a", "c"], False, 9000),
            ("101-101.1-0003", " ls  -i ", True, 1500),
        ]
        assert {a["session_id"] for a in answers} == {session}
        assert all(a["answered_at"].endswith("+00:00") for a in answers)
        assert reopened.answers(session) == answers
        assert reopened.answers(session + 1) == []


def test_accuracy_by_objective(db: Path) -> None:
    with Store(db) as store:
        session = store.start_session("101", "mixed")
        for qid, ok in [("101-101.1-0001", True), ("101-101.1-0002", False), ("101-101.2-0001", True)]:
            store.record_answer(session, qid, "x", ok, 100)
        store.record_answer(store.start_session("102", "mixed"), "102-104.1-0001", "a", False, 100)
        assert store.accuracy_by_objective("101") == {"101.1": Accuracy(1, 2), "101.2": Accuracy(1, 1)}
        assert store.accuracy_by_objective("102") == {"104.1": Accuracy(0, 1)}


def test_lpic_db_overrides_the_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "custom" / "my.sqlite"
    monkeypatch.setenv("LPIC_DB", str(target))
    assert default_db_path() == target
    with Store() as store:
        store.start_session("101", "weak")
    assert target.exists()


def test_xdg_data_home_and_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("LPIC_DB", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert default_db_path() == tmp_path / "data" / "lpic-practice" / "results.sqlite"
    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert default_db_path() == tmp_path / "home" / ".local" / "share" / "lpic-practice" / "results.sqlite"


def test_valid_flags_are_stored(db: Path) -> None:
    with Store(db) as store:
        store.add_flag("101-101.1-0001", "wrong-answer", "  Option c also works.  ")
        store.add_flag("101-101.1-0002", "typo")
        store.add_flag("101-101.1-0003", "other", "x" * FLAG_NOTE_MAX)
    with Store(db) as store:
        flags = store.flags()
    assert [(f.question_id, f.reason, f.note) for f in flags] == [
        ("101-101.1-0001", "wrong-answer", "Option c also works."),
        ("101-101.1-0002", "typo", None),
        ("101-101.1-0003", "other", "x" * FLAG_NOTE_MAX),
    ]


@pytest.mark.parametrize(
    ("reason", "note"),
    [
        ("wrong-answer", "x" * (FLAG_NOTE_MAX + 1)),
        ("ambiguous", "see https://example.org/page"),
        ("ambiguous", "see HTTP://example.org"),
        ("typo", "details at www.example.org"),
        ("other", "ftp://files.example.org/x"),
        ("not-a-reason", None),
    ],
)
def test_invalid_flags_are_rejected(db: Path, reason: str, note: str | None) -> None:
    with Store(db) as store:
        with pytest.raises(FlagError):
            store.add_flag("101-101.1-0001", reason, note)
        assert store.flags() == []


def test_reasons_are_the_fixed_list() -> None:
    assert FLAG_REASONS == ("wrong-answer", "ambiguous", "typo", "outdated", "other")


def test_flags_export(monkeypatch: pytest.MonkeyPatch, db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("LPIC_DB", str(db))
    assert main(["flags", "export"]) == 0
    assert yaml.safe_load(capsys.readouterr().out) == []

    with Store(db) as store:
        store.add_flag("101-101.1-0002", "ambiguous", "Two options could be right.")
        with pytest.raises(FlagError):
            store.add_flag("101-101.1-0003", "typo", "https://example.org")

    assert main(["flags", "export"]) == 0
    exported = yaml.safe_load(capsys.readouterr().out)
    assert len(exported) == 1
    flag = exported[0]
    assert list(flag) == ["question_id", "reason", "note", "flagged_at"]
    assert (flag["question_id"], flag["reason"], flag["note"]) == (
        "101-101.1-0002",
        "ambiguous",
        "Two options could be right.",
    )


# --- schema version 2 (results-database-v2 ADR)

V1_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sessions (id INTEGER PRIMARY KEY, exam TEXT NOT NULL, mode TEXT NOT NULL, started_at TEXT NOT NULL,
    finished_at TEXT);
CREATE TABLE answers (id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES sessions(id),
    question_id TEXT NOT NULL, exam TEXT NOT NULL, objective TEXT NOT NULL, response TEXT NOT NULL,
    correct INTEGER NOT NULL CHECK (correct IN (0, 1)), time_taken_ms INTEGER NOT NULL CHECK (time_taken_ms >= 0),
    answered_at TEXT NOT NULL);
CREATE INDEX answers_by_objective ON answers (exam, objective);
CREATE TABLE flags (id INTEGER PRIMARY KEY, question_id TEXT NOT NULL, reason TEXT NOT NULL, note TEXT,
    flagged_at TEXT NOT NULL);
INSERT INTO meta VALUES ('schema_version', '1');
INSERT INTO sessions VALUES (1, '101', 'objective', '2026-10-25T09:00:00+00:00', '2026-10-25T09:10:00+00:00');
INSERT INTO sessions VALUES (2, '101', 'weak', '2026-10-25T10:00:00+00:00', NULL);
INSERT INTO answers VALUES (1, 1, '101-101.1-0001', '101', '101.1', '"b"', 1, 4200, '2026-10-25T09:01:00+00:00');
INSERT INTO answers VALUES (2, 1, '101-101.1-0002', '101', '101.1', '["a", "c"]', 0, 900, '2026-10-25T09:02:00+00:00');
INSERT INTO flags VALUES (1, '101-101.1-0002', 'typo', 'Missing word.', '2026-10-25T09:03:00+00:00');
"""


def write_v1(path: Path) -> None:
    import sqlite3

    conn = sqlite3.connect(path)
    conn.executescript(V1_SCHEMA)
    conn.commit()
    conn.close()


def test_a_v1_database_opens_as_v2_with_its_rows_intact(db: Path) -> None:
    write_v1(db)
    with Store(db) as store:
        assert store.schema_version == 2
        assert [(a["question_id"], a["response"], a["correct"], a["time_taken_ms"]) for a in store.answers()] == [
            ("101-101.1-0001", "b", True, 4200),
            ("101-101.1-0002", ["a", "c"], False, 900),
        ]
        assert [(f.question_id, f.reason, f.note) for f in store.flags()] == [
            ("101-101.1-0002", "typo", "Missing word.")
        ]
        assert store.session(1).mock_id is None and store.session(2).finished_at is None
        assert store.accuracy_by_objective("101") == {"101.1": Accuracy(1, 2)}
        assert store.drafts(1) == {} and store.reviews() == []
        # The CLI keeps working on the migrated database.
        session = store.start_session("101", "mixed")
        store.record_answer(session, "101-101.2-0001", "a", True, 100)
    with Store(db) as reopened:  # opening again is a no-op
        assert reopened.schema_version == 2
        assert len(reopened.answers()) == 3


def test_a_new_database_is_v2(db: Path) -> None:
    with Store(db) as store:
        assert store.schema_version == 2
        tables = {row[0] for row in store.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert {"meta", "sessions", "answers", "flags", "drafts", "reviews"} <= tables


def test_drafts_and_submit_in_one_transaction(db: Path) -> None:
    with Store(db) as store:
        sid = store.start_session("101", "mock", mock_id="101-mock-01", started_at="2026-10-26T09:00:00+00:00")
        store.save_draft(sid, "101-101.1-0001", "a", False)
        store.save_draft(sid, "101-101.1-0001", "b", True)  # overwritten
        store.save_draft(sid, "101-101.1-0002", ["c", "a"], False)
        store.save_draft(sid, "101-101.1-0003", None, True)
        assert store.drafts(sid) == {
            "101-101.1-0001": Draft("b", True),
            "101-101.1-0002": Draft(["a", "c"], False),
            "101-101.1-0003": Draft(None, True),
        }
        assert store.resumable_session("101-mock-01").id == sid
        store.submit_mock(
            sid,
            [
                ("101-101.1-0001", "b", True, 3000),
                ("101-101.1-0002", ["a", "c"], True, 0),
                ("101-101.1-0003", None, False, 0),
            ],
            "2026-10-26T09:40:00+00:00",
        )
        assert store.drafts(sid) == {}
        assert store.session(sid).finished_at == "2026-10-26T09:40:00+00:00"
        assert [a["response"] for a in store.answers(sid)] == ["b", ["a", "c"], None]
        assert store.resumable_session("101-mock-01") is None
        assert store.accuracy_by_objective("101") == {"101.1": Accuracy(2, 3)}  # mock answers count


def test_a_failed_submit_writes_nothing(db: Path) -> None:
    with Store(db) as store:
        sid = store.start_session("101", "mock", mock_id="101-mock-01")
        store.save_draft(sid, "101-101.1-0001", "b", False)
        with pytest.raises(Exception):  # noqa: B017 — the CHECK constraint on time_taken_ms
            store.submit_mock(sid, [("101-101.1-0001", "b", True, 10), ("101-101.1-0002", "a", False, -1)])
        assert store.answers(sid) == [] and store.session(sid).finished_at is None
        assert list(store.drafts(sid)) == ["101-101.1-0001"]


def test_reviews(db: Path) -> None:
    with Store(db) as store:
        sid = store.start_session("101", "mock", mock_id="101-mock-01")
        assert store.add_review("101-101.1-0001", sid) is True
        assert store.add_review("101-101.1-0001", sid) is False  # one per question per session
        other = store.start_session("101", "mock", mock_id="101-mock-01")
        assert store.add_review("101-101.1-0001", other) is True
        with pytest.raises(ValueError):
            store.add_review("101-101.1-0002", sid, verdict="rejected")
        assert [r.question_id for r in store.reviews()] == ["101-101.1-0001", "101-101.1-0001"]
        assert len(store.reviews(sid)) == 1


def test_reviews_export_when_empty(
    monkeypatch: pytest.MonkeyPatch, db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LPIC_DB", str(db))
    assert main(["reviews", "export"]) == 0
    assert capsys.readouterr().out == "[]\n"
