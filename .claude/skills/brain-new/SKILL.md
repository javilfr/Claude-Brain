---
name: brain-new
description: Start a new project in an attached empty repo, or adopt an existing repo into the brain. Use for "New project: …", "Adopt this repo", "Build me …" with an empty repo attached, or in Spanish "Nuevo proyecto: …", "Adopta este repo".
---

# New project or adoption

The owner describes a project in one sentence and expects it to start. His largest past rework came from building on unanswered assumptions about the biggest fork in the design, while a questionnaire file sat unread. He answers chat; he does not fill in files.

BRAIN means `python3 "${CLAUDE_SKILL_DIR}/../../../bin/brain"`.

## Mechanical part

- Empty repo: `BRAIN init <path> --family F --title "T"`, with F one of software, data, knowledge, language, operations (the nearest fit; record a poor fit as a decision). Running it twice changes nothing.
- Repo with content and no `.brain/`: first a read-only survey (`BRAIN map <path>`, plus a scout if it is large), then `BRAIN adopt <path>`, which adds only the contract files and keeps an existing `CLAUDE.md` intact.
- `BRAIN validate` afterwards. Fill `.brain/project.json`: commands, gates, release rule (`main-on-green` when the project deploys from `main`), languages, live address if known.

## Judgment: the questions

Find the unknowns that would change what gets built: who uses it, what it must never do, a fork in architecture (for example read-only display versus editing). Ask at most three, in one numbered message, each with the default you will use if he does not answer. Ask nothing that only changes details; decide those and record them in `.brain/DECISIONS.md`.

Do not wait for the answers. Start with work that every answer shares, and avoid building the parts a pending answer could delete. When he replies, record his exact words in the requirements ledger.

Things only he can do (accounts, keys, payments) go to `NEEDS_YOU.md` as click steps with what happens meanwhile. Build against local stand-ins behind interfaces so nothing waits.

## Next

Continue with the brain-plan skill.

## Tell the owner

The three questions with defaults, one line saying work has started, and what he will be able to see first.
