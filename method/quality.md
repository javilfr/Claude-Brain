# Quality

Checks that run beat a model rereading its own work, reviewers need fresh context, and "double-check everything" lines make current models slower, not better. So quality lives in artefacts and scripts. This file holds the reasons; the procedures are in brain-plan, brain-verify and `method/dod/`.

## Requirements ledger

At size 2 and above, every sentence the owner wrote becomes at least one line in `.brain/requirements.jsonl` (through `BRAIN req add`; `.brain/REQUIREMENTS.md` is generated from it): his exact words, a "passes when" written before work starts, and at the end a pointer to evidence (a gate log, a screenshot, a `path:line`, a source). Checking against his exact words, not the plan, catches plans that missed something. `BRAIN req check` fails while any line lacks evidence; nothing else calls it, so run it before reporting done and before a handover. An empty ledger passes, which is why every sentence must be entered.

The claim-audit rule in `CLAUDE.md` nearly eliminated invented status reports in Anthropic's tests.

## Review

Review depth follows risk, not size: a one-line data migration at size 1 is high risk. One reviewer, not a panel. Criteria are yes/no "passes when" lines, not scores. The reviewer reports everything with evidence and an estimated severity and the lead filters afterwards, since a model told to report only serious issues holds back real ones. A reviewer always finds something, so stop when only style remains. The risk table is in brain-verify.

## Creativity

Where taste decides, real alternatives and a separate choice beat asking for "creative" output. The method is in brain-create.

## What scripts catch, and what they do not

Of 21 catalogued ways work is wrongly reported finished, the scripts catch a few: `release` treats a gate with no recorded exit code, or one recorded on an earlier commit, as not passed; `gate` flags added skip markers and TODO or not-implemented stubs in the diff; `req check` flags ledger lines without evidence. Nothing checks deleted tests, broken links, word counts or screenshot freshness yet, so those rest on the definitions of done and the reviewer.
