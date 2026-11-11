# Handover: the next session on the brain

## Where things stand (2026-11-11, later)

- CB-210 and CB-211 are done on branch `claude/keen-sagan-deq8fd` (not yet on `main`; the owner merges). Evidence: `docs/BUILD_STATUS.md`, sections "CB-210 result" and "CB-211 result".
  - CB-210: third held-out set `evals/hr_golden_3.jsonl` (looked at twice). The everyday-word expansion did not clear its pre-set bar and ships off (`hr.expand`).
  - CB-211: a named matching template ties a plain brief on pass (8/8 each) and costs 63% more tokens (8 of 8 worse). Default stays plain.
- Owner instruction, standing (D-14): keep building until everything is done, without stopping to ask or report. Steps that cannot be undone wait for his yes in `NEEDS_YOU.md`.

## What to do

Only CB-212 and CB-213 remain, and both need a project attached:

- CB-212: the two-repository live checks. Open a new chat with this brain **and a scratch project repository** attached (an empty repository is fine), say "Continue", and run each live check's steps in `docs/plan/tickets.json`; record pass or fail in `docs/BUILD_STATUS.md`.
- CB-213: lock the learned zone, after CB-212.

Open follow-ups from CB-211 (small, brain-only, no ticket yet): `canonical-facts-keeper`'s scope line forbids fixing documents even when asked; eval briefs should say the check may be run although its files must not be read.

Mark each ticket done in the JSON, commit with the trailer `Brain-Bootstrap: <ids>`, and push the session's branch. Do not push to `main` without the owner's word; he merges.

## Rules learned in the last sessions

- In a paired run give each arm a distinct task text (a second hire with the same text supersedes the first), and never pipe a test run through `tail` in an `&&` chain.

- Pre-register before any paired run; look at a held-out set once; use `hr hire --eval` for trials.
- Consolidate only in a brain-only chat on an up-to-date `main` (the command enforces it).
- By hand, `learn apply` may only curate. Owner items change only with his words, given as `quote`.
- If a helper stops on a usage limit, re-run the same brief on the next model in the escalation order.
