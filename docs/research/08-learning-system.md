# 08 — The learning system of the Claude Brain

Analyst 8 of 10. Date 2026-11-10. Lens: how the brain repo "learns".
Claim marking: `[source: URL]` = read today; `[recalled]` = from my training knowledge of the cited paper, not re-read today; `[observed]` = checked in this session's container or the sample repo; `[inference]` = my reasoning.

---

## 0. Three findings that change the design (read these first)

**F1. In a two-repo cloud session, repository hooks, permission rules and `.mcp.json` do not load.** The Claude Code docs say that, in an Anthropic-hosted environment, a session with several repositories "starts above the clones and reads only the `enabledPlugins` and `extraKnownMarketplaces` keys from each repository's `.claude/settings.json`, not permission rules, hooks, `env`, or other keys", and that the plugins those keys declare still do not load. [source: https://code.claude.com/docs/en/settings.md#settings-in-cloud-sessions] The carry-over table lists `.claude/settings.json` hooks and `.mcp.json` as "Yes, in a session with one repository"; `CLAUDE.md`, `.claude/rules/`, `.claude/skills/`, `.claude/agents/`, `.claude/commands/` are plain "Yes". [source: https://code.claude.com/docs/en/cloud-environments.md]

This matches what I see in this session, which has two repos attached [observed]:
- the session root is `/home/user` (transcript at `/root/.claude/projects/-home-user/<session>.jsonl`), above both clones;
- `CLAUDE_PROJECT_DIR` is empty, `CLAUDE_CODE_REMOTE=true`;
- the only hooks configured are the platform's own (`/root/.claude/launcher-settings.json`: a SessionStart and a Stop script); none of the sample repo's five hooks appear;
- no `library` MCP tools are available to me, although the sample repo registers that server in `.mcp.json`;
- the sample repo's `CLAUDE.md` and its two skills (`library`, `reproduce-effect`) did load.

The "Known context" line in OWNER_PROMPT.md ("both repos' ... hooks and .mcp.json are loaded") is therefore wrong for the owner's stated runtime. **Every design that puts capture, guarding or retrieval in repo hooks or a repo MCP server will silently do nothing in the two-repo sessions the owner will always use.** The sample repo's payroll meter, path guard and checkpoint reminder are in exactly that position.

**F2. Claude Code auto-memory does not persist in cloud sessions.** "Auto memory is machine-local... Files are not shared across machines or cloud environments." [source: https://code.claude.com/docs/en/memory] No memory directory exists in this container [observed]. Cloud sessions start from a fresh clone. So **the brain repo's committed files are the only durable memory**, and a learning step that is not committed and merged to the brain's default branch is lost.

**F3. Zero-token capture is still possible without hooks.** The session transcript and each subagent's transcript are on disk in the container, with per-message `usage` (input, cache-write, cache-read, output tokens) and model id [observed: this session's file shows 38 assistant messages, 322,108 cache-write, 5,218,870 cache-read and 203,926 output tokens on `claude-fable-5-2`; subagent files sit under `<session>/subagents/agent-*.jsonl`]. A plain Python script can turn those into a run record and ledger rows with no model call. What changes is the trigger: one Bash call made by the model at checkpoint/stop (a few dozen tokens), not a hook.

Consequences used throughout this report:
- Capture = a script the lead runs by instruction (always-loaded rule in the brain `CLAUDE.md`), plus an optional hook install through the environment setup script (needs a test, see E1).
- Retrieval = skills (native progressive disclosure) and a CLI script, not an MCP server.
- The hard guard = GitHub Actions on the brain repo plus branch protection, not a PreToolUse hook.
- Deep consolidation = a scheduled routine that runs in a **one-repo** session on the brain, where the brain's own hooks and `.mcp.json` do load.

Experiments the lead should run before committing to details:
- **E1** Does a `~/.claude/settings.json` written by the environment setup script get its hooks honoured in a multi-repo cloud session? The docs show a setup script writing `~/.claude/CLAUDE.md` and that file loading as user instructions [source: https://code.claude.com/docs/en/cloud-environments.md]; they do not say the same for user `settings.json`. If yes, the brain can install its Stop/PreToolUse hooks from the setup script (`Claude-Brain/bin/install-hooks.sh`). The setup script lives on the environment, which the owner approves once by clicking.
- **E2** Does `git config core.hooksPath` set by the setup script survive into the session, giving a local pre-commit guard?
- **E3** Does a scheduled routine on the brain alone have push rights and can it open and auto-merge a PR?
- **E4** Do path-scoped `.claude/rules/` in the brain fire when the file being edited is in the *other* repo?

---

## PART A — Extraction of the owner's message 2

Each item quotes the words it comes from. Tags: **R** requirement, **C** constraint, **P** preference, **I** implied expectation, **A** ambiguity, **X** impossible or needs honest reframing.

1. **R** "I essentially used this repo as a brain to create everything in my travel journal in the best possible way" — the sample repo is the reference model; "best possible way" sets the quality bar it reached as the floor.
2. **R** "I want now to create a repo that will act as that" — deliverable is a repository, not a document or a hosted service.
3. **R** "(essentially a mega complex orchestrator)" — the brain orchestrates (plans, routes, delegates, reviews); it is not just a prompt file. **A**: "mega complex" describes capability; it conflicts with item 21 (efficiency). Complexity should live in scripts and on-demand files, not in always-loaded context. [inference]
4. **R** "but to build anything I will ever need from now on" — general-purpose scope, not one product. **X**: "anything ... ever" cannot be guaranteed; honest form is "any project type, with a defined intake that classifies the request and says plainly when something is outside what a cloud coding session can do".
5. **C** "When using it I will always use two repos in a chat" — the runtime is always a two-repo session. This is the constraint that triggers F1.
6. **R** "one of them the Claude brain" — the brain is one fixed repo reused in every chat.
7. **C/X** "which will be only modified by its own machine learning systems" — nobody edits the brain by hand, including the working agent mid-task. **X**: there is no machine learning in the weights sense; a git repo cannot train Claude. Honest form: the brain's *contents* change only through a governed, measured learning pipeline. Also a bootstrap exception is unavoidable: the first version is written by hand by the lead.
8. **R** "as it improves by learning with everything I use it for" — every session is learning input; improvement must be real (measured), and it must happen without the owner doing anything.
9. **I** from 7+8 — learning must be automatic at session end; the sample repo's discretionary rule ("write a lesson whenever a ticket costs more than two hours of rework") produced one lesson file in 50 commits [observed], so opt-in lesson writing under-delivers.
10. **R** "the other repo will be where the project will be built" — product code lives only in the project repo.
11. **R** "which can also hold files and tools to complement the Claude brain functionality that are specific to that project" — a defined project-side extension point (project memory, project skills, project tools). Project-specific learning belongs there, not in the brain.
12. **R** "both will always be worked together from now on" — a stable contract between the two repos.
13. **R** "so the project must be built to work perfectly with it forever" — the contract needs a version number and a compatibility rule so that a brain that keeps changing does not break old projects. **X**: "perfectly ... forever" → versioned interface plus a migration step, checked at session start. **A**: "the project" could mean every future project repo or the brain-building project itself; I read it as every project repo.
14. **R** "Now you will create a super long, super detailed plan on how to build this" — first deliverable is a long written plan.
15. **R** "based on very comprehensive research about Claude fable 5.2 and opus 5.5 (the main models ai will use it with)" — research must be about those two models specifically; the brain must work with both ("ai" reads as "I").
16. **R** "and also using everything we learned with the sample repo I attached" — the sample repo's lessons must be carried over (cold start, §B5).
17. **C** "(obviously having present that the current Claude brain's scope for creating stuff is much bigger)" — do not copy travel-journal specifics into the brain; generalise.
18. **R/X** "Also you must look at all your memory in detail and all our chats" — **X**: a cloud session has no access to the owner's other chats or to claude.ai memory unless it is exported into a file; auto-memory is machine-local (F2). Honest form: use what is on disk (the sample repo, its `KICKOFF_PROMPT.md`, persona, status, decisions) and ask the owner, via a NEEDS_YOU item, to drop a memory export file into the brain's inbox.
19. **R** "and consider everything I have ever asked you to build on Claude or any question I have ever asked you can be successfully processed to completion" — the brain must cover the owner's whole request range, including plain questions, not only builds; "to completion" means no half-done hand-offs. Depends on 18 for the actual history.
20. **R** "Also VERY IMPORTANT, you MUST MAKE THIS THE MOST EFFICIENT CLAUDE TOOL EVER" — efficiency is the top-ranked requirement. **X**: "most efficient ever" is not provable; honest form is a measured token ledger with a baseline and a published trend.
21. **R** "it should be much more efficient in tokens" — token cost per completed task is a primary metric.
22. **R/X** "through plugins" — **X** for the stated runtime: plugins declared in a repo's settings do not install in cloud sessions [source: https://code.claude.com/docs/en/cloud-environments.md]. Skills, agents and commands committed to the repo do load. Reframe as "skills and scripts".
23. **R** "and algorithms" — deterministic code should replace model work where it can (capture, curation maths, budgets, routing tables).
24. **X** "and quantum logic" — there is no quantum computing available to a Claude session and no credible way it reduces tokens. Say so plainly. If a nearby idea is wanted, the honest one is probabilistic decision-making under uncertainty (bandit routing, Bayesian evidence thresholds, §B4).
25. **R** "and many other thing you must research to see how you can make this super efficient token wise and super fast" — open-ended research mandate; speed (latency) is a second metric next to tokens.
26. **R** "while delivering the absolutely highest quality work with absolute attention to detail" — efficiency may not be bought with quality; quality gates stay.
27. **P** "(focus a lot on accuracy, creativity and extreme attention to detail)" — three named quality dimensions; the evals and critic rubrics should score these three by name.
28. **A** tension between 20–25 and 26–27 — the owner states both as absolutes. The plan needs an explicit rule for conflicts (I suggest: quality gates are constraints, tokens are minimised subject to them).
29. **R** "Create now the super long and super detailed plan considering also all our previous builds in Claude" — repeat of 14 and 18/19; "previous builds" are only partly visible (the travel journal).
30. **R** "and then start building until completion once you have a full plan based on extremely extensive research" — sequence: research → plan → build, in the same engagement, without stopping to ask.
31. **R** "Make sure you analyze this prompt by 10 independent agents and extract everything I said in full detail" — this analysis step itself; independence matters (no shared drafts).
32. **R** "and you can execute to perfection by planning perfectly and researching and analyzing heavily everything" — heavy up-front analysis is authorised even though it costs tokens; **A**: this conflicts locally with 21, so the research cost should be reported honestly.
33. **I** from the known context — the owner does not use the command line; anything he must do is a click or a file to read. Applies to branch protection, environment setup and overrides.
34. **I** — both models are "main"; the brain must record which model ran each task so learning is not confounded by a model switch.
35. **I** — the brain will be read in every session forever, so its always-loaded size is a permanent tax on every chat; size budgets are a first-class requirement. [inference]
36. **I** — the sample repo is read-only ("we will not modify or touch this repo at all in this chat", message 1).
37. **A** "its own machine learning systems" (plural) — could mean several mechanisms (memory, skills, routing statistics, retrieval). I treat it as one pipeline with several stores.
38. **A** whether the owner wants to see or approve what is learned — not stated. Default: he sees a short digest and can undo with one click; he approves nothing routinely.
39. **A** whether the brain is private — it will hold an owner model. The sample repo's persona file holds age, home area and companions [observed]; the brain should hold working preferences only unless the repo is confirmed private.
40. **A** "always use two repos in a chat" vs. scheduled routines — a consolidation routine would run on the brain alone. That is not "using it" in his sense, but it should be disclosed.

---

## PART B — The learning system

### B0. What can and cannot learn

- Cannot: model weights. Nothing in a git repo changes Fable 5.2 or Opus 5.5.
- Can: everything the model reads or that scripts compute from — instructions, playbooks, skills, verified facts, the retrieval index, routing statistics, eval sets. The research below shows that agents improve measurably from exactly this kind of non-parametric learning, and also how it fails.

### B1. Research base

**Verbal reflection as memory.** Reflexion: agents "verbally reflect on task feedback signals, then maintain their own reflective text in an episodic memory"; 91% pass@1 on HumanEval against 80% for the GPT-4 baseline of the time. [source: https://arxiv.org/abs/2303.11366] Lesson: reflection needs an external feedback signal (test result, gate, owner correction); without one it is opinion.

**Skill libraries.** Voyager keeps "an ever-growing skill library of executable code for storing and retrieving complex behaviors"; skills are "temporally extended, interpretable, and compositional", which "alleviates catastrophic forgetting"; 3.3x more unique items and milestones up to 15.3x faster than prior work. [source: https://arxiv.org/abs/2305.16291] A skill enters the library only after self-verification that it worked [recalled]. Lesson: procedural memory should be executable and admitted only after verification.

**Insights from many runs.** ExpeL "autonomously gathers experiences and extracts knowledge using natural language from a collection of training tasks" and recalls insights at inference, with no weight updates. [source: https://arxiv.org/abs/2308.10144] Its insight list is edited with ADD / EDIT / UPVOTE / DOWNVOTE operations and an insight is dropped when its votes reach zero [recalled]. Lesson: counters on small items, and compare successes with failures rather than reflecting on one run.

**Memory stream and retrieval scoring.** Generative Agents store "a complete record of the agent's experiences", synthesise "higher-level reflections", and retrieve to plan. [source: https://arxiv.org/abs/2304.03442] Retrieval scores each memory by recency (exponential decay), importance (rated once when written) and relevance (embedding similarity), summed after normalisation [recalled]. Lesson: the three-factor score, with importance fixed at write time.

**Tiered memory.** MemGPT: "virtual context management" with "data movement between fast and slow memory" and distinct memory tiers. [source: https://arxiv.org/abs/2310.08560] Lesson: a small always-in-context core, and everything else paged in on demand.

**Linked notes.** A-MEM builds Zettelkasten-style notes with keywords, tags and links; new memories can trigger updates to older notes (NeurIPS 2025). [source: https://papers.nips.cc/paper_files/paper/2025/hash/19909c36f51abc4856b4560aff3d36d6-Abstract-Conference.html] Lesson: atomic notes with tags and explicit links. The "new notes rewrite old notes" part is the risky half; I keep links and reject silent rewrites.

**Workflows as memory.** Agent Workflow Memory induces reusable workflows from past trajectories: +51.1% relative success on WebArena, +24.6% relative step success on Mind2Web, about 2 fewer steps per task. [source: https://arxiv.org/abs/2409.07429] Lesson: reusable routines cut steps (tokens) as well as raising success; the unit is a parameterised sub-routine, not a whole transcript.

**Prompt optimisation against a metric.** MIPRO optimises "free-form instructions and few-shot demonstrations of every module" with a surrogate model over mini-batch evaluations; up to 13% accuracy gain. [source: https://arxiv.org/abs/2406.11695] GEPA uses reflection on execution traces plus a Pareto front of candidates; the ICLR 2026 version reports +13% aggregate against MIPROv2's +5.6%, with far fewer rollouts than reinforcement learning. [source: https://arxiv.org/abs/2507.19457v2] TextGrad "backpropagates textual feedback provided by LLMs to improve individual components of a compound AI system". [source: https://arxiv.org/abs/2406.07496] Lessons: (a) prompt changes should be accepted on a held-out metric, not on how good they sound; (b) all three need tens to hundreds of scored rollouts, which a single owner's usage will not supply for most task classes, so this is a periodic, targeted tool for the few high-traffic skills, not the everyday loop. [inference]

**ACE — the closest match to what the owner wants.** ACE "treats contexts as evolving playbooks" with a Generator, Reflector and Curator. The Curator emits small "delta" entries that non-LLM logic merges deterministically; each bullet has an id and helpful/harmful counters; "grow-and-refine" de-duplicates by embedding similarity, either after each delta or lazily when a size limit is reached. It names two failure modes: *brevity bias* and *context collapse*, where "iterative rewriting erodes details over time". The case study: a context of 18,282 tokens at 66.7% accuracy was rewritten down to 122 tokens and fell to 57.1%, below the 63.7% no-adaptation baseline. Gains: +10.6% on agent tasks, +8.6% on finance; 82.3% lower adaptation latency than GEPA offline and 83.6% lower token cost online. It works from execution feedback without labels (+14.8% on AppWorld), but the authors state that without reliable feedback the context "may become noisy or even harmful", and that a weak Reflector pollutes it. [source: https://arxiv.org/abs/2510.04618 and https://arxiv.org/html/2510.04618v1] ACE builds on Dynamic Cheatsheet, whose memory is "self-curated, focusing on concise, transferable snippets rather than entire transcripts". [source: https://arxiv.org/abs/2504.07952]
Lessons taken directly: itemised bullets with ids and counters; LLM proposes, script merges; never a whole-file rewrite; do not learn from runs that have no trustworthy outcome signal.

**Anthropic's own guidance.**
- Memory tool: file-based, client-side; "supports just-in-time context retrieval"; security section tells implementers to cap file sizes, expire files not accessed for a long time, strip sensitive data, and validate paths. It also describes a multi-session pattern: progress log + feature checklist, read at start, updated at end, "mark a feature complete only after end-to-end verification". [source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool] A real path-traversal bug in the SDK's local memory tool (CVE-2026-34451) shows that model-supplied paths steered by injection are a live risk. [source: https://nvd.nist.gov/vuln/detail/CVE-2026-34451]
- Context management announcement: memory tool plus context editing improved an internal agentic eval by 39% over baseline, context editing alone 29%, and cut tokens 84% in a 100-turn web-search eval (vendor-reported). [source: https://www.anthropic.com/news/context-management]
- Claude Code memory docs: target under 200 lines per `CLAUDE.md` because "longer files consume more context and reduce adherence"; "if two instructions contradict each other, Claude may pick one arbitrarily"; instructions are "context, not enforced configuration", so use a hook to enforce; auto-memory keeps a one-line-per-entry index (first 200 lines or 25 KB loaded) with detail in topic files read on demand, and types entries as `user`, `feedback`, `project`, `reference`. [source: https://code.claude.com/docs/en/memory]
- Skill-creator eval loop [observed: `/mnt/skills/examples/skill-creator/SKILL.md`]: each test prompt is run with the skill and with a baseline (no skill, or the snapshot of the old version) in the same turn; assertions are graded; an analyst pass flags non-discriminating assertions and high variance; an optional blind comparator judges A against B; the description optimiser splits queries 60% train / 40% held-out and runs each query 3 times to get a stable trigger rate.

**Failure modes in the literature.**
- Memory poisoning. MINJA injects malicious records into an agent's memory through ordinary queries, with 98.2% injection success and 76.8% attack success in the paper's setting. [source: https://arxiv.org/abs/2503.03704] AgentPoison backdoors memory/RAG stores with over 80% success [source: search summary of the paper; number not re-read]. MemoryGraft plants fake "successful experiences" that the agent later imitates. [source: https://arxiv.org/abs/2512.16962] A 2026 study found detection-style moderation of memory largely ineffective against MINJA. [source: https://arxiv.org/abs/2601.05504] Meaning for us: text from web pages, project files or tool output must never become a brain instruction just because the agent read it.
- Context collapse and brevity bias: ACE, above.
- Polluted memory from weak feedback: ACE limitations, above.
- Contradiction: Claude "may pick one arbitrarily" (memory docs, above).
- Bloat: adherence falls as instruction files grow (memory docs, above).
- Overfitting to one project, drift and error propagation through reused experiences: [inference], consistent with the above; I did not find a source I could read today for a precise figure.

### B2. Memory taxonomy

Common item schema (JSONL, one item per line, each item ≤ 400 characters of `text`):

```json
{"id":"pb-gate-0007","type":"procedural","scope":"global","class":["release","git"],
 "text":"Chain an irreversible step (push, deploy, delete) to its gate with && on the gate's recorded exit code; never with ;",
 "evidence":["run:2026-11-05-s2#push-red-main"],"provenance":"seed:travel-journal/docs/lessons/2026-11-05-push-only-on-a-green-exit.md",
 "trust":"observed","confidence":0.80,"helpful":3,"harmful":0,"uses":3,"sessions":2,"projects":1,
 "importance":3,"created":"2026-11-10","last_used":"2026-11-10","status":"active","supersedes":[],"conflicts":[],"links":[]}
```

Field notes: `scope` ∈ `global | type:<project-type> | project`; `trust` ∈ `owner-stated | observed | derived | external`; `importance` 1–3 fixed at write time; `status` ∈ `candidate | probation | active | demoted | retired`; `confidence` is computed by script from the counters (§B4), never typed by a model.

| Memory | What it holds | Where it lives | Format | Loaded |
|---|---|---|---|---|
| **Episodic** | One run record per session: task classes, outcomes, gate results, owner corrections, token totals per model, items retrieved and whether they were followed | Brain `memory/episodes/YYYY/MM/<session>.json` (≤ 2 KB each, no transcript text, no project content); project detail stays in the project repo's own status files | JSON | Never loaded; read only by pipeline scripts |
| **Semantic** | Verified facts: model capabilities and prices, platform behaviour (e.g. F1, F2), pinned doc snapshots with fetch date and source URL | Brain `memory/facts.jsonl` + `memory/pins/<topic>.md` | JSONL + Markdown | Retrieved; each fact carries `verified_on` and a re-check interval |
| **Procedural** | Playbook bullets (short rules) and skills (multi-step procedures, often with scripts) | Brain `playbooks/<class>.jsonl` (source of truth) rendered to `playbooks/<class>.md`; `.claude/skills/<name>/SKILL.md` | JSONL → Markdown; skill folders | Skill descriptions always loaded (native); bodies and playbooks on demand |
| **Owner model** | Standing instructions (verbatim, dated), preferences, defaults for decisions he delegates | Brain `owner/standing.jsonl` (verbatim quotes) + `owner/preferences.jsonl` | JSONL, rendered into a short block | Top items always loaded via `CLAUDE.md`; rest retrieved |
| **Statistics** | Token ledger; routing table (task class × model × effort → successes, failures, token distribution); skill trigger and outcome counts | Brain `stats/ledger/YYYY-MM.jsonl` (append-only), `stats/routing.json`, `stats/items.json` | JSONL / JSON | Never loaded as text; a script answers "which model and effort for class X" in one line |
| **Project memory** | Anything true only for one project: its stack, commands, decisions, local lessons | **Project repo** `.brain/` (`project.json` contract version, `memory/*.jsonl`, `skills/`, `tools/`) and its `CLAUDE.md` | Same schema, `scope: project` | Loaded by the project's own `CLAUDE.md` |

Always loaded (hard budget, enforced by script and CI):
- Brain `CLAUDE.md` ≤ 150 lines: the kernel rules, the top owner standing instructions, the routing one-liner, and the pointer to the recall script. The docs' adherence guidance is under 200 lines. [source: https://code.claude.com/docs/en/memory]
- Skill descriptions: capped count (start at 25) and capped length, because every description is paid for in every session. [inference]
- Nothing else.

Retrieved on demand:
- `python3 Claude-Brain/bin/recall.py "<task description>" --class <c> --k 8` prints the top items as terse lines with ids. Score = relevance × (0.5 + 0.5·confidence) × recency factor × importance weight, the Generative Agents three-factor idea plus the evidence counters [recalled + inference]. Relevance from SQLite FTS5 (BM25) over text and tags; with a few hundred items that is enough, and it avoids downloading an embedding model in each fresh container (the sample library's eval took 599 s with bge-small plus a reranker [observed]). The index is derived and not committed.
- MCP is not available in two-repo sessions (F1), so the CLI is the retrieval surface there; the same code can also be served as an MCP server for one-repo sessions.

### B3. The learning pipeline

Seven stages. "Script" means deterministic Python in `Claude-Brain/bin/`, no model call.

**1. CAPTURE — owner: script, 0 model tokens beyond one Bash call.**
- Trigger: the brain `CLAUDE.md` rule "before your final message of a session and before any long task, run `bin/capture.py`". If E1 succeeds, also a Stop hook installed by the environment setup script; Stop hooks receive `transcript_path` and `last_assistant_message`, and a SessionEnd hook has only a 1.5 s default budget (up to 60 s if its timeout is raised), so Stop is the better trigger. [source: https://code.claude.com/docs/en/hooks]
- Inputs: the session transcript and subagent transcripts on disk (F3); `git log`/`git diff --stat` of both repos; gate logs with exit codes; a small `session.json` the lead keeps (task ids, classes, declared outcomes).
- Outputs: `memory/episodes/.../<session>.json`; ledger rows per task and per subagent (model, effort, four token counters, wall time, outcome), the same shape the sample repo's payroll ledger already uses [observed: `payroll/data/ledger.jsonl`]; counter events for every retrieved item (`retrieved`, `followed`, `outcome`).
- Owner corrections are detected by script from user turns that follow an assistant turn and contain correction markers, then confirmed in REFLECT. [inference]
- Idempotent: keyed by session id, re-running replaces the same record.

**2. REFLECT — owner: one small-model subagent (Haiku 5.5), bounded input.**
- Runs only when the episode has a signal worth learning from: a failed gate, rework, an owner correction, a token outlier (above the class's 90th percentile), or a first success in a new task class. Most sessions produce zero or one candidate; that is intended (auto-memory likewise "doesn't save something every session" [source: https://code.claude.com/docs/en/memory]).
- Input: the run record plus the 20–40 transcript lines around each signal, extracted by script. Never the whole transcript.
- Output: at most 3 candidate lessons as JSON, each with `text`, proposed `scope` and `class`, an `evidence` pointer that must resolve to a real event in the episode, and the outcome signal it rests on. A candidate with no resolvable evidence is dropped by script. This is the Reflexion/ExpeL step with ACE's requirement of a reliable feedback signal.
- Where possible, contrast a failed and a successful attempt at the same class (ExpeL) [recalled].

**3. CURATE — owner: script; a model is called only for a yes/no "same meaning?" check on near-duplicates.**
- Scope gate first: a candidate that mentions project names, paths, package names or domain nouns from the project is `scope: project` and is written to the **project repo's** `.brain/memory/`, not to the brain. It can be proposed for `type:` or `global` scope only after the same lesson is independently captured in a second project.
- Dedupe: lexical similarity against existing items; near-match → increment the existing item's `helpful` and append evidence (ACE "update in place"); no new item.
- Conflict detection: same class and tags with opposing polarity ("always X" / "never X"), or a candidate that contradicts an `owner-stated` item. Owner-stated always wins; otherwise both are marked `conflicts` and neither is promoted until evidence separates them. Contradictions are queued in the digest, because the model "may pick one arbitrarily" when both are loaded.
- Trust rule: `external` text (web pages, project files, tool output) can supply facts with a source URL, never imperative rules.

**4. VALIDATE — owner: script + eval subagents; the candidate must not make the suite worse.**
- Static checks (free): schema; size budgets; no secrets or personal data patterns; no instruction-like text addressed to the model inside `external` facts; item text ≤ 400 chars; file budgets.
- Regression suite `evals/`: a small fixed set of tasks per class with graded assertions, run baseline against candidate in the same batch, as skill-creator does. Cheap items (a playbook bullet) are validated by batch at consolidation time, not one by one. Changes to always-loaded text or to a skill description require the full paired run before merge.
- Canary: a newly merged item is `probation`. It is retrievable, flagged in the recall output, and its first uses are scored. It becomes `active` or is `demoted` by the thresholds in §B4.

**5. PROMOTE — owner: script; delta edits only.**
- The only write path into learned files is `bin/apply_delta.py`, which takes a delta file of operations `ADD | INC_HELPFUL | INC_HARMFUL | EDIT_TEXT (≤ 1 item) | SET_STATUS | LINK | MOVE_SCOPE` and applies them to JSONL, then re-renders the Markdown views. No operation can replace a file. A delta that removes more than 10% of a file's items, or shrinks any file by more than 20%, is refused. This is the direct guard against the 18,282 → 122 token collapse ACE measured.
- Size budgets per file are checked before commit; a file at budget forces a retire-or-merge of its lowest-confidence item in the same delta.
- Each promotion appends a line to `learning/manifest.jsonl` (delta id, hash of the ops, files touched, evidence episode ids, eval result id) and commits with the trailer `Brain-Learning: <delta-id>`.
- Delivery: push to a `learning/<date>-<id>` branch, open a PR labelled `learning`, CI runs, auto-merge on green. A merged PR is what makes the lesson visible to the next session (F2).

**6. DECAY / RETIRE — owner: script, at consolidation.**
- An item not retrieved in 90 days and with `importance` < 3 → `demoted` (kept, excluded from default recall). Demoted and unused for a further 180 days → `retired` (moved to `memory/archive/`, never deleted). The memory tool docs recommend expiring long-unaccessed files. [source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool]
- Harmful evidence retires faster than age (§B4).
- Semantic facts past their re-check interval are flagged `stale` and re-verified against their source URL before next use; model- and platform-facts get short intervals because, as F1 shows, they change and are easy to get wrong.

**7. AUDIT — owner: script + GitHub.**
- `learning/CHANGELOG.md` (one line per delta, human-readable), `learning/manifest.jsonl` (machine-readable), a git tag per consolidation (`brain-YYYY.MM.DD`).
- Rollback: every learning change is one PR, so the owner's rollback is the "Revert" button on that PR in GitHub. `bin/rollback.py <delta-id>` produces the inverse delta for the agent path.
- Weekly `learning/digest/YYYY-Www.md` (see §B3 governance).

### B3-bis. Governance for "only modified by its own learning systems"

**Zones.**
- *Learned zone* — `memory/`, `playbooks/`, `owner/preferences.jsonl`, `stats/`, learned skills. Writable only by `apply_delta.py`.
- *Kernel zone* — `bin/`, schemas, `evals/`, CI, `CLAUDE.md` skeleton, `owner/standing.jsonl`. The pipeline cannot rewrite its own rules or its own tests. Changes need an owner override.
- Honest statement for the owner: "learning systems only" holds for the learned zone after tag `brain-v1.0.0`. The first build, and later changes to the pipeline's own code, are engineering changes that he authorises.

**Guard layers, strongest first.**
1. **CI check on the brain repo (authoritative).** For every PR to the default branch: (a) each commit touching the learned zone carries `Brain-Learning: <id>` and a matching manifest entry; (b) CI re-applies the recorded delta ops to the base commit and requires the resulting tree to equal the PR's tree, so a hand edit dressed up with a trailer fails; (c) budgets, schema, secret and injection-pattern checks; (d) the regression eval result id exists and is not worse. Commits touching the kernel zone fail unless the PR has the `owner-override` label.
2. **Branch protection on the default branch** requiring that check. One-time setup by the owner through GitHub's settings page (clicks only) → a NEEDS_YOU item.
3. **Local guard where it can run.** A PreToolUse hook on Edit/Write that blocks direct edits under the learned zone (the sample repo's `protect-paths.sh` is the pattern [observed]). It works in one-repo sessions (the consolidation routine) and in two-repo sessions only if E1 succeeds. A git pre-commit hook if E2 succeeds.
4. **Instruction in `CLAUDE.md`.** The weakest layer; the docs are explicit that this is context, not enforcement.

**Owner override.** The owner applies the `owner-override` label to a PR in the GitHub web UI; CI reads who applied the label from the event and accepts only his account. A trailer typed in a commit message is not an override, because any agent can type one. [inference] Standing instructions he gives in chat are captured verbatim with date into `owner/standing.jsonl` through the pipeline with `trust: owner-stated`, which skips the evidence threshold but not the size and conflict checks.

**Injection defence.**
- Content read from project files, web pages, issues or tool results is data. REFLECT sees only script-extracted transcript slices around outcome signals, and its instructions say so.
- A candidate needs evidence that resolves to an outcome event (gate, test, owner turn). "A file told me to always do X" has no such event and is dropped.
- `external`-trust items cannot be imperative and cannot enter always-loaded text.
- Anything that would change always-loaded text, permissions, hooks, network hosts, credentials handling or the guard itself is kernel zone → owner override.
- The poisoning papers show filters on memory content are weak on their own; the structural controls above (provenance, evidence, quarantine/probation, eval gate, reversible PRs) are the real defence. [inference from https://arxiv.org/abs/2601.05504]

**What the owner sees.** `learning/digest/YYYY-Www.md`, at most 15 lines:
- "Learned this week" (≤ 5 plain sentences, each with the one-click revert link of its PR);
- "Retired" (≤ 3);
- "Efficiency" (tokens per completed task by class against the previous 4 weeks, with the count of tasks so a small sample is visible);
- "I am unsure about" (conflicts needing his word, ≤ 3, each answerable by replying in chat).

### B4. Measuring learning

**Metrics (all from CAPTURE, no extra model calls except critic scores that already exist).**

| Metric | Definition | Segmented by |
|---|---|---|
| Tokens per completed task | Sum of the four token counters, cost-weighted, for tasks whose gate passed | task class, model, effort |
| Rework rate | Tasks reopened or files re-edited after a declared "done" ÷ tasks | class |
| First-pass gate pass rate | Tasks whose first full gate run exits 0 ÷ tasks | class |
| Critic score | Existing reviewer scores (accuracy, creativity, attention to detail as named sub-scores) | class |
| Owner corrections | Corrective owner turns per session | session, class |
| Time to first useful output | Wall time from task start to first artefact the owner can open | class |
| Memory quality | Share of retrieved items that were followed and preceded a pass; share of active items never retrieved | item, file |
| Always-loaded size | Tokens of brain `CLAUDE.md` + skill descriptions | per release |

Every row records the model id, because a move between Fable 5.2 and Opus 5.5 would otherwise look like learning or regression.

**Telling improvement from noise with small samples.**
- *Item evidence.* Treat each item's usefulness as a rate with a Beta(1,1) prior; after `helpful = h` and `harmful = m`, the posterior is Beta(1+h, 1+m). Rules, computed by script:
  - promote `probation → active` when the 10th percentile of the posterior is above 0.5 **and** the evidence spans ≥ 2 sessions. With no harmful votes this needs h = 3 (10th percentile 0.56); h = 2 gives 0.46 and is not enough. [inference; arithmetic: for Beta(1+h,1) the q-quantile is q^(1/(1+h))]
  - `global` scope additionally needs evidence from ≥ 2 projects.
  - demote when the 90th percentile falls below 0.5 (three harmful votes with none helpful gives 0.44).
  - a single harmful event tied to a failed gate puts an `active` item back on `probation` at once.
- *What counts as a vote.* `helpful` only when the item was retrieved, visibly followed, and the task passed its gate first time; `harmful` when followed and the failure is attributed to it by REFLECT with evidence. "Retrieved and task passed" alone is not a vote, since most tasks pass anyway. [inference]
- *Routing table.* Per (class, model, effort) keep Beta counts for first-pass success and a running log-mean of tokens. Choose by Thompson sampling among arms that meet the class's quality floor, with a minimum of 5 trials per arm before it can be excluded. The sample repo already seeds priors this way (`prior_strength: 4`, `prior_sigma: 0.5` in `payroll/data/priors.json` [observed]).
- *Efficiency claims.* Token cost per task is heavy-tailed, so compare medians of log tokens within a class and model. Do not report a change with fewer than 8 completed tasks per side; show the count in the digest. [inference]
- *Eval comparisons.* Paired runs on the same tasks. With n paired tasks and no ties, 6 wins out of 6 is the smallest result that reaches p ≈ 0.03 on a two-sided sign test; 5 of 5 gives p ≈ 0.06. Run each eval prompt 3 times, as skill-creator does, and keep a held-out split (60/40) when optimising any text against the suite so the suite is not overfitted.
- *Global health check.* At each consolidation, re-run the frozen regression suite with the current brain against the last tagged brain. A drop beyond the suite's own run-to-run spread blocks the tag and opens a rollback PR.

### B5. Cold start and schedule

**Seeds from the sample repo** (all `provenance: seed:travel-journal/...`, `status: probation`, `scope` as noted; each must be re-earned by evidence in a second project before it counts as global-proven):

| Seed | Source in sample repo | Goes to |
|---|---|---|
| Irreversible steps chained to a recorded green exit code with `&&`; investigate a red gate before any push | `docs/lessons/2026-11-05-push-only-on-a-green-exit.md` | playbook `release` |
| Timing/LCP specs fail under load; run the full gate with at most 2 e2e agents | `docs/status/PROGRESS.md` note 4 | playbook `testing` (type: web) |
| Fresh worktree needs generated content built before tests | same lesson, rule 3 | generalised: "build generated inputs before testing in a fresh checkout" |
| Never block; park owner-only decisions in a file with click-only steps and continue | `CLAUDE.md` §1.1, §10 | owner model, standing |
| Decide, record as ASSUMED, list in one overturn file | `CLAUDE.md` §1.6, `docs/DECISIONS.md` | playbook `decisions` |
| Checkpoint file that lets a new session resume from the file alone | `CLAUDE.md` §1.4, §3 | kernel (session protocol) |
| Delegated tasks must carry their facts; reviewer is never the author | `CLAUDE.md` §8, §9 | playbook `delegation` |
| Never use a library API from memory; query pinned docs | `CLAUDE.md` §7 | playbook `accuracy` |
| Reference token profile of a research-analyst run (input 226, output 19,482, cache-write 100,364, cache-read 480,517) and the 10 ledger rows | `payroll/data/priors.json`, `ledger.jsonl` | `stats/` priors, tagged model `claude-fable-5-1` so they are not mixed with 5.2 data |
| Retrieval eval pattern: golden set, recall@5 gate (244 questions, 0.914) | `library/eval/` | kernel `evals/` design |
| Path-protection hook pattern | `.claude/hooks/protect-paths.sh` | kernel guard |
| Owner facts: no shell commands, clicks and files only; Max plan; UI languages; standing release rule | `CLAUDE.md` §4, §10, §11 | owner model (working preferences only; personal details stay out, see A39) |
| Platform facts F1–F3 | this report | `memory/facts.jsonl`, `verified_on: 2026-11-10`, re-check 30 days |

Two negative lessons to seed as well: (1) opt-in lesson writing yielded one lesson and an empty performance folder in 50 commits [observed], so capture must be automatic; (2) hook-based metering does nothing in two-repo cloud sessions (F1).

**Schedule.**
- *Every session, at stop (micro-learning):* CAPTURE always. REFLECT only on a signal. CURATE + static VALIDATE + PROMOTE of counter updates and at most 3 new `probation` items, as one small PR. Target cost: one Bash call when there is no signal; a few thousand Haiku tokens when there is. [inference]
- *Weekly (deep consolidation), as a scheduled routine in a one-repo session on the brain:* merge near-duplicates, resolve conflicts, apply decay, recompute routing posteriors, run the regression suite against the last tag, re-verify stale facts, write the digest, tag. Cloud scheduled tasks use the same environments as interactive sessions. [source: https://code.claude.com/docs/en/cloud-environments.md] In a one-repo session the brain's hooks and `.mcp.json` load, so the local guard is active there.
- *Monthly or on demand:* targeted optimisation of the 1–3 most-used skills against their eval sets (skill-creator loop; GEPA-style reflective search only if a skill has enough scored tasks), and a review of always-loaded text size.

### B6. Risks and what not to automate

| Risk | Control |
|---|---|
| Capture silently not running (F1) | Capture is a script call required by `CLAUDE.md`; the next session's start check looks for the previous session's episode and says so if it is missing |
| Learning lost because the PR never merged (F2) | Auto-merge on green; session-start check lists unmerged `learning/*` branches |
| Poisoned memory | Trust levels, evidence must resolve to an outcome event, external text never imperative, probation, eval gate, one-click revert |
| Context collapse | Delta ops only; shrink limits; no whole-file writes in the learned zone |
| Bloat | Hard budgets per file and for always-loaded text; at budget, add = retire |
| Overfitting to one project | Project-scoped items live in the project repo; global needs 2 projects |
| Contradictory lessons | Conflict detection; owner-stated wins; unresolved pairs are not loaded together |
| Drift and stale facts | Re-check intervals; frozen regression suite against the last tag |
| Eval overfitting / judge bias | Held-out split, 3 runs per prompt, blind comparator for text changes, outcome signals preferred to model judgement |
| Model confounding | Model id on every ledger row and routing arm |
| Learning cost exceeding its benefit | Learning tokens are a ledger class of their own, with a budget (start at 3% of weekly tokens) shown in the digest [inference] |
| Privacy | No project content, secrets or personal details in episodes; scan in static validation |

**Do not automate:**
1. Changes to the kernel zone: the pipeline's code, the guard, the eval suite and its thresholds. A learner that can edit its own tests can make any change pass.
2. Changes to permissions, hooks, network allow-lists, credentials handling, or anything that widens what a session can do.
3. Edits to the owner's verbatim standing instructions. The pipeline may add a new dated instruction he gave; it may not paraphrase, merge or retire one.
4. Whole-file rewrites or "tidy-up" summarisation of playbooks, at any stage.
5. Promotion of anything whose only support is text the agent read (as opposed to an outcome it observed).
6. Promotion to `global` from a single project.
7. Deletion. Retire means archive.
8. Force-pushes or history rewrites on the brain's default branch.
9. Automatic prompt optimisation of always-loaded text. It affects every session; it needs the full paired eval and the owner's label.
10. Claims of improvement in the digest without the sample count beside them.

---

## Sources read today

- https://code.claude.com/docs/en/settings.md#settings-in-cloud-sessions
- https://code.claude.com/docs/en/cloud-environments.md
- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/en/hooks
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
- https://www.anthropic.com/news/context-management (via search summary)
- https://arxiv.org/abs/2510.04618 and https://arxiv.org/html/2510.04618v1 (ACE)
- https://arxiv.org/abs/2504.07952 (Dynamic Cheatsheet, via search summary)
- https://arxiv.org/abs/2303.11366 (Reflexion)
- https://arxiv.org/abs/2305.16291 (Voyager)
- https://arxiv.org/abs/2308.10144 (ExpeL)
- https://arxiv.org/abs/2304.03442 (Generative Agents)
- https://arxiv.org/abs/2310.08560 (MemGPT)
- https://arxiv.org/abs/2502.12110 / NeurIPS 2025 page (A-MEM, via search summary)
- https://arxiv.org/abs/2409.07429 (Agent Workflow Memory, via search summary)
- https://arxiv.org/abs/2406.11695 (MIPRO)
- https://arxiv.org/abs/2507.19457v2 (GEPA, via search summary)
- https://arxiv.org/abs/2406.07496 (TextGrad)
- https://arxiv.org/abs/2503.03704 (MINJA), https://arxiv.org/abs/2512.16962 (MemoryGraft), https://arxiv.org/abs/2601.05504 (poisoning defences), via search summary
- https://nvd.nist.gov/vuln/detail/CVE-2026-34451 (via search summary)
- Local: `/mnt/skills/examples/skill-creator/SKILL.md`; the sample repo at `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose` (read-only)

Not verified today and marked `[recalled]` in the text: ExpeL's vote operations, Voyager's self-verification gate, Generative Agents' retrieval formula. Letta's current product documentation was not read; MemGPT is cited from the paper only.
