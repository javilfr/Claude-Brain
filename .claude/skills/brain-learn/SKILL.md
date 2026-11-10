---
name: brain-learn
description: Close a session into the learning loop, consolidate lessons, or report what was learned. Use at the end of a session, for "What did you learn?", "Consolidate", "Learning digest", or in Spanish "¿Qué has aprendido?", "Consolida".
---

# Learn

The brain improves only through its pipeline: lessons backed by a real outcome, applied as small changes the owner can revert.

## Close (every session that changed files)

`BRAIN close` writes the token ledger, a run record and lesson candidates from the session's own records; a second run changes nothing. For each item recall gave you, add `--used <id>:1` if you followed it or `--used <id>:0` if not (repeat the flag): that is how items earn or lose weight.

Add a lesson by hand only after a signal (failed gate, rework, owner correction, unusually expensive task, first success in a new kind of work): `BRAIN learn note --text "<at most 400 characters>" --class <task class> --evidence "<gate log, outcome or owner turn>" --signal <signal>`. Add `--scope project` when it names this project's people, places or content; it then goes to the project's `.brain/`.

Commit the inbox file on the brain's working branch, push it, and open or update one pull request to `main` titled "learning inbox": consolidation only sees what has reached `main`.

## Radar leads

A radar line is a lead, never a rule. Open its official URL, confirm the claim there, and record it as a fact: `BRAIN learn note --trust external --source <url> --text "…" --class <c> --evidence "<url, date read>"`. A changed price, model id or default also gets a `NEEDS_YOU.md` item proposing the `memory/models.json` edit.

## Consolidate (when he asks, or weekly)

`BRAIN learn consolidate` turns the pending inbox into one delta and applies it locally; `BRAIN learn decay` demotes unused items. Commit it and open one pull request to `main` describing it in plain words. `memory/`, `owner/`, `stats/` and `playbooks/` change only through `BRAIN learn`; `BRAIN learn verify` exposes any hand edit.

## "What did you learn?"

Answer from `BRAIN learn digest --weeks <weeks since the last digest>` and `BRAIN ml report`: each change as one plain sentence, with how many outcomes it rests on. If nothing changed, say so in one line.

## Tell the owner

Plain sentences, no jargon; any learning change is undone with Revert on its pull request.
