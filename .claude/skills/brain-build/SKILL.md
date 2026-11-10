---
name: brain-build
description: Execute plan items with the right helpers and real checks: delegation briefs, running checks quietly, escalating on failure, checkpointing. Use after brain-plan or brain-start when there are items to build, or for "Build it", "Constrúyelo".
---

# Build

The outcome is each plan item finished with its check passing and evidence recorded, at the lowest cost that holds the quality bar.

BRAIN means `python3 "${CLAUDE_SKILL_DIR}/../../../bin/brain"`.

## Do it yourself or delegate

Delegate an item only when it is self-contained, its raw material is large next to what you need back, and it has a check. Otherwise do it yourself: a helper starts cold and pays to load its context. Use the agents in `.claude/agents/`: scout for bulk reading, builder for implementation, writer for prose, researcher for sourced questions.

## The brief

A helper does not see this conversation. Every brief carries:

- the goal and why it matters, and who the output is for;
- the constraints, including what must not change;
- the files it owns (no two running helpers own the same file);
- the check that proves it worked, as a command where possible;
- what to return: the result, the check's real output, under about 2,000 tokens, detail in a named file.

Give facts, not instructions to be careful. Say which actions are approved.

## Checks and escalation

Run builds and tests through `BRAIN run -- <command>`: the full log goes to a file and only the result and failing lines come back. Record evidence with `BRAIN req evidence` (see `--help`).

Start at the routed model and effort (`BRAIN route "<item>"`). If the check fails, read why; fix it or re-run that item one step up the escalation order in `memory/models.json` (Sonnet medium, Opus medium, Opus high, Fable high). Escalate on a failed check, not on a hunch.

Timing and performance checks run when no helpers are working, because other agents' load produces false failures.

## Checkpoint

After each item: `BRAIN checkpoint --item <done> --next <ids>`, and commit. Unfinished work is pushed as a branch, not left in temporary folders.

## Tell the owner

Nothing until something is visible or blocked. Then one or two lines: what is now done and where he can see it.
