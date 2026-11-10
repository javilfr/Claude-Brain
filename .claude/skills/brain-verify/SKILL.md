---
name: brain-verify
description: Decide whether work is done and deliver it: definition of done for the deliverable type, review sized to risk, ledger check, release. Use before reporting a deliverable finished, for "Ship it", "Release", "Push to main", "Publícalo", "Súbelo a main".
---

# Verify and deliver

The outcome: a deliverable the owner can rely on unchecked, and a report whose every claim points to this session's evidence.

## 1. Definition of done

Read the `method/dod/` checklist for the deliverable type; confirm each line with evidence or say why it does not apply.

## 2. Gates

`BRAIN gate --all` records each gate's exit code; a gate with no recorded exit code has not passed. Run timing gates when no helpers are working.

## 3. Review by risk

- Trivial (typo, copy change): your own check.
- Standard (a feature, a memo): a complete runnable check; a reviewer only for what no check covers.
- High (release, data migration, anything public or legal), whatever the size: one fresh reviewer agent, given the work and the ledger lines, not your reasoning; set the per-call model to put it on a different model from the author.
- One-way door (deleting data, irreversible architecture, spending money): the above, plus the redteam agent, plus his go-ahead for that step; other work continues.

One round; a second only to confirm blocking fixes; stop when only style remains.

## 4. Ledger

`BRAIN req check` exits non-zero while any line lacks evidence the engine can resolve (a gate, a run log, an existing path, a commit, a live address); a line with a stored check closes only through `BRAIN req verify`. `BRAIN done` gives the one verdict from tool results; quote its last line in the report. Fix the gap, or `BRAIN req drop <id> --reason "…"`, which he sees. Never narrow the request quietly.

## 5. Release

Under release rule `main-on-green`: `BRAIN release --run-gates --push`. It refuses uncommitted changes and a branch behind `origin/main` (merge it, re-run, try again), runs every gate itself on this commit and pushes only when all pass (skipped, removed or masked tests hold it unless `--accept-skips "<reason>"`), never forces, then checks the live address. Without `--push` it only reports. Push to `main` no other way. `BRAIN release --check-live` re-checks the live address alone; if it fails, say so first and give click steps. Under rule `pr`, open a pull request when he asks.

A change to the brain itself needs `BRAIN eval contract` passing; a claim that it helps needs `BRAIN eval compare <run-file> --a ARM --b ARM`.

## Tell the owner

Report each item as verified, done but not verified, or not done.
