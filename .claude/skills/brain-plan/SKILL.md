---
name: brain-plan
description: Turn a request into a requirements ledger, a plan sized to it, and a schedule for parallel work. Use for size-2 or size-3 requests, "Plan this", "Make a plan", "Planifica", or after brain-new. Not for quick questions or small edits.
---

# Plan

The outcome is three things a later session can resume from: a requirements ledger that holds the owner's exact words, a plan no bigger than the request needs, and, if work can run in parallel, a schedule.

BRAIN means `python3 "${CLAUDE_SKILL_DIR}/../../../bin/brain"`.

## 1. Look before planning

`BRAIN recall "<the request in a line>"` returns the few memory items and playbook lines that apply. Read the family playbook (`playbooks/<family>.md`) and `method/lifecycle.md` only if this is your first plan in the session.

## 2. Requirements ledger

Every sentence of the request becomes at least one line: his exact words, what will satisfy them, and a "passes when" that a script, a screenshot or a source can show. Add implied and ambiguous items as their own lines, each marked, with the assumption taken. `BRAIN req add` writes each line; `BRAIN req list` shows them; see `BRAIN req --help` for flags. Every line has its "passes when" before work starts, because the check is what lets cheaper models try first and escalation work.

## 3. The plan

Write `.brain/PLAN.md` sized to the request: a short ordered list of items, each with the ledger lines it serves, the check, and the files it owns. Choose an approach in two or three lines when there is a real alternative and record why in `.brain/DECISIONS.md`. A plan for a small request is a few lines.

## 4. Parallel work

Only when items are independent, bulky and checkable: `BRAIN plan schedule <file>` returns waves that never put two items touching the same file together, with the elapsed-time and token cost of parallel versus sequential. Use at most four helpers at once unless the owner asked for more. `BRAIN plan assign <file>` suggests model and effort per item.

## 5. Checkpoint

`BRAIN checkpoint --item <first> --next <ids>`.

## Tell the owner

The plan in five lines or fewer, the assumptions he may want to overturn, and what he will see first.
