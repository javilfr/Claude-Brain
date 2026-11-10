---
name: brain-start
description: Resume a project from its recorded state without asking. Use when the owner types "Start running", "Continue", "Resume", "Keep going", "set up", or in Spanish "Empieza", "Continúa", "Sigue", or opens a chat with a project attached and no other request.
---

# Start or resume

The owner wants work to continue from exactly where the last session stopped, with no questions and no re-planning. He types two words on his phone and expects hours of correct work.

BRAIN means `python3 "${CLAUDE_SKILL_DIR}/../../../bin/brain"`.

## Mechanical part

1. `BRAIN boot` finds the project, reads `.brain/STATE.md`, reports the mode (work, bootstrap, adopt, migrate, brain only, choose, stale brain), open items for the owner, stale facts, and whether another session holds the lease. It is about 15 lines; do not re-read the files it summarised.
2. If the mode is `migrate`, run `BRAIN migrate` (it commits a backup first). If it is `stale brain`, write nothing to the project and tell the owner the brain needs updating. If `bootstrap` or `adopt`, switch to the brain-new skill.
3. If another session holds the lease, say which one in one line and continue only if the owner's message makes clear this chat is the active one.
4. Check `NEEDS_YOU.md` and `.brain/DECISIONS.md` for lines the owner marked `RESOLVED:` or `OVERTURNED`, and apply them before resuming.

## Judgment

Resume the item `STATE.md` names, at the size the project already records. Re-plan only if the state file says the plan is finished or an overturned decision invalidates it. If the recorded item is blocked on the owner, write or update its `NEEDS_YOU.md` entry and move to the next unblocked item.

Then continue with the brain-build skill. Checkpoint at each item boundary with `BRAIN checkpoint --item <id> --next <ids>`.

## Tell the owner

At most five lines: where things stand, which item you are on, anything only he can do (pointing to `NEEDS_YOU.md`). Then work. Reply in the language he wrote in.
