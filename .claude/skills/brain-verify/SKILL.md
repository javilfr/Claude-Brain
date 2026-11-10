---
name: brain-verify
description: Decide whether work is done and deliver it: definition of done for the deliverable type, review sized to risk, ledger check, release. Use before reporting a deliverable finished, for "Ship it", "Release", "Push to main", "Publícalo", "Súbelo a main".
---

# Verify and deliver

The outcome is a deliverable the owner can rely on without checking it himself, and a report in which every claim points to evidence from this session.

BRAIN means `python3 "${CLAUDE_SKILL_DIR}/../../../bin/brain"`.

## 1. Definition of done

Read the one checklist for the deliverable type in `method/dod/` (code-change, app-or-feature, screen, research-memo, plan, data-analysis, writing-or-translation, automation, answer). Confirm each line with evidence, or record why it does not apply.

## 2. Gates

`BRAIN gate --all` runs the project's gates and records each exit code. A gate with no recorded exit code has not passed. Run timing gates when no helpers are working.

## 3. Review by risk

- Trivial (typo, copy change): your own check.
- Standard (a feature, a memo): a complete runnable check; a model reviewer only for what no check can cover.
- High (release, data migration, anything public or legal): one reviewer agent, fresh context, ideally a different model from the author, given the work and the ledger lines, not your reasoning.
- One-way door (deleting data, irreversible architecture, spending money): the above, plus the redteam agent, plus the owner's confirmation.

One review round; a second only to confirm blocking fixes; never more than three. Stop when only style remains.

## 4. Ledger

`BRAIN req check` exits non-zero while any line lacks evidence. Fix the gap, or mark the line descoped with a reason the owner will see. Do not quietly narrow the request.

## 5. Release

When the project's release rule is `main-on-green`: `BRAIN release`. It runs the full gate, pushes only on a recorded zero exit, never force-pushes, and checks that the live address serves the new version. Do not push to `main` any other way. If the live check fails, say so first and give click steps.

## Tell the owner

Before writing the report, check each claim against a tool result from this session. Report each item as verified, done but not verified, or not done. For an app: the address, and what to look at on his phone.
