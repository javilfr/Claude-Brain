# Build status

Where the brain stands after the build session of 2026-11-10. Ticket state is in `docs/plan/tickets.json`; this file is the evidence behind it.

## Done and checked in the build session

| Area | What exists | Check and result |
|---|---|---|
| Core | `CLAUDE.md`, 10 skills, 6 agents, `bin/brain` with 21 engine modules (about 9,500 lines, standard library only) | `brain doctor`: healthy · `brain lint`: 0 errors |
| Always-loaded cost | `CLAUDE.md` 5,356 bytes; project stub 1,150 bytes; descriptions | `brain budget`: about 2,534 tokens in total (cap 3,200) |
| Orientation | `brain boot` | 757 bytes for "Continue" in this session (cap 1,500) |
| Contract v1 | init, adopt, validate, migrate with manifest backup; frozen schema pinned by hash; three frozen fixtures | `tests/test_core.py`, `tests/test_fixtures.py` |
| State and release | one state file; checkpoint that pushes; resume; handover; gates as exit codes; release only on green, fast-forward only | `tests/test_core.py`, `tests/test_hygiene.py` |
| Requirements ledger | strict loader, implied lines, evidence required | `tests/test_core.py::ReqTests` |
| Token ledger | real usage by model and helper from session records | `tests/test_ledger.py`; this session measured below |
| Learning pipeline | inbox, verified evidence, admission gate, delta operations, replay check, supersede, decay, digest | `tests/test_learn.py`, `tests/test_guard.py` |
| Statistical learning | routing bandit, calibration, drift alarms, memory credit, flakiness, forgetting, review stopping, sizing in shadow | `tests/test_mlearn.py` |
| Recall | built-in full-text search, three items by default, silence allowed | `tests/test_recall.py` with the 60-query labelled set: recall@5 0.781, MRR 0.853 |
| Scheduler | critical path plus annealing; skips finished tickets | `tests/test_schedule.py`: annealing matched brute force on 25 of 25 small plans |
| Update radar | 10 sources, conditional requests, leads only | `tests/test_radar.py`; live: 10 of 10 sources in 0.96 s |
| Evaluation | task and run formats, paired statistics, pre-registration, ablation, 12 tasks, 6 seeded defects | `tests/test_evals.py`; `brain eval audit`: 12 sound, 0 broken |
| Lint | commands and flags named in instructions exist; budgets; imports; links | `tests/test_lint.py` |
| End to end | bootstrap → requirement → failing gate → fix → release → close → lesson → consolidate | `tests/test_rehearsal.py` |

**Full gate, last run:** `python3 -m unittest discover -s tests -t .` → 406 tests, OK; `doctor`, `lint`, `hr audit`, `items check`, `eval audit` all exit 0. (Before the HR work: 358 tests, with and without `BRAIN_NO_NETWORK=1`.)

## HR department (added later the same day, at the owner's request)

| Area | What exists | Check and result |
|---|---|---|
| Rack | 100 templates in ten groups, as data that is never always-loaded | `brain hr audit`: 100 templates, sound |
| Guidelines and schema | `hr/GUIDELINES.md`, `hr/template.schema.json`, from four research memos | audit enforces the limits and wording rules |
| Engine | hire, settle, staff, rack, audit, report; settled hires feed the learner | `tests/test_hr.py`: 48 tests |
| Selection accuracy | 200 labelled requests, half never used for tuning | held-out: right template first 78%, in top three 86% (before tuning: 73% and 83%) |
| Real use in this session | two helpers hired through the engine | settled: 54,250 of a 200,000 wage with its check passed; 81,995 of 200,000 with no check |
| Review | fresh-context review of HR (`docs/review/2026-11-10-hr-review.md`) | 2 must-fix, 10 should-fix, 13 minor: both must-fix and all should-fix items fixed with a test each; minor items fixed except those listed below |

Found by using it and by the review, and fixed: wages that swung back down after being raised; a pass that could be recorded without the check running; briefs that pointed at a check nobody had given; long task descriptions that matched no template; the helper cap not applying without a project; one malformed template stopping every hire.

Open for HR:

- Selection is word-based, so about one request in seven does not surface the right template in the top three. The lead sees the closest candidates and can name one.
- No template runs on the cheapest agent (scout): work that needs commands cannot, and pure reading is usually done by the lead. Four read-only templates run on the reviewer agent at the Sonnet tier instead.
- Wage bands other than medium are starting assumptions until hires of those sizes are settled.
- A wage is a budget that is tracked and settled, not a hard limit: Claude Code has no per-helper token cap, and writing a budget into a brief changes how current models spend.
- A helper with command access could still tamper with files on the same machine; the seal makes that detectable for the check, not impossible in general.
- Template wording has not been tested against real tasks yet. Templates that do badly are flagged by `brain hr report`; rewriting one is a reviewed change.
- Review minor items left: `staff` treats tickets as parallel unless told otherwise; forged inbox records are not distinguishable from real ones; template fields `needs` and `pitfalls` are shown and rendered, `risk` only raises the hire's risk.

## Mutation spot-checks (does a test fail when the rule is broken?)

Each was done in a scratch copy by making the breaking change and running the named tests.

| Invariant | Breaking change | Result |
|---|---|---|
| I-12 | release ignores a missing green gate | caught (`test_rehearsal`) |
| I-12 | release skips the fast-forward check | caught (`test_core`) |
| I-03 | budget cap changed | caught (`test_core`) |
| I-15 | an enum value removed from the frozen schema | caught (`test_fixtures`); the schema hash is now pinned as well |
| I-07 | an external-trust rule allowed | caught (`test_core`, `test_learn`) |
| I-04 | boot byte cap removed | caught (`test_core`); a second test now asserts the 1,500-byte figure itself |
| I-07, I-08, I-10, I-11, I-16 | each broken in `mlearn` | caught (`test_mlearn`, reported by its builder) |

The final reviewer ran 24 further mutations and found three that slipped through (forcing push, boot cap, unseeded scheduler). Tests were added for all three: `test_release_never_uses_a_forcing_push`, `test_boot_never_exceeds_its_byte_cap_whatever_the_state_holds`, `test_same_seed_same_schedule_where_annealing_runs`.

## Reviews and what they changed

| Review | Found | Outcome |
|---|---|---|
| Audit of the instruction surface (`docs/research/round2/10-audit.md`) | 6 blocking, about 17 should-fix | All blocking and should-fix items applied |
| Final fresh-context review (`docs/review/2026-11-10-final-review.md`) | 7 blocking, 22 should-fix, 22 minor | All 7 blocking fixed, each with a reproducing test. All 22 should-fix items addressed (S20 by correcting the spec; S9's flakiness score is exposed as a command but not yet consulted by `release`). Minor: about half fixed; the rest listed below |

Blocking items from the final review, all fixed: a model could label its own note as stated by the owner (now verified against what the owner typed); a crafted path could write outside the learned zone; a checkpoint could push ungated work to the release branch; a corrupt ledger line was silently dropped; the test suite depended on the brain's own recorded state; the CI check would have been red by construction; this file was missing.

## Open, with reasons

| Item | Why open |
|---|---|
| GitHub's automatic checks do not start on this account | Every run ends as failed within about four seconds, before any step. `NEEDS_YOU.md` item 7. Until fixed, nothing is enforced on GitHub; the same checks pass inside a session |
| Learned zone not locked | By decision D-08: lock at tag `brain-v1.0.0` after the live checks |
| The brain is on its working branch, not `main` | `NEEDS_YOU.md` item 1 |
| No measured comparison against the earlier way of working | Needs live sessions (CB-109). No efficiency claim is made until then |
| Duplicated wording between memory items and method files | Harmless while both are on demand; five items overlap the always-loaded file. Left in place because the labelled recall set refers to item ids |
| Minor review items not fixed | M6 (success output mixes the last lines of both streams), M8 (repo map lists generated files), M15 (radar thread shutdown may add seconds at exit; not measured), M16 (logs outside a project go to a temporary folder), M17 (`close` options are declared by the model), M18 (two tunables still inline), M19 (lead field names), M20 (radar state changes the brain tree daily), M22 (routing examples mention trips) |
| Gate and release do not consult the flakiness score automatically | It is available as `brain ml flaky`; wiring it into `release` waits for real data |

## Needs a live session (cannot be closed from inside the build session)

| Ticket | Check |
|---|---|
| CB-101 | The brain's `CLAUDE.md`, skills and agents load beside a project and `boot` runs from the first message. Partly seen: the skills and agents appeared live in the build session |
| CB-102 | A quick question gets an answer with zero process steps |
| CB-103 | "New project: …" on an empty repo: contract installed, at most three questions, first item started |
| CB-104 | End a session mid-item; "Continue" in a new chat resumes the same item |
| CB-105 | Helpers honour model, effort and skip-handbook settings (visible in the ledger) |
| CB-106 | Whether hooks installed through the cloud environment load in two-repo sessions |
| CB-107 | Whether a skill's own hooks fire after it is used |
| CB-108 | Pushing to both repositories from one session, with branch protection on the brain |
| CB-109 | An A/A run, then the first paired benchmark with and without the brain |
| CB-110 | A first real project end to end |
| CB-111 | The plugin manifest loads on desktop |
| CB-112 | Whether an effort change keeps the prompt cache |

## What the build itself cost (measured by `brain ledger`)

- About 131 minutes, 30 helpers, about 198 million tokens, about $123 at list prices (a subscription pays no per-token charge; this is the list-price equivalent).
- Helpers were 73% of the cost. The first ten analysts ran on the session's model because nothing set theirs; later helpers used the brain's own agents or an explicit cheaper model. That is the reason every brain agent file sets its model.
- The main conversation read 99% of its input from cache. Three tool results exceeded 5,000 tokens.
- This was a deliberately heavy session: two research rounds of ten agents each were asked for by name. It is not a baseline for normal work.

## Improvement session, 2026-11-10 (tickets CB-200 to CB-209)

### CB-200 Baseline and self-audit

Every number below is from a command run in this session, before any change.

| Check | Result |
|---|---|
| `python3 -m unittest discover -s tests -t .` | 407 tests, OK, 35.0 s |
| `brain doctor` | healthy; version 0.9.0; model facts verified 0 days ago; always-loaded budget about 2,550 tokens |
| `brain lint` | 0 errors, 0 notes |
| `brain hr audit` | 100 templates in 10 groups (researcher 17, builder 48, writer 19, reviewer 15, redteam 1, scout 0); sound |
| `brain lint --transcript` | 0 oversized results, 0 re-reads, 1 model, 0 helpers, 82% input from cache (target 80%) |
| `brain items check` | 141 items in 9 files, all valid |
| `brain eval audit` | 12 tasks, 12 sound |
| `brain learn consolidate` | first real delta `d-20261110-a431e755f2`: 3 ops (APPEND_STAT 1, MARK_INBOX 1, ML_FOLD 1); 1 ledger row, 2 hire records folded; inbox now empty |
| `brain learn verify` | 1 delta replayed on `origin/main`; learned zone matches |
| `brain learn status` | 141 active items, 0 candidate, 0 in conflict |

Differs from the handover: the inbox held one file with three records (one ledger row, two settled hires), as stated; the scout tier still has no template (an open item for CB-206).

### CB-201 Live platform checks (one-repo cloud session, 2026-11-10)

Observations from this session's own tool results and transcripts. None is recorded as a fact in `memory/`, because no official page was checked for it; each is an observation of one session.

| Question | Observed | How |
|---|---|---|
| Does the `PreToolUse` guard in `.claude/settings.json` fire? | **Yes.** With `learned_zone_locked` set to true for the test, a `Write` to `memory/_probe.txt` was refused with the guard's own message; the file was not created. `VERSION.json` was restored byte for byte afterwards | Live Write call |
| Does the `Stop` hook (`session_end.py`) fire? | See the follow-up line below: it can only be seen after a turn ends | Inbox file keyed by this session id |
| Do a skill's own frontmatter hooks fire? | **Not testable here.** No brain skill declares hooks, and skills are listed at session start, so a skill added now would not be offered. Stays open as CB-107 | `grep '^hooks:' .claude/skills/*/SKILL.md` finds none |
| Do helpers honour `model`? | **Yes.** A builder hired with model sonnet produced only `claude-sonnet-5-5` turns; a writer hired with opus produced `claude-opus-5-5` turns. The subagent meta file also records `pickedEffortModel: claude-opus-5-5` for both, a field whose meaning is not documented | `subagents/*.jsonl` and `*.meta.json` |
| Do helpers honour `effort`? | **Recorded as medium** in every request of both helpers (`"effort":"medium"`); whether the served effort matched cannot be seen | Transcript fields |
| Do helpers honour `omitClaudeMd`? | **Yes.** The brain's `CLAUDE.md` opening sentence appears in the main transcript and in neither helper transcript | `grep -c` on the transcripts |
| Does an effort change keep the prompt cache? | **Not testable by the session.** Effort is changed by the person (`/effort`), not by a tool. Stays open as CB-112 | — |

Also seen: `brain hr hire` chose `rag-index-builder` for "Review all 100 HR templates … (biodiversity, ML experiments, RAG index …)", because listed domain nouns outweighed the verb. Passed to CB-204 as a test case.

### CB-202 End-to-end trial (scratch project `tipcalc`, local bare remote)

Flow run as the lead: `boot` (bootstrap) → `init` → four ledger lines (one implied) → `PLAN.md` and a three-ticket file → `plan schedule` (one wave, 2.5x) → `hr staff` → two hires through `hr hire`, run in parallel on sonnet → gate → `hr settle` → `req check` (4/4) → `release --run-gates --push` (fast-forward to `main` on the remote, gates green) → `checkpoint --push` → `resume` → `boot "Continue"` (mode work, 4/4 done) → `handover` (correctly refused: the brain had uncommitted helper work). The README was the lead's own work.

Measured (`brain ledger`, whole session so far): two trial helpers used 4,831 and 4,029 tokens against wages of 20,000 and 60,000; the session's main conversation read 98% of its input from cache.

| Found | Fixed |
|---|---|
| `boot` and `detect` ignored `--project` and `BRAIN_PROJECT`, so a project outside the brain's folder was invisible | Both take `--project` and honour `BRAIN_PROJECT`; test `test_explicit_project_outside_the_brains_folder` (fails on the old code) |
| The typo rule matched one real word to another: `tests` read as Spanish `tesis`, so "a calculator in Python with tests" routed as `knowledge.longform` | A word the vocabularies know is never a slip for another; Python/CLI words added; two routing rows; routing set 109/109 (one row fails on the old code) |
| A new project with no verb said "no task verb; answer or acknowledge" | Says "names a whole deliverable" |
| Evidence from earlier in the session was refused: the session start was taken from the project's open-session marker, written only when a command first touched the project | The earlier of marker and transcript start; test `test_marker_written_late_does_not_hide_earlier_logs` (fails on the old code) |
| Parallel briefs: the T1 brief lacked the plan file, so `split()` returned a tuple where the plan said a dict; T2's tests failed 5 of 9; the lead repaired it | `brain-build` now says parallel helpers sharing an interface each get its file as `--input`; lesson recorded through `brain learn note` |
| `hr settle` runs the check when called, so a repair made before settling is credited to the helper (T2 reported failure, settle recorded a pass) | `brain-build` now says settle before repairing; the recorded T2 outcome is wrong and is listed here |
| Selection: four misses (template review → rag-index-builder; CLI script → "none fits" though cli-script-builder was closest; "write tests" → a reviewer on opus, effort high; README → repo-cartographer) | Passed to CB-204 as dev cases |
| `cli-script-builder` made a pure calculator grow `--dry-run` and `--self-test` | Passed to CB-205 |
| `hr report` still counts consolidated hires as waiting | Passed to CB-204 (owner of `engine/hr.py` this session) |

Not exercised: a deploy with a live address (none for a CLI), `close` for the trial project (one session holds one ledger; `close` runs once, for the brain, at the end).

### CB-204 Template selection (helper `h-20261110-73b7df`, checked by the lead)

A new held-out set `evals/hr_golden_2.jsonl` (100 requests, one per template) was written and measured before `engine/hr.py` changed; the rule (new-set top-3 up 3+ points, no class lower on any set) was written down first in `docs/review/selection-2026-11-10.md`. Not a `brain eval prereg` file: that command takes only `evals/tasks` ids.

| Set | Before (top-1 / top-3) | After (lead's re-run) |
|---|---|---|
| New held-out (`hr_golden_2`) | 87 / 90 | 99 / 100 |
| Old dev | 100 / 100 | 100 / 100 |
| Old held-out | 78 / 86 | 80 / 88 |

Changes: accent folding and light Spanish stemming; an accept path when most known words match; a 0.7 penalty when the leading verb asks for the other kind of role (review → not a builder or writer; write/build → not a reviewer); `hr report` no longer counts folded hires as waiting (test added). Selection time rose from about 10 to about 50 ms per request.

Still open, measured by the lead on the original live texts (the helper checked paraphrases): a long technical brief still dilutes the fit. "Write tipcalc.py … argparse CLI …" gives "none fits" (cli-script-builder is first but below the floor); "Write tests/… with unittest …" still ranks requirement-verifier first (0.44 against coverage-analyst 0.42); "Review all 100 HR templates …" ranks dataset-source-finder. The new set was written by a helper that had read the rack, so it is easier than real speech. For lead-written briefs, `--template` remains the way; this is not tuned further on the held-out set.

### CB-205 Template quality pass (helper `h-20261110-6561fd`, writer on opus)

Review and fixes in `docs/review/templates-2026-11-10.md`; research for the five thin data templates in `docs/research/round4/data-templates.md`. 38 of 100 templates revised (ids, `when`, `name` and `keywords` unchanged; `version` 1 → 2). The helper's scan, before → after: lines asking for tools the base agent lacks 30 → 22 (the rest are `curl` fetches a builder can run); method lines with no reason 78 → 52 flagged, 19 rewritten; three near-duplicate pairs pulled apart; three generic lines replaced. The lead also made `cli-script-builder` ask for a dry-run only when a script changes files or systems (the trial's calculator grew one it did not need). `brain hr audit` sound; `tests.test_hr` OK. Cost: 201,048 tokens against a 200,000 wage.

Not done: no template has been tried on a real task against its earlier wording (that is CB-203). Three source pages (eBird terms, GBIF rate limits, Pl@ntNet terms) could not be reached. No agent has both web access and a shell, and scout still carries no template.

### CB-207 Research round four (`docs/research/round4/`)

`brain radar --force`: 10 sources checked, 12 new items, 0 errors in 0.79 s. The three official leads are enterprise compliance pages, not relevant to the brain.

| Memo | Result |
|---|---|
| `01-facts-recheck.md` | 14 of 18 facts confirmed against official pages; `fact-effort-curves` changed (the deep-research gain is 3.3 points; 3.2 is the cost multiple); three confirmed only in part (two-repo loading of skills and agents rests on inference plus CB-201's live view; adding MCP servers breaks the cache only when tools load upfront; the cost-shape percentages are a local measurement). `memory/models.json` matches every id and price but lacks Haiku 5.5's higher price above 100K tokens, so cost routing under-prices Haiku five-fold on very long prompts |
| `02-platform.md` | All five confirmed by official pages: skill descriptions budgeted at 1% of context, least-used dropped first; skill frontmatter hooks register on invocation (answers CB-107 from the docs); sub-agent `model`, `effort` and `omitClaudeMd` honoured (matches CB-201); an effort change keeps the cache on Opus 5.5 with a subscription, a model switch does not (answers CB-112 from the docs); main-conversation cache lives 1 hour on a subscription, sub-agents 5 minutes |
| `03-persona-and-briefs.md` | Three independent 2024-2026 studies find expert role lines do not raise accuracy and sometimes lower it; none tested Claude. No direct measurement of pointer-to-file against inline briefs exists; the memo's estimate is that a pointer pays only when a brief is reused. The rack's `role_line` is a short functional label, which fits this; the pointer saving stays unproven |

Recorded through `brain learn note --trust external` (five facts with their official URLs: skill hooks, effort and cache, skill listing budget, Haiku long-prompt price, the corrected effort figure); they enter `memory/` at the next consolidation. The Haiku price row in `models.json` needs a model-table change, listed as open. The facts researcher used 86,765 tokens on a 20,000 wage (4.3x): the template's size band was too small for eighteen page checks.
