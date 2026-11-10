# How a lesson earns its place

These are the rules `brain learn` applies. They are code in `engine/learn.py`; this page says the same thing in plain words.

## Getting in

- A lesson needs evidence that points to something that happened in the same session, and a script checks that it did: a gate run recorded in the project's gate log, a test name found in the saved output of a run, a run log written since the session began, an outcome record of the session, or a review file that exists. Without a managed project only a review file or the owner's own words count. No evidence that checks out, no lesson.
- It must say what to do ("Run the gate twice", "Builds should pin the toolchain", "Helpers write their detail to a file"). A plain observation ("The build was slow on Tuesday") is turned away, at once, when the note is made, so it can be reworded.
- Text Claude only read (a web page, a project file, tool output) can become a fact with its source. It can never become a rule or a pitfall.
- No secrets and no email addresses. At most 400 characters.
- A lesson about one project stays in that project's `.brain/memory/`. There it is usable from the next session: on probation, or active when the owner's checked words back it. A lesson for the brain that names a path, a file, a known project, or the attached project's name, id or folder is turned away when it is noted. Names every project shares (`CLAUDE.md`, `package.json`) do not count.
- When a lesson is noted, the two closest existing lessons are shown. One that says nearly the same thing (60% or more of the same words, or 80% of the shorter one's words) does not become a new item: it counts as one more confirmation of the existing one. The same lesson in other words is recorded as a confirmation with `--confirms <id>`. One session confirms a lesson once.
- A pitfall (a mistake to avoid) is only created when, inside one session, a check failed and the same check later passed, and a lesson about that failure was noted in that session.

## What counts as the owner's words

- "The owner said it" is accepted only when Claude quotes his words and the quote is found, word for word, in a message he typed in this session. A tool result, a helper's report, a system message, the summary written when a long chat is compacted, and a message from another session are not his words. Only a fingerprint of the quote and where it was found are kept, never the quote itself.
- When the lesson is consolidated, the script looks for the quote again. Found again in the session's record on disk: the lesson becomes active as his instruction. Not found, or no record on disk: the lesson is kept as a claim that waits for him. It is not used and not shown as a rule; `brain learn status` and the weekly digest list it.
- `brain learn confirm <id> --quote "<his words>"` makes a waiting claim (or any lesson) his instruction; whatever it contradicted is set aside. `brain learn reject <id>` retires a waiting claim; withdrawing anything in use needs his words too (a short answer such as "no 2" counts when it is a whole line he typed).
- A line written by hand into the inbox, or a change file written by hand, never becomes an active owner rule.

## Who decides whether a lesson helped

Only results that do not depend on Claude's opinion: whether the gates of the session where the lesson was followed passed on the first try, and the owner's corrections. Claude only reports which lessons it followed; it never says whether they helped. A lesson that is still a candidate is credited only in a session where the recall log proves it was shown. Facts and the owner's instructions take no votes from results at all.

## Moving up

| From | To | When |
|---|---|---|
| candidate | probation | it helped once (a passing session followed it, or another session confirmed it) |
| probation | active | at a later consolidation: it is supported by at least 2 separate sessions, and the learning statistics, once they have data on it, do not rate it below neutral |
| any | active | the owner stated it, and his words were found in a message he typed |

A lesson moves one step per consolidation. A fact moves on how many sessions read it at its source: two for probation and active; a fact that replaces an older one starts on probation.

Two lessons that say opposite things about the same subject ("always X", "never X") are linked as a conflict; what counts is the main sentence, not a reason given after "because". Neither moves up while the other is in use. The weekly digest lists them under "Unsure"; the owner settles it with `brain learn confirm`.

## Moving down

- Only lessons learned from sessions fade or are demoted by results. What shipped with the brain, the playbooks, the owner's preferences and instructions, and facts are never demoted for lack of use.
- Harm: followed at least 8 times, with failures in at least 3 different weeks, and failing clearly more often than not. Three bad sessions in a row are not enough: the cause is often outside. A shipped item followed in failed sessions is listed in the digest as "In question" and nothing changes.
- A correction in the owner's checked words demotes the item at once (never one of his own; that takes `brain learn reject`).
- Faded from disuse, measured by a forgetting curve that fades slowly for lessons followed often (90 days unused when the statistics are not available), and not marked most important: demoted. A candidate nobody was ever shown is not counted as forgotten before 180 days. At most a tenth of a file is demoted per run, the most faded first.
- Demoted for a further 180 days: retired to `memory/archive.jsonl`. Nothing is ever deleted.
- `brain learn restore <id> --reason "<why>"` brings a demoted or retired item back: a learned lesson on probation, shipped knowledge as it was. A helpful vote or a new note of the same lesson also brings a demoted lesson back. What the owner withdrew comes back only with his words.
- What the owner stated is never demoted, faded or replaced by learning.

## Facts that change

When a fact is read again with different numbers or names (a new price, a new default), the new fact replaces it: the old one gets an end date, both stay on file, and only the current one is shown. Read again unchanged, its check date moves (`brain learn reverify <id> --source <address>` does the same). A fact past its check date is reported as stale, not removed.

## Safety limits on every change

- One change at a time, as a list of small operations, recorded in `learning/manifest.jsonl` and described in `learning/CHANGELOG.md`.
- A change that would retire more than 10% of a file's items (one item is always allowed), shrink a larger file by more than 20%, rewrite more than 30% of a lesson's text or leave it under 40 characters, or break an item's format is refused whole, and nothing is written. A file holds at most 400 items in use; a new lesson that does not fit is turned away alone and the rest of the change applies.
- A change file applied by hand (`brain learn apply`) can add only candidates, and cannot add, edit, move, link, replace, restore or change the status of anything that is the owner's. Changes to the owner's items are made only by the commands that check his words.
- A change may only add to the item files of the learned zone. A path that is absolute, contains `..` or is not one of those files is refused whole, so learning can never rewrite the routing tests, the engine or anything else outside its own files.
- One unreadable or malformed record in the inbox is turned away with its file and line; the rest is used. A record delivered twice counts once.
- CI replays every recorded change on the previous version with the same rules and requires exactly the same files, so a hand edit cannot pass as learning, and a recorded change that breaks these rules fails the check. Inbox files only grow, except that a session may re-record its own file until that file is consolidated. The weekly digest is a report and can be written again.
