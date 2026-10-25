from __future__ import annotations

import json
from pathlib import Path

import yaml

from engine.build import FORMAT_VERSION, main


def run_build(content: Path, out: Path) -> int:
    return main(["--content-dir", str(content), "--out-dir", str(out)])


def test_build_writes_one_json_file_per_exam(content_copy: Path, tmp_path: Path) -> None:
    out = tmp_path / "build" / "content"
    assert run_build(content_copy, out) == 0
    assert sorted(p.name for p in out.iterdir()) == ["101.json", "102.json"]

    doc = json.loads((out / "101.json").read_text(encoding="utf-8"))
    assert doc["format_version"] == FORMAT_VERSION
    assert doc["exam"] == "101"
    assert doc["objectives"]["exam"] == "101"
    assert [q["id"] for q in doc["questions"]] == sorted(q["id"] for q in doc["questions"])
    assert len(doc["questions"]) == 7
    assert doc["mocks"] == []


def test_two_builds_are_byte_identical(content_copy: Path, tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    assert run_build(content_copy, first) == 0
    assert run_build(content_copy, second) == 0
    for name in ("101.json", "102.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_output_is_utf8_with_sorted_keys(content_copy: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert run_build(content_copy, out) == 0
    text = (out / "102.json").read_bytes().decode("utf-8")
    assert "with a non-ASCII dash" in text and "—" in text
    assert text.endswith("}\n")
    doc = json.loads(text)
    assert list(doc) == sorted(doc)


def test_invalid_content_writes_nothing(content_copy: Path, tmp_path: Path, capsys) -> None:
    path = content_copy / "101" / "questions" / "101.1.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("answer: [b]", "answer: [z]"), encoding="utf-8")
    out = tmp_path / "out"
    assert run_build(content_copy, out) == 1
    assert not out.exists()
    assert "101-101.1-0001/answer/0" in capsys.readouterr().out


def test_invalid_content_leaves_an_earlier_build_untouched(content_copy: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert run_build(content_copy, out) == 0
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    objectives = content_copy / "102" / "objectives.yaml"
    objectives.write_text(
        objectives.read_text(encoding="utf-8").replace("weight: 10", "weight: 9", 1), encoding="utf-8"
    )
    assert run_build(content_copy, out) == 1
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def add_mock(content: Path) -> None:
    """Add 60 synthetic holdout questions (10 per objective) and a mock exam using them to exam 101."""
    objectives = yaml.safe_load((content / "101" / "objectives.yaml").read_text(encoding="utf-8"))
    ids = []
    for n, objective in enumerate(o["id"] for t in objectives["topics"] for o in t["objectives"]):
        path = content / "101" / "questions" / f"{objective}.yaml"
        data = (
            yaml.safe_load(path.read_text(encoding="utf-8"))
            if path.exists()
            else {"schema_version": 1, "exam": "101", "objective": objective, "questions": []}
        )
        for i in range(10):
            qid = f"101-{objective}-{100 + i:04d}"
            ids.append(qid)
            data["questions"].append(
                {
                    "id": qid,
                    "type": "fill_in",
                    "difficulty": (n * 10 + i) % 5 + 1,
                    "pool": "holdout",
                    "stem": "Synthetic holdout question for a mock.",
                    "fill_in": {"accepted": ["fixture"], "match": "exact"},
                    "explanation": "Synthetic explanation.",
                    "source": {
                        "material": "Fixture material",
                        "material_version": "2000-01-01",
                        "objective": objective,
                        "lesson": 1,
                    },
                    "review": {"status": "draft"},
                }
            )
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mock = {
        "schema_version": 1,
        "id": "101-mock-01",
        "exam": "101",
        "number": 1,
        "duration_minutes": 90,
        "difficulty_mix": {"1": 12, "2": 12, "3": 12, "4": 12, "5": 12},
        "questions": ids,
    }
    (content / "101" / "mocks").mkdir(exist_ok=True)
    (content / "101" / "mocks" / "mock-01.yaml").write_text(yaml.safe_dump(mock, sort_keys=False), encoding="utf-8")


def test_build_includes_mock_manifests(content_copy: Path, tmp_path: Path) -> None:
    add_mock(content_copy)
    out = tmp_path / "out"
    assert run_build(content_copy, out) == 0
    doc = json.loads((out / "101.json").read_text(encoding="utf-8"))
    assert [m["id"] for m in doc["mocks"]] == ["101-mock-01"]
    assert len(doc["mocks"][0]["questions"]) == 60
    assert len(doc["questions"]) == 67
