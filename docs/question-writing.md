# Writing and checking questions

The rules every generated question follows. The workflow around them (batches, counts, who checks
what) is in `docs/adr/2026-10-25-question-generation-workflow.md`; the schema is in `schemas/`.

## Writing

- **Original wording.** Read the lesson for facts, then write from scratch. Never restate a Guided
  or Explorational Exercise, even with new names, and don't paraphrase lesson sentences closely. Test
  the same fact through a different scenario.
- **Self-contained stem.** Answerable without the lesson open. Put command output or file contents in
  `exhibit`, not inside the stem.
- **One defensible answer.** If a knowledgeable admin could argue for a second option, rewrite.
  Check every distractor by asking "would this actually fix / show / do it?", not just "is this the
  intended answer?".
- **Plausible distractors.** Real commands, real paths, real options, wrong for a stated reason. No
  joke options, no "all of the above" / "none of the above".
- **No giveaways.** The correct option should not be the longest, the only one that explains a
  mechanism, or the only one echoing the stem's wording. Put explanations in the rationale.
- **Spread answer positions.** Across a batch, correct answers fall roughly evenly on a, b, c, d.
- **Every option gets a `rationale`.** Why it is right, or the specific reason it is wrong. Rationales
  must be true statements in their own right.
- **Negatives in bold caps.** "Which option does **NOT** …" — and use them sparingly.
- **Distribution-neutral** unless the objective is distribution-specific (e.g. 102.4 Debian, 102.5 RPM).
- **Fill-in answers** accept every common correct form, consistently across a batch: the bare
  option, the full command, a `sudo` prefix and full paths where natural. Use `normalized` matching
  when the forms can be listed, `regex` (full match) when they can't.
- **Current behaviour wins.** Where the lesson describes older behaviour, test current behaviour or
  avoid the point, and say so in the PR.

## Checking

| Pass | Who | Does |
|---|---|---|
| 1 | The writing session | Re-reads each question against its lesson: fact, single right answer, originality, difficulty |
| 2 | A separate agent that did not write the batch | Answers each question **cold** from a copy without answers, then compares with the key, and tests every command and scenario on a real Linux system |

The writer fixes pass-2 findings before the PR. A rewritten question goes back to the pass-2
reviewer. Each pass adds an entry to `review.history`:

```yaml
review:
  status: pass2
  history:
    - { stage: pass1, by: claude, date: "2026-10-25", result: ok }
    - { stage: pass2, by: claude-reviewer, date: "2026-10-25", result: fixed, notes: "…what changed and why" }
```

`result` is `ok` (no change), `fixed` (changed, say what in `notes`) or `rejected` (question dropped).

## Human sign-off (maintainer)

- **Don't read holdout questions before taking the mocks** — that leaks them. A content PR's
  summary (counts, what the checks found, lesson-vs-reality notes) is enough to merge it.
- **Practice questions:** flag anything wrong while studying in the CLI.
- **Holdout questions:** review them on the results screen after the mock. That review is the
  `human` history entry and makes the question `approved`.
