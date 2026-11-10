# Analyst 10 — Two-repo architecture, universality, and red team

Date: 2026-11-10. Scope: Part A (literal extraction of owner message 2) and Part B (brain/project contract, universality, owner experience, red team, trees, acceptance tests).

Claim markers: **[owner]** = owner's words; **[sample]** = measured in the read-only sample repo `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose`; **[source: URL]** = external evidence; **[inference]** = my reasoning, not verified; **[verify]** = must be tested in a real two-repo cloud session before the plan depends on it.

---

## 0. The twelve findings that should change the plan

1. **The brain cannot be "modified only by its own machine learning systems" in the literal sense.** No model weights are trained here. The honest equivalent is a gated, file-based learning pipeline: project sessions may only append structured observations to an inbox; a separate consolidation step promotes them; a path guard blocks every other edit. Section B1.6.
2. **Three clauses are impossible or unverifiable as written** ("quantum logic", "all our chats", "most efficient Claude tool ever") and need honest reframing rather than silent compliance. Part A, items 31, 24, 29.
3. **The sample repo mixed three things in one repo**: universal method, Travel-Journal project state, and Travel-Journal evidence. Roughly 425 MB of its `docs/` is project evidence (390 MB design screenshots) [sample]. None of that belongs in a brain that must stay small forever. Section B1.8.
4. **Request-size routing is the single largest efficiency lever.** Anthropic reports agents use about 4x and multi-agent systems about 15x the tokens of a chat [source: https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent, secondary summary of Anthropic's engineering post]. A quick question that triggers the project machinery wastes more than any caching trick saves. Section B2.3.
5. **The always-loaded surface must have a hard byte budget enforced by CI.** The sample's handbook is 16.5 KB and its 31 agent specs total about 184 KB [sample]. With two repos, both `CLAUDE.md` files and both agent/skill catalogues load. Proposed budget: brain `CLAUDE.md` at most 6 KB, project stub at most 2 KB.
6. **The learning loop in the sample barely ran.** The rule "write a lesson whenever a ticket costs more than two hours of rework" produced one lesson file in `docs/lessons/` across about 50 commits; the real lessons were written by hand into `START_HERE.md` [sample]. A learning system that depends on the agent remembering will not learn. It needs a deterministic trigger (Stop hook or end-of-session script).
7. **Role sprawl was real in the sample**: 31 agent specs, a 7-seat board, a 500-role HR catalogue (1.2 MB of `orgdesign/`), and a token payroll [sample]. MAST finds 41.8% of multi-agent failures are specification issues and 36.9% inter-agent misalignment [source: https://arxiv.org/html/2503.13657v2]. The brain should ship about 6 archetypes, not a company.
8. **Usage limits already bit**: "Ten parallel Opus agents exhausted the 5-hour window twice" [sample, START_HERE.md]. Fan-out caps must be a default in the brain, not a lesson to rediscover.
9. **The contract needs a schema version and a migration chain tested against frozen fixture projects**, or "forever" fails at the first brain refactor. Section B1.5.
10. **The manifest should be JSON, not YAML.** Python and Node read and write JSON with no installs; YAML needs a dependency, and dependency installs at session start were a 900-second-timeout hook in the sample [sample]. Section B1.2.
11. **Each repo must be usable alone.** A project attached without the brain must still resume from its own checkpoint; the brain attached alone must answer questions and maintain itself. Section B1.7.
12. **Branch confusion is a structural risk in cloud sessions.** In the sample, the company repo's `main` held only the initial commit while all work lived on a `claude/...` branch, and a new chat starts from `main` [sample]. The brain must define one rule for how its `main` advances (pull request with a path-restricted check), and the owner step must be one click.

---

# PART A — Literal extraction of owner message 2

Method: clause by clause, in order. Each item quotes the exact words, classifies them (R = requirement, C = constraint, P = preference, I = implied expectation, A = ambiguity, X = impossible or needs reframing), and states the reading.

## A.1 Framing and origin

1. **R/I** — *"I essentially used this repo as a brain to create everything in my travel journal"* — The sample repo is the precedent and the mental model. The new thing must feel like that, not like a different product.
2. **I** — *"in the best possible way"* — He judges the sample approach a success. The plan must preserve what worked (resume loop, NEEDS_YOU, DECISIONS, checkpointing, gates) and must not discard it for novelty. **A**: "best possible" is his belief; the sample also shows waste (items in B4), so "keep everything" is not the right reading.
3. **R** — *"I want now to create a repo"* — One new repository. Target is `javilfr/Claude-Brain` (context fact).
4. **R** — *"that will act as that"* — Same function as the sample: brain for building.
5. **R/A** — *"(essentially a mega complex orchestrator)"* — He expects orchestration: agents, routing, coordination. **X (reframe)**: "mega complex" conflicts directly with item 28 (most efficient ever). Complexity must be available on demand, not always on. State this conflict to him plainly.
6. **R** — *"but to build anything I will ever need from now on"* — Universal scope: not only apps. Unbounded in type and in time. **X (reframe)**: "anything" cannot be guaranteed; the honest form is a defined set of project types plus a generic fallback playbook, with coverage measured (B2).
7. **I** — *"from now on"* — Durability. The design must survive model changes, Claude Code changes, and years of use.

## A.2 The two-repo operating model

8. **C** — *"When using it I will always use two repos in a chat"* — Exactly two repositories attached per session is the normal case. **A**: "always" — what should happen when only one is attached, or three? Not stated; must be designed (B1.7).
9. **R** — *"one of them the Claude brain"* — The name is "Claude brain". The brain is one of the two, every time.
10. **C/X** — *"which will be only modified by its own machine learning systems"* — (a) The owner will not hand-edit the brain. (b) Project work must not edit the brain ad hoc. (c) There must exist identifiable "learning systems" that are the only writers. **X (reframe)**: there is no machine learning in the training sense; nothing here updates model weights. What can exist is a deterministic pipeline in which Claude sessions write structured lessons, evals decide promotion, and scripts apply the change. Say so explicitly. **A**: is the initial build (this session, the lead writing the brain) an exception? It must be, and so must emergency fixes; record that as a decision.
11. **R** — *"as it improves by learning"* — The brain must measurably improve over time. Implies metrics, before/after comparison, and the ability to show what changed.
12. **R** — *"with everything I use it for"* — Every use is a learning source: all project types, and also small requests. Implies a capture step that runs on every session at near-zero cost.
13. **R** — *"and the other repo will be where the project will be built"* — All project output lives in the project repo. The brain holds no project deliverables.
14. **R** — *"which can also hold files and tools to complement the Claude brain functionality that are specific to that project"* — The project repo may extend the brain: project-specific skills, agents, tools, knowledge, hooks. Implies an extension mechanism with precedence rules (project overrides or adds, never forks the brain).
15. **C** — *"and both will always be worked together from now on"* — Reinforces item 8. Also implies the two must be consistent with each other across sessions (version compatibility).
16. **R** — *"so the project must be built to work perfectly with it forever"* — A stable contract between brain and project, with backward compatibility. Old projects must keep working with newer brains. **A**: "the project" is singular but item 6 implies many projects; read as "every project". **X (reframe)**: "perfectly … forever" cannot be promised; the honest form is a versioned contract, migrations, and a compatibility test suite that runs on every brain change.

## A.3 The plan deliverable

17. **R** — *"Now you will create a super long, super detailed plan on how to build this"* — First deliverable is a plan document. Length and detail are explicit preferences. **P**: he wants to see depth; a short plan will read as low effort. Tension with efficiency: a long plan is a one-time artefact, not always-loaded context, so there is no conflict if it is stored as a file that sessions do not load by default.
18. **R** — *"based on very comprehensive research about Claude fable 5.2 and opus 5.5"* — Research must cover both named models specifically: capabilities, limits, pricing, context, effort settings, differences between them. **A**: model names are written informally; the ids are `claude-fable-5-2` and `claude-opus-5-5` (context fact).
19. **R/I** — *"(the main models ai will use it with)"* — "ai" is a typo for "I". These two are the main models, not the only ones. Implies model-aware routing (which model for which work) and that cheaper tiers may be used for sub-work. Also implies model facts will go stale and need a refresh mechanism.
20. **R** — *"and also using everything we learned with the sample repo I attached"* — A lessons-learned extraction from the sample is mandatory input: what worked, what wasted effort.
21. **C** — *"(obviously having present that the current Claude brain's scope for creating stuff is much bigger)"* — Do not copy the sample's software-product assumptions (phases 0–6, design critic, PWA gates). Generalise.

## A.4 Memory and history

22. **R/X** — *"Also you must look at all your memory in detail"* — Review whatever persistent memory is available. **X (reframe)**: a Claude Code cloud session has no built-in access to claude.ai chat memory unless a memory store or export is attached. The honest action: inspect what exists (the sample repo, its `docs/owner/` persona file, `KICKOFF_PROMPT.md`, any attached memory), state what could not be read, and ask for an export via NEEDS_YOU.
23. **R/X** — *"and all our chats"* — Same limitation. Prior chats are not readable from here. The sample repo is the durable record of those chats (kickoff prompts, decisions, owner brief).
24. **R/X** — *"and consider everything I have ever asked you to build on Claude or any question I have ever asked you can be successfully processed to completion"* — The brain must handle the full historical range of his requests, including plain questions, not only builds. **X (reframe)**: "everything ever" cannot be enumerated without the history. Honest form: build a request corpus from what is recoverable, classify it into types and sizes, and use it as a routing test set; let him add examples. **I**: "any question" confirms that small requests are in scope, which makes size routing a requirement, not an optimisation.
25. **R** — *"successfully processed to completion"* — Completion is a requirement in itself: no half-finished work, a definition of done per request, and resumability across sessions.

## A.5 Efficiency and quality

26. **R (flagged by him as the top priority)** — *"Also VERY IMPORTANT, you MUST MAKE THIS THE MOST EFFICIENT CLAUDE TOOL EVER"* — Capitals mark this as the highest-weight clause in the message.
27. **X (reframe)** — same words — "Most efficient ever" is a superlative with no possible proof. Honest form: define a baseline (the same tasks run without the brain, and the sample repo's measured overhead), measure tokens, wall time and quality per task, and commit to beating the baseline by a stated margin.
28. **R** — *"it should be much more efficient in tokens"* — Token efficiency is the named metric. Requires measurement.
29. **R/A** — *"through plugins"* — He expects Claude Code plugins (or possibly MCP servers, skills) to be part of the solution. **A**: he may mean plugins loosely. Read: evaluate packaging brain capabilities as on-demand skills/plugins so they cost nothing until used. **[verify]** whether plugins install cleanly in cloud sessions.
30. **R/A** — *"and algorithms"* — Deterministic code in place of model calls where possible: scripts for detection, validation, routing rules, retrieval, cost metering.
31. **X (impossible)** — *"and quantum logic"* — There is no quantum computing available to a Claude Code session and no token-saving technique by that name. Do not fake it. Offer the nearest real ideas: evaluate several candidate plans cheaply before committing to one, prune early, and use probabilistic routing with measured outcomes. Say plainly that "quantum" is not literal.
32. **R** — *"and many other thing you must research to see how you can make this super efficient token wise"* — Open-ended research mandate on efficiency: prompt caching, context editing/compaction, progressive disclosure, subagent context isolation, model tiering, retrieval instead of loading, output brevity, batch processing.
33. **R** — *"and super fast"* — Latency matters too: session start time, time to first useful action, parallelism where it pays. Tension with token efficiency (parallel fan-out is fast but expensive).
34. **R** — *"while delivering the absolutely highest quality work"* — Quality must not be traded for efficiency. Implies verification gates stay; what goes is ceremony.
35. **R** — *"with absolute attention to detail"* — Requirements ledgers, checklists, and verification against the original words of the request.
36. **R** — *"(focus a lot on accuracy, creativity and extreme attention to detail)"* — Three named quality axes. Accuracy implies citation and fact-checking; creativity implies deliberate divergent steps for design and writing work; detail is repeated a second time, so it is weighted.
37. **Tension to surface** — items 5, 17, 26, 34 together — "mega complex", "super long", "most efficient", "highest quality" pull in different directions. The resolution to propose: complexity and length live in files that load only when needed; the default path is lean.

## A.6 Execution instructions

38. **R** — *"Create now the super long and super detailed plan"* — Repeated; plan comes first and now.
39. **R** — *"considering also all our previous builds in Claude"* — Third mention of history (with 22–24). Other builds exist beyond the travel journal. **A**: which ones is unknown from here; the sample notes a GitHub project "pathreview" marked "unrelated; do not touch it" [sample, CLAUDE.md §4].
40. **R** — *"and then start building until completion"* — After the plan, build without waiting for approval. Matches the sample's "decide and record, don't ask" culture.
41. **A** — *"until completion"* — Completion of what is not defined. Must be defined in the plan as explicit acceptance tests (B5.3), or the build cannot end.
42. **C** — *"once you have a full plan based on extremely extensive research"* — Ordering constraint: research, then plan, then build. No building before the plan exists.
43. **R** — *"Make sure you analyze this prompt by 10 independent agents"* — Process requirement, literal count of 10, and independent (no shared drafts).
44. **R** — *"and extract everything I said in full detail"* — A requirements ledger that traces every clause. This Part A is that.
45. **R/X** — *"and you can execute to perfection"* — **X (reframe)**: perfection is not attainable; the honest form is every ledger item marked done, deferred with a reason, or reframed with his agreement.
46. **R** — *"by planning perfectly and researching and analyzing heavily everything"* — Heavy up-front analysis is authorised for this build. **I**: this authorisation is for building the brain; it must not become the brain's default behaviour for every later request (conflict with item 26).

## A.7 Implied expectations not stated in the message

47. **I** — Owner works by clicking and reading, never shell commands (context fact; sample CLAUDE.md §4 and §10). Every owner step must be a file to read, a sentence to type, or a button.
48. **I** — The sample must not be modified (message 1: *"we will not modify or touch this repo at all in this chat, just read it"*).
49. **I** — Claude Max subscription (context fact): cost is experienced as usage-limit windows, not a bill. Efficiency should be reported as share of window and tokens, not only dollars.
50. **I** — The Travel Journal itself is a candidate first adopter of the new contract (an existing two-repo project not built with the brain). He did not ask for migration; do not do it uninvited, but design adoption so it is possible.
51. **I** — Privacy: the brain will accumulate knowledge about him and all his projects. It must be a private repo, and project-confidential facts must not flow into it unredacted.
52. **I** — He expects autonomy with a record: decisions assumed and listed so he can overturn them (sample pattern).

## A.8 Ambiguities to put to the owner (non-blocking; proceed on defaults)

| # | Question | Default to proceed with |
|---|---|---|
| Q1 | May the initial build and emergency repairs edit the brain directly? | Yes; recorded as bootstrap exception |
| Q2 | Who merges learning changes into the brain's `main`: automatic when checks pass, or his click? | Automatic for inbox appends; his click for promoted rule changes |
| Q3 | Should the Travel Journal be adopted onto the new contract? | No, until he asks |
| Q4 | May knowledge learned in one project be reused in another? | Yes for method; no for project content |
| Q5 | Can he export claude.ai memory/chats for the request corpus? | Proceed with what the sample repo records |
| Q6 | Is "plugins" literal (Claude Code plugins) or loose? | Evaluate plugins; use skills as the baseline |
| Q7 | What does "completion" of the brain mean? | The acceptance suite in B5.3 passes and one real project has run through it |

---

# PART B — Architecture, universality, red team

## B1. The brain/project contract

### B1.1 Principle

The brain is a method and a memory. The project is state and output. The contract is the small set of files in the project that the brain reads and writes, plus the version number that says which shape those files have. Everything else in either repo is free to change.

Two rules follow [inference]:

- **The brain never contains a project name.** A CI grep enforces it.
- **A project never contains a copy of brain content.** It contains a pointer and a version.

### B1.2 What the project carries: `.brain/` plus two owner files

```
<project>/
  CLAUDE.md                 stub, at most 2 KB: "this project uses Claude-Brain contract vN; read ../Claude-Brain/CLAUDE.md;
                            if the brain is absent, follow .brain/STATE.md and tell the owner"
  NEEDS_YOU.md              owner-facing: numbered items, clickable steps, RESOLVED: lines
  STATUS.md                 owner-facing: what is done, what is next, cost this session, what was learned (at most 40 lines)
  .brain/
    project.json            the manifest (below)
    STATE.md                machine checkpoint: stage, current item, next three, half-finished work and where it lives
    REQUIREMENTS.md         requirements ledger: every owner clause, id, status, evidence link
    PLAN.md                 current plan (may link to longer documents in docs/)
    DECISIONS.md            one line per assumed decision; OVERTURNED: lines from the owner
    lessons/                project-local lessons (structured records, same schema as the brain inbox)
    memory/                 project facts worth keeping across sessions (glossary, voice, domain notes)
    ext/                    project-specific extensions: skills/, agents/, tools/, playbook-overrides/
    log/                    per-session records (tier, tokens, agents spawned, outcome), one small JSON per session
```

Why two owner files at the root: he reads on GitHub or in the cloud UI, and files at the top level are found without instructions [inference].

**Manifest format: JSON.** Python's `json` and Node's `JSON` read and write it with no installs; YAML needs PyYAML or equivalent; TOML has a standard reader in Python 3.11+ but no writer. A manifest that needs `pip install` before the brain can detect a project reintroduces the session-start cost seen in the sample's hook (900 s timeout, pnpm plus a Python venv) [sample]. Comments are replaced by a `"_help"` key per section.

```json
{
  "contract": 1,
  "project": { "id": "example-app", "title": "Example App", "created": "2026-11-10" },
  "type": ["web-app"],
  "tier_default": "project",
  "stage": "build",
  "commands": {
    "setup": "pnpm install --frozen-lockfile",
    "check_fast": "pnpm lint && pnpm typecheck",
    "check_full": "pnpm test && pnpm build",
    "run": "pnpm dev"
  },
  "gates": [
    { "id": "tests-green", "kind": "command", "command": "pnpm test" },
    { "id": "owner-review", "kind": "owner", "file": "NEEDS_YOU.md" }
  ],
  "paths": { "deliverables": ["apps/", "packages/"], "evidence": "docs/evidence/", "never_touch": [] },
  "release": { "rule": "none" },
  "models": { "lead": "inherit", "bulk": "inherit" },
  "privacy": { "share_lessons_with_brain": "method-only" },
  "brain": { "last_seen_commit": "", "min_contract": 1 }
}
```

For non-code projects `commands` holds whatever is checkable (a word count script, a link checker, a spreadsheet recalculation), or is empty and gates are of kind `checklist` or `owner`.

### B1.3 What the brain carries

Universal method (stages, tiers, routing rules), playbooks per project type, skills, about six agent archetypes, deterministic scripts, global memory (owner profile, cross-project lessons, model facts with dates), evals (routing test set, contract fixtures), the contract schema and migrations, and the learning pipeline. Full tree in B5.1.

### B1.4 Detection

One deterministic script, `scripts/brain_detect.py` (Python standard library only), run by the brain's SessionStart hook and also callable by hand. It:

1. Finds the brain root from its own file path, never from `$CLAUDE_PROJECT_DIR`. Which repo that variable points to in a two-repo session is not something to depend on **[verify]**.
2. Lists sibling directories of the brain root.
3. Classifies each sibling: `managed` (has `.brain/project.json`), `empty` (no files besides README/licence/.git), `unmanaged` (has content, no manifest).
4. Prints one compact block, at most about 15 lines, for example: mode, project path, contract version, stage, current item, open NEEDS_YOU count, migration needed yes/no.

That block is the entire always-on cost of orientation. The sample spends a "5 minutes" orientation step reading six documents at every start [sample, START_HERE.md]; the detect block replaces most of it and the rest is read only at the project tier.

| Detection result | Mode | Behaviour |
|---|---|---|
| One `managed` sibling | **work** | Route the request by tier (B2.3); resume from `STATE.md` only if the request is "start running/continue" |
| One `empty` sibling | **bootstrap** | Offer intake; on a one-sentence brief, install the contract files and start |
| One `unmanaged` sibling | **adopt** | Read-only survey first; write `.brain/` only; never restructure existing code (B1.7) |
| No sibling | **brain-only** | Answer questions, run brain maintenance and consolidation, or tell the owner how to attach a project |
| Several siblings | **choose** | Use the one named in the request; else the one with the most recent `STATE.md`; else ask once |
| Contract older than brain | **migrate** | Run the migration chain after a backup commit, then work |
| Contract newer than brain | **stale brain** | Do not write `.brain/`; tell the owner the brain's `main` is behind |

### B1.5 Versioning so old projects work "forever"

- `contract` is an integer. The schema for each version is a frozen file `contract/v1.schema.json`, `v2.schema.json`, never edited after release.
- Changes are **additive by default**: new optional keys with defaults; readers ignore unknown keys. A new integer is needed only for a rename or removal.
- Each bump ships `contract/migrations/NNN_to_MMM.py`: idempotent, standard library only, makes a commit before and after, writes a line to `.brain/DECISIONS.md`.
- The brain supports every older version through the chain. No version is ever dropped; the cost is one small script per bump.
- **Frozen fixtures**: `evals/fixtures/project-v1/` and so on are snapshots of real project `.brain/` folders at each version. CI runs detect, migrate and validate against every fixture on every brain change. This is the mechanical meaning of "forever".
- The project records `brain.last_seen_commit`. If a session behaves worse after a brain change, the previous brain commit is known and can be checked out (rollback path).
- A project may pin `min_contract` but may not pin a brain commit, to avoid a fleet of projects on different brains [inference].

### B1.6 Who may write to the brain

The owner's rule is "only modified by its own machine learning systems". Proposed mechanism:

1. **Path guard (PreToolUse hook on Edit/Write, and a CI check on pull requests).** In work mode, writes inside the brain are blocked except under `learning/inbox/`. The sample already has the pattern in `protect-paths.sh` [sample].
2. **Capture.** At session end (Stop hook reminder plus a script), the session appends zero or more structured records to `learning/inbox/YYYY-MM-DD-<session>.jsonl`: `{type, tier, project_type, observation, evidence, cost, proposed_change, source: "own-experience|owner-said|external"}`. Maximum field lengths. No free-form instructions.
3. **Consolidation.** A separate session in brain-only mode (owner types "Consolidate", or a scheduled routine) reads the inbox, clusters records, and proposes edits to playbooks/memory. A proposal is promoted only when (a) it is supported by at least two independent records or one owner statement, (b) the routing and contract evals still pass, and (c) the always-loaded byte budget still holds.
4. **Merge.** Inbox appends auto-merge to the brain's `main` when the path-restriction check passes. Promoted changes arrive as one pull request with a plain-language summary; default is one owner click, switchable to automatic (Q2).
5. **Bootstrap exception.** The initial build and repairs of a broken brain may edit anything; they are labelled as such in the commit message.

Records with `source: external` (text from web pages, repositories, tool output) can never be promoted into instruction files. This is the defence against injected instructions entering permanent memory (B4 item 6).

### B1.7 Single repo, new repo, existing repo

- **Project without brain.** The stub `CLAUDE.md` says so in three lines; the session works from `.brain/STATE.md`, `PLAN.md` and `commands`, skips learning capture into the brain (writes to `.brain/lessons/` instead, to be collected later), and tells the owner once. The project stays resumable because all state is on its side.
- **Brain without project.** Brain-only mode: questions, consolidation, evals, or "New project" instructions.
- **Empty project (bootstrap).** One script, `scripts/brain_init.py --type <t>`, copies the template from `contract/template/` and fills the manifest. Intake asks at most five questions in one message; unanswered ones take defaults recorded in `DECISIONS.md`.
- **Existing codebase (adoption).** Three steps, each reversible: (1) survey read-only and infer type, stack and commands from manifests and CI files; (2) write only `.brain/`, `NEEDS_YOU.md`, `STATUS.md`, and prepend a pointer block to an existing `CLAUDE.md` rather than replacing it; (3) run `check_fast` to confirm the inferred commands work. Existing docs are linked from `PLAN.md`, not moved. The existing repo's own conventions outrank brain defaults.
- **Company-repo layouts like the sample (three repos in effect).** If the owner later adopts the Travel Journal, the contract goes into the product repo; the old company repo becomes an archive that `PLAN.md` links to. Not in scope unless asked (Q3).

### B1.8 How the new split differs from the sample, and what moves to the project side

The sample's ADR-000 put all "AI building" material in a company repo and only shippable code in the product repo [sample]. That made the company repo both the method and the project's management state. It worked for one project. With many projects it fails: a second project would either share Travel-Journal state or need a second company repo.

| In the sample company repo | New home | Reason |
|---|---|---|
| `CLAUDE.md` §1 prime directives, §3 resume loop, §10 communication rules | Brain (generalised, shortened) | Universal method |
| `CLAUDE.md` §0, §2, §4–6, §9, §11 (repos, done definition, defaults, stand-ins, phases, stack, release rule) | Project (`.brain/project.json`, `PLAN.md`, `DECISIONS.md`) | Travel-Journal specific |
| `docs/MASTER_PLAN.md` (116 KB), `docs/phases`, `docs/plans`, `docs/gates` | Project | Project plan |
| `docs/status/PROGRESS.md`, daily digests, `docs/handover/` | Project (`.brain/STATE.md`, `.brain/log/`) | Project state |
| `docs/NEEDS_YOU.md`, `docs/DECISIONS.md`, `docs/adr/` | Project | Project decisions |
| `docs/design/` (390 MB), `docs/l10n/` (33 MB) | Project evidence folder, or outside git | Evidence; would bloat every brain clone |
| `journal/` voice guides, glossary | Project `.brain/memory/` | Project domain knowledge |
| `docs/owner/` persona | Split: stable owner preferences to brain `memory/owner.md`; trip-specific persona stays in project | Privacy and reuse |
| `library/` pipeline code | Brain, as an optional skill (not always on) | Reusable tool |
| `library/index`, cards D1–D7/E1–E7, snapshots of pinned stack docs | Project (`.brain/ext/`), with any truly general cards promoted through the learning pipeline | Content is project specific |
| 31 agent specs | About 6 archetypes in the brain; project-specific roles (media pipeline, motion designer) in `.brain/ext/agents/` | Role sprawl |
| Board of 7, 500-role catalogue, HR engine, payroll | Not carried over as machinery; keep one idea from each: a second-opinion review step and a cost log | Orchestration theatre [inference] |
| `/reproduce-effect` skill, design lab | Brain as an on-demand design playbook; lab outputs in project | Method general, results specific |
| Hooks (`protect-paths`, `checkpoint-reminder`, `session-start`) | Brain: path guard, checkpoint reminder, detect. Project: dependency setup only | Split by purpose |
| Lessons in `START_HERE.md` (usage limits, worktrees, 4 cores) | Brain `memory/lessons/` as seeded universal lessons | Already universal |

---

## B2. Universality

### B2.1 One lifecycle, eight stages

**intake → requirements ledger → research → plan → build → verify → deliver → learn**

Every stage has an exit artefact and a skip rule. Lower tiers collapse stages; they do not run them faster.

| Stage | Exit artefact | Skippable when |
|---|---|---|
| Intake | Request classified: type, tier, definition of done | Never (it is one sentence at tier 0) |
| Requirements ledger | Numbered clauses with source quotes | Tier 0–1 |
| Research | Findings with sources and confidence | Answer already in memory, repo or pinned docs |
| Plan | Ordered work items with gates | Tier 0–1 |
| Build | The deliverable | Never |
| Verify | Evidence against each ledger item | Never; depth scales with tier |
| Deliver | Deliverable in the owner's format plus what to read or click | Never |
| Learn | Inbox record, or nothing | When nothing surprising happened |

### B2.2 Project types and what varies

Five playbook families cover the fifteen types. The variation is confined to four slots: what "build" produces, how "verify" is done, what "deliver" looks like, and which archetype leads.

| Family (playbook) | Types covered | Build produces | Verify by | Deliver as |
|---|---|---|---|---|
| **Software** | Web/PWA app, mobile app, backend/API, CLI/tool, design system | Code, tests | Commands in manifest: lint, types, tests, build, e2e; visual review for UI | Branch, PR or preview URL |
| **Data and experiments** | Data pipeline/analysis, ML experiment, spreadsheets | Scripts, notebooks, tables, charts | Re-run from clean state, sanity checks on totals, held-out metrics, seed recorded | Report file plus reproducible script |
| **Knowledge and writing** | Research report, business plan/strategy, document/book, decks | Structured prose, slides | Claim-by-claim source check, consistency pass, independent reader review | Doc, PDF, deck |
| **Language** | Translation, localisation | Target-language text, glossary | Blind back-translation, glossary and length checks (the sample already did this for Spanish [sample]) | Files in project format |
| **Operations** | Automation, scheduled agents, personal knowledge tasks | Routines, hooks, small scripts | Dry run, idempotency check, failure notification test | Enabled routine plus a one-page runbook |
| (no playbook) | Quick questions | An answer | Self-check, citation if factual | Chat reply |

Rule for an unlisted type: use the nearest family, record the gap as an inbox record, and let consolidation decide whether a new playbook is earned. A sixth playbook needs evidence of at least two projects that fitted badly [inference].

Per-type differences worth encoding in playbooks, briefly:

- **Mobile app**: device testing cannot run in a cloud container; verification is emulator screenshots or store-build checks, with an owner gate.
- **ML experiment**: budget for compute and data is a NEEDS_YOU item; the definition of done is a metric threshold fixed before the run.
- **Book-length writing**: state is an outline plus per-chapter status; context must be loaded per chapter, never the whole manuscript.
- **Business strategy**: the research stage dominates; the verify stage is a source audit and a counter-argument pass.
- **Scheduled agents**: each run starts with no memory, so the routine prompt must be self-contained and the project `STATE.md` is the only continuity.

### B2.3 Request-size routing

This is where most waste is prevented. Anthropic's own guidance is to find "the simplest solution possible, and only increasing complexity when needed", and it notes that "agentic systems often trade latency and cost for better task performance" [source: https://www.anthropic.com/engineering/building-effective-agents].

| Tier | Examples | Reads | Agents | Writes | Target overhead |
|---|---|---|---|---|---|
| **0 Answer** | "What does X mean?", "Which is better, A or B?" | Nothing beyond what is loaded | 0 | Nothing | Zero tool calls of process |
| **1 Small task** | Fix a typo, add a field, rewrite a paragraph, one chart | The files touched | 0 (1 for an isolated search) | The change, one line in `STATE.md` if a project is active | Under about 5% of task tokens |
| **2 Project** | A new app, a report, a translation of a site | `STATE.md`, ledger, plan, relevant playbook | 1 lead, up to 4 concurrent helpers, each justified | Full contract files | Under about 15% |
| **3 Programme** | Multi-week build with phases and parallel streams | As tier 2, per phase | Teams, only for 3 or more independent streams, with a written plan first (the sample's own rule [sample, CLAUDE.md §1.5]) | As tier 2 plus phase gates | Under about 25%, reported |

Percentages are design targets, not measurements [inference]. They become real only when the session log records them (B3.4).

Routing rules, deterministic where possible:

- The default is the **lowest** tier that can meet the definition of done. Escalation is allowed mid-task and is logged with a reason; silent escalation is a defect.
- Tier 0 and 1 never read the project plan, never spawn reviewers, never write digests.
- "Start running", "continue", "resume" mean tier 2 or 3 as recorded in the manifest.
- Explicit owner phrases override: "quick:" forces tier 0–1; "go deep:" permits tier 2 on a question.
- A routing test set (`evals/routing.jsonl`, about 60 labelled requests drawn from the owner's history and the type table) checks the written rules. Keyword pre-classification is scripted; the model makes the final call.

---

## B3. Owner experience

### B3.1 Trigger phrases

| He types | Meaning |
|---|---|
| **New project: \<one sentence\>** | Bootstrap in the attached empty repo; at most five questions in one message, then start |
| **Start running** / continue / resume | Resume from `STATE.md` without confirmation (kept from the sample) |
| **Adopt this repo** | Adoption survey, then contract files only |
| **Quick: \<question\>** | Tier 0–1, no machinery |
| **Go deep: \<question\>** | Research-grade answer with sources |
| **Status** | Regenerate and show `STATUS.md` |
| **What did you learn?** | Summary of new inbox records and promoted changes since last asked |
| **Consolidate** | Brain-only: run the learning promotion and open the pull request |
| **Stop after this** | Finish the current item, checkpoint, summarise |

None is required. Plain language works; the phrases only remove ambiguity.

### B3.2 What he reads

Three files, all in the project root or one click away: `STATUS.md` (what happened, what is next, cost, what was learned), `NEEDS_YOU.md` (things only he can do, as numbered click steps), `.brain/DECISIONS.md` (assumptions he can overturn). In the brain, one file: `CHANGELOG.md`, written in plain language by the consolidation step.

### B3.3 How he answers questions

Either reply in chat, which is easiest, and the session records the answer in the right file; or edit `NEEDS_YOU.md` on GitHub and add `RESOLVED:` to the item, as in the sample. Questions are batched: one message, numbered, each with the default that will be used if he does not answer. Work continues on everything not blocked (sample directive "Never block").

### B3.4 How he sees cost and learning

- Every session appends a small record to `.brain/log/`: tier, models used, agents spawned, approximate tokens in and out, wall time, outcome.
- `STATUS.md` shows a three-line summary: this session, project to date, share spent on process versus deliverable.
- On a Max subscription there is no per-session invoice, so the meaningful unit is tokens and the number of agents, with a warning when a session is on course to exhaust a usage window [inference]. Exact token counts depend on what the hooks can read from the transcript **[verify]**; if unavailable, report agent count and wall time and label the token figure as an estimate.
- Learning is shown as a short list: "3 observations recorded; 1 rule changed: \<plain sentence\>".

### B3.5 A new project in one sentence

Create an empty repository on GitHub (the one unavoidable click path, documented with screenshots in the brain's `OWNER_GUIDE.md`), start a cloud session with it and Claude-Brain attached, and type: *"New project: a site that tracks my bird sightings by trip."* Everything else is asked or assumed.

---

## B4. Red team: twenty likely failures and the counter-measure for each

Evidence base: MAST's taxonomy of 14 failure modes in three categories (specification 41.8%, inter-agent misalignment 36.9%, verification 21.3%) [source: https://arxiv.org/html/2503.13657v2]; the authors "conjecture that improvements in the base model capabilities will be insufficient" and attribute many failures to "organizational design and agent coordination" [same source]. Anthropic's three principles: simplicity, transparency, careful tool interface [source: https://www.anthropic.com/engineering/building-effective-agents]. Plus what the sample shows.

| # | Failure | Why it is likely here | Counter-measure |
|---|---|---|---|
| 1 | **Over-engineering** | The request says "mega complex orchestrator"; the sample grew a board, HR catalogue and payroll [sample] | Every component must name the measured problem it solves. Start with the lean core (B4.1); add a component only after two inbox records show the gap |
| 2 | **Always-loaded instructions too long** | Two `CLAUDE.md` files plus two sets of agent and skill descriptions load every session; the sample handbook alone is 16.5 KB [sample] | CI byte budget: brain `CLAUDE.md` ≤ 6 KB, project stub ≤ 2 KB, each skill/agent description ≤ 300 characters. Everything else is loaded on demand |
| 3 | **Process on trivial requests** | A handbook that says "read this fully every session, then five more files" [sample] applies to a typo fix too | Tier routing (B2.3) as the first rule in `CLAUDE.md`; routing eval in CI; process share reported in `STATUS.md` |
| 4 | **Role sprawl** | 31 specs in the sample; MAST FM-1.2 and FM-2.x arise from role and hand-off design | Six archetypes (lead, researcher, builder, reviewer, verifier, writer). A new archetype requires consolidation evidence. Project-specific roles live in the project |
| 5 | **Self-modification corrupts the brain** | A repo that edits its own instructions can degrade them, and every later session inherits the damage | Path guard; promotion only via pull request with evals; `last_seen_commit` for rollback; fixtures detect contract breakage; `CHANGELOG.md` in plain language |
| 6 | **Learning loop stores junk or injected instructions** | Sessions read web pages and third-party repos; a planted sentence could become a permanent rule | Structured records with length limits; `source: external` never promotable to instructions; two-record rule; consolidation treats inbox content as data |
| 7 | **Learning loop never runs** | One lesson file in the sample despite a written rule [sample] | Deterministic trigger at session end; "nothing learned" is a valid record; consolidation reports inbox size so silence is visible |
| 8 | **Memory grows without bound** | "Learn from everything" forever | Size caps per memory file; consolidation must merge or retire before adding; retired items move to an archive that is never auto-loaded |
| 9 | **Two-repo branch and merge confusion** | In the sample the company `main` held only the initial commit and new chats needed a manual merge step [sample, START_HERE.md] | One rule: brain work reaches `main` only by pull request; inbox appends auto-merge; detect warns when the checked-out brain is behind `origin/main`; project release rule lives in its manifest |
| 10 | **Ephemeral cloud state lost** | Containers are replaced; the sample notes "a session can end at any moment" [sample] | Checkpoint after every work item; nothing important only in `/tmp`; half-finished work saved as a branch push, not as patches in docs (the sample's handover patches were a workaround [sample]) |
| 11 | **Usage-limit exhaustion from fan-out** | Happened twice with ten parallel Opus agents [sample]; multi-agent runs cost about 15x a chat [source: https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent] | Default cap of 4 concurrent helpers; cheaper tier for search and mechanical work; each spawn states its expected value; resume agents after a reset rather than recreating them |
| 12 | **Hooks that break sessions** | A failing or slow hook blocks every tool call; the sample runs a gate on every Agent call and a 900 s start hook [sample] | Hooks are few (three), standard-library only, fail open with a visible warning, time out in seconds, and are unit-tested in CI with recorded inputs |
| 13 | **Slow session start from installs** | pnpm plus a Python venv plus an index rebuild at start [sample] | The brain installs nothing at start. Project setup is declared in the manifest and belongs in the cloud environment's setup script, run only when a fresh container is built |
| 14 | **Stale pinned model facts** | The plan is researched for Fable 5.2 and Opus 5.5; both will be superseded | Model facts in one dated file with a `verified_on` field; routing refers to roles ("lead", "bulk"), not model ids; detect warns when the file is older than 90 days |
| 15 | **Brittle scripts** | Shell scripts that assume paths, `jq`, or a working directory | Python standard library, paths derived from the script's own location, every script has a `--self-test`, all run in CI on a clean container |
| 16 | **Secrets leakage** | Lessons and logs copy command output; the brain spans all projects | Secret-pattern scan on every inbox record and in CI; logs store counts, not content; credentials only via the environment's secret mechanism, never in manifests |
| 17 | **The brain becomes project-specific** | The most recent project dominates what is learned | CI grep for project ids in brain files; records carry `project_type`, not project name; a rule is promoted to universal only with evidence from two project types, otherwise it goes to a type playbook |
| 18 | **Nothing is measured** | "Most efficient ever" with no baseline | Session log from day one; a fixed benchmark of about 10 tasks run with and without the brain at each consolidation; results in `evals/results/` |
| 19 | **Verification theatre** | MAST: 21.3% of failures are verification failures, including incorrect verification [source: https://arxiv.org/html/2503.13657v2]; the sample pushed a red build to `main` twice [sample, lesson file] | Gates are commands with exit codes where possible; push only on a recorded zero exit (the sample's own lesson); the reviewer is never the author; verify against ledger quotes, not against the plan |
| 20 | **Contract drift between brain and old projects** | A brain refactor renames a file that older projects rely on | Frozen schemas, migration chain, fixture projects in CI (B1.5) |

Two further risks worth naming: **cross-project privacy** (a client project's facts surfacing in another project) is handled by `privacy.share_lessons_with_brain` in the manifest and method-only records; and **the owner cannot repair a broken brain himself**, so the brain needs a documented "known good" tag and a one-sentence recovery phrase ("Repair the brain from the last good tag").

### B4.1 The leanest design that still satisfies the owner

What he asked for, reduced to obligations: (1) two repos that always work together, (2) universal scope, (3) a brain that learns and is not hand-edited, (4) measurable efficiency, (5) high quality with attention to detail, (6) no shell commands for him.

The smallest design that meets all six [inference]:

- One `CLAUDE.md` of about 100 lines: tier routing, the eight stages, the write rules, where things are.
- Five playbooks, loaded on demand.
- Six agent archetypes.
- Five scripts: detect, init, migrate, validate, learn-capture.
- Three hooks: session-start detect, path guard, end-of-session checkpoint and capture reminder.
- One contract (the `.brain/` folder) with a version number.
- One learning pipeline: inbox, consolidate, pull request.
- One measurement: the session log and a small benchmark.

"Mega complex" is satisfied by what the system can scale up to at tier 3, not by what runs by default. This should be said to him directly, with the numbers: a lean default is what makes the heavy mode affordable.

### B4.2 Explicit non-goals

1. No model training or fine-tuning; "learning" means curated files and evals.
2. No quantum computing or anything labelled as such.
3. No always-on vector database or RAG service in the brain. Retrieval starts as file search over small, well-named files; an index is added per project only when its corpus is too large to search directly.
4. No virtual company: no board, HR catalogue or payroll simulation.
5. No custom orchestration runtime; use Claude Code's own subagents, skills, hooks and routines.
6. No project content, deliverables or evidence in the brain.
7. No automatic migration of existing projects (including the Travel Journal) without his request.
8. No support for other AI vendors.
9. No dashboard or web app for the brain itself; files are the interface.
10. No promise of "perfect" or "forever"; the promise is a versioned contract with tests.

---

## B5. Trees and acceptance tests

### B5.1 Claude-Brain repository

```
Claude-Brain/
  CLAUDE.md                     always loaded; ≤ 6 KB: routing tiers, stages, write rules, pointers
  README.md                     what this is, in plain language, for the owner
  OWNER_GUIDE.md                trigger phrases, the three files to read, how to start a project (click steps)
  CHANGELOG.md                  plain-language record of every promoted change
  VERSION                       brain version and current contract number
  .claude/
    settings.json               three hooks only
    hooks/                      session_start.py, guard_paths.py, session_end.py (stdlib, fail open)
    agents/                     lead, researcher, builder, reviewer, verifier, writer
    skills/                     on-demand entry points: new-project, adopt, status, consolidate, plus playbook loaders
  method/
    lifecycle.md                the eight stages, exit artefacts, skip rules
    routing.md                  tiers, escalation rules, fan-out caps
    quality.md                  accuracy, creativity and detail checks per stage
    efficiency.md               context, caching, model-tier and delegation rules
  playbooks/
    software.md  data.md  knowledge.md  language.md  operations.md
    variants/                   short per-type notes (mobile, ml-experiment, book, deck, ...)
  contract/
    v1.schema.json              frozen manifest schema
    template/                   files installed into a project (B5.2)
    migrations/                 NNN_to_MMM.py, idempotent
    COMPATIBILITY.md            which contract versions exist and what changed
  scripts/
    brain_detect.py  brain_init.py  brain_migrate.py  brain_validate.py  learn_capture.py  cost_log.py
  memory/
    owner.md                    stable owner preferences (size-capped)
    lessons/                    promoted cross-project lessons, one topic per file (size-capped)
    models.json                 model facts with verified_on dates; roles mapped to model ids
    archive/                    retired items; never auto-loaded
  learning/
    inbox/                      append-only JSONL from sessions (the only path writable in work mode)
    record.schema.json          shape and limits of an inbox record
    PROMOTION_RULES.md          evidence thresholds and what can never be promoted
  evals/
    routing.jsonl               labelled requests for tier and type routing
    fixtures/                   frozen project snapshots per contract version; empty, unmanaged and multi-sibling cases
    benchmark/                  about 10 fixed tasks for with/without-brain comparison
    results/                    dated outcomes
  tests/                        unit tests for scripts and hooks
  .github/workflows/ci.yml      runs the acceptance suite; enforces budgets and path rules on pull requests
  docs/
    PLAN.md                     the long build plan (never auto-loaded)
    adr/                        architecture decisions for the brain itself
```

### B5.2 What the brain installs into a project

```
<project>/
  CLAUDE.md                     stub ≤ 2 KB (or a pointer block prepended to an existing file)
  NEEDS_YOU.md                  owner actions
  STATUS.md                     owner summary
  .brain/
    project.json                manifest (contract version, type, commands, gates, paths, privacy)
    STATE.md                    checkpoint
    REQUIREMENTS.md             ledger
    PLAN.md                     plan
    DECISIONS.md                assumed decisions
    lessons/                    project-local lessons
    memory/                     project knowledge
    ext/                        skills/ agents/ tools/ playbook-overrides/  (project-specific complements)
    log/                        per-session records
  .claude/                      only if the project needs its own hooks, skills or agents; created on demand
```

Precedence: project `ext/` adds to or overrides brain playbooks for that project only; brain write rules and the contract cannot be overridden.

### B5.3 Minimal acceptance suite: "the brain works with a project"

All tests except the last group run in CI with no model calls.

**Contract and scripts**

| ID | Test | Pass condition |
|---|---|---|
| T01 | Detect: brain alone | Mode `brain-only`, exit 0 |
| T02 | Detect: brain plus empty sibling | Mode `bootstrap` |
| T03 | Detect: brain plus managed fixture | Mode `work`, correct stage and item |
| T04 | Detect: brain plus unmanaged fixture | Mode `adopt`; no file written |
| T05 | Detect: two managed siblings | Mode `choose`; deterministic pick rule applied |
| T06 | Detect output size | At most 15 lines and 1.5 KB |
| T07 | Init into empty directory, for each of the five families | All contract files exist; manifest validates against the current schema |
| T08 | Init twice | Second run changes nothing (idempotent) |
| T09 | Adopt on a fixture with existing `CLAUDE.md` and source files | Only `.brain/`, `NEEDS_YOU.md`, `STATUS.md` added; existing `CLAUDE.md` gains a pointer block and loses nothing; no other file changed |
| T10 | Migrate every frozen fixture to current | Validates; second run is a no-op; unknown keys preserved |
| T11 | Project newer than brain | Detect reports `stale brain`; no writes |
| T12 | Project stub without brain present | Stub contains the degraded-mode instructions and the fixture has a valid `STATE.md` |

**Guards and budgets**

| ID | Test | Pass condition |
|---|---|---|
| T13 | Path guard, recorded hook inputs | Edit to `playbooks/x.md` in work mode is blocked; append to `learning/inbox/` is allowed |
| T14 | Hooks fail open | With malformed input or a missing interpreter feature, each hook exits 0 with a warning within its timeout |
| T15 | Always-loaded budget | `CLAUDE.md` ≤ 6 KB; template stub ≤ 2 KB; every agent and skill description ≤ 300 characters |
| T16 | No project names in brain | Grep for known project ids outside `learning/inbox/` finds nothing |
| T17 | Secret scan | No secret patterns in the repo or in inbox records |
| T18 | Inbox record schema | Every record validates; over-length or `external`-sourced instruction records are rejected by the promotion script |
| T19 | Pull-request path rule | A change limited to `learning/inbox/` is marked auto-mergeable; any other path is not |
| T20 | No install at start | `session_start.py` makes no network call and completes in under 2 seconds on the fixtures |
| T21 | Scripts self-test | Every script's `--self-test` exits 0 on a clean container with only Python present |
| T22 | Links | No broken relative links in `CLAUDE.md`, `OWNER_GUIDE.md`, playbooks, template |

**Routing (rule layer, no model)**

| ID | Test | Pass condition |
|---|---|---|
| T23 | Keyword pre-classifier on `evals/routing.jsonl` | Trigger phrases map to the labelled tier; no tier 0–1 item is pre-classified as 2–3 |

**Live checks (need a model; run by hand at each consolidation, not in CI)**

| ID | Test | Pass condition |
|---|---|---|
| L1 | Two-repo cloud session, type a tier 0 question | Answer with zero process tool calls |
| L2 | "New project: …" on an empty repo | Contract files created, at most five questions, first work item started |
| L3 | End a session mid-item, start another, type "Start running" | Resumes the same item from `STATE.md` without re-planning |
| L4 | Benchmark of about 10 tasks with and without the brain | Quality not lower; tokens and time recorded in `evals/results/` |
| L5 | Verify loading assumptions | Both repos' `CLAUDE.md`, agents, skills and hooks are active; record which directory `$CLAUDE_PROJECT_DIR` names |

L5 matters most before the build: several design choices above assume both repos' configuration loads. In this analysis session only the working-directory repo's `CLAUDE.md` was visible in my instructions, and the brain repo has no `CLAUDE.md` yet, so this could not be confirmed either way **[verify]**. If only the working-directory repo's configuration loads, the project stub must carry the pointer that pulls the brain in, and the brain's hooks must be installed through the stub's `.claude/settings.json`.

---

## Sources

- MAST failure taxonomy (Cemri et al., NeurIPS 2025): https://arxiv.org/html/2503.13657v2
- Anthropic, "Building effective agents": https://www.anthropic.com/engineering/building-effective-agents
- Secondary summary of Anthropic's multi-agent research system post (4x and 15x token figures): https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent
- Sample repo, read-only: `CLAUDE.md`, `START_HERE.md`, `docs/adr/ADR-000-two-repositories.md`, `docs/status/PROGRESS.md`, `docs/lessons/`, `.claude/settings.json`, `.claude/hooks/`, directory sizes measured with `du` and `wc` on 2026-11-10.

Not verified: the 4x/15x token figures come from a secondary summary, not Anthropic's own page; the tier overhead targets are design targets; hook and configuration loading behaviour across two attached repos is untested.
