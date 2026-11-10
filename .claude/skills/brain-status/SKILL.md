---
name: brain-status
description: Show where a project stands, what is next and what it has cost, in under 15 lines. Use for "Status", "Where are we?", "How much has this cost?", or in Spanish "Estado", "¿Cómo vamos?", "¿Cuánto ha costado?".
---

# Status

The owner reads this on his phone. He wants to know what is done, what is next, whether anything waits on him, and what the work has cost, in under 15 lines and plain words.

BRAIN means `python3 "${CLAUDE_SKILL_DIR}/../../../bin/brain"`.

## Mechanical part

1. `BRAIN status` regenerates `STATUS.md` from `.brain/STATE.md` (the only checkpoint) and prints the summary.
2. `BRAIN ledger` gives token use and list-price cost for this session, by model and helper, and the share of input read from cache. Project totals come from `STATUS.md`.
3. `BRAIN req list` if he asks how complete the work is against his request.
4. `BRAIN budget` only if he asks about the brain's own size.

Do not read the plan, decisions or logs to answer; the scripts already summarise them. Do not restate the same fact twice.

## Judgment

Say plainly if anything is wrong: a red gate, a live address serving an old version, a second chat holding the lease, a stale model-facts file, an item waiting on him. These come first.

Cost is list-price equivalent: on his subscription he is not billed these dollars, and the real limit is his plan's usage window. Say so once if he asks about money.

## Shape of the reply

- Line 1: the one-sentence state.
- Done since last status (up to 4 lines).
- Next (up to 3 lines).
- Waiting on you: the `NEEDS_YOU.md` item numbers, or "nothing".
- Cost: this session and project to date.

Reply in the language he wrote in. No headers beyond what fits on a phone screen.
