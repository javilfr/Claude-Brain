---
name: brain-verify
description: Decide whether work is done and deliver it: definition of done for the deliverable type, review sized to risk, ledger check, release. Use before reporting a deliverable finished, for "Ship it", "Release", "Push to main", "Publícalo", "Súbelo a main".
---

# Verify and deliver

The outcome is a deliverable the owner can rely on without checking it himself, and a report in which every claim points to evidence from this session.

## 1. Definition of done

Read the one checklist for the deliverable type in `method/dod/` (code-change, app-or-feature, screen, research-memo, plan, data-analysis, writing-or-translation, automation, answer). Confirm each line with evidence, or record why it does not apply.

## 2. Gates

`BRAIN gate --all` runs the project's gates and records each exit code. A gate with no recorded exit code has not passed. Run timing gates when no helpers are working.

## 3. Review by risk

- Trivial (typo, copy change): your own check.
- Standard (a feature, a memo): a complete runnable check; a model reviewer only for what no check can cover.
- High (release, data migration, anything public or legal), whatever the size: one reviewer agent, fresh context, given the work and the ledger lines, not your reasoning. To put it on a different model from the author, set the per-call model.
- One-way door (deleting data, irreversible architecture, spending money): the above, plus the redteam agent, plus the owner's go-ahead for that step; other work continues meanwhile.

One review round; a second only to confirm blocking fixes. Stop when only style remains.

## 4. Ledger

`BRAIN req check` exits non-zero while any line lacks evidence. Fix the gap, or drop the line with `BRAIN req drop <id> --reason "…"`, which he will see. Do not quietly narrow the request.

## 5. Release

Under release rule `main-on-green`: `BRAIN release --run-gates --push`. It refuses uncommitted changes, refuses when `origin/main` has commits this branch lacks (merge it, re-run the gates, try again), pushes only when every gate is green on this commit, never force-pushes, then checks the live address. Without `--push` it only reports. Do not push to `main` any other way. `BRAIN release --check-live` re-checks the live address alone. Under rule `pr`, open a pull request when the owner asks. If the live check fails, say so first and give click steps.

For a change to the brain itself, `BRAIN eval contract` must pass, and a claim that a change helps needs `BRAIN eval compare <run-file> --a ARM --b ARM`.

## Tell the owner

Report each item as verified, done but not verified, or not done. For an app: the address, and what to look at on his phone.
