---
name: brain-status
description: Show where a project stands, what is next and what it has cost, in under 15 lines. Use for "Status", "Where are we?", "How much has this cost?", or in Spanish "Estado", "¿Cómo vamos?", "¿Cuánto ha costado?".
---

# Status

The owner reads this on his phone. He wants to know what is done, what is next, whether anything waits on him, and what the work has cost, in under 15 lines and plain words.

## Sources

- `BRAIN status` regenerates `STATUS.md` from `.brain/STATE.md` (the only checkpoint) and prints the summary.
- `BRAIN ledger` gives this session's token use and list-price cost, by model and helper, and the share of input read from cache. Project totals come from `STATUS.md`.
- `BRAIN release --check-live` when `release.live_url` is set in `.brain/project.json`: it says whether the live address serves the latest release. It pushes nothing.
- `BRAIN req list` if he asks how complete the work is against his request.
- `BRAIN budget` only if he asks about the brain's own size; `BRAIN ml report` only if he asks what the brain has learned about routing or cost. For "HR report" or a question about helpers and wages: `BRAIN hr report`.

Do not read the plan, decisions or logs to answer; the scripts already summarise them. Do not restate the same fact twice.

## Judgment

Put anything wrong first: a red gate, a live address serving an old version, a second chat holding the lease, a stale model-facts file, an item waiting on him.

Cost is list-price equivalent: on his subscription he is not billed these dollars, and the real limit is his plan's usage window. Say so once if he asks about money. Give two cost lines: this session (tokens, list-price dollars, cache share) and the project to date.

## Shape of the reply

A phone-screen shape: one-sentence state, done since the last status, next, waiting on you (the `NEEDS_YOU.md` item numbers, or "nothing"), cost. No headers beyond what fits on a phone screen.
