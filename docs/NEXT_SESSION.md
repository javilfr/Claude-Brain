# Handover: the next session on the brain

## Where things stand (2026-11-11)

- The improvement programme CB-200 to CB-209 is done and on `main`. The owner confirmed the 01:09 UTC reverts were a mistake, so `main` was fast-forwarded to the work. Evidence is in `docs/BUILD_STATUS.md`, its last sections first.
- The learning inbox is consolidated; `learn verify` matches.
- Owner instruction, standing (D-14): keep building until everything is done, without stopping to ask or report. Steps that cannot be undone wait for his yes in `NEEDS_YOU.md`.

## What to do

Work tickets CB-210 to CB-213 in the order `python3 bin/brain plan schedule docs/plan/tickets.json` gives. Each has a goal, a reason, the files it owns and an acceptance command:

- CB-210: a third held-out selection set, then selection work.
- CB-211: a paired run with a named matching template against a plain brief.
- CB-212: the two-repository live checks. They need a project attached; if this chat has only the brain, do CB-210 and CB-211 and leave CB-212 with its steps.
- CB-213: lock the learned zone.

Mark each ticket done in the JSON, commit with the trailer `Brain-Bootstrap: <ids>`, and push the session's branch. Do not push to `main` without the owner's word; he merges.

## Rules learned in the last session

- Pre-register before any paired run; look at a held-out set once; use `hr hire --eval` for trials.
- Consolidate only in a brain-only chat on an up-to-date `main` (the command enforces it).
- By hand, `learn apply` may only curate. Owner items change only with his words, given as `quote`.
- If a helper stops on a usage limit, re-run the same brief on the next model in the escalation order.
