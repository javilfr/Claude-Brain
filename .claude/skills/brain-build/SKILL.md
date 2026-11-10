---
name: brain-build
description: Execute plan items with the right helpers and real checks: delegation briefs, running checks quietly, escalating on failure, checkpointing. Use after brain-plan or brain-start when there are items to build, or for "Build it", "Constrúyelo".
---

# Build

The outcome is each plan item finished with its check passing and evidence recorded, at the lowest cost that holds the quality bar.

## Do it yourself or delegate

Delegate an item only when it is self-contained, its raw material is large next to what you need back, and it has a check; otherwise do it yourself. Use the agents in `.claude/agents/`: scout for bulk reading, builder for implementation, writer for prose, researcher for sourced questions. Each sets its own model; the tiers and the escalation order are in `memory/models.json`.

## The brief

A helper does not see this conversation. Every delegated item carries an acceptance command that exits 0 only when the item is done; without one, do not delegate it. When the plan is a tickets file, `BRAIN plan packet <tickets.json> <ticket-id>` prints the brief. Otherwise write it yourself:

- the goal, why it matters, and who the output is for;
- the constraints, including what must not change, and which actions are approved;
- the files it owns (no two running helpers own the same file);
- the acceptance command;
- what to return: the result and the command's real output, under about 2,000 tokens, detail in a named file.

Give facts, not instructions to be careful.

## Checks and escalation

Run the acceptance command yourself when the helper returns. Record evidence with `BRAIN req evidence <id> "<log path or path:line>" --done` (without `--done` the line stays open).

If a check fails, read why. Fix it, or re-run that item one step up the escalation order. Escalate on a failed check, not on a hunch. Run timing checks when no helpers are working, because their load produces false failures.

## Checkpoint

After each item: `BRAIN checkpoint --done <id> --item <next id> --next <id> --next <id> --push` (one `--next` per item, up to three). It commits only the bookkeeping files and pushes the branch, so a new session sees the state; commit the work itself first. Keep going while `.brain/CHECKLIST.md` has open lines and nothing blocks them.

## Tell the owner

Nothing until something is visible or blocked. Then one or two lines: what is now done and where he can see it.
