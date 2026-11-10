# Handover: working on the brain itself

For the Claude session that opens this repository on its own. The owner's instruction (2026-11-10): "Test, analyze, research and improve heavily … until fully done", then, at the end of that session: "the repo completely ready to be used and completely finished … amazing context management … prepare everything to start in a new chat with renewed context."

## Where things stand (end of the 2026-11-10 improvement session)

- Done and committed on branch `claude/inspiring-dijkstra-ndv02x`: CB-200 baseline, CB-201 live platform checks, CB-202 end-to-end trial on a scratch project (seven defects fixed with tests), CB-204 template selection (new held-out top-3 90 → 100), CB-205 template quality pass (38 templates), CB-206 open review items, CB-207 research round four. Details and every number: `docs/BUILD_STATUS.md`, section "Improvement session, 2026-11-10".
- Last gate: full suite OK (about 420 tests), `doctor` healthy, `lint` 0 errors, `hr audit` sound, `eval audit` 12/12.
- Context management was tightened at the owner's request: helper replies capped at 80 words, core rule 7 in `CLAUDE.md`, a "Context" section in `method/efficiency.md`, batch-through-one-coordinator in `brain-build`.

## What to do, in order

1. `python3 bin/brain boot`, then `python3 bin/brain plan schedule docs/plan/tickets.json`. Open: CB-203, CB-208, CB-209.
2. **CB-203** (paired template evaluation). Pre-registrations `evals/prereg/aa-plain-2026-11-10b.json` and `template-vs-plain-2026-11-10b.json` are committed; no valid trial exists yet. Run it as ONE background coordinator agent (general-purpose), not trial by trial in the main chat:
   - `python3 evals/tools/template_trials.py prepare <scratchpad>/evalrun` (24 briefs: 8 dev tasks × plainA, tpl, plainB).
   - The coordinator launches each brief on the builder agent with model haiku, at most four at a time, arms interleaved, then `python3 evals/tools/template_trials.py score <scratchpad>/evalrun template-vs-plain-2026-11-10b`, and returns one table (task, arm, template, pass, tokens) in under 150 words.
   - Then `brain eval compare` for A/A (plainA vs plainB) and A/B (tpl vs plainA); report the verdict with n. Fewer than 8 valid pairs is "not proven". Never touch the held-out tasks.
3. **CB-208** red team and final review: one `redteam` agent and one `reviewer` agent, fresh context, each returning findings in a file and a short reply. Fix blocking and should-fix items with tests.
4. **CB-209** close out: update `docs/BUILD_STATUS.md`, `docs/REQUIREMENTS.md`, `NEEDS_YOU.md`, `OWNER_GUIDE.md`; mark tickets; `brain learn consolidate` for whatever the inbox then holds (the 2026-11-10 records were consolidated as delta `d-20261110-8f209eba44`); `brain close`; commit with `Brain-Bootstrap: <ids>`; push the branch. Do not push to `main`.

## Known open items (not tickets)

- Selection still misses long, technical lead-written briefs (cli script → "none fits"; "write tests" → a reviewer). Use `--template <id>` for those; see BUILD_STATUS CB-204.
- `memory/models.json` lacks Haiku 5.5's higher price above 100K-token prompts (BUILD_STATUS CB-207); the pipeline has no operation for the model table yet.
- Five external facts entered memory as candidates; the old `fact-effort-curves` still says 3.2 points and should be superseded by the new 3.3-point fact through the pipeline.
- `hr settle` runs the check when called, so settle before repairing a helper's work (now in `brain-build`).
- The ledger's minutes figure looked lower than wall-clock time; check `engine/ledger.py`.
- A Stop-hook capture record for this session was not confirmed (CB-201); check `learning/inbox/` for a `ledger` record keyed by the previous session id.

## How to work here

- Size the work; run commands through `brain run`; hire through `brain hr hire` (at most four helpers at once, each with an acceptance command); never weaken a test; commit after each ticket; push the session's branch.
- Keep the chat small (core rule 7): batch similar helper runs behind one coordinator, read helper notes files only on failure, and move to a new chat after a long stretch.
- Kernel changes (invariants, `CLAUDE.md`, contract schema, template text) are deliberate, tested and named in the commit. Learned files change only through `brain learn`.

## What needs the owner (unchanged)

`NEEDS_YOU.md`: protect `main` once GitHub's checks can run; GitHub's automatic checks do not start on this account (item 7); the weekly learning run; how learning changes get merged.
