"""Grade one response to one question. Items score 0 or 1 (proposed LPI-style scoring ADR).

Responses by question type:
- `single_choice`: the selected option ID, e.g. `"b"`.
- `multi_choice`: the selected option IDs, e.g. `["a", "c"]`; order doesn't matter.
- `fill_in`: the typed text.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from engine.model import FillIn, Question


def is_correct(question: Question, response: str | Iterable[str]) -> bool:
    if question.type == "single_choice":
        if not isinstance(response, str):
            raise TypeError(f"{question.id}: single_choice response must be one option ID string")
        return response == question.answer[0]
    if question.type == "multi_choice":
        if isinstance(response, str):
            raise TypeError(f"{question.id}: multi_choice response must be a collection of option IDs")
        # All or nothing: exactly the answer set, no more and no fewer.
        return set(response) == set(question.answer)
    if question.type == "fill_in":
        if not isinstance(response, str):
            raise TypeError(f"{question.id}: fill_in response must be a string")
        assert question.fill_in is not None
        return matches_fill_in(question.fill_in, response)
    raise ValueError(f"{question.id}: unknown question type {question.type!r}")


def normalize(text: str) -> str:
    """Trim both ends and collapse internal runs of whitespace to one space."""
    return " ".join(text.split())


def matches_fill_in(fill_in: FillIn, response: str) -> bool:
    if fill_in.match == "regex":
        flags = 0 if fill_in.case_sensitive else re.IGNORECASE
        # Each accepted entry must match the whole response, not just part of it. Outer whitespace
        # is dropped first; internal whitespace is left to the pattern (e.g. `\s+`).
        response = response.strip()
        return any(re.fullmatch(pattern, response, flags) for pattern in fill_in.accepted)

    def prepare(text: str) -> str:
        if fill_in.match == "normalized":
            text = normalize(text)
        return text if fill_in.case_sensitive else text.casefold()

    candidate = prepare(response)
    return any(candidate == prepare(accepted) for accepted in fill_in.accepted)
