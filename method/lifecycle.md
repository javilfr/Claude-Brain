# Lifecycle

Every request, of any kind, moves through the same eight stages. Smaller requests skip stages; they do not run them faster. Each stage leaves an artefact a later session can resume from, so work survives a chat ending without warning.

**intake → requirements → research → plan → build → verify → deliver → learn**

| Stage | Exit artefact | Skipped when |
|---|---|---|
| Intake | The request sized (0–3), its family and deliverable type named | Never; at size 0 it is one silent decision |
| Requirements | Lines in the ledger `.brain/requirements.jsonl` (written by `BRAIN req add`): the owner's exact words, a "passes when" for each | Size 0–1, where the request itself is the ledger |
| Research | A memo with sources, or a pointer to an earlier memo or memory item | The answer is already in memory, the repo or current docs |
| Plan | `.brain/PLAN.md`: ordered items, each with its check and the files it owns; a schedule if parallel | Size 0–1 |
| Build | The deliverable | Never |
| Verify | Evidence against each ledger line; gate exit codes recorded | Never; depth scales with risk |
| Deliver | The deliverable where the owner can see it, plus what to read or click | Never |
| Learn | A run record from `close`, and lesson candidates only when there was a signal | Nothing surprising happened (the run record is still written) |

`.brain/REQUIREMENTS.md`, `.brain/CHECKLIST.md` and `STATUS.md` are generated from the ledger and the state file; edit them and the next command overwrites the change.

## Why each stage exists

- **Intake** prevents the main waste in the earlier projects: heavy process on light requests. See `method/routing.md`.
- **Requirements** stops two silent failures: covering part of the request, and quietly cutting scope. The ledger is checked by script (`req check`), not by memory.
- **Research** comes before building because a plan built on recalled API behaviour or prices fails later and more expensively.
- **Plan** fixes the order, the checks and the file ownership before helpers start, because helpers that share files collide.
- **Verify** uses checks that run (tests, builds, link checks, screenshots, source checks). A model rereading its own work is the weakest check.
- **Deliver** means the owner can see it.
- **Learn** is automatic at close, because a rule that relied on someone choosing to write a lesson produced one lesson in fifty commits.

## Moving between stages

`.brain/STATE.md` records the stage and the current item; `checkpoint` writes it at each item boundary. A new chat resumes from that file alone. Moving up a size mid-task is allowed when something unexpected appears; record the reason. Moving down is recorded the same way.
