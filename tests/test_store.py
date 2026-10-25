from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cli.main import main
from engine.store import FLAG_NOTE_MAX, FLAG_REASONS, Accuracy, FlagError, Store, default_db_path


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
