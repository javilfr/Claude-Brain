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

## 2026-11-10 improvement session (CB-200 to CB-209)

### CB-200 Baseline and self-audit

Every line below is a command run at the start of this session, before any change.

| Check | Result |
|---|---|
| `python3 -m unittest discover -s tests -t .` | 407 tests, OK, 37.7 s |
| `brain doctor` | brain is healthy; always-loaded budget about 2550 tokens; model facts verified 0 days ago |
| `brain lint` | 0 errors, 0 notes |
| `brain hr audit` | 100 templates in 10 groups (scout 0, researcher 17, builder 48, writer 19, reviewer 15, redteam 1); rack is sound |
| `brain lint --transcript` | 0 whole-file re-reads, 0 serial read-only runs, 1 model, 0 helpers, 95% input from cache |
| `brain items check` | 141 items in 9 files, all valid |
| `brain eval audit` | 12 tasks, 12 sound |
| `brain learn consolidate` | first real delta `d-20261110-a431e755f2`: 3 ops (APPEND_STAT 1, MARK_INBOX 1, ML_FOLD 1); 1 ledger row, 2 hire records folded into statistics, inbox empty |
| `brain learn verify` | 1 delta replayed on `origin/main`; learned zone matches |

Differs from the handover: the build session's 407 tests and clean audits reproduce exactly. The "brain is on its working branch, not `main`" line above is out of date (commit `19fb016`: the owner merged it); CB-209 corrects it.

### CB-202 End-to-end trial on a scratch project

A tip calculator (Python CLI, split between people, tests) in a scratch repository with a local bare remote, run through the real flow: `boot` → `init` → 4 ledger lines (one implied) → plan and tickets → `plan schedule` (2 parallel, 2.0x) → `hr staff` (2 plain builders, $1.20 payroll) → 2 × `hr hire` → 2 builder helpers on sonnet in parallel → `hr settle` (both checks passed when the brain re-ran them; 5,234 and 5,220 of 20,000 output-equivalent tokens, 0.26x of wage) → `req check` → `gate` (12 tests) → `release` (refused uncommitted work, then pushed on green) → `checkpoint --push` → `resume` → `handover` (refused while the brain had uncommitted work, then ready).

Found and fixed, each with a test:

| Found | Fix |
|---|---|
| `boot` and `detect` ignored `--project`, `BRAIN_PROJECT` and the current repository; only siblings counted | Same precedence as every other command (`test_explicit_project_wins_over_siblings_like_every_other_command`) |
| "a command-line tip calculator in Python … with tests" routed as `knowledge.longform`: the typo matcher read "tests" as Spanish "tesis" | A vocabulary word never matches another as a slip; software vocabulary gains python, cli, script, program; the request joins `evals/routing.jsonl` |
| `req evidence --done` accepted typed evidence; I typed "13 unit tests", the gate ran 12 | `--done` runs a line's command check and refuses on failure; `req check --run` re-runs them; brain-verify uses it |
| `init` wrote no root `.gitignore`; the first release committed 7 `__pycache__` files | `init` writes one (secrets files and build caches); `adopt` still adds nothing outside `.brain/` |
| brain-plan told the lead to put implied needs in `--passes-when`; the CLI has `--implied --assumption` | Skill text matches the CLI |
| `method/quality.md` said an empty ledger passes; it fails at project size once building | Text matches the code |

Seen and left, with reasons: `hr hire` found no template for either Python item and offered unrelated "closest" ones (rubric-mapper, accessibility-auditor) — evidence for CB-204. `checkpoint --push` also committed the brain's learning inbox to the brain branch (only `learning/inbox/`; it left work in progress alone) — as designed. The local push printed a protocol warning caused by this container's `push.negotiate` git setting, not by the brain.

Cost from `brain ledger` at this point of the session: 12.5M tokens, $5.57 at list prices, helpers 43% (the CB-205 reviewer included); the two trial builders together $0.10. Cache read 99%.

### CB-201 Live platform checks in a one-repository session

Observations from this session (2026-11-10), not official statements; none is recorded as a fact because no official page was read for it.

| Question | Observed | How |
|---|---|---|
| Does the `PreToolUse` guard hook in `.claude/settings.json` fire? | **Yes.** With `learned_zone_locked` set to true for the test, an Edit to `memory/facts.jsonl` was refused by the platform: "PreToolUse:Edit hook error: memory/facts.jsonl is in the learned zone …". `VERSION.json` was restored at once (`git status` clean) | Edit tool call, then `git checkout VERSION.json` |
| Is the guard a no-op today? | Yes, by design (D-08): unlocked, it exits 0 for every path. `memory/ml_config.json` is a kernel file, not learned, so the guard never blocks it even when locked | Manual runs of `.claude/hooks/guard_paths.py`: exit 0 unlocked, exit 2 on `memory/facts.jsonl` locked |
| Does the `Stop` hook fire? | Not observable inside one turn; checked at the end of the session (see CB-209) | — |
| Do a skill's frontmatter hooks fire? | Not tested: no brain skill declares hooks (`grep -l '^hooks:' -r .claude/skills` finds none) | — |
| Do helpers honour the agent file's model and effort? | **Yes.** The CB-205 reviewer, launched with no override, ran every turn on `claude-opus-5-5` at effort `high`, as `.claude/agents/reviewer.md` sets. The two builders ran on `claude-sonnet-5-5` at effort `medium` (model also passed explicitly) | `"model"` and `"effort"` fields in each helper transcript under `~/.claude/projects/…/subagents/` |
| Is `omitClaudeMd` honoured? | **Yes.** No helper transcript contains the brain's `CLAUDE.md` text ("First, size the request"); the main transcript contains it 3 times | `grep -c` over the transcripts |
| Does an effort change mid-session keep the prompt cache? | Not testable from inside a session: the lead cannot change its own effort with a tool | Still open as CB-112 |

### CB-205 Template quality pass

A fresh-context reviewer (hire `h-20261110-872034`, rubric-mapper on opus, settled: 144,271 of 200,000, check passed) read all 100 templates against `hr/GUIDELINES.md`; findings with file and line in `docs/review/CB-205-templates.md` (0 blocking).

Fixed (renderer changes reach every template; each has a test in `tests/test_hr.py`):

| Finding | Fix |
|---|---|
| 18 researcher and redteam briefs said to run a command; those agents have no shell | Shell-less agents are told the lead runs the check at settlement (`NO_SHELL_CHECK`; rendered into exactly those 18) |
| 9 builders and 2 reviewers needed current web pages with no web tools | A brief whose template or task asks for current docs, and whose agent has no web tools, says so and asks the helper to name the page instead of guessing (`NO_WEB`; 10 templates) |
| Review templates without severity or confidence | Reviewer and redteam briefs without their own grading ask for severity and confidence (`FINDING_GRADES`; 10 templates) |
| The outside-content line went only to researchers | Also to reviewers and redteam, whose work is reading material they did not write |
| canonical-facts-keeper looped "until the script finds none" on files it may not edit | Fix only owned documents; the loop ends at zero or at a list for the lead |
| security-reviewer "top three paths"; premortem-redteam "three causes" against the redteam agent's "about five" | Every traced path tried or listed; about five causes |
| migration-planner (researcher) told to inspect the running system | Works from config and exports in its inputs and names what it could not see |
| visual-option-generator "three to five" against the source's "3-4" | Three or four |
| voice-matcher "never" without a reason | Reason added |

All 100 templates render a brief at most 403 words with no lint problem; `brain hr audit`: rack is sound.

Left, with reasons: about 56 method lines in 48 templates state no reason (the reviewer's regex counts 74). Rewriting them is polish of unknown value until CB-203 shows whether a template beats a plain brief at all. The near-duplicate pairs (legal-citation-verifier / legal-research-analyst; api-integration-builder / api-live-prober) wait for selection data from CB-204. The research pass on the five thinly sourced data templates moved to CB-207. Owner pronouns in five templates are left as the owner's own files use them.

### CB-204 Selection: baseline on a new held-out set (recorded before any change)

`evals/hr_golden_2.jsonl`: 100 requests written by a cold writer helper (hire `h-20261110-a6278d`, settled 22,989 of 60,000, check passed) from template names and `when` lines only, without opening `engine/` or `hr/rack/`; 34 in Spanish, typos in English rows, 100 templates covered, 4 rows with two labels.

| Set | Top 1 | Top 3 |
|---|---|---|
| dev (tuned on) | 100 | 100 |
| old held-out | 78 | 86 |
| **new held-out (heldout2), before any change** | **37** | **47** |

The old held-out figure overstated real accuracy: its requests were written alongside the keywords. The honest starting point is about one request in two finding its template in the top three.
