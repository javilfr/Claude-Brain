---
name: brain-build
description: Execute plan items with the right helpers and real checks: delegation briefs, running checks quietly, escalating on failure, checkpointing. Use after brain-plan or brain-start when there are items to build, or for "Build it", "Constrúyelo".
---

# Build

The outcome is each plan item finished with its check passing and evidence recorded, at the lowest cost that holds the quality bar.

## Do it yourself or hire

A helper starts cold, so hire one only for work that is self-contained, bulky next to what you need back, and checkable. HR decides and prepares it:

`BRAIN hr hire "<the goal, as an outcome>" --why "<reason and who uses it>" --owns <path> --input <file to read first> --check "<acceptance command>" [--parallel] [--material-tokens <rough size>]`

It answers "do not hire" when the work is small or has no check. Otherwise it picks the best of the 100 templates in the rack for the task, the model and effort (from learned results, with safe defaults), and a token wage, and writes the full brief to a file. Delegate exactly as its last line says: the named agent, model and effort, with the one-line message pointing at the brief. Do not retype the brief; that pointer is the saving. No two running helpers own the same file, and at most four run at once. Helpers that run side by side against a shared interface each get the file that defines it as `--input`; one brief without it builds a different interface.

Add `--also "<constraint, with its reason>"` for anything only this task needs. If no template fits, HR says so and writes a plain brief. `BRAIN hr rack --search "<task>"` shows candidates; `--template <id>` forces one.

When the helper returns, settle it before you repair anything, so the outcome recorded is the helper's: `BRAIN hr settle` runs the acceptance command itself and compares real token use with the wage (`BRAIN close` also settles whatever is still open). A failed check goes back to the same helper once with the failing output, then up one step in the escalation order in `memory/models.json`.

## Checks and escalation

Run the acceptance command yourself when the helper returns. Record evidence with `BRAIN req evidence <id> "<log path or path:line>" --done` (without `--done` the line stays open).

If a check fails, read why, then fix it or re-run the item one step up the escalation order; escalate on a failed check, not a hunch.

## Checkpoint

After each item: `BRAIN checkpoint --done <id> --item <next id> --next <id> --next <id> --push` (one `--next` per item, up to three). It commits only bookkeeping files and pushes, so a new session sees the state; commit the work itself first. Keep going while `.brain/CHECKLIST.md` has open lines and nothing blocks them.

## Tell the owner

Nothing until something is visible or blocked. Then one or two lines: what is now done and where he can see it.
