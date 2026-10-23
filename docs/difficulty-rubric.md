# Difficulty rubric

Every question gets a `difficulty` from 1 to 5. Rate by what the question
*requires*, not by how obscure the topic feels.

| Level | Requires | Example shape |
|---|---|---|
| 1 | Recall what a command, file or concept is | "Which command lists block devices?" |
| 2 | Choose the right command or file for a task | "Which file defines the default systemd target?" |
| 3 | Know specific options and flags | "Which `tar` option extracts while preserving permissions?" |
| 4 | Combine tools, interpret output, handle edge cases | Read `ls -l` output and decide what a user can do |
| 5 | Multi-step scenarios, subtle distractors, rarely used options | Order the steps to move `/home` to a new partition safely |

Rules of thumb:

- Fill-in-the-blank is usually one level harder than the same question as multiple choice.
- A distractor that is *almost* right (wrong flag, right command) raises difficulty by about one level.
- Low-weight "awareness" objectives (e.g. 106.2, 106.3) rarely justify level 5.

## Difficulty mix per mock exam (60 questions)

| Mock | L1 | L2 | L3 | L4 | L5 |
|---|---|---|---|---|---|
| 1 | 30 | 20 | 10 | 0 | 0 |
| 2 | 24 | 22 | 12 | 2 | 0 |
| 3 | 18 | 22 | 14 | 6 | 0 |
| 4 | 12 | 20 | 18 | 8 | 2 |
| 5 | 8 | 16 | 20 | 12 | 4 |
| 6 | 4 | 12 | 20 | 16 | 8 |
| 7 | 2 | 8 | 18 | 20 | 12 |
| 8 | 0 | 6 | 14 | 22 | 18 |
| 9 | 0 | 4 | 10 | 22 | 24 |
| 10 | 0 | 2 | 8 | 20 | 30 |
| **Total** | **98** | **132** | **144** | **128** | **98** |

The totals row is the holdout bank's target difficulty split per exam (600 questions).
