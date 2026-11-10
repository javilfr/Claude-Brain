# Quality

Checks that run beat a model rereading its own work, reviewers need fresh context, and "double-check everything" lines make current models slower, not better. So quality lives in artefacts and scripts.

## Requirements ledger

For any size-2 request, every sentence the owner wrote becomes at least one line in `.brain/REQUIREMENTS.md`: his exact words, what satisfies them, a "passes when" written before work starts, and at the end a pointer to evidence (a gate log, a screenshot, a `path:line`, a source). Implied and ambiguous items get their own lines, marked, with the assumption taken. `BRAIN req check` fails while any line lacks evidence; `handover`, `release` and `close` call it. Checking against his exact words, not the plan, catches plans that missed something.

Report each line as **verified** (evidence), **done, not verified** (reason), or **not done** (reason). Scope cuts are shown to the owner with a reason.

## The claim-audit sentence

Before reporting progress, check each claim against a tool result from this session. In Anthropic's tests this nearly eliminated invented status reports. It is the only verification instruction the brain carries in prose.

## Risk levels and review

| Risk | Examples | Verification |
|---|---|---|
| Trivial | Typo, copy change | The author's own check |
| Standard | A feature, a memo | A complete runnable check; a model reviewer only for what no check covers |
| High | Release, data migration, public or legal content | One fresh-context reviewer, ideally on a different model from the author, against the ledger |
| One-way door | Deleting data, irreversible architecture, spending money | The above, plus the redteam agent, plus the owner's confirmation |

One reviewer, not a panel. Criteria are yes/no "passes when" lines, not scores. The reviewer reports everything with evidence and an estimated severity; filter afterwards, since a model told to report only serious issues holds back real ones. One round always; a second only to confirm blocking fixes; never more than three. A reviewer always finds something, so stop when only style remains.

## Creativity pass

Where taste decides: five 40-word sketches from different starting constraints in one call, a blind pick against the brief, and only the winner expanded. Facts stay outside the creative step. No creative pass for bug fixes or data work. Details in the brain-create skill.

## False "done" detectors

Of 21 catalogued ways work is wrongly reported finished, `gate` and `req check` catch those a script can: a gate with no recorded exit code, or run before the last edit; tests skipped or deleted in the change; TODO stubs in new code; links that do not resolve; ledger lines without evidence; word counts off target; a UI change with no screenshot newer than the edit. Beyond scripts: reproduce a bug before fixing it; derive checks from the ledger, not the code; for an app, "done" means the live address serves the new version and the owner has been told what to look at on his phone.

## Definitions of done

Nine checklists in `method/dod/`, one per deliverable type; read the one that applies at delivery.
