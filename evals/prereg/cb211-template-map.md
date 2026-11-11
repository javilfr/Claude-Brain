# CB-211: templates named by the lead, fixed before any trial

| Task | Template | Base agent |
|---|---|---|
| cb211-idempotent-renamer | cli-script-builder | builder |
| cb211-refactor-dedupe | refactor-engineer | builder |
| cb211-reconcile-members | data-reconciler | builder |
| cb211-sqlite-add-column | schema-migration-engineer | builder |
| cb211-es-en-guide | es-en-translator | writer |
| cb211-flaky-bug | bug-reproducer | builder |
| cb211-api-fallback | api-integration-builder | builder |
| cb211-facts-consistency | canonical-facts-keeper | writer |

Both arms: the same agent, model and effort as the template arm's hire gives (forced on the plain arm with `--agent`), `--eval`, a clean folder per trial, the task's grader (`brain eval grade`) as the acceptance command, arms interleaved. Tokens from `brain hr settle`; pass from an independent `brain eval grade` by the lead. Run file: `evals/runs/cb211.jsonl`. Verdicts: `brain eval compare cb211 --a plain --b template --prereg <change>` for each of the two pre-registrations.
