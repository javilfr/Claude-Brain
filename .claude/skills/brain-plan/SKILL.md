---
name: brain-plan
description: Turn a request into a requirements ledger, a plan sized to it, and a schedule for parallel work. Use for size-2 or size-3 requests, "Plan this", "Make a plan", "Planifica", or after brain-new. Not for quick questions or small edits.
---

# Plan

The outcome is three things a later session can resume from: a requirements ledger that holds the owner's exact words, a plan no bigger than the request needs, and, if work can run in parallel, a schedule.

## 1. Look before planning

`BRAIN recall "<the request in a line>" --family <family>`; it returns at most three items and may return none. Read the family playbook (`playbooks/<family>.md`) only on your first plan in the session.

## 2. Requirements ledger

Every sentence of the request becomes at least one line, written with `BRAIN req add --quote "<his exact words>" --passes-when "<what a script, screenshot or source shows>" --check "<command>"`. The ledger is `.brain/requirements.jsonl`; `.brain/REQUIREMENTS.md` is generated from it, so never edit that file. `--quote` holds only his words: for an implied or ambiguous item, quote the sentence it comes from and put the assumption in `--passes-when`, then record the assumption in `.brain/DECISIONS.md`. Every line has its "passes when" before work starts, because the check is what lets cheaper models try first and escalation work. `BRAIN req list` shows the lines; a line that is cut is `BRAIN req drop <id> --reason "…"`, which he will see.

## 3. The plan

Write `.brain/PLAN.md` sized to the request: a short ordered list of items, each with the ledger lines it serves, its check, and the files it owns. When there is a real alternative, choose in two or three lines and record why in `.brain/DECISIONS.md`. A plan for a small request is a few lines.

## 4. Parallel work

Only when items are independent, bulky and checkable: put them in a tickets file (`{"tickets": [{"id", "title", "goal", "files", "deps", "est" in minutes, "accept" command}]}`) and run `BRAIN plan schedule <file>`. It returns waves that never put two items touching the same file together, with the elapsed-time and token cost of parallel versus sequential. Give `est` as the minutes the item should take, not a safe upper bound: it is the item's target, twice it is its stop, and calibration replaces both once similar work has outcomes. `BRAIN hr staff <file>` then shows which template, agent and wage each ticket would get and the total payroll (add `--budget <tokens>` to test a ceiling).

## 5. Checkpoint

`BRAIN checkpoint --stage build --item <first id> --next <id> --next <id> --push`.

## Tell the owner

The plan in five lines or fewer, the assumptions he may want to overturn, and what he will see first.
