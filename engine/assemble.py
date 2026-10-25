"""Assemble the 10 mock exams for one exam from its holdout bank (mock-exam-composition ADR).

Usage:
    python -m engine.assemble <exam> [--seed N] [--content-dir content]

Writes `content/<exam>/mocks/mock-01.yaml` … `mock-10.yaml`. Every mock has exactly `weight`
questions from each objective, no question is used twice, and each mock's difficulty counts are
within ±`TOLERANCE` per level of its row in `DIFFICULTY_MIX`. Eligible questions are holdout, not
retired, and `pass2` or `approved`. The same bank and seed always give byte-identical files.

If the bank can't satisfy every constraint, nothing is written and the problems are printed: the
shortfall per objective and per difficulty level, or the mocks whose difficulty mix is off.

How it works: questions are first allocated as counts per (objective, mock, level). The start is a
ramp — each objective's chosen questions, sorted by difficulty, are dealt to mocks 1…10 in turn —
and a deterministic local search then swaps levels between mocks (or with unused questions of the
same objective) until every mock's mix is within tolerance. Concrete question IDs and the order
inside each mock come from the seed.
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from engine.loader import load_exam
from engine.model import Bank, Question
from engine.validation import CONTENT_DIR, MIX_TOLERANCE, MOCK_READY_STATUSES, validate

MOCKS = 10
LEVELS = (1, 2, 3, 4, 5)
TOLERANCE = MIX_TOLERANCE
DEFAULT_SEED = 1

# Difficulty mix per mock (L1–L5), from docs/difficulty-rubric.md. tests/test_assemble.py checks that
# this table equals the document's.
DIFFICULTY_MIX: dict[int, tuple[int, int, int, int, int]] = {
    1: (30, 20, 10, 0, 0),
    2: (24, 22, 12, 2, 0),
    3: (18, 22, 14, 6, 0),
    4: (12, 20, 18, 8, 2),
    5: (8, 16, 20, 12, 4),
    6: (4, 12, 20, 16, 8),
    7: (2, 8, 18, 20, 12),
    8: (0, 6, 14, 22, 18),
    9: (0, 4, 10, 22, 24),
    10: (0, 2, 8, 20, 30),
}

MAX_RESTARTS = 200
KICK_MOVES = 6


class AssemblyError(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__(f"{len(problems)} problem(s)")
        self.problems = problems


def level_split(n: int) -> dict[int, int]:
    """Split `n` questions across levels in proportion to the bank-wide totals (largest remainder)."""
    totals = [sum(DIFFICULTY_MIX[k][i] for k in DIFFICULTY_MIX) for i in range(len(LEVELS))]
    grand = sum(totals)
    exact = [n * t / grand for t in totals]
    counts = [int(e) for e in exact]
    by_remainder = sorted(range(len(LEVELS)), key=lambda i: (-(exact[i] - counts[i]), i))
    for i in by_remainder[: n - sum(counts)]:
        counts[i] += 1
    return {level: counts[i] for i, level in enumerate(LEVELS)}


def eligible_questions(bank: Bank) -> dict[str, dict[int, list[Question]]]:
    """Eligible questions per objective and level, sorted by ID."""
    pools: dict[str, dict[int, list[Question]]] = {o.id: {lv: [] for lv in LEVELS} for o in bank.objectives}
    for q in bank.questions:
        if q.pool == "holdout" and not q.retired and q.review_status in MOCK_READY_STATUSES:
            pools[q.objective][q.difficulty].append(q)
    return pools


def supply_problems(bank: Bank, pools: dict[str, dict[int, list[Question]]]) -> list[str]:
    """Shortfalls that make assembly impossible whatever the search does."""
    problems = []
    for o in bank.objectives:
        have = sum(len(qs) for qs in pools[o.id].values())
        need = MOCKS * o.weight
        if have < need:
            split = ", ".join(f"L{lv} {len(pools[o.id][lv])}" for lv in LEVELS)
            problems.append(f"objective {o.id}: {have} eligible holdout question(s) ({split}); needs {need}")
    for i, level in enumerate(LEVELS):
        have = sum(len(p[level]) for p in pools.values())
        need = sum(max(0, row[i] - TOLERANCE) for row in DIFFICULTY_MIX.values())
        if have < need:
            problems.append(f"difficulty {level}: {have} eligible holdout question(s); the mocks need at least {need}")
    return problems


@dataclass
class Allocation:
    """Counts per objective, mock and level, plus each objective's unused eligible questions per level."""

    used: dict[str, list[dict[int, int]]]
    unused: dict[str, dict[int, int]]
    mix: list[dict[int, int]]

    def deviation(self, k: int, level: int) -> int:
        return self.mix[k][level] - DIFFICULTY_MIX[k + 1][level - 1]


def initial_allocation(bank: Bank, pools: dict[str, dict[int, list[Question]]]) -> Allocation:
    used: dict[str, list[dict[int, int]]] = {}
    unused: dict[str, dict[int, int]] = {}
    for o in bank.objectives:
        available = {lv: len(pools[o.id][lv]) for lv in LEVELS}
        n = MOCKS * o.weight
        # Choose n questions, as close as availability allows to the bank-wide level split.
        chosen = {lv: min(c, available[lv]) for lv, c in level_split(n).items()}
        while sum(chosen.values()) < n:
            spare = [lv for lv in LEVELS if chosen[lv] < available[lv]]
            short = max(LEVELS, key=lambda lv: level_split(n)[lv] - chosen[lv])
            chosen[min(spare, key=lambda lv: (abs(lv - short), lv))] += 1
        # Ramp: sorted by difficulty, dealt `weight` at a time to mocks 1…10.
        ramp = [lv for lv in LEVELS for _ in range(chosen[lv])]
        used[o.id] = [{lv: 0 for lv in LEVELS} for _ in range(MOCKS)]
        for i, lv in enumerate(ramp):
            used[o.id][i // o.weight][lv] += 1
        unused[o.id] = {lv: available[lv] - chosen[lv] for lv in LEVELS}
    mix = [{lv: sum(used[o][k][lv] for o in used) for lv in LEVELS} for k in range(MOCKS)]
    return Allocation(used, unused, mix)


def cell_cost(dev: int) -> tuple[int, int]:
    """(squared excess beyond the tolerance, squared deviation) for one mock and level."""
    excess = max(0, abs(dev) - TOLERANCE)
    return excess * excess, dev * dev


def total_cost(alloc: Allocation) -> tuple[int, int]:
    costs = [cell_cost(alloc.deviation(k, lv)) for k in range(MOCKS) for lv in LEVELS]
    return sum(c[0] for c in costs), sum(c[1] for c in costs)


def move_delta(alloc: Allocation, changes: dict[tuple[int, int], int]) -> tuple[int, int]:
    """Cost change if each (mock, level) count in `changes` moves by its amount."""
    before = after = (0, 0)
    for (k, lv), d in changes.items():
        dev = alloc.deviation(k, lv)
        b, a = cell_cost(dev), cell_cost(dev + d)
        before = (before[0] + b[0], before[1] + b[1])
        after = (after[0] + a[0], after[1] + a[1])
    return after[0] - before[0], after[1] - before[1]


def moves(alloc: Allocation, objective: str):
    """Every swap of one question's level between two mocks, or with an unused question."""
    used = alloc.used[objective]
    for a in range(MOCKS):
        for l1 in LEVELS:
            if not used[a][l1]:
                continue
            for l2 in LEVELS:
                if l2 == l1:
                    continue
                if alloc.unused[objective][l2]:
                    yield ("unused", a, l1, None, l2), {(a, l1): -1, (a, l2): +1}
                for b in range(a + 1, MOCKS):
                    if used[b][l2]:
                        yield ("swap", a, l1, b, l2), {(a, l1): -1, (a, l2): +1, (b, l2): -1, (b, l1): +1}


def apply(alloc: Allocation, objective: str, move: tuple) -> None:
    kind, a, l1, b, l2 = move
    used = alloc.used[objective]
    used[a][l1] -= 1
    used[a][l2] += 1
    alloc.mix[a][l1] -= 1
    alloc.mix[a][l2] += 1
    if kind == "swap":
        used[b][l2] -= 1
        used[b][l1] += 1
        alloc.mix[b][l2] -= 1
        alloc.mix[b][l1] += 1
    else:
        alloc.unused[objective][l2] -= 1
        alloc.unused[objective][l1] += 1


def descend(alloc: Allocation) -> None:
    """First-improvement local search, in a fixed order, until no move lowers the cost."""
    improved = True
    while improved:
        improved = False
        for objective in alloc.used:
            for move, changes in list(moves(alloc, objective)):
                if move_delta(alloc, changes) < (0, 0) and still_valid(alloc, objective, move):
                    apply(alloc, objective, move)
                    improved = True


def still_valid(alloc: Allocation, objective: str, move: tuple) -> bool:
    """A move listed earlier in the same pass may have been invalidated by one applied since."""
    kind, a, l1, b, l2 = move
    used = alloc.used[objective]
    if not used[a][l1]:
        return False
    return bool(alloc.unused[objective][l2]) if kind == "unused" else bool(used[b][l2])


def copy(alloc: Allocation) -> Allocation:
    return Allocation(
        {o: [dict(m) for m in ms] for o, ms in alloc.used.items()},
        {o: dict(u) for o, u in alloc.unused.items()},
        [dict(m) for m in alloc.mix],
    )


def search(alloc: Allocation, rng: random.Random) -> Allocation:
    """Descend; if a violation remains, kick with a few random swaps and descend again."""
    descend(alloc)
    best = copy(alloc)
    objectives = sorted(alloc.used)
    for _ in range(MAX_RESTARTS):
        if total_cost(best)[0] == 0:
            break
        alloc = copy(best)
        for _ in range(KICK_MOVES):
            objective = rng.choice(objectives)
            candidates = [m for m, _ in moves(alloc, objective)]
            if candidates:
                apply(alloc, objective, rng.choice(candidates))
        descend(alloc)
        if total_cost(alloc) < total_cost(best):
            best = alloc
    return best


def mix_problems(alloc: Allocation) -> list[str]:
    problems = []
    for k in range(MOCKS):
        for lv in LEVELS:
            dev = alloc.deviation(k, lv)
            if abs(dev) > TOLERANCE:
                target = DIFFICULTY_MIX[k + 1][lv - 1]
                problems.append(
                    f"mock {k + 1:02d}: difficulty {lv} would have {alloc.mix[k][lv]} question(s), "
                    f"target {target} (±{TOLERANCE})"
                )
    return problems


def assemble(bank: Bank, seed: int = DEFAULT_SEED, duration_minutes: int = 90) -> dict[str, str]:
    """Return `{file name: YAML text}` for the 10 mocks, or raise `AssemblyError`."""
    pools = eligible_questions(bank)
    problems = supply_problems(bank, pools)
    if problems:
        raise AssemblyError(problems)
    rng = random.Random(seed)
    alloc = search(initial_allocation(bank, pools), rng)
    problems = mix_problems(alloc)
    if problems:
        raise AssemblyError(problems)

    # Deal concrete questions: within each (objective, level) a seeded shuffle, taken in mock order.
    mocks: list[list[str]] = [[] for _ in range(MOCKS)]
    for objective in sorted(alloc.used):
        for lv in LEVELS:
            ids = [q.id for q in pools[objective][lv]]
            rng.shuffle(ids)
            for k in range(MOCKS):
                take = alloc.used[objective][k][lv]
                mocks[k].extend(ids[:take])
                ids = ids[take:]

    files = {}
    for k, ids in enumerate(mocks, start=1):
        random.Random(f"{seed}:{bank.exam}:{k}").shuffle(ids)
        doc = {
            "schema_version": 1,
            "id": f"{bank.exam}-mock-{k:02d}",
            "exam": bank.exam,
            "number": k,
            "title": f"Mock exam {k}",
            "duration_minutes": duration_minutes,
            "assembly_seed": seed,
            "difficulty_mix": {str(lv): DIFFICULTY_MIX[k][lv - 1] for lv in LEVELS},
            "questions": ids,
        }
        files[f"mock-{k:02d}.yaml"] = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exam")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"assembly seed (default {DEFAULT_SEED})")
    ap.add_argument("--content-dir", type=Path, default=CONTENT_DIR)
    args = ap.parse_args(argv)
    content_dir: Path = args.content_dir.resolve()
    mocks_dir = content_dir / args.exam / "mocks"

    if not (content_dir / args.exam / "objectives.yaml").exists():
        print(f"FAIL: no objectives.yaml for exam {args.exam!r} in {content_dir}")
        return 1
    # The mocks being replaced may be stale; everything else must be valid.
    stale = f"{(mocks_dir.relative_to(content_dir.parent)).as_posix()}/"
    errors = [e for e in validate(content_dir)[0] if not e.startswith(stale)]
    if errors:
        print("FAIL: content is invalid; nothing written\n")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    bank = load_exam(args.exam, content_dir)
    duration = yaml.safe_load((content_dir / args.exam / "objectives.yaml").read_text(encoding="utf-8"))["exam_format"][
        "duration_minutes"
    ]
    try:
        files = assemble(bank, args.seed, duration)
    except AssemblyError as exc:
        print(f"FAIL: cannot assemble {MOCKS} mocks for exam {args.exam}; nothing written\n")
        for p in exc.problems:
            print(f"  ✗ {p}")
        return 1

    mocks_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (mocks_dir / name).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {mocks_dir / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
