# Routing

Size the request first. Over-process was the main waste in earlier builds: a handbook that said "read this fully, then five more files" applied to a typo fix as much as to a new app. The rule is to use the smallest size that can meet the definition of done.

## The four sizes

| Size | Examples | Reads | Helpers | Writes |
|---|---|---|---|---|
| **0 Answer** | "What does this mean?", "Which is better?" | Nothing extra | None | Nothing |
| **1 Small task** | Fix a typo, add a field, one chart, rewrite a paragraph | The files touched | None, or one for an isolated search | The change; one line of state if a project is active |
| **2 Project** | A new app, a report, a translated site | State, ledger, plan, one playbook | Up to four at once, each justified | The full contract |
| **3 Programme** | A multi-week build with phases | As size 2, per phase | Scheduled helpers, after a written plan | As size 2, plus phase gates |

Process overhead targets (design goals until the ledger measures them): zero process steps at size 0, under 5% of tokens at size 1, under 15% at size 2, under 25% at size 3.

## Rules

- Sizes 0 and 1 never read the plan, never start reviewers, never write digests.
- Moving up a size mid-task is allowed and logged with a reason. Moving down silently is not.
- `BRAIN route "<request>"` gives a scripted first guess at size, family, model and effort, from rules and logged outcomes. You make the final call; the script exists so the guess is consistent and measurable.
- Size 3 uses parallel helpers only for three or more independent streams, and only once the plan is written.
- Helper cap: four at once by default. Twenty parallel agents once hit the rate limit and produced nothing; ten exhausted a usage window three times in two days. Go above four only when the owner asks and the work is truly independent.

## Trigger phrases

| The owner types | Means |
|---|---|
| New project: … / Nuevo proyecto: … | brain-new: install the contract, at most three questions, start |
| Start running / Continue / Resume / set up / Continúa | brain-start: resume the recorded item at the recorded size, no questions |
| Quick: … | Size 0–1, no machinery |
| Go deep: … / A fondo: … | A researched answer with sources (brain-research) |
| Status / Estado | brain-status |
| Hand over / Pasa a un chat nuevo | brain-handover |
| What did you learn? / ¿Qué has aprendido? | brain-learn |
| Go back | Restore the last tagged good version |
| Stop after this | Finish the current item, checkpoint, summarise |

Plain language works too; the phrases only remove doubt. He dictates on a phone, so read intent rather than spelling. Reply in the language he wrote in.

## Families

Software, data, knowledge, language, operations. Each has a playbook (`playbooks/<family>.md`) that says how work in that family is built, checked and delivered. A request that fits none uses the nearest and records the gap; a sixth family is added only after two projects fit badly.
