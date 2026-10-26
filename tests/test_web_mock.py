"""Taking a mock in the web app (FastAPI TestClient) on a synthetic bank."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mock_bank import MOCK_ID, SECRET, correct_response, wrong_response

from engine.loader import load_exam
from engine.scoring import score
from engine.store import Store
from web.app import create_app

ROOT = Path(__file__).resolve().parent.parent
START = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
LEAKS = (SECRET, "rationale", "explanation", "✓", "Correct", "Accepted")


class Clock:
    def __init__(self) -> None:
        self.moment = START

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, **delta: float) -> None:
        self.moment += timedelta(**delta)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "results.sqlite"


def client_for(content: Path, db: Path, clock: Clock) -> TestClient:
    return TestClient(create_app(content, db, clock=clock))


def form_for(q: dict, response, marked: bool = False, go: str | None = None) -> dict:
    data: dict = {"response": response if response is not None else ""}
    if q["type"] == "multi_choice" and response is None:
        data = {}
    if marked:
        data["marked"] = "1"
    if go:
        data["go"] = go
    return data


def session_id_from(url: str) -> int:
    match = re.search(r"/sessions/(\d+)/", url)
    assert match, url
    return int(match.group(1))


def test_full_mock(mock_bank, db: Path) -> None:
    content, questions = mock_bank
    clock = Clock()
    served: list[str] = []  # every page and partial before submit
    expected: list[bool] = []

    with client_for(content, db, clock) as client:
        index = client.get("/")
        assert index.status_code == 200 and "Start" in index.text and f"/mocks/{MOCK_ID}/start" in index.text
        first = client.post(f"/mocks/{MOCK_ID}/start")
        assert first.status_code == 200 and first.url.path.endswith("/questions/1")
        served.append(first.text)
        sid = session_id_from(str(first.url))

        for n, q in enumerate(questions, start=1):
            page = client.get(f"/sessions/{sid}/questions/{n}")
            assert page.status_code == 200 and f"Question {n} of 60" in page.text
            served.append(page.text)
            if n >= 58:
                expected.append(False)  # the last three stay unanswered
                continue
            right = n % 3 != 0  # every third answer is wrong
            response = correct_response(q) if right else wrong_response(q)
            if n == 1:
                # Answer wrong first, then change it (htmx autosave both times).
                saved = client.post(
                    f"/sessions/{sid}/questions/1/save",
                    data=form_for(q, wrong_response(q)),
                    headers={"HX-Request": "true"},
                )
                assert saved.status_code == 200 and 'id="navigator"' in saved.text
                served.append(saved.text)
            if n % 2:
                saved = client.post(
                    f"/sessions/{sid}/questions/{n}/save",
                    data=form_for(q, response, marked=n == 5),
                    headers={"HX-Request": "true"},
                )
            else:
                saved = client.post(f"/sessions/{sid}/questions/{n}", data=form_for(q, response, go="next"))
            assert saved.status_code == 200
            served.append(saved.text)
            expected.append(right)

        # The changed answer and the mark are shown when revisiting.
        revisit = client.get(f"/sessions/{sid}/questions/1")
        assert 'value="b" data-key="b" checked' in revisit.text
        served.append(revisit.text)
        assert 'class="answered marked' in client.get(f"/sessions/{sid}/questions/5").text

        confirm = client.get(f"/sessions/{sid}/submit")
        assert "3 question(s) unanswered and 1 marked for review" in confirm.text
        served.append(confirm.text)
        assert client.get(f"/sessions/{sid}/review").status_code == 403  # no review before submit

        for text in served:
            for leak in LEAKS:
                assert leak not in text, f"{leak!r} served before submit"

        clock.advance(minutes=42, seconds=5)
        results = client.post(f"/sessions/{sid}/submit")
        assert results.url.path == f"/sessions/{sid}/results"

    bank = load_exam("101", content)
    expected_score = score([(bank.question(q["id"]), ok) for q, ok in zip(questions, expected, strict=True)])
    text = results.text
    assert f'<span class="big">{expected_score.scaled}</span>' in text
    assert f"Raw score {expected_score.correct} / 60 ({expected_score.percent:.1f} %)" in text
    assert ("Likely pass" if expected_score.likely_pass else "Below the pass mark") in text
    assert "Time used: 42:05 of 90:00" in text
    assert "lpic practice</code> → weak areas" in text

    with Store(db) as store:
        answers = store.answers(sid)
        assert [a["question_id"] for a in answers] == [q["id"] for q in questions]  # exactly one row each
        assert [a["correct"] for a in answers] == expected
        assert [a["response"] for a in answers[-3:]] == [None, None, None]
        assert store.drafts(sid) == {}


def test_results_and_list_after_a_mock(mock_bank, db: Path) -> None:
    content, questions = mock_bank
    clock = Clock()
    with client_for(content, db, clock) as client:
        sid = session_id_from(str(client.post(f"/mocks/{MOCK_ID}/start").url))
        for n, q in enumerate(questions[:39], start=1):
            client.post(f"/sessions/{sid}/questions/{n}/save", data=form_for(q, correct_response(q)))
        text = client.post(f"/sessions/{sid}/submit").text
        assert '<span class="big">500</span>' in text and "Likely pass" in text
        # Objectives entirely in the unanswered tail are weak areas.
        assert re.search(r"<h2>Weak areas</h2>\s*<ol>", text)
        index = client.get("/").text
        assert f"/sessions/{sid}/results" in index and "Start" in index and "Resume" not in index
        assert re.search(r"<td>1</td>\s*<td>500</td>", index)


def test_resume_on_a_new_app_instance(mock_bank, db: Path) -> None:
    content, questions = mock_bank
    clock = Clock()
    with client_for(content, db, clock) as client:
        sid = session_id_from(str(client.post(f"/mocks/{MOCK_ID}/start").url))
        client.post(f"/sessions/{sid}/questions/2/save", data=form_for(questions[1], ["a", "c"], marked=True))
        client.post(f"/sessions/{sid}/questions/3/save", data=form_for(questions[2], "typed answer"))
        deadline = re.search(r'data-deadline="([^"]+)"', client.get(f"/sessions/{sid}/questions/1").text).group(1)

    clock.advance(minutes=20)  # "server restart" twenty minutes later
    with client_for(content, db, clock) as client:
        assert "Resume" in client.get("/").text
        resumed = client.post(f"/mocks/{MOCK_ID}/start")
        assert session_id_from(str(resumed.url)) == sid
        assert f'data-deadline="{deadline}"' in resumed.text
        assert 'data-remaining="4200"' in resumed.text  # 70 minutes left
        q2 = client.get(f"/sessions/{sid}/questions/2").text
        assert 'value="a" data-key="a" checked' in q2 and 'value="c" data-key="c" checked' in q2
        assert 'name="marked" value="1" checked' in q2
        assert 'value="typed answer"' in client.get(f"/sessions/{sid}/questions/3").text


def test_deadline_is_enforced_by_the_server(mock_bank, db: Path) -> None:
    content, questions = mock_bank
    clock = Clock()
    with client_for(content, db, clock) as client:
        sid = session_id_from(str(client.post(f"/mocks/{MOCK_ID}/start").url))
        client.post(f"/sessions/{sid}/questions/1/save", data=form_for(questions[0], correct_response(questions[0])))
        clock.advance(minutes=90, seconds=10)
        late = client.post(
            f"/sessions/{sid}/questions/2/save",
            data=form_for(questions[1], correct_response(questions[1])),
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
        assert late.headers["HX-Redirect"] == f"/sessions/{sid}/results"
        late_plain = client.post(
            f"/sessions/{sid}/questions/3", data=form_for(questions[2], "x", go="next"), follow_redirects=False
        )
        assert late_plain.status_code == 303 and late_plain.headers["location"] == f"/sessions/{sid}/results"
        results = client.get(f"/sessions/{sid}/results").text
        assert "Raw score 1 / 60" in results and "Time used: 90:00 of 90:00" in results

    with Store(db) as store:
        answers = store.answers(sid)
        assert len(answers) == 60 and sum(a["correct"] for a in answers) == 1
        assert store.session(sid).finished_at == "2026-10-26T10:30:00+00:00"


def test_a_mock_left_past_its_deadline_is_submitted_on_the_next_request(mock_bank, db: Path) -> None:
    content, _ = mock_bank
    clock = Clock()
    with client_for(content, db, clock) as client:
        sid = session_id_from(str(client.post(f"/mocks/{MOCK_ID}/start").url))
        clock.advance(hours=3)
        page = client.get(f"/sessions/{sid}/questions/7")
        assert page.url.path == f"/sessions/{sid}/results" and "Raw score 0 / 60" in page.text


def test_unknown_session_question_and_mock(mock_bank, db: Path) -> None:
    content, _ = mock_bank
    with client_for(content, db, Clock()) as client:
        assert client.get("/sessions/99/questions/1").status_code == 404
        assert client.post("/mocks/101-mock-07/start").status_code == 404
        sid = session_id_from(str(client.post(f"/mocks/{MOCK_ID}/start").url))
        assert client.get(f"/sessions/{sid}/questions/61").status_code == 404
        assert client.get(f"/sessions/{sid}/results", follow_redirects=False).status_code == 303


def test_static_files_and_offline_htmx(mock_bank, db: Path) -> None:
    content, _ = mock_bank
    with client_for(content, db, Clock()) as client:
        page = client.get("/").text
        assert '<script src="/static/htmx.min.js">' in page and "unpkg" not in page and "cdn" not in page
        assert client.get("/static/htmx.min.js").status_code == 200
        assert client.get("/static/app.js").status_code == 200


def test_the_real_101_mocks_load(tmp_path: Path) -> None:
    # Smoke test only: the list page names the committed mocks; no question text is read here.
    with TestClient(create_app(ROOT / "content", tmp_path / "results.sqlite")) as client:
        page = client.get("/").text
    for k in range(1, 11):
        assert f"/mocks/101-mock-{k:02d}/start" in page
