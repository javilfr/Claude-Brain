---
name: brain-learn
description: Close a session into the learning loop, consolidate lessons, or report what was learned. Use at the end of a session, for "What did you learn?", "Consolidate", "Learning digest", or in Spanish "¿Qué has aprendido?", "Consolida".
---

# Learn

The brain improves only through its learning pipeline: lessons backed by a real outcome, applied as small tracked changes that the owner can undo with one Revert. This skill runs the parts of that loop a working session is allowed to run.

BRAIN means `python3 "${CLAUDE_SKILL_DIR}/../../../bin/brain"`.

## Close (every session that did work)

`BRAIN close` reads the session's own records and writes the token ledger, a run record, lesson candidates and a refreshed status. It is keyed by session, so running it twice changes nothing. "Nothing learned" is a valid result.

Add a lesson by hand only when there was a signal: a failed gate, rework, a correction from the owner, an unusually expensive task, or a first success in a new kind of work. `BRAIN learn note` (see `--help`) takes the lesson, at most 400 characters, and the evidence it rests on. A lesson must point to an outcome; something you only read in a web page or a file can be a fact with a source, never a rule. Lessons that mention this project's names or content belong in the project's `.brain/memory/`, not in the brain.

Commit the inbox file on the brain's working branch and push it.

## Consolidate (when the owner asks, or in the weekly routine)

`BRAIN learn consolidate` turns inbox records into small operations and opens them as one change. `BRAIN learn decay` demotes unused items. Never edit `memory/`, `owner/`, `stats/` or `playbooks/` by hand: the guard and CI reject it.

## Digest

`BRAIN learn digest` writes the weekly summary of at most 15 lines.

## "What did you learn?"

Answer from `BRAIN learn status`: new lessons and changed rules since the owner last asked, each as one plain sentence, plus how many outcomes each rests on. If nothing changed, say so in one line.

## Tell the owner

Plain sentences, no jargon, in his language. Mention that any learning change can be undone with the Revert button on its pull request.
