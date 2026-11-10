---
name: brain-start
description: Resume a project from its recorded state without asking. Use when the owner types "Start running", "Continue", "Resume", "Keep going", "set up", or in Spanish "Empieza", "Continúa", "Sigue", or opens a chat with a project attached and no other request.
---

# Start or resume

The owner wants work to continue from exactly where the last session stopped, with no questions and no re-planning. He types two words on his phone and expects hours of correct work.

## Orient

Run `BRAIN boot` and act on its mode line; it already summarises `.brain/STATE.md`, so do not re-read what it printed.

- `work`: resume the recorded item at the recorded size. If boot names a newer saved state on another branch (the last chat saves on its own branch), run `BRAIN resume --adopt` first: it fast-forwards to that state and prints the position.
- `migrate`: run `BRAIN migrate`. It keeps a copy of the manifest under `.brain/log/backup/` before each step; commit its changes as their own commit.
- `stale-brain`: write nothing to `.brain/` and tell the owner the brain needs updating.
- `bootstrap` or `adopt`: switch to brain-new.
- `choose`: boot picked the most recently active project; continue with it unless his message names another.
- `brain-only`: no project is attached. A question gets an answer. If his message asks for work on the brain, or says nothing beyond the trigger while boot lists open brain tickets, the work is the brain itself: read `docs/NEXT_SESSION.md`, then work the tickets in the order `BRAIN plan schedule docs/plan/tickets.json` gives, marking each done in that file. Otherwise answer what he asked.

If a warning says another session holds the lease, say which in one line and continue only if his message makes clear this chat is the active one. A line about an earlier session that was not closed means boot has already recorded what it could; mention it once and carry on. A radar line is a lead to check later in brain-learn, not a fact to act on now.

Apply any lines he marked `RESOLVED:` in `NEEDS_YOU.md` or `OVERTURNED` in `.brain/DECISIONS.md` before resuming. Re-plan only if the plan is finished or an overturned decision invalidates it. If the recorded item is blocked on him, update its `NEEDS_YOU.md` entry and move to the next unblocked item.

## Keep going

Continue with brain-build. An unattended run keeps working while `.brain/CHECKLIST.md` (regenerated at each checkpoint) has open lines and nothing blocks them; a progress report is not the end of the work. Continue on your own at most three times in a row, then stop and report. After the context is compacted, run `BRAIN resume` instead of re-reading files.

## Tell the owner

At most five lines: where things stand, which item you are on, anything only he can do (pointing to `NEEDS_YOU.md`). Then work.
