# Routing

Size the request first, with the table in `CLAUDE.md`. Over-process was the main waste in earlier builds: a handbook that said "read this fully, then five more files" applied to a typo fix as much as to a new app.

## Examples and targets

| Size | Examples | Reads | Helpers |
|---|---|---|---|
| **0 Answer** | "What does this mean?", "Which is better?" | Nothing extra | None |
| **1 Small task** | Fix a typo, add a field, one chart, rewrite a paragraph | The files touched | None, or one for an isolated search |
| **2 Project** | A new app, a report, a translated site | State, ledger, plan, one playbook | Up to four at once, each justified |
| **3 Programme** | A multi-week build with phases | As size 2, per phase | Scheduled helpers, after a written plan |

Process overhead targets (design goals until the ledger measures them): zero process steps at size 0, under 5% of tokens at size 1, under 15% at size 2, under 25% at size 3.

## Rules

- Sizes 0 and 1 skip the plan and the digest. Review depth follows risk (brain-verify), not size.
- Moving up a size mid-task is allowed and logged with a reason; so is moving down.
- `BRAIN route "<request>"` gives a scripted first guess at size, family, and the lead's model and effort, from rules and logged outcomes. You make the final call; the script exists so the guess is consistent and measurable. Helper tiers come from the agent files.
- Size 3 runs items in parallel only when they are independent, bulky and checkable, and only once the plan is written.
- Helper cap: four at once by default. Twenty parallel agents once hit the rate limit and produced nothing; ten exhausted a usage window twice. Go above four only when the owner asks and the work is truly independent.

## The phrase with no skill

The skill descriptions carry the trigger phrases ("Stop after this" goes to brain-handover). **Go back** has none: return the project to the last release he accepted (releases are listed in `.brain/log/releases.jsonl`) with revert commits on the working branch, then release as usual, never by force-pushing.

## Families

Software, data, knowledge, language, operations, and career (a job search: targets, postings, documents, outreach, interviews, offers; its method is the `brain-career` skill and `kits/jobsearch/`). Each has a playbook (`playbooks/<family>.md`) that says how work in that family is built, checked and delivered. A request that fits none uses the nearest and records the gap; a further family is added only after two projects fit badly. Career was added on the owner's request (D-17); a job-search project's manifest says family `knowledge` with `"kit": "jobsearch"`, because the released manifest schema is frozen, and routing reads the kit.
