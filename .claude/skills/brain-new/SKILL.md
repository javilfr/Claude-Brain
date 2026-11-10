---
name: brain-new
description: Start a new project in an attached empty repo, or adopt an existing repo into the brain. Use for "New project: …", "Adopt this repo", "Build me …" with an empty repo attached, or in Spanish "Nuevo proyecto: …", "Adopta este repo".
---

# New project or adoption

The owner describes a project in one sentence and expects it to start. His largest past rework came from building on unanswered assumptions about the biggest fork in the design, while a questionnaire file sat unread. He answers chat; he does not fill in files.

## Set up

- Empty repo: `BRAIN init <path> --family F --title "T" --release R --language L`, with F one of software, data, knowledge, language, operations (the nearest fit; record a poor fit as a decision) and R `main-on-green` when the project deploys from `main`, `pr` or `none`. Running it twice changes nothing.
- Repo with content and no `.brain/`: `BRAIN adopt <path> --survey` first (it writes nothing), plus `BRAIN map <path>` or a scout if the code is large; then `BRAIN adopt <path> --family F --title "T"`. Adopt adds the contract files and a pointer block above an existing `CLAUDE.md`, with a line saying the brain's way wins where they disagree. When the old `CLAUDE.md` is large it also adds a "Slim the old handbook" item to `NEEDS_YOU.md`, because every byte of it is paid on every request; it never moves the file. Leave the file in place and include that choice among your questions.
- `BRAIN validate` afterwards. Fill the rest of `.brain/project.json`: commands, gates, live address if known.

## The questions

Find the unknowns that would change what gets built: who uses it, what it must never do, a fork in architecture (for example read-only display versus editing). Ask at most three, in one numbered message, each with the default you will use if he does not answer. Decide everything that only changes details and record it in `.brain/DECISIONS.md`.

Do not wait for the answers. Start with work that every answer shares, and avoid building the parts a pending answer could delete. When he replies, record his exact words in the requirements ledger.

Things only he can do (accounts, keys, payments) go to `NEEDS_YOU.md` as click steps with what happens meanwhile. Build against local stand-ins behind interfaces so nothing waits.

## Next

Continue with brain-plan.

## Tell the owner

The questions with defaults, one line saying work has started, and what he will be able to see first.
