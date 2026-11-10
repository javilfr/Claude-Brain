# How a lesson earns its place

These are the rules `brain learn` applies. They are code in `engine/learn.py`; this page says the same thing in plain words.

## Getting in

- A lesson needs evidence that points to something that happened: a gate, a test, an outcome, a run record, a review, or something the owner said. No evidence, no lesson.
- It must say what to do ("Run the gate twice", "Builds should pin the toolchain"). A plain observation is turned away.
- Text Claude only read (a web page, a project file, tool output) can become a fact with its source. It can never become a rule or a pitfall.
- No secrets and no email addresses. At most 400 characters.
- A lesson about one project stays in that project's `.brain/memory/`. A lesson that names a path, a file or a known project is turned away for that reason.
- A lesson that says nearly the same thing as an existing one (60% or more of the same words, or 80% of the shorter one's words) does not become a new item: it counts as one more confirmation of the existing one.
- A pitfall (a mistake to avoid) is only created when a check failed and a later one in the same kind of task passed, and a lesson about that failure was noted.

## Who decides whether a lesson helped

Only results that do not depend on Claude's opinion: whether the gates of the session where the lesson was followed passed on the first try, and the owner's corrections. Claude only reports which lessons it followed; it never says whether they helped.

## Moving up

| From | To | When |
|---|---|---|
| candidate | probation | it helped once (a passing session followed it, or a second note confirmed it) |
| probation | active | it is supported by at least 2 separate sessions, and the learning statistics, once they have data on it, do not rate it below neutral |
| any | active | the owner stated it |

Two lessons that say opposite things about the same subject ("always X", "never X") are linked as a conflict. Neither moves up until the owner settles it. The weekly digest lists them under "Unsure".

## Moving down

- Harmed at least 3 times and more often than it helped: demoted.
- Faded from disuse, measured by a forgetting curve that fades slowly for lessons followed often (90 days unused when the statistics are not available), and not marked most important: demoted.
- Demoted and unused for a further 180 days: retired to `memory/archive.jsonl`. Nothing is ever deleted.
- What the owner stated is never demoted, faded or replaced by learning.

## Facts that change

When a fact stops being true (a new price, a new default), the new fact replaces it: the old one gets an end date, both stay on file, and only the current one is shown.

## Safety limits on every change

- One change at a time, as a list of small operations, recorded in `learning/manifest.jsonl` and described in `learning/CHANGELOG.md`.
- A change that would retire more than 10% of a file's items (one item is always allowed), shrink a larger file by more than 20%, rewrite more than 30% of a lesson's text or leave it under 40 characters, break an item's format, or push a file past 400 items is refused whole, and nothing is written.
- CI replays every recorded change on the previous version and requires exactly the same files, so a hand edit cannot pass as learning.
