"""Reviewing a submitted mock: keys and rationales, "Looks right", and flags."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from mock_bank import MOCK_ID, SECRET, correct_response

from cli.main import main
from engine.store import FLAG_NOTE_MAX, Store
from web.app import create_app


@pytest.fixture
def finished(mock_bank, tmp_path: Path):
    """A client and a submitted session (first 10 answered correctly)."""
    content, questions = mock_bank
    db = tmp_path / "results.sqlite"
    with TestClient(create_app(content, db)) as client:
        sid = int(re.search(r"/sessions/(\d+)/", str(client.post(f"/mocks/{MOCK_ID}/start").url)).group(1))
        for n, q in enumerate(questions[:10], start=1):
            client.post(f"/sessions/{sid}/questions/{n}/save", data={"response": correct_response(q)})
        client.post(f"/sessions/{sid}/submit")
        yield client, sid, db, questions


def test_review_shows_keys_rationales_and_explanations(finished) -> None:
    client, sid, _, questions = finished
    page = client.get(f"/sessions/{sid}/review").text
    assert page.count(f"EXPLANATION-{SECRET}") == 60
    assert f"RATIONALE-{SECRET} b {questions[0]['id']}" in page
    assert f"ACCEPTED-{SECRET}-{questions[2]['id']}" in page
    assert page.count('<span class="pass">Correct</span>') == 10
    assert page.count('<span class="fail">Unanswered</span>') == 50


def test_looks_right_writes_one_review_row(finished, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    client, sid, db, questions = finished
    qid = questions[0]["id"]
    response = client.post(f"/sessions/{sid}/review/{qid}/approve", headers={"HX-Request": "true"})
    assert response.status_code == 200 and "Signed off" in response.text
    client.post(f"/sessions/{sid}/review/{qid}/approve")  # a second click adds nothing
    plain = client.post(f"/sessions/{sid}/review/{questions[1]['id']}/approve", follow_redirects=False)
    assert plain.status_code == 303 and plain.headers["location"].endswith(f"/review#{questions[1]['id']}")

    with Store(db) as store:
        assert [(r.question_id, r.verdict) for r in store.reviews(sid)] == [
            (qid, "approved"),
            (questions[1]["id"], "approved"),
        ]
    monkeypatch.setenv("LPIC_DB", str(db))
    assert main(["reviews", "export"]) == 0
    exported = yaml.safe_load(capsys.readouterr().out)
    assert [list(r) for r in exported] == [["question_id", "verdict", "reviewed_at"]] * 2
    assert exported[0]["question_id"] == qid and exported[0]["verdict"] == "approved"
    assert exported[0]["reviewed_at"].endswith("+00:00")
    assert "Signed off" in client.get(f"/sessions/{sid}/review").text


@pytest.mark.parametrize("note", ["see https://example.org", "x" * (FLAG_NOTE_MAX + 1), "details at www.example.org"])
def test_invalid_flags_are_refused(finished, note: str) -> None:
    client, sid, db, questions = finished
    qid = questions[3]["id"]
    htmx = client.post(
        f"/sessions/{sid}/review/{qid}/flag", data={"reason": "ambiguous", "note": note}, headers={"HX-Request": "true"}
    )
    assert htmx.status_code == 200 and "Flag refused" in htmx.text
    plain = client.post(f"/sessions/{sid}/review/{qid}/flag", data={"reason": "ambiguous", "note": note})
    assert plain.status_code == 400 and "Flag refused" in plain.text
    with Store(db) as store:
        assert store.flags() == []


def test_valid_flag_is_stored_and_exported(finished, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    client, sid, db, questions = finished
    qid = questions[4]["id"]
    response = client.post(
        f"/sessions/{sid}/review/{qid}/flag",
        data={"reason": "wrong-answer", "note": "Option d also works."},
        headers={"HX-Request": "true"},
    )
    assert "Flagged: wrong-answer — Option d also works." in response.text
    assert client.post(f"/sessions/{sid}/review/{qid}/flag", data={"reason": "bogus"}).status_code == 400
    monkeypatch.setenv("LPIC_DB", str(db))
    assert main(["flags", "export"]) == 0
    exported = yaml.safe_load(capsys.readouterr().out)
    assert [(f["question_id"], f["reason"], f["note"]) for f in exported] == [
        (qid, "wrong-answer", "Option d also works.")
    ]


def test_review_is_refused_for_questions_outside_the_mock(finished) -> None:
    client, sid, _, _ = finished
    assert client.post(f"/sessions/{sid}/review/101-101.1-0999/approve").status_code == 404
    assert client.post(f"/sessions/{sid}/review/101-101.1-0999/flag", data={"reason": "typo"}).status_code == 404


def test_htmx_targets_do_not_use_question_ids_as_selectors(finished) -> None:
    # Question IDs contain dots ("101-102.3-0003"), which a CSS id selector reads as a class.
    client, sid, _, _ = finished
    page = client.get(f"/sessions/{sid}/review").text
    assert 'hx-target="#actions-' not in page
    assert page.count('hx-target="closest .review-actions"') == 120
