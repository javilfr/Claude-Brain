# .brain: this project's memory

Everything a new chat needs to continue this project is in this repository; the brain holds method only.

## Continue in a new chat

1. Brain attached (a sibling folder with `bin/brain`): run `python3 <brain>/bin/brain boot` and follow what it prints.
2. If boot names a newer saved state on another branch (the last chat may have saved on its own branch): `python3 <brain>/bin/brain resume --adopt`.
3. No brain attached: read `STATE.md`, then `PLAN.md`, then `HANDOVER.md` if it is there.

## What each file is for

| File | Holds | Written by |
|---|---|---|
| `project.json` | the contract: family, commands, gates, release rule | `brain init`, then edited by hand |
| `STATE.md` | where the work stands: stage, item, next steps, notes, log | `brain checkpoint` |
| `PLAN.md` | the plan and its items | the lead, by hand |
| `DECISIONS.md` | decisions and assumptions, one row each | the lead, by hand |
| `requirements.jsonl` | one line per sentence of the owner's request, with its evidence | `brain req` |
| `HANDOVER.md` | the note the last chat left for the next one | `brain handover` |
| `memory/lessons.jsonl` | lessons that belong to this project only | the lead; the brain collects them later |
| `ext/` | skills, agents and tools for this project only | the lead, by hand |
| `log/` | gate results, the stored request, session records (`log/run/` and `cache/` stay out of git) | the engine |

Beside this folder, for the owner: `STATUS.md` (rewritten by `brain status` and by each checkpoint) and `NEEDS_YOU.md` (what only the owner can do).
