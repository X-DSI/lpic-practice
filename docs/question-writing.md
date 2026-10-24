# Writing and checking questions

The rules every generated question follows. The workflow around them (batches, counts, review) is in
`docs/adr/proposed/2026-10-25-question-generation-workflow.md`; the schema is in `schemas/`.

## Writing

- **Original wording.** Read the lesson for facts, then write from scratch. Never restate a Guided
  or Explorational Exercise, even with new names. Test the same fact through a different scenario.
- **Self-contained stem.** Answerable without the lesson open. Put command output or file contents in
  `exhibit`, not inside the stem.
- **One defensible answer.** If a knowledgeable admin could argue for a second option, rewrite.
- **Plausible distractors.** Real commands, real paths, real options, wrong for a stated reason. No
  joke options, no "all of the above" / "none of the above".
- **Every option gets a `rationale`.** Why it is right, or the specific reason it is wrong.
- **Negatives in bold caps.** "Which option does **NOT** …" — and use them sparingly.
- **Distribution-neutral** unless the objective is distribution-specific (e.g. 102.4 Debian, 102.5 RPM).
- **Fill-in answers** list every common correct variant: short and long options, `sudo` prefix or
  full paths where natural. Use `normalized` matching by default; `regex` only when the variants
  can't be listed.
- **Current behaviour wins.** Where the lesson describes older behaviour, test current behaviour or
  avoid the point.

## Checking

Pass 1 (against the source) and pass 2 (against reality) each add an entry to `review.history`:

```yaml
review:
  status: pass2
  history:
    - { stage: pass1, by: claude, date: "2026-10-25", result: ok }
    - { stage: pass2, by: claude, date: "2026-10-25", result: fixed, notes: "…what changed and why" }
```

`result` is `ok` (no change), `fixed` (changed, say what in `notes`) or `rejected` (question dropped).

## Reviewing a content PR (maintainer)

1. Read each question cold, answering it before looking at `answer`.
2. Check the rationale for each wrong option, not just the right one.
3. Comment on any question to change; approve the PR when happy. The final commit then marks the
   batch `approved`.
