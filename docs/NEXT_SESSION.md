# Handover: the next session on the brain

## Where things stand (2026-11-11)

- The improvement programme CB-200 to CB-209 is done on branch `claude/amazing-albattani-204zc8`. Evidence is in `docs/BUILD_STATUS.md`, its last sections first.
- `main` was reverted by another session at 01:09 UTC (three commits, including the programme's own setup). The owner decides via `NEEDS_YOU.md` item 8.
- The learning inbox has records waiting: hires, notes and radar leads from this session. They were not consolidated, because the single-writer rule refuses on a branch behind `origin/main`.

## What to do first

1. Read `NEEDS_YOU.md` item 8 and act on the owner's answer. If the branch is merged, `main` holds this work.
2. In a chat with only the brain, on an up-to-date `main`, run `python3 bin/brain learn consolidate`, then `python3 bin/brain learn verify`, commit, and open the learning pull request.
3. Then the live checks that need two repositories (`docs/plan/tickets.json`, `live_checks`, each with steps), starting with CB-101 and CB-103.

## Open questions worth a ticket

- A paired run where the lead names a matching template, on tasks bulky enough for method lines to matter, to settle whether templates help at all.
- Selection is still weak on dictated requests (0.45 first, 0.55 in the top three on `evals/hr_golden_2.jsonl`). That set has now been looked at three times; write a third held-out set before tuning again.
- Hand-made deltas committed with their manifest entries are caught only by branch protection; once GitHub checks run, protect `main`.
