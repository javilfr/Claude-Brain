# Analyst 5 — Lessons from the sample repo (operating history)

Sample repo root (read-only, nothing modified): `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose` (all paths below are relative to it unless absolute). Checked-out branch: `claude/wizardly-darwin-91m4pl`; history available locally is 50 commits (shallow), all dated 2026-11-05 05:30–20:03 UTC; session 1 (2026-11-04) is squashed into the first commit `1b0a7f9` (630 files, 94,555 insertions). The product repo `Travel-Journal` is not checked out on this machine, so product-side claims rest on what the company repo records about it.

Limits of this analysis: token costs of waste are not metered anywhere in the repo except ten research runs on day 1 (`payroll/data/ledger.jsonl`), so "where tokens were wasted" is inferred from artefacts (deleted work, unused machinery, document sizes), not measured.

---

## PART A — Independent extraction of the owner's message 2

Source: `/tmp/claude-0/-home-user/ad24da2f-7dc0-51cf-aa28-dee6f5e57a4f/scratchpad/OWNER_PROMPT.md`.

| # | Type | Exact words | What it requires |
|---|---|---|---|
| 1 | Context | "I essentially used this repo as a brain to create everything in my travel journal in the best possible way" | The sample is the reference pattern: a company/brain repo steering a product repo. Its successes and failures are primary evidence. |
| 2 | Requirement | "create a repo that will act as that (essentially a mega complex orchestrator)" | Deliverable is a repository (`javilfr/Claude-Brain`), functioning as an orchestrator. "Mega complex" describes capability, not a mandate for bulk (see #14). |
| 3 | Requirement | "but to build anything I will ever need from now on" | Domain-agnostic: not web-app specific. Must handle software, documents, research, data, design, writing, automation. |
| 4 | Constraint | "When using it I will always use two repos in a chat, one of them the Claude brain" | Fixed runtime topology: brain repo + one project repo per chat. Brain must detect and adapt to whichever project repo is the sibling. |
| 5 | Constraint | "which will be only modified by its own machine learning systems as it improves by learning with everything I use it for" | (a) The brain self-improves from every use. (b) Nobody hand-edits it: the owner does not, and project work must not casually edit it. Needs a governed write path. **Reframe needed** — see F1. |
| 6 | Requirement | "the other repo will be where the project will be built which can also hold files and tools to complement the Claude brain functionality that are specific to that project" | Project-repo extension layer: project-specific rules, tools, skills, state. Brain = generic; project = specific. Clear precedence rules needed. |
| 7 | Requirement | "both will always be worked together from now on so the project must be built to work perfectly with it forever" | A stable, versioned contract between brain and project repos; backward compatibility; a check that a project repo conforms. "The project" here most plausibly means the brain project (it must work with any project repo forever); ambiguity A1. |
| 8 | Deliverable | "Now you will create a super long, super detailed plan on how to build this" | A long, detailed build plan is an explicit deliverable, before building. |
| 9 | Requirement | "based on very comprehensive research about Claude fable 5.2 and opus 5.5 (the main models ai will use it with)" | Research on both models' actual behaviour, limits, pricing, features; the design targets these two models (with cheaper tiers for delegation). |
| 10 | Requirement | "and also using everything we learned with the sample repo I attached" | This report's Part B. |
| 11 | Constraint | "(obviously having present that the current Claude brain's scope for creating stuff is much bigger)" | Do not copy travel-journal specifics (PWA, maps, Critic rubric for phone screens). Generalise mechanisms only. |
| 12 | Requirement | "you must look at all your memory in detail and all our chats and consider everything I have ever asked you to build on Claude or any question I have ever asked you can be successfully processed to completion" | Coverage requirement: the brain must handle the full range of his past requests. **Reframe needed** — F2. |
| 13 | Top priority | "VERY IMPORTANT, you MUST MAKE THIS THE MOST EFFICIENT CLAUDE TOOL EVER" | Efficiency is the headline non-functional requirement. Needs measurable budgets, not a superlative. F3. |
| 14 | Requirement | "much more efficient in tokens through plugins and algorithms and quantum logic and many other thing you must research" | Research concrete token-saving mechanisms: plugins/skills (progressive disclosure), hooks, scripts instead of prose, caching, model routing, retrieval. "quantum logic" — **reframe needed**, F4. |
| 15 | Requirement | "super efficient token wise and super fast" | Two separate budgets: tokens and wall-clock. |
| 16 | Requirement | "while delivering the absolutely highest quality work with absolute attention to detail (focus a lot on accuracy, creativity and extreme attention to detail)" | Three named quality axes: accuracy, creativity, attention to detail. Verification must be built in, not optional. Tension with #13/#15 — T1. |
| 17 | Requirement | "Create now the super long and super detailed plan considering also all our previous builds in Claude" | Plan must reference prior builds (at minimum the Travel Journal pair; others only if accessible — F2). |
| 18 | Requirement | "and then start building until completion once you have a full plan based on extremely extensive research" | Sequence: research → plan → build to completion, in this same engagement, without stopping to ask. Needs a definition of "completion" (A2). |
| 19 | Process | "Make sure you analyze this prompt by 10 independent agents and extract everything I said in full detail" | Ten independent analyses (this is one). Independence means no shared drafts. |
| 20 | Process | "you can execute to perfection by planning perfectly and researching and analyzing heavily everything" | Heavy up-front analysis is authorised and expected for this task. |
| 21 | Constraint (msg 1, still binding) | "we will not modify or touch this repo at all in this chat, just read it" | Sample repo is read-only. |

Implied expectations (not stated, but evident from the sample repo and context):

- I1. No shell commands for the owner, ever (`CLAUDE.md` §4, §10; `docs/NEEDS_YOU.md` header "Nothing here requires a command").
- I2. A one-phrase trigger like "Start running" must keep working (`START_HERE.md`).
- I3. Autonomy: decide and record, do not ask (`CLAUDE.md` §1.6).
- I4. Runs in Claude Code cloud sessions on a Max subscription, so the binding scarce resource is the 5-hour usage window, not dollars (`docs/status/2026-11-04.md`, `docs/status/2026-11-05.md`).
- I5. Deployable work visible continuously on `main` (`CLAUDE.md` §11).
- I6. Multilingual output at native quality when asked (Spanish from Spain treated as a gate: `docs/board/OPERATING_SYSTEM.md` §4.3).

Flags — impossible or needing honest reframing:

- **F1 "its own machine learning systems".** No model weights are trained. What is achievable: a file-based learning loop (capture outcome → distil a lesson → test it against an eval set → promote it into a rule, skill, script or hook → prune what stops paying). "Only modified by" can be enforced mechanically: a PreToolUse hook that blocks edits to brain paths unless the edit comes through the learning pipeline, with every change committed as a reviewable diff. In cloud sessions the brain repo is pushed on a session branch, so "learning" also needs a merge path to the brain's `main` that the owner does not have to operate by shell.
- **F2 "all your memory … all our chats".** A session can read only what is in the attached repos, the current conversation and any memory the runtime exposes. The honest substitute: mine the sample repo pair for the full range of request types, and state plainly which past chats could not be read.
- **F3 "MOST EFFICIENT CLAUDE TOOL EVER".** Unverifiable as stated. Replace with numeric budgets (orientation tokens per session, tokens per delivered task, first-pass acceptance rate) and a benchmark against the sample repo's measured baseline (Part B §6).
- **F4 "quantum logic".** No quantum computation is available to Claude Code. Say so. The useful adjacent ideas are classical: search/selection algorithms, probabilistic routing, early-exit verification, caching. Do not ship anything labelled "quantum".
- **T1 Tension: longest plan + highest quality + fewest tokens + fastest.** Resolve by separating the one-time build (heavy analysis authorised, #20) from the steady-state runtime (lean by budget).
- **A1 Ambiguity:** "the project must be built to work perfectly with it forever" — which project? Reading: every project repo, hence a versioned contract plus a conformance check.
- **A2 Ambiguity:** "until completion" — the sample repo's own definition of done was never reached (Part B §1). The new plan needs gates that can actually be closed in one engagement.
- **A3 Ambiguity:** who writes the brain initially? The build itself is a manual write; "only modified by its own ML systems" applies after bootstrap.
- **A4 Ambiguity:** "plugins" — Claude Code plugins/skills/hooks/MCP servers, or something he imagines installing elsewhere. Assume the former.

---

## PART B — The sample repo as an operating history

### 1. Timeline: how the company actually operated, and where time and tokens went

**Day 1, 2026-11-04 (session 1; squashed into `1b0a7f9`).**

- Kit installed; ten research analysts launched in the same second at 17:30:10 and finished in 4–11 minutes (`payroll/data/ledger.jsonl`, `first_ts`/`last_ts`). All ten ran on `claude-fable-5-1` although the role was budgeted for `sonnet-5-5` (`docs/hr/payroll/REPORT.md`: role row "sonnet-5-5 … Last actual 212 (fable-5-1)"). Cost 211–527 credits each against a 150-credit base salary; total 2,848 credits (USD 28.48). Model tiering was a prose rule, not enforced.
- 22 agent specs, hooks, token payroll with 94 tests, journal voice guide (`docs/status/2026-11-04.md`).
- The owner asked for the app first, so TJ-016 was pulled forward and the plan's order broke on day 1 (`docs/adr/ADR-005-phase-0-rebaseline.md` Context).
- "the session hit the 5-hour usage limit once; four agents were resumed after the reset" (`docs/status/2026-11-04.md`).

**Day 2 early (session 1 continued).**

- Built before the product had passed its own quality bar: a management canon of 100 thinkers (107 card files, about 60,600 words; 61 of 100 cards needed correction, 36 claims removed, 75 still unverified — `library/cards/management/VERIFICATION.md`), a 7-seat Board, a 500-role HR catalogue (about 102,700 words of Markdown in `docs/hr/catalogue/` plus JSON in `orgdesign/catalogue/`), and a staffing engine (`docs/status/2026-11-05.md` first bullet).
- Improvement wave 1: nine teams in parallel worktrees (`docs/phases/improvement-wave-1.md` line 16).
- "two usage-limit stops; agents resumed after resets" (`docs/status/2026-11-05.md`). `START_HERE.md` records the cause: "Ten parallel Opus agents exhausted the 5-hour window twice."
- Subagent output was lost in transit: the Board's pre-read was incomplete — "the sixth initiative … cut off after its roles list. A third strategist's lens was announced but not received" (`docs/board/minutes/2026-11-05-inaugural.md`, "Pre-read defect"; also `docs/phases/improvement-wave-1.md` line 313).
- The Board found the state it had to govern: `docs/gates/` empty, no Phase 1 plan, "All 500 ideas are `todo`", Critic r1 4/10 and r2 6/10 against a bar of 8, a wrong timestamp on screen, 0 Spanish files, staffing demand "computed from 134 ideas and 0 tickets", payroll estimator MAPE 52% against a 35% target (minutes §1).

**Day 2, session 2 (branch `claude/start-running-uh1x7t`; commits 05:30–20:03).**

- 05:30 ADR-005 re-baselines the Phase 0 gate instead of passing it: criteria 2, 6 and 8 not done (`docs/adr/ADR-005-phase-0-rebaseline.md`).
- 05:51 Live site crashed after the owner's Vercel import: `MIDDLEWARE_INVOCATION_FAILED`; the family-gate middleware was unplugged (`docs/NEEDS_YOU.md` #9, TJ-021). The local gate had not caught a deploy-only failure.
- The owner reviewed on a real iPhone and found blank maps, an invisible trip cover and a title collision (`docs/status/2026-11-05.md`, TJ-022). The e2e suite blocks MapLibre on purpose (`START_HERE.md` lessons), so the tests could not have caught it.
- 06:24 Two pushes reached `main` without a green check (`docs/lessons/2026-11-05-push-only-on-a-green-exit.md`): a `;`-chained push after a failing unit run, and a push after a gate that exited 1.
- 07:24 Ticket-id collision: "TJ-021…024 were used by session hotfixes; planned work renumbered TJ-025…028" (commit `4317299`).
- 14:11 T2 held from main because a racy LCP test exposed a real 2.6–3.6 s paint (`docs/status/2026-11-05.md`); flakes under load are a recurring theme ("heavy suites with many agents running give false timing failures", `START_HERE.md`).
- 15:51 Blind Critic round 4: iPhone 3/14, Mac 4.5/14, "much of it missing evidence … captures at 393×659 instead of 402×874" (`docs/design/reviews/critic-r4/REVIEW.md` line 3). A full Critic round was largely spent scoring absent evidence. Work had been reaching `main` all day while the Critic score was below the "≥ 8 to merge" rule in `CLAUDE.md` §1.3.
- 16:43–18:23 The owner's persona report and then his "read-only" statement arrived. ADR-012 withdrew capture, inbox, outbox, desk endpoint, Questions card, Gemini hand-off page, planner editing and the whole sync track (`docs/adr/ADR-012-read-only-display-journal.md` "Supersedes"). TJ-093 deleted that code. This is the single largest rework in the history: wave 1 Team 6, wave 2 T7's capture flow, the long NEEDS_YOU #10 (now struck through), ADR-004/005 sync items, research memos R-A03/R-A04, and three engineering agent specs (`data-sync-engineer`, `media-pipeline-engineer`, parts of `frontend-mobile`) were built for a product the owner did not want. Root cause: the ten owner-interview questions were never answered (`docs/owner-brief.md`: every row "open"), and the build ran on ASSUMED answers to the biggest architectural fork.
- 19:55 gate21 red with 17 e2e failures, caused by adding a second sample trip (tests assumed one trip; `docs/status/PROGRESS.md` `last_completed`).
- 20:03 Session ended with three tickets mid-flight, saved as about 480 KB of patch files (`docs/handover/2026-11-05/`).

**State left behind (what a new session inherits).**

- Three branches named in one file: `START_HERE.md` says work is on `claude/start-running-uh1x7t`, then tells the owner to open a PR comparing `claude/new-session-cqavij`; this machine is on `claude/wizardly-darwin-91m4pl`. Company `main` is "initial commit only" (`docs/status/PROGRESS.md` note 1).
- Inconsistent handover instructions: PROGRESS note 3 says each folder has `STATUS.md` and to use `git am`; no `STATUS.md` exists and `docs/handover/2026-11-05/README.md` says `git apply --index COMBINED.diff`.
- Stale standing instruction: `START_HERE.md` step 5 says "run the design wave first … design wave 2", while PROGRESS says wave 2 is complete.
- Commit noise: 26 of 50 commits are "checkpoint" commits, several changing one line.
- Repo weight: `docs/design` is 390 MB (521 files, mostly review PNGs) and `.git` is 449 MB. Every cloud session clones this.
- The SessionStart hook installs the product workspace and a Python ML stack, and rebuilds the Library index in the background with a 900 s timeout (`.claude/hooks/session-start.sh`, `.claude/settings.json`); the Library eval alone takes 598.7 s (`library/eval/last_result.json`).

**Machinery that was built and then never used (verified in the tree).**

| Machinery | Evidence of non-use |
|---|---|
| 500-idea coverage table | All 500 rows `todo`, none with a ticket (`docs/IDEA_COVERAGE.md`), although `CLAUDE.md` §9 requires updating it per ticket |
| Performance cards, hire/fire | "No cards exist yet" (`docs/hr/performance/README.md`); `.claude/agents/_retired/` holds only a README; `docs/ORG.md` "Retired roles: None" |
| Payroll | Ledger has 10 rows, all from 17:30 on day 1; "No grants issued yet" (`docs/hr/payroll/REPORT.md`); yet its hooks fire on every `Agent` call and every `SubagentStop` (`.claude/settings.json`) |
| Phase gates | `docs/gates/` does not exist; no gate was ever run |
| Backlog / Deferred | Both empty tables (`docs/BACKLOG.md`, `docs/DEFERRED.md`) |
| Principles Cards D1–D7, E1–E7 | Never written (ADR-005 criterion 6), yet every agent spec tells the agent to query the Library for them (for example `.claude/agents/design-critic.md` "Before you start") |
| Lessons corpus | One lesson file (`docs/lessons/`). The real lessons were written into `START_HERE.md` and PROGRESS notes instead |
| Per-role scope hooks, ADR-touched check, ingest-on-merge | "Planned additions (not yet implemented)" (`.claude/hooks/README.md`), although `CLAUDE.md` §8 says "hooks block edits outside a role's declared paths" |
| Board cadence artefacts | `PORTFOLIO.md`, `POKA_YOKE.md`, `DECISION_LOG.md` are referenced by `docs/board/OPERATING_SYSTEM.md` and do not exist in `docs/board/` |

### 2. KEEP — mechanisms that demonstrably worked

| Mechanism | Evidence it worked | How to generalise |
|---|---|---|
| Single checkpoint file + resume loop | Session 2 resumed from `docs/status/PROGRESS.md` and shipped eight waves to main in one day; the file carries branch, last green commit, next three, and notes | Keep one machine-readable `STATE` file per project repo (not in the brain). Fields: goal, current step, last verified artefact, next three, blockers. Applies to any deliverable type. Generate the human view from it. |
| One-phrase trigger ("Start running") | `START_HERE.md`; the owner needs to remember two words | Keep as a skill/command. Its behaviour must be defined in one place and never contradict the state file. |
| NEEDS_YOU with click-only steps and a "Meanwhile" default | The owner completed the Vercel import from item 5 (`docs/status/2026-11-05.md`); work never blocked | Keep. Generic rule: every ask states what, why, exact clicks, and what is assumed meanwhile. But see §5: he answers in chat, not in files — also ask the one or two fork-level questions in chat. |
| DECISIONS / ASSUMED with one-line overturn | 17 rows in `docs/DECISIONS.md`; owner directions (#13–17) were recorded the same way and became binding | Keep, as an append-only log. Mark each row with reversibility (cheap / expensive / one-way). |
| ADRs for real forks | ADR-005 and ADR-012 are the clearest documents in the repo; ADR-012 quotes the owner verbatim and lists what is withdrawn | Keep, but only for expensive or one-way decisions; rename generically ("decision record") for non-software work. |
| Blind reviewer with a written rubric, author excluded | Critic rounds moved 4 → 6 → specific must-fix lists; the Spanish edition was "independently back-translated with zero fact drift" (`docs/status/2026-11-05.md`) | Keep as the core quality primitive: a separate-context verifier given only the artefact and the acceptance criteria. Generalise the rubric per deliverable type (code, prose, data, design). Add an evidence-completeness precheck so a round is not spent scoring missing inputs (r4). |
| Deterministic gate as one command with numeric budgets | "gate green: 833 unit / 415 e2e", initial JS 133 kB of 250 (`docs/status/PROGRESS.md`) | Keep: every project declares one `verify` command in its repo; the brain only knows "run verify, read exit code". |
| Release rule: push to main only on a green exit | `CLAUDE.md` §11 plus the lesson; the owner sees progress on Vercel | Keep, but as a script/hook (see §4), and add a post-deploy smoke check. |
| Handover patches for unfinished work | `docs/handover/2026-11-05/README.md` gives base commit, apply order, done/left per ticket | Keep the idea; simplify: push WIP branches and record their names in STATE. Patches inside another repo are a workaround for branch confusion. |
| Lesson → rule conversion | The one lesson produced a concrete guard (`grep -qx 'exit 0'` before push) | Keep, and make it the learning pipeline: each lesson must end in a hook, script, test or a one-line rule, or it is not accepted. |
| Verbatim owner quotes in decisions and plans | ADR-012, `docs/plans/READINESS.md` | Keep: store the owner's exact words with each requirement; it prevented drift. |
| Fact discipline: facts only from the owner's material, guesses listed as `uncertain`, questions asked in chat | `journal/WORKFLOW.md` | Generalise to an "unverified claims" list on every deliverable. |
| Stand-ins behind interfaces, never block on credentials | `CLAUDE.md` §5; work proceeded with no accounts | Keep as a principle; one paragraph. |
| Disjoint file ownership per parallel worker, with pre-agreed seams | `docs/phases/improvement-wave-1.md` §3; nine teams merged | Keep as the precondition for any parallel fan-out. |
| One independent "red team" read at a decision point | The Board (by reading code itself) found the UTC timestamp bug, the GPS leak risk, and refused to let a skipped gate be called passed (minutes §1, §2.1, §2.4) | Keep the function, not the institution: one adversarial reviewer with a short checklist at gates (see §3). |

### 3. DROP / SHRINK — heavy relative to value

| Item | Cost (measured) | Value observed | Lean replacement |
|---|---|---|---|
| 22 standing roles + 7 board seats = 30 agent specs | 26,500 words of specs; 1,239 words of descriptions loaded into every session; each spec repeats the product paragraph and a "Before you start" checklist | 14 of 22 roles "dormant" (`docs/ORG.md`); real work was done by ad-hoc teams named T1–T9; no role ever reached a performance card | 4–6 generic agents defined by function, not job title: explorer (cheap, read-only), builder, verifier (blind), researcher, plus project-specific ones in the project repo. Description ≤ 25 words each. |
| 7-seat Board, charter, operating system | 2,963 + 2,946 + 5,516 words, on the start-of-session reading list; seven Opus runs per session; several referenced files never created | One session; three real findings and one useful veto | A single red-team review skill run only at gates and one-way decisions, with a 10-line checklist (ruin/data loss, facts, privacy, evidence present, scope cut). |
| 100-thinker management canon | 60,600 words; a full verification pass in which 61% of cards needed correction | Used as citations in Board prose; no product decision traces to a card that common sense would not have reached | Drop. Keep about ten operating rules as plain sentences (`OPERATING_SYSTEM.md` §1 is already that list). |
| 500-role HR catalogue + staffing engine | About 102,700 words Markdown plus JSON, about 1,900 lines of Python and 69 tests | Staffing plan computed from "0 open tickets"; it demoted the Design Critic (minutes §1) and needed manual pins | Drop. Role selection is a 5-line routing table: task type → agent → model tier. |
| Token payroll | 14 Python modules, 94 tests, 3,270-word README, two hooks on every spawn/stop | 10 metered runs, 0 grants, MAPE 52%; did not prevent three usage-limit stops; did not stop Fable being used where Sonnet was budgeted | One hook that (a) caps concurrent subagents, (b) enforces the model tier in the routing table, (c) appends one line per subagent to a usage log. No salaries, grants or negotiation. |
| 500-idea coverage table inside an 18,000-word master plan | 9,569 + 17,936 words | 0 of 500 rows ever updated; the owner's real direction (six pillars, read-only) came from his own report and replaced much of it | A short requirements list derived from the owner's words, each with an acceptance check; a backlog that is allowed to be small. Generate ideas on demand, not up front. |
| Phases 0–6 with formal gates | Gate criteria written; `docs/gates/` never created | Order broke on day 1 when the owner asked to see the app | Thin vertical slice first, shown to the owner early; gates attached to slices that can close within a session. |
| Local RAG stack (embeddings, reranker, MCP server, 244-question golden set) | Python ML install each fresh session; 10-minute eval; background index rebuild | Recall 0.914 on its own golden set; no evidence in status files that retrieval changed a decision; the cards it was meant to serve were never written | Start with file layout + grep/FTS and short index files; add dense retrieval only if a measured miss rate justifies it. |
| Screenshots committed to the company repo | 390 MB, 521 files | Evidence for Critic rounds | Keep evidence out of git history (artefact store, or keep only the latest round, downscaled). |
| Daily digest + PROGRESS + START_HERE + handover README + minutes all restating status | Five places; they disagreed by the end (branches, `STATUS.md`, `git am` vs `git apply`, wave 2 done vs "run wave 2 first") | PROGRESS alone was the working source | One state file; everything else generated or dropped. |
| Checkpoint commits | 26 of 50 commits | Protection against sudden session end | Keep the protection, cut the noise: a Stop hook that commits the state file automatically. |

Honest counterweight: the ambition of these systems is what the owner asked for and enjoys ("mega complex orchestrator"). The recommendation is not "small brain", it is "complexity in scripts, hooks and on-demand skills that cost zero tokens until used, not in always-read prose and standing institutions".

### 4. FAILURE MODES and the preventive mechanism to build in

| # | Failure observed | Evidence | Preventive mechanism (deterministic where possible) |
|---|---|---|---|
| 1 | Building on assumed answers to the biggest fork; large rework when the owner's real intent arrived | `docs/owner-brief.md` all "open"; ADR-012 "Supersedes" list | Intake step that identifies fork-level unknowns (those that change architecture) and asks at most three of them in chat before any build; everything else assumed. A script refuses to mark intake complete while a fork-level item is still ASSUMED and expensive work depends on it — or the work is limited to a thin slice. |
| 2 | Usage-window exhaustion from wide Opus fan-out | `START_HERE.md` lessons; both digests | PreToolUse hook on agent spawn: hard cap on concurrent agents (4–6), model tier taken from the routing table, refuse top-tier model for exploration/mechanical tasks. |
| 3 | Push to main on a red or untested build | `docs/lessons/2026-11-05-push-only-on-a-green-exit.md` | A `release` script is the only path to main: runs verify, checks exit code, checks ancestry, pushes, then polls CI and the deployment. PreToolUse hook blocks raw `git push … main`. |
| 4 | Deploy-only failure invisible to the local gate | NEEDS_YOU #9 (live 500) | Post-deploy smoke check in the release script (fetch the live URL, assert status and a marker). |
| 5 | Tests cannot see what the owner sees | TJ-022 iPhone findings; MapLibre blocked in e2e | Verification plan per deliverable must name what is not covered and how the owner-visible surface is checked (real-device screenshots or an explicit "unverified" note in the report). |
| 6 | Flaky timing tests under machine load | `START_HERE.md` (4 cores), PROGRESS note 4 | Gate runner takes a lock so only one heavy verify runs at a time; timing budgets run single-worker; a failed timing test is retried once in isolation and labelled flaky vs real. |
| 7 | Worktree started at the wrong commit; `git add -A` swept worktrees; port clashes | `START_HERE.md` lessons | A `spawn-worktree` script that creates the worktree at the named commit, assigns a port, and verifies; worktree directory ignored by default. |
| 8 | Branch and main-state confusion across sessions | `START_HERE.md` names two branches; company main is the initial commit; this checkout is a third branch | SessionStart script prints a 5-line truth table (current branch, where the latest state lives, ahead/behind main for both repos) and fast-forwards from the branch recorded in STATE. STATE is the only place a branch name is written. |
| 9 | Status documents drift and contradict each other | §1 "State left behind" | Single source of truth; a lint script that fails if a referenced path does not exist (would have caught `STATUS.md`, `docs/gates/`, `PORTFOLIO.md`, `POKA_YOKE.md`). |
| 10 | Rules exist only in prose and are not followed | Critic ≥ 8 to merge vs pushes at 6/10 and 3/14; IDEA_COVERAGE never updated; "hooks block edits outside a role's paths" not implemented | Every "must" in the always-loaded file must be backed by a hook, script or test, or be deleted. A periodic self-audit lists rules with no enforcement and no observed compliance. |
| 11 | Review round spent on missing evidence | `critic-r4/REVIEW.md` | Evidence manifest checked by script before the reviewer is spawned (required captures, sizes, states present). |
| 12 | Subagent output truncated or never delivered | Minutes "Pre-read defect" | Subagents write results to a file with an end marker; the lead checks the marker before synthesising. |
| 13 | Tests encode an assumption the next change breaks (single sample trip) | gate21, 17 failures | Fixtures with ≥ 2 of everything from the start; a rule in the test-writing skill. |
| 14 | Ticket-id collisions between planned and hotfix work | commit `4317299` | Ids issued by a script (next integer from the state file), never typed by hand. |
| 15 | Infrastructure built ahead of need and never used | §1 table | "Earn its keep" rule for the brain itself: a mechanism is added only after the problem occurred twice (or the owner asked), and each mechanism records uses; unused after N sessions → flagged for removal by the learning pipeline. |
| 16 | Lessons not captured in the lessons system | one file in `docs/lessons/` | Stop hook prompts for a lesson only when a trigger fired (red gate, reverted commit, usage stop, owner correction), and writes it to a queue the learning pipeline processes. |
| 17 | Session ends mid-ticket | handover folder | WIP limit of in-flight units tied to remaining budget; near the limit, stop starting new work and land or park what is open. |
| 18 | Heavy session start | `.claude/hooks/session-start.sh` | Session start does nothing slow by default; installs happen lazily when a task first needs them. |
| 19 | Repo bloat from binary evidence | 390 MB of PNGs | Size check in the commit path; binaries above a threshold go elsewhere. |

### 5. Owner working-style profile (as generic orchestrator requirements)

Derived from `CLAUDE.md` §4, §10, §11; `docs/NEEDS_YOU.md`; `docs/DECISIONS.md` #13–17; `docs/adr/ADR-012-read-only-display-journal.md`; `docs/plans/READINESS.md`; `docs/board/OPERATING_SYSTEM.md` §3.2, §4.3; `docs/status/*`. Persona material in `docs/owner/` was read only for working style; no personal details are reproduced.

1. **Short trigger, long autonomy.** He types a few words ("Start running") and expects hours of unattended, correct work. Never ask for confirmation to proceed.
2. **Ambitious, superlative briefs in one long paragraph.** Requirements, constraints and priorities are interleaved. The orchestrator must extract and number them itself and keep his exact words.
3. **Direction arrives mid-build, in plain words, and overrides the plan.** Six pillars, read-only display, light theme all arrived on day 2. Treat his latest statement as binding, record it verbatim, and state what it withdraws.
4. **He does not fill in questionnaires in files.** Items #1, #3, #6, #8 and #12 of `docs/NEEDS_YOU.md` remain unanswered; he did complete the one click task that produced something visible (#5). Requirement: defaults must always work; ask very few questions, in chat, only when the answer changes the architecture.
5. **No shell commands, ever.** Everything he does is reading a file, clicking in a browser, or typing in the chat.
6. **The chat is his only input surface.** He wants to tell Claude and see the result elsewhere (ADR-012). Generic form: do not build input UIs or admin tools for him unless asked; the orchestrator is the interface.
7. **"Done" means he can see and use it.** Deployed on `main`, visible on a real device, checked by him personally; he notices visual defects quickly. A green test suite is necessary, not sufficient.
8. **Continuous visible progress.** "keep shipping visible, testable improvements to main continuously" (commit `e6d8b02` PROGRESS line). Prefer many small verified releases to one large one.
9. **Prove it completely on samples before real data.** "have it 100% ready with a sample so we can check everything is ready and fully implemented and working" (`docs/plans/READINESS.md`).
10. **He asks for scale and parallelism** ("large teams of agents working at the same time", `OPERATING_SYSTEM.md` §3.2). The orchestrator must deliver throughput within the usage window, and say so honestly when a cap applies.
11. **Native-quality multilingual output** when a second language is requested: transcreation, independent review, fact parity.
12. **Accuracy is non-negotiable.** A wrong date was treated as a stop-the-line defect. Unverified claims must be listed, never smoothed over.
13. **Taste: precise, editorial, restrained.** Clean tables, high contrast, nothing gamified or generic. Applies to documents and reports as much as to UI.
14. **Privacy by default** for personal material: private source files stay in the non-deployed repo and are never published.
15. **He values understanding how the system works.** Explanations should be plain and exact; he reads the files.
16. **Standing instructions persist across chats.** When he says "from now on", it must be written where every future session will load it (`CLAUDE.md` §11 is the model).

### 6. Size audit and orientation tax

Word counts from `wc -w`; tokens ≈ words × 1.35.

**Always loaded in every session (company repo side).**

| Item | Words | ≈ Tokens |
|---|---:|---:|
| `CLAUDE.md` | 2,412 | 3,260 |
| 30 agent `description:` lines (`.claude/agents/*.md`) | 1,239 | 1,670 |
| 2 skill descriptions (`.claude/skills/*/SKILL.md`) | 139 | 190 |
| **Subtotal** | **3,790** | **≈ 5,100** |

The product repo's own `CLAUDE.md` adds to this (not measurable here).

**Told to read at session start (`START_HERE.md` steps 1–2 and 5).**

| Item | Words | ≈ Tokens |
|---|---:|---:|
| `START_HERE.md` | 944 | 1,270 |
| `CLAUDE.md` again ("Read this file fully at the start of every session") | 2,412 | 3,260 |
| `docs/status/PROGRESS.md` | 652 | 880 |
| `docs/handover/2026-11-05/README.md` | ≈ 420 | 570 |
| `docs/NEEDS_YOU.md` | 1,709 | 2,310 |
| `docs/DECISIONS.md` | 582 | 790 |
| `docs/board/CHARTER.md` | 2,963 | 4,000 |
| Latest minutes `docs/board/minutes/2026-11-05-inaugural.md` | 5,516 | 7,450 |
| `docs/phases/` (three files) | 7,411 | 10,000 |
| **Subtotal, mandatory list** | **22,609** | **≈ 30,500** |
| `docs/board/OPERATING_SYSTEM.md` ("use the operating rules") | 2,946 | 3,980 |
| Current plan `docs/plans/WAVE_3_SIX_PILLARS.md` | 7,888 | 10,650 |
| **Subtotal with the two documents the work actually needs** | **33,443** | **≈ 45,100** |

Further: the first-run kickoff says to read `docs/MASTER_PLAN.md` "completely" (17,936 words ≈ 24,200 tokens, `KICKOFF_PROMPT.md`); the design-wave documents step 5 points to are part of about 32,000 more words under `docs/design/`; and step 3 runs a baseline lint/typecheck/test whose output also enters context.

**Per-subagent tax.** Each spec is 687–1,172 words (≈ 930–1,580 tokens) and instructs the agent to read PROGRESS, the current phase file and bound ADRs and to query the Library before starting (`.claude/agents/design-critic.md` "Before you start"): roughly 3,000–12,000 tokens per spawn before any work. With nine or ten agents in parallel that is 30,000–120,000 tokens of repeated orientation per wave.

**Estimate.** Lead orientation ≈ 35,000–50,000 tokens per session (always-loaded 5,100 + reading list 30,500–45,100), before tool output. On a model with a large context this is affordable once, but it is re-paid as cached or uncached input on every turn of a long session and after every compaction.

**Proposed targets for the new brain.**

| Budget | Sample repo | Target |
|---|---:|---:|
| Brain always-loaded (CLAUDE.md + agent/skill descriptions) | ≈ 5,100 tokens | ≤ 1,800 tokens (CLAUDE.md ≤ 900 words; ≤ 8 agents at ≤ 25 words; skills carry the detail and load on demand) |
| Project always-loaded | unknown | ≤ 600 tokens |
| Session-start orientation read | ≈ 30,500–45,100 tokens | ≤ 2,500 tokens: one generated state brief (≤ 400 words) injected by the SessionStart hook, plus only the changed lines of the needs/decisions logs |
| Per-subagent orientation | ≈ 3,000–12,000 tokens | ≤ 800 tokens: a self-contained brief generated from a template; no "read these five files first" |
| Total lead orientation | ≈ 35,000–50,000 tokens | ≤ 5,000 tokens (about a 90% cut) |

Enforce the budgets with a script in the brain's own verify step (word counts of always-loaded files and of the generated brief), so the brain cannot grow past them through its own learning.

---

## Twelve findings that should drive the design

1. Orientation tax was about 35–50k tokens per session and 3–12k per subagent; target ≤ 5k and ≤ 800.
2. The biggest waste was building for assumed owner answers (capture/sync), later deleted under ADR-012; fork-level questions must be asked in chat up front, at most three.
3. Most governance machinery was never used: 500 ideas all `todo`, zero performance cards, zero gates run, payroll with 10 rows, empty backlog.
4. Prose rules were not followed where no hook enforced them (Critic ≥ 8 to merge; scope hooks "planned"). Every "must" needs a hook, script or test.
5. Usage-limit stops (three in two days) came from wide top-tier fan-out; payroll did not prevent them. A concurrency cap and tier enforcement hook would.
6. Two pushes reached main without a green check; release must be a single script, raw pushes to main blocked.
7. Status lived in five places and ended up contradictory; keep one state file and lint for dead references.
8. What worked: the checkpoint file, the trigger phrase, NEEDS_YOU with defaults, DECISIONS/ASSUMED, ADRs with verbatim owner quotes, the blind reviewer with a rubric, the one-command gate, disjoint file ownership.
9. The Board's real value was one adversarial read at a decision point; keep that as a single red-team skill.
10. The owner does not answer file questionnaires but does act on click tasks with visible payoff; he steers in chat, mid-build.
11. "Done" for him is deployed, visible and personally checked on a real device; tests missed what he saw.
12. Three phrases in the new request need honest reframing: "machine learning systems" (a governed file-based learning loop, no training), "quantum logic" (not available), "all your memory and all our chats" (only what the session can read).
