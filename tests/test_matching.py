from __future__ import annotations

import pytest

from engine.matching import is_correct, normalize
from engine.model import Bank, FillIn, Question


def fill_in(match: str, accepted: list[str], case_sensitive: bool = True) -> Question:
    return Question(
        id="101-101.1-0999",
        type="fill_in",
        difficulty=1,
        pool="practice",
        objective="101.1",
        stem="Synthetic fill-in question.",
        explanation="Synthetic explanation.",
        review_status="draft",
        fill_in=FillIn(tuple(accepted), match, case_sensitive),  # type: ignore[arg-type]
    )


# --- single choice


def test_single_choice(bank_101: Bank) -> None:
    q = bank_101.question("101-101.1-0001")
    assert is_correct(q, "b")
    assert not is_correct(q, "a")
    assert not is_correct(q, "")


@pytest.mark.parametrize("response", [["b"], ("b",), {"b"}, None])
def test_single_choice_rejects_a_non_string(bank_101: Bank, response) -> None:
    with pytest.raises(TypeError):
        is_correct(bank_101.question("101-101.1-0001"), response)


# --- multi choice: all or nothing


def test_multi_choice_exact_set_is_correct_in_any_order(bank_101: Bank) -> None:
    q = bank_101.question("101-101.1-0002")
    assert is_correct(q, ["a", "c"])
    assert is_correct(q, ("c", "a"))


@pytest.mark.parametrize("response", [["a"], ["c"], ["a", "b", "c"], ["a", "c", "d"], [], ["b", "d"]])
def test_multi_choice_subset_superset_and_wrong_sets_are_wrong(bank_101: Bank, response: list[str]) -> None:
    assert not is_correct(bank_101.question("101-101.1-0002"), response)


def test_multi_choice_rejects_a_plain_string(bank_101: Bank) -> None:
    with pytest.raises(TypeError):
        is_correct(bank_101.question("101-101.1-0002"), "ac")


# --- fill in: exact


def test_exact_requires_identical_text() -> None:
    q = fill_in("exact", ["ls -i"])
    assert is_correct(q, "ls -i")
    assert not is_correct(q, " ls -i")
    assert not is_correct(q, "ls  -i")
    assert not is_correct(q, "LS -I")


def test_exact_case_insensitive() -> None:
    assert is_correct(fill_in("exact", ["ls -i"], case_sensitive=False), "LS -I")


# --- fill in: normalized


def test_normalize() -> None:
    assert normalize("  ls \t  -i \n") == "ls -i"


def test_normalized_ignores_outer_and_repeated_whitespace(bank_101: Bank) -> None:
    q = bank_101.question("101-101.1-0003")
    assert is_correct(q, " ls   -i ")
    assert is_correct(q, "ls\t-i")
    assert not is_correct(q, "ls-i")


def test_normalized_also_normalizes_accepted_answers() -> None:
    assert is_correct(fill_in("normalized", ["  ls   -i "]), "ls -i")


def test_normalized_is_case_sensitive_by_default(bank_101: Bank) -> None:
    assert not is_correct(bank_101.question("101-101.1-0003"), "LS -I")


def test_normalized_case_insensitive() -> None:
    assert is_correct(fill_in("normalized", ["ls -i"], case_sensitive=False), "LS -I")


# --- fill in: regex


def test_regex_full_match(bank_101: Bank) -> None:
    q = bank_101.question("101-101.2-0001")
    assert is_correct(q, "ls -i")
    assert is_correct(q, "ls    --inode")


def test_regex_does_not_match_a_response_that_merely_contains_it(bank_101: Bank) -> None:
    q = bank_101.question("101-101.2-0001")
    assert not is_correct(q, "sudo ls -i")
    assert not is_correct(q, "ls -i /tmp")
    assert not is_correct(q, "ls -il")


@pytest.mark.parametrize("response", ["ldconfig", "ldconfig ", " ldconfig", "\tldconfig\n"])
def test_regex_ignores_outer_whitespace(response: str) -> None:
    assert is_correct(fill_in("regex", ["ldconfig"]), response)


@pytest.mark.parametrize("response", ["sudoldconfig", "sudo ldconfig", "ldconfig -p", "ld config"])
def test_regex_still_rejects_other_text(response: str) -> None:
    assert not is_correct(fill_in("regex", ["ldconfig"]), response)


def test_regex_leaves_internal_whitespace_to_the_pattern() -> None:
    assert not is_correct(fill_in("regex", ["ls -i"]), "ls  -i")
    assert is_correct(fill_in("regex", [r"ls\s+-i"]), " ls  -i ")


def test_regex_case_sensitivity() -> None:
    assert not is_correct(fill_in("regex", [r"ls\s+-i"]), "LS -I")
    assert is_correct(fill_in("regex", [r"ls\s+-i"], case_sensitive=False), "LS -I")


def test_fill_in_rejects_a_list(bank_101: Bank) -> None:
    with pytest.raises(TypeError):
        is_correct(bank_101.question("101-101.1-0003"), ["ls -i"])
