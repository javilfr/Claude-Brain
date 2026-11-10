# How a lesson earns its place

These are the rules `brain learn` applies. They are code in `engine/learn.py`; this page says the same thing in plain words.

## Getting in

- A lesson needs evidence that points to something that happened: a gate, a test, an outcome, a run record, a review, or something the owner said. No evidence, no lesson.
- Text Claude only read (a web page, a project file, tool output) can become a fact with its source. It can never become a rule.
- No secrets and no email addresses. At most 400 characters.
- A lesson about one project stays in that project's `.brain/memory/`.
- A lesson that says nearly the same thing as an existing one (60% or more of the same words) does not become a new item: it counts as one more confirmation of the existing one.

## Moving up

| From | To | When |
|---|---|---|
| candidate | probation | a second record supports it, or the owner stated it |
| probation | active | it helped at least 3 times, across at least 2 sessions |

Two lessons that say opposite things about the same subject ("always X", "never X") are linked as a conflict. Neither moves up until the owner settles it. The weekly digest lists them under "Unsure".

## Moving down

- Harmed at least 3 times and more often than it helped: demoted.
- Not used for 90 days and not marked most important: demoted. What the owner stated does not fade.
- Demoted and unused for a further 180 days: retired to `memory/archive.jsonl`. Nothing is ever deleted.

## Safety limits on every change

- One change at a time, as a list of small operations, recorded in `learning/manifest.jsonl` and described in `learning/CHANGELOG.md`.
- A change that would retire more than 10% of a file's items (one item is always allowed), shrink a larger file by more than 20%, break an item's format, or push a file past 400 items is refused whole, and nothing is written.
- CI replays every recorded change on the previous version and requires exactly the same files, so a hand edit cannot pass as learning.
