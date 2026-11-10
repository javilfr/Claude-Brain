# 06 — Sample repo machinery teardown (analyst 6 of 10)

Sample repo (read-only, untouched): `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose` (abbreviated `SR/` below).
Scratch experiment (mine): `/tmp/claude-0/-home-user/ad24da2f-7dc0-51cf-aa28-dee6f5e57a4f/scratchpad/a6/lean.py`.

Labels used: **MEASURED** = I ran it or counted it here; **RECORDED** = a number the sample repo stores; **ESTIMATE** = my calculation from knowledge, not verified on this machine.

---

## PART A — Independent extraction of the owner's message 2

Each item quotes the words it comes from.

### A.1 What the thing is

1. **A new repository that plays the role the sample repo played.** "I want now to create a repo that will act as that".
2. **It is an orchestrator, and a complex one.** "essentially a mega complex orchestrator". Implied: multi-agent coordination, planning, delegation, review, checkpointing, as in the sample.
3. **Universal scope.** "to build anything I will ever need from now on". Not only software. *Needs honest reframing:* "anything" is bounded by what Claude Code sessions with tools can produce (code, documents, research, data work, designs, automations). The plan should define supported project types and an extension path for new ones.
4. **The sample repo is the prototype and source of lessons.** "I essentially used this repo as a brain to create everything in my travel journal in the best possible way" and "using everything we learned with the sample repo I attached".
5. **The scope is explicitly wider than the sample's.** "obviously having present that the current Claude brain's scope for creating stuff is much bigger". Implied: nothing travel-specific may remain hard-coded.
6. **Name.** "the Claude brain" (target repo `Claude-Brain`).

### A.2 Two-repo operating model

7. **Always two repos per chat.** "When using it I will always use two repos in a chat, one of them the Claude brain".
8. **The brain is modified only by its own learning systems.** "which will be only modified by its own machine learning systems as it improves by learning with everything I use it for". Implied: (a) a write-protection rule so project work never edits the brain ad hoc; (b) a defined, audited learning pipeline that is the only writer; (c) learning happens from every use. *Needs honest reframing:* no model weights are trained. "Machine learning" here must mean a file-based learning loop (lessons, playbooks, retrieval index, measured statistics, eval sets) written by scripts and gated by evaluation. *Ambiguity:* who approves a brain change, and whether the owner himself may edit it (the initial build obviously requires the lead to write it).
9. **The project repo holds the build.** "the other repo will be where the project will be built".
10. **The project repo may hold project-specific extensions to the brain.** "which can also hold files and tools to complement the Claude brain functionality that are specific to that project". Implied: a documented extension contract (per-project manifest, agents, skills, hooks, knowledge) that the brain discovers.
11. **Permanent pairing and forward compatibility.** "both will always be worked together from now on so the project must be built to work perfectly with it forever". Implied: a versioned brain-to-project interface, migration rules, and a project bootstrap step. *Reframing:* "forever" cannot be guaranteed; it can be approached with a versioned contract, compatibility tests and no dependence on fragile external services.

### A.3 Process the owner demands

12. **Plan first, and the plan must be very long and detailed.** "Now you will create a super long, super detailed plan on how to build this" and again "Create now the super long and super detailed plan".
13. **Research on the two main models.** "based on very comprehensive research about Claude fable 5.2 and opus 5.5 (the main models ai will use it with)". Implied: model-specific guidance (tiering, effort, context, caching, pricing) baked into the design; the cheaper tiers matter for routing.
14. **Use the owner's history.** "you must look at all your memory in detail and all our chats and consider everything I have ever asked you to build on Claude or any question I have ever asked you can be successfully processed to completion". *Needs honest reframing:* a session only has what is available to it (memory files, attached repos, this conversation). The report must state what history was actually accessible and derive the capability checklist from that, not claim complete recall.
15. **Past builds are also input.** "considering also all our previous builds in Claude".
16. **Then build, to completion, without waiting.** "then start building until completion once you have a full plan based on extremely extensive research". Implied: autonomous execution; no confirmation step between plan and build.
17. **Ten independent analysts on this prompt.** "Make sure you analyze this prompt by 10 independent agents and extract everything I said in full detail".
18. **Flawless execution through planning and research.** "you can execute to perfection by planning perfectly and researching and analyzing heavily everything". *Reframing:* perfection is not verifiable; replace with explicit acceptance tests and measured gates.

### A.4 Efficiency and quality (flagged by the owner as most important)

19. **Top priority: efficiency.** "Also VERY IMPORTANT, you MUST MAKE THIS THE MOST EFFICIENT CLAUDE TOOL EVER". *Reframing:* "most efficient ever" is not provable; commit to measured token and time budgets with a baseline (the sample repo) and report the ratio.
20. **Token efficiency by named means.** "much more efficient in tokens through plugins and algorithms and quantum logic and many other thing you must research". Plugins and algorithms are real levers. **"Quantum logic" is not available:** no quantum computation runs in Claude Code. Say so plainly, and offer what the owner probably wants from it: retrieval instead of loading, progressive disclosure, caching, deterministic scripts replacing model turns, model routing, parallel fan-out.
21. **Speed.** "super efficient token wise and super fast".
22. **Without losing quality.** "while delivering the absolutely highest quality work with absolute attention to detail".
23. **Three named quality dimensions.** "(focus a lot on accuracy, creativity and extreme attention to detail)". Implied: a verification step, a creative-divergence step, and a detail audit as distinct mechanisms.
24. **Research is itself a requirement, not a nicety.** "many other thing you must research to see how you can make this super efficient".

### A.5 Implied expectations and standing constraints

25. Owner is non-technical in the command-line sense (context file): everything he must do is a file to read or a button to click.
26. The sample repo is never modified (message 1: "we will not modify or touch this repo at all in this chat, just read it").
27. Both repos' `CLAUDE.md`, agents, skills, hooks and `.mcp.json` load together, so **every always-loaded word in the brain is paid in every session of every project**. This makes always-in-context size the main cost driver (see B.3).
28. *Tension to resolve:* "mega complex orchestrator" versus "most efficient". The sample shows complexity that was built and not used (B.5). The honest design is rich capability on disk, tiny footprint in context.
29. *Tension:* "only modified by its own machine learning systems" versus "start building until completion" (someone has to write the first version). Treat the initial build as bootstrap, then lock.
30. *Ambiguity:* whether the brain serves several projects at once and whether lessons from one project may leak private details into the brain used by another.

---

## PART B — Technical teardown

### B.1 Library / RAG

**Architecture (as coded).**

| Stage | Implementation | Where |
|---|---|---|
| Discovery | Seven corpora C1–C7 by glob, priority order decides overlaps, 2 MB file cap | `SR/library/config.json:53-144`, `SR/library/pipeline/ingest.py:53-75` |
| Normalise | Markdown/HTML to Markdown; record-list JSON to one `## id: title` section per record | `SR/library/pipeline/ingest.py:118-150` |
| Chunking | Heading-split Markdown, heading path, parent section pointers; target 380, max 440 WordPiece tokens, 12 % overlap; table header repeated; regex splitter for TS/TSX; top-level blocks for JSON/YAML/CSS | `SR/library/config.json:19-26`, `SR/library/pipeline/chunker.py:216-296, 298-428` |
| Contextual prefix | `From [kind] heading path: first sentence` prepended (rule-based, no model call) | `SR/library/pipeline/chunker.py:54-79` |
| Lexical | FTS5, columns body/heading/path, tokenizer `porter unicode61 remove_diacritics 2`, weights 1.0/3.0/0.5; query is OR of quoted tokens plus phrases for hyphenated ids | `SR/library/pipeline/store.py:80-83`, `SR/library/pipeline/search.py:14-46` |
| Dense | `sqlite-vec` `vec0` table, `float[384]`, corpus column | `SR/library/pipeline/store.py:85-87`, `SR/library/pipeline/search.py:49-57` |
| Embedding | `BAAI/bge-small-en-v1.5` (384-d, 512-token window) via fastembed quantised ONNX on CPU | `SR/library/config.json:5-12`, `SR/library/pipeline/embed.py:14-20` |
| Fusion | Reciprocal Rank Fusion, k=60, top 20 from each list | `SR/library/pipeline/search.py:60-65, 136-139` |
| Rerank | Cross-encoder `Xenova/ms-marco-MiniLM-L-12-v2`, 20 to 5, plus an additive "authority prior" of -4 logits for derivative sources | `SR/library/config.json:13-17, 39-44`, `SR/library/pipeline/search.py:89-96, 146-152` |
| Diversity | Word-set Jaccard 0.6 near-duplicate filter, max 3 per source | `SR/library/pipeline/search.py:72-86` |
| Citations | `source — heading path (version <git sha>)` | `SR/library/pipeline/search.py:122-123` |

Code size (MEASURED): 2,224 lines across `mcp_server.py` (80), `pipeline/*` (1,377), `scripts/*` (216), `eval/*` (551 incl. the 244-line golden set).

**Dependencies** (`SR/library/requirements.txt:2-8`): sqlite-vec 0.1.9, fastembed 0.9.1, mcp 2.3.0, tiktoken 0.14.0, onnxruntime 1.31.1, numpy 2.5.4, tokenizers 0.23.3. **No torch.** ESTIMATE of install weight: a venv of roughly 250–400 MB (onnxruntime and numpy dominate), plus model downloads into `library/.models/` of roughly 65 MB (quantised bge-small) and roughly 130 MB (MiniLM-L-12 cross-encoder). None of these were present on this machine (`library/.venv`, `library/index`, `library/.models` all absent), so I could not measure them; fastembed, sqlite_vec, tiktoken and tokenizers are not installed in the system Python either.

**Committed or rebuilt.** Rebuilt. `.gitignore` excludes `library/.venv/`, `library/index/`, `library/.models/` (`SR/.gitignore:2-4`). Every fresh cloud container therefore pays the full install, download and embed cost.

**Cold start and the SessionStart hook** (`SR/.claude/hooks/session-start.sh`):
- Exits immediately unless `CLAUDE_CODE_REMOTE=true` (line 9).
- Runs `pnpm install --frozen-lockfile` in `../Travel-Journal` (lines 12-20), guarded by a sha256 stamp.
- Creates `library/.venv` and pip-installs the pins (lines 22-29).
- If the index is missing, launches `rebuild.py` in the background with `nohup` (lines 31-34).
- Hook timeout is 900 s (`SR/.claude/settings.json:53`).
- Consequence: `.mcp.json` points at `library/.venv/bin/python` (`SR/.mcp.json:5`). On a cold container the MCP server either cannot start (venv not yet there) or starts with no index and `connect(create=False)` raises `FileNotFoundError` (`SR/library/pipeline/store.py:62-63`). The Library is unavailable for the first minutes of every new session. The skill says "about 2–3 minutes" (`SR/.claude/skills/library/SKILL.md:52`); `rebuild.sh` budgets "< 15 minutes" (`SR/library/scripts/rebuild.sh:3`).

**Eval set and scores.** `SR/library/eval/golden.jsonl`: 244 hand-written questions, fields `q`, `expected_source`, `expected_heading`, `corpus`, optional `also_accept` (63 rows have it). A hit is source match plus heading substring match (`SR/library/pipeline/evaluate.py:28-34`). Gates: recall@5 >= 0.9, MRR >= 0.8, drop <= 0.03 (`SR/library/config.json:46-52`).
- RECORDED (`SR/library/eval/last_result.json`): recall@5 **0.9139**, MRR **0.822**, 21 misses, **598.7 s** for 244 queries, about **2.45 s per query** on CPU.
- Coverage is narrow: 187 questions target `docs/MASTER_PLAN.md`, 26 `CLAUDE.md`, 9 ADR-000, 20 the role catalogue (MEASURED). There are no questions on C1 cards, C5 memos, C6 code or C7 lessons, so retrieval quality on code and lessons is unmeasured.
- The barely-passing margin (0.9139 against 0.90) needed a hand-tuned authority prior and a larger reranker.

**Other observations.**
- `SR/library/README.md:75-91` still contains unrendered placeholders `{{PINS}}`, `{{RESULTS}}`, `{{GOLDEN}}`, `{{DECISIONS}}`, `{{LIMITS}}`. The README is in corpus C2, so the index contains template stubs.
- `SR/library/snapshots/` holds only `.gitkeep`: the "pinned vendor docs" corpus C3, which every engineering spec is told to query before any API call, was never populated.
- `SR/docs/phases/phase-0.md:23` lists TJ-003 (the Library) as "in progress"; `SR/docs/status/2026-11-04.md:5` likewise.
- `SR/docs/lessons/` holds one lesson. The learning loop existed on paper, not in volume.
- Cards: 112 files, 108 of them management-thinker cards (`library/cards/management/**`), 3 effect cards. The D1–D7/E1–E7 Principles Cards named in `CLAUDE.md` §7 are not in `library/cards/`.

**MCP tool surface and token cost.** Five tools: `search`, `get_section`, `cite`, `ingest`, `eval` (`SR/library/mcp_server.py:38-76`).
- Always-loaded cost (ESTIMATE from MEASURED sizes): 958 characters of docstrings plus about 420 characters of server instructions plus five JSON schemas, roughly **500–700 tokens** in every session, unless the client defers MCP schemas.
- Per-call cost: `search` returns full chunk text for each of k=5 results with 15 fields each, pretty-printed with `indent=1` (`SR/library/mcp_server.py:34-45`, `SR/library/pipeline/search.py:99-119`). At up to 440 WordPiece tokens per chunk plus prefix and metadata, a typical call is **roughly 2,500–3,500 tokens**; `get_section` on a large section can be several thousand more. Fields such as `rrf`, `bm25_rank`, `dense_rank`, `rerank_score`, `prior`, `confidence`, `date`, `lines` are debugging data the model pays for on every call.
- `cite` is redundant (every result already carries `citation`). `eval` and `ingest` are maintenance operations that do not belong in the always-visible tool list.

**Stdlib FTS5 check on this machine (MEASURED).** `python3 -I` 3.13.18 with SQLite 3.53.1 reports `ENABLE_FTS5`; `bm25()` with column weights, `snippet()`, the porter tokenizer and the trigram tokenizer all work; `enable_load_extension` is present, so `sqlite-vec` could be loaded later as an optional extra.

**Experiment: zero-dependency BM25 against the sample's own golden set (MEASURED).** `lean.py` (about 150 lines, stdlib only) indexes the same non-code corpora (258 files) by heading section and scores the 244 golden questions with the sample's hit rule.

| Variant | recall@5 | recall@10 | MRR@5 | Build | Per query | Index size |
|---|---|---|---|---|---|---|
| Sample hybrid + cross-encoder (RECORDED) | 0.914 | n/a | 0.822 | minutes, needs ~200 MB of models | ~2,450 ms | not present |
| Stdlib BM25, 1,800-char chunks, no prior | 0.820 | 0.889 | 0.623 | 0.20 s | 1.7 ms | 4.9 MB |
| Same + simple source prior | 0.848 | 0.914 | 0.696 | 0.19 s | 1.7 ms | 4.9 MB |
| Stdlib BM25, 1,200-char chunks + source prior | **0.869** | **0.930** | 0.716 | 0.22 s | 1.9 ms | 4.9 MB |

Caveats: my corpus omits C6 product code (the sibling repo is not part of this check), which removes some distractors; I did not tune beyond two knobs; the golden questions are deliberately paraphrased, which favours dense retrieval. Even so, the lexical baseline reaches about 95 % of the hybrid's recall@5 with a build about three orders of magnitude faster, queries about a thousand times faster, no installs and no downloads. Because the reader is a strong model, returning 8–10 short hits instead of 5 long ones recovers recall (0.93 at k=10) at lower token cost.

**Heaviest parts.** (1) pip install of onnxruntime/numpy/fastembed on every cold container; (2) two model downloads; (3) embedding every chunk on CPU; (4) the cross-encoder at about 2.4 s per query; (5) the MCP server's dependence on all of the above being finished before it can answer.

**Lean design proposed for the brain.**
1. **Default tier, zero dependencies.** One stdlib script (`brain/kb.py`, about 350–450 lines) using `sqlite3` FTS5: heading-aware chunking (port the sample's logic), contextual prefix, column-weighted BM25, quoted-OR query builder with id phrases, stop-word drop, source prior, per-source cap, near-duplicate filter. Index build under one second for a few hundred files, so it can rebuild incrementally inside SessionStart synchronously, or lazily on first query keyed on file sha256. No venv, no background job, no race.
2. **Cheap recall boosters before any model.** Query expansion written by the calling model (it can pass 2–3 paraphrases; fuse with RRF, which is 6 lines, `SR/library/pipeline/search.py:60-65`); a trigram FTS table for identifiers and typos; a small synonym file per project.
3. **Optional dense tier, off by default.** Enabled per project in the manifest only when the measured eval shows lexical recall is below target. Loaded lazily; never a session-start requirement.
4. **CLI first.** `python3 brain/kb.py search "q" [--scope ...] [--k 8]` printing compact lines: `id | path:lines | heading path | 1-2 line snippet` (about 60–80 tokens per hit, so 8 hits cost about 600 tokens against about 3,000 today). A second command `kb.py get <id> [--max-tokens N]` expands a hit. No tool schema sits in context; the one-line usage lives in a skill that loads on demand.
5. **MCP second.** A thin optional wrapper with two tools (`search`, `get`) for clients that prefer it; `ingest` and `eval` stay CLI-only.
6. **Two indexes, one tool.** A brain index (universal playbooks, lessons, patterns) and a project index (the project's docs and code), queried together with a scope flag. The project manifest supplies globs, kinds and priors.
7. **Keep the eval gate**, but generate golden rows per project and include code, lessons and playbooks, with recall@k and tokens-per-answer both tracked.

### B.2 Hooks

| Hook | Event / matcher | What it does | Cost per fire | Failure modes | Verdict |
|---|---|---|---|---|---|
| `protect-paths.sh` (73 lines) | PreToolUse on `Edit\|Write\|MultiEdit` (`SR/.claude/settings.json:5-14`) | Blocks (exit 2) edits to `docs/MASTER_PLAN.md`, `KICKOFF_PROMPT.md`, `.claude/agents/_retired/*`, and emptying `docs/NEEDS_YOU.md` (lines 53-71). Uses jq, falls back to python | One `sh` + up to 5 `jq` processes on every edit, tens of ms; zero tokens unless it blocks | Absolute paths outside the repo are waved through (line 43), so the product repo is unprotected; Bash redirection, `sed -i`, `git mv` bypass it; protected list is hard-coded | **Port the pattern, rewrite as data-driven.** This is the natural enforcement point for "the brain is only modified by its own learning systems": read protected globs from the brain and the project manifest, and add a Bash matcher for obvious write commands |
| `checkpoint-reminder.sh` (33 lines) | Stop (`SR/.claude/settings.json:27-37`) | If any file under `docs/` is newer than `docs/status/PROGRESS.md`, emits a `systemMessage` reminder; honours `stop_hook_active`; never blocks | One `find` over `docs/`; about 60–90 tokens when it fires | Only watches `docs/` in the company repo, so product-repo work without a checkpoint is not detected; mtime logic misfires after a fresh clone (all mtimes equal) | **Port, generalised.** Compare against `git status`/last commit in the project repo and the manifest's progress file |
| `payroll-gate.sh` (10) + `payroll/payroll/hooks.py:55-75` | PreToolUse on `Agent` | Denies a subagent spawn when the role's grant for the ticket is spent | One Python start per spawn (about 30–50 ms) | Ticket regex is `TJ-\d+\|R-[A-Z]\d+` (`hooks.py:17`); with no grant it allows. The ledger contains zero `grant` events, so the gate never had anything to enforce | **Drop** (keep a soft budget warning in the meter instead) |
| `payroll-meter.sh` (8) + `hooks.py:36-52` | SubagentStop | Sums `message.usage` from the subagent transcript, prices it, appends a `run` line to `payroll/data/ledger.jsonl` | One Python start per subagent stop; zero tokens | Fails open. In practice the committed ledger has exactly 10 rows, all `research-analyst` on 2026-11-04, none carrying the hook's `"source": "SubagentStop"` marker (they were seeded by hand), across a 50-commit history: in cloud sessions the appended lines are uncommitted working-tree changes that die with the container | **Port the meter (139 lines, generic), fix persistence.** Write to the project repo's state folder and commit it with checkpoints, or the learning loop has no data |
| `session-start.sh` (34) | SessionStart, timeout 900 s | Described in B.1 | Minutes of wall time on a cold container | Hard-codes `../Travel-Journal` and pnpm (lines 12-19); `set -euo pipefail` means a pip or network failure fails the hook; background rebuild races the MCP server | **Rewrite.** With a zero-dependency index the hook reduces to: detect the paired repo, read the manifest, refresh the index (sub-second), print a short orientation line. Project-specific installs belong in the project's own hook or the environment setup script |

Hooks promised in `SR/.claude/hooks/README.md:49-52` but never built: per-role path scope enforcement, the "ADR touched" check, ingest-on-merge. `CLAUDE.md` §8 and §9 describe them as if they exist. Lesson for the brain: a rule that is not mechanised should be labelled as advice.

### B.3 Agents

30 specs in `SR/.claude/agents/` (22 standing roles, 7 board seats, 1 effect-reproducer); `_retired/` holds only a README. Front-matter is exactly four fields in every file: `name`, `description`, `tools`, `model` (MEASURED). No `effort`, no `skills`, no `disallowedTools`. Every spec lists the three `mcp__library__*` tools by name, so every role is coupled to the MCP server.

| Role | Words | Model | Tools beyond Read/Glob/Grep + library |
|---|---|---|---|
| accessibility-auditor | 756 | sonnet | Bash |
| board-capital / craft / operations / people / product / risk / strategy | 1,081 / 1,172 / 1,019 / 1,110 / 1,142 / 1,110 / 1,141 | opus | Write |
| chief-of-staff | 820 | opus | Edit, Write, Bash, WebSearch, WebFetch |
| data-sync-engineer | 960 | sonnet | Edit, Write, Bash |
| design-critic | 1,042 | opus | WebSearch, WebFetch (read-only) |
| design-director | 805 | opus | WebSearch, WebFetch, Write |
| docs-writer | 729 | sonnet | Edit, Write, Bash |
| education-lead | 758 | sonnet | Edit, Write, Bash |
| effect-reproducer | 854 | opus | Edit, Write, Bash, WebFetch |
| frontend-mobile / frontend-web | 949 / 914 | sonnet | Edit, Write, Bash |
| hr-lead | 768 | sonnet | Edit, Write, Bash |
| media-pipeline-engineer | 970 | sonnet | Edit, Write, Bash |
| mobile-ui-designer / web-ui-designer / motion-designer | 828 / 827 / 815 | sonnet | WebSearch, WebFetch, Write |
| performance-auditor | 759 | sonnet | Bash |
| platform-engineer | 960 | sonnet | Edit, Write, Bash |
| product-manager | 716 | sonnet | Edit, Write |
| qa-lead | 796 | sonnet | Edit, Write, Bash |
| release-manager | 687 | sonnet | Edit, Write, Bash |
| research-lead | 719 | sonnet | Write, WebSearch, WebFetch |
| security-reviewer | 746 | opus | Bash (read-only) |
| tech-lead | 795 | opus | Edit, Write, Bash |

Totals (MEASURED): 27,082 words, 184 kB. 13 roles on opus, 17 on sonnet; none on haiku, although `CLAUDE.md` §8 calls for the fastest tier on search and mechanical work.

**Always-in-context cost.** The 30 `description` fields total 1,216 words / 8,262 characters, about **2,000–2,300 tokens** loaded in every session to describe subagents, most of which a given session never spawns. Add `CLAUDE.md` (2,412 words, about 3,300 tokens), two skill descriptions (about 170 tokens) and the MCP schemas (about 600): roughly **6,000 tokens of fixed overhead per session and per subagent that inherits it**. In a two-repo setup the brain's fixed overhead is paid by every project forever, so this number is the one to minimise.

**Per-spawn cost and duplication.** Each spawn loads its 700–1,170-word spec (about 1,000–1,600 tokens). Two paragraphs are pasted verbatim into 22 specs: the 100-word "Delegation and context" block and the 58-word product description (MEASURED), which is 3,476 duplicated words. Five engineering specs also repeat a 127-word Definition of Done and a 79-word PR template. The sample's own search code needed a near-duplicate filter specifically because of "the boilerplate section repeated in all 22 agent specs" (`SR/library/pipeline/search.py:73-75`).

**Which roles are generic.** Travel- or web-app-specific: data-sync-engineer, media-pipeline-engineer, frontend-mobile, frontend-web, mobile-ui-designer, web-ui-designer, motion-designer, effect-reproducer, performance-auditor (as written), accessibility-auditor (as written). Generic in function: chief-of-staff, product-manager, research-lead, tech-lead, qa-lead, security-reviewer, docs-writer, release-manager, design-critic, design-director, hr-lead, education-lead. The seven board seats are a generic "multi-perspective review" device with heavy prose.

**Collapse to parameterised archetypes.** Seven always-registered archetypes cover software, documents, research, data, design and automation:

| Archetype | Absorbs | Default tier | Tools | Parameterised by |
|---|---|---|---|---|
| `scout` | codebase search, fixture/mechanical helpers | fastest | read-only + Bash | query |
| `researcher` | research-lead, analysts, education-lead (content) | mid | read + web + Write to a memo path | question, sources, memo template |
| `planner` | product-manager, tech-lead (ADRs), design-director (specs), UI/motion designers | most capable | read + Write to docs paths | domain pack: software / document / data / design / automation |
| `builder` | all engineers, docs-writer, effect-reproducer | mid (capable for risky work) | full edit + Bash | domain pack, allowed paths, acceptance tests |
| `reviewer` | qa-lead, security-reviewer, accessibility and performance auditors, tech-lead reviews | capable | read-only + Bash | lens: correctness / security / accessibility / performance / factual accuracy |
| `critic` | design-critic, the seven board seats | most capable | read-only | lens and rubric; N lenses run as one fan-out, not N specs |
| `operator` | release-manager, platform-engineer, hr-lead, chief-of-staff bookkeeping | mid | edit + Bash | runbook |

Seven descriptions at about 25 words each is about 250 tokens always loaded, against about 2,100 now. Role specificity moves into small "lens" and "domain pack" files (150–300 words each) that the orchestrator names in the delegation prompt and the subagent reads on demand; the shared delegation contract is stated once. Projects may add their own specialised agents in the project repo, where the cost is paid only by that project.

### B.4 Skills

Two skills, both in `SR/.claude/skills/`.

- **`library/SKILL.md` (62 lines).** Front-matter `name` + `description` with trigger phrases. Body in two halves: "For Javier: how to use it" (examples, sample answer) and "For Claude: how to run it" (six numbered steps: map shelf words to corpus, prefer MCP `search`, fall back to the script, expand with `get_section`, answer in plain words with numbered sources, say so when nothing is found; lines 39-62).
- **`reproduce-effect/SKILL.md` (40 lines).** Same two-audience shape. The Claude half resolves the reference and licence, delegates the loop to the `effect-reproducer` subagent with an explicit context checklist ("it does not inherit your context", line 27), verifies the result itself, and reports in plain words. Numeric pass thresholds are stated (line 40). It sets a licence boundary (open-licensed references only, line 22).

Pattern quality: good and worth keeping. Strong points: trigger-rich descriptions, an owner-facing half that never asks for a command, graceful degradation (MCP then script then rebuild), an explicit "never answer from memory as if it came from the Library" rule, a delegation checklist, measurable thresholds, and a verify-before-answer step. Weak points: hard-coded names and paths (Javier, corpus ids, `library/.venv`), the owner-facing half is loaded into the model's context every time the skill runs (about half the file is documentation for a human), no `allowed-tools` or model hints, no supporting files for progressive disclosure, and the corpus mapping duplicates `config.json`. For the brain: keep the two-audience idea but put the human half in a separate README the skill links to, keep each `SKILL.md` body under about 300 words, and move detail into reference files read only when needed. Skills are the right home for most brain capability because only the description (about 50–80 tokens each) is always loaded.

### B.5 `orgdesign/hr.py` and `payroll/`

**orgdesign** (MEASURED: 1,945 non-test lines, 1,010 test lines, a 937 kB catalogue of 500 roles in 20 JSON files, `taxonomy.json`). `hr.py` itself is a 10-line entry shim; the logic is in:
- `demand.py` (203): turns ideas (priority-weighted P0=4 … P3=0.5) and open tickets into a skill-demand vector and a ticket load (docstring lines 1-18).
- `selection.py` (244): greedy weighted set cover, picking roles by marginal covered demand per cost until 80 % coverage, with governance pins (orchestrator, security reviewer, design critic), reviewer closure and sprawl rejection by Jaccard (lines 1-22).
- `combine.py` (251): constrained agglomerative clustering merging roles into multi-role agents (similarity = skill Jaccard + path overlap + bonuses), with hard separation-of-duties constraints: an author never merges with its reviewer, a read-only role never merges with a writer (lines 1-25).
- `plan.py` (365), `departments.py` (76), `render.py` (248), `validate.py` (120), `catalogue_io.py` (315), `pay.py` (84), `config.py` (71), `cli.py` (221).

Is it useful? The algorithms are sound and deterministic. In practice it answers a question a capable orchestrator can answer by reading a task list: "which few roles does this phase need?" Its Phase 1 output (`SR/docs/hr/staffing/phase-1.md:9-11`) is 8 standing agents plus 31 ephemeral roles at an estimated $290, while the actual roster stayed the hand-written 22. The inputs it needs (a 500-row idea table with themes, tickets in a fixed format, a 500-role catalogue) are expensive to produce for each new project, and the catalogue is saturated with travel-journal content. The catalogue also polluted retrieval until a -4 logit penalty was added (`SR/library/config.json:39-44`). Worth keeping: the **separation-of-duties rule** and the **utilisation rule** (a role expecting less than one task is spawned ad hoc, not kept standing).

**payroll** (MEASURED: 1,409 non-test lines, 696 test lines, stdlib only).
- `meter.py` (139): exact token usage per model from transcript JSONL, de-duplicated by message id. Generic and valuable.
- `pricing.py` (144) + `data/prices.json`: pinned price table and cost function. Useful but stale by design: it aliases `fable` to `claude-fable-5-1` and has no entry for `claude-fable-5-2` (`SR/payroll/data/prices.json:7-8, 20-21`), so current sessions price as unknown models.
- `estimator.py` (175): log-normal reference-class forecast with shrinkage (`w = n/(n+4)`) and robust scale from MAD. Reasonable statistics, never fed data.
- `allocator.py` (139): weighted max-min fairness for budget envelopes; Thompson sampling over Beta posteriors of reviewer acceptance to recommend the cheapest model that clears a quality threshold. The second half is the only component in the sample that resembles a real learning system, and it is the right idea for the brain's model routing.
- `enforcer.py` (69): spend states at 70/90/100 % with one response of grace; MAD-based anomaly flags.
- `negotiation.py` (124), `accuracy.py` (83), `books.py` (109), `ledger.py` (44), `cli.py` (286), `hooks.py` (93).

Is it useful? As built, no: `SR/docs/hr/payroll/REPORT.md` shows every role "uncalibrated (0 paired runs, 0 metered)" except the 10 seeded analyst runs; there are no grants, top-ups or settlements in the ledger. The measurement never persisted and the control loop never ran. The owner is on a Max subscription, where dollar credits are a proxy at best (`prices.json` itself records the window share as unknown).

**What to keep as a small "staffing and budget" script (about 300–350 lines, stdlib):**
1. `meter` (port, about 140 lines): tokens per subagent, per model, per task type, appended to a ledger that is committed with checkpoints.
2. A routing table learned from that ledger (about 80 lines): per (task type, model tier) keep counts of accepted and rejected results and median tokens; recommend the cheapest tier whose acceptance clears the bar (Thompson sampling or a plain lower confidence bound), never below a floor for security and final review.
3. A budget line per task (about 40 lines): median plus spread from history, warn at 70 % and 100 %, no hard blocking.
4. A staffing lint (about 40 lines): author is never its own reviewer; a role expected to do less than one task is not registered.
5. Prices in one small JSON updated by the learning job, with unknown models reported instead of silently skipped.

### B.6 PORT / REWRITE / DROP

| Component | Size now | Decision | Rationale | Replacement size |
|---|---|---|---|---|
| Heading-aware Markdown chunker, contextual prefix (`pipeline/chunker.py:54-296`) | ~300 lines | **PORT** (simplify) | Good logic; character budget replaces WordPiece counting | ~150 lines |
| TS/TSX regex code splitter (`chunker.py:298-428`) | ~130 lines | **REWRITE** | Language-specific; replace with a generic blank-line/def/class splitter plus `git grep` for code | ~60 lines |
| FTS5 store + query builder (`store.py`, `search.py:14-46`) | ~160 lines | **PORT** | Works on stdlib; drop the sqlite-vec load from the default path | ~100 lines |
| RRF, diversity filter, source prior (`search.py:60-96`) | ~40 lines | **PORT** | Tiny, dependency-free, measurably helpful | ~40 lines |
| Embeddings, sqlite-vec, cross-encoder (`embed.py`, `tokens.py`, vec table) | ~110 lines + ~500 MB of installs and models | **DROP from default; optional plug-in** | 5 points of recall@5 for minutes of cold start and ~2.4 s per query | optional module ~80 lines, off by default |
| MCP server (`mcp_server.py`) | 80 lines | **REWRITE** as optional thin wrapper; CLI is primary | Five schemas always loaded; verbose JSON results | CLI ~80 lines; optional MCP ~40 lines, two tools |
| Golden set + eval gate (`evaluate.py`, `golden.jsonl`) | 113 + 244 lines | **PORT the harness, DROP the data** | Gate is the right discipline; questions are travel-plan specific; add tokens-per-answer metric | ~90 lines + per-project golden file |
| `gen_golden.py` | 275 lines | **DROP** | Hand-written travel questions | brain skill that drafts golden rows per project |
| `config.json` corpora and doc kinds | 175 lines | **REWRITE** as per-project manifest section | All globs are travel-repo paths | ~30 lines of manifest |
| `rebuild.sh`, venv bootstrap | 19 lines | **DROP** | Not needed without dependencies | none |
| `snapshots/` (empty) | 0 | **REWRITE as a procedure** | Pinned-docs idea is right; make it a `docs fetch` step that stores trimmed snapshots in the project repo | skill ~150 words |
| Management cards (108 files) | ~8,000 words | **DROP from the brain core** (keep 1 page of the handful of rules actually cited) | Reading material, not operating instructions; large retrieval noise | 1 file, ~400 words |
| Effect cards + card format with measured front-matter | 3 files | **PORT the format** as the generic "pattern card" | Evidence-carrying, reusable knowledge unit | template ~120 words |
| `protect-paths.sh` | 73 lines | **REWRITE**, data-driven | Enforces brain immutability and owner-file protection from manifest globs; add Bash coverage | ~80 lines |
| `checkpoint-reminder.sh` | 33 lines | **PORT**, generalised | Cheap, effective, never blocks | ~40 lines |
| `session-start.sh` | 34 lines | **REWRITE** | Hard-coded sibling repo and heavy installs | ~40 lines |
| `payroll-gate.sh` + gate logic | 10 + ~25 lines | **DROP** | Never had a grant to enforce; blocks work on a proxy currency | none |
| `payroll-meter.sh` + `meter.py` | 8 + 139 lines | **PORT** | Exact usage data is the fuel for learning | ~150 lines |
| `pricing.py`, `prices.json` | 144 lines + data | **REWRITE** smaller | Keep cost function; current table lacks the current model | ~50 lines + JSON |
| `estimator.py`, `enforcer.py`, `accuracy.py` | 327 lines | **REWRITE** as one small budget module | Keep median/MAD forecast and 70/100 % warnings | ~70 lines |
| `allocator.py` Thompson model routing | ~50 lines | **PORT** | Genuine learn-from-outcomes routing | ~60 lines |
| `allocator.py` max-min allocation, `negotiation.py`, `salaries.py`, `books.py`, payroll `cli.py` | ~700 lines | **DROP** | Bureaucracy with no observed use | none |
| `orgdesign/*` engine | 1,945 lines | **DROP**, keep two rules as a lint | Solves a problem the orchestrator solves by reading the task list | ~40 lines |
| `orgdesign/catalogue` (500 roles) | 937 kB | **DROP** | Travel-saturated; hurt retrieval | ~10 lens files, ~200 words each |
| 30 agent specs | 27,082 words | **REWRITE** as 7 archetypes + lens/domain packs | Cut always-loaded descriptions about 8x and remove 3,500 duplicated words | 7 specs x ~250 words + ~12 packs x ~200 words |
| Board (7 seats, charter, operating system) | ~7,800 words of specs | **REWRITE** as one `critic` archetype with a lens list and a single fan-out skill | Same value (independent perspectives) at a fraction of the text | 1 skill ~250 words |
| `/library` skill | 62 lines | **PORT**, parameterised, human half moved out | Sound pattern | ~200 words |
| `/reproduce-effect` skill + `design-lab/` (Playwright capture, SSIM/pixel/easing comparison, 9 MB incl. fonts and captures) | 40 lines + lab | **PORT as an optional design plug-in**, not core | The measure-compare-iterate loop is generic and valuable for visual work; the weight belongs only in projects that need it | skill ~250 words; lab code copied on demand into the project repo |
| `CLAUDE.md` handbook | 2,412 words | **REWRITE** | Prime directives, resume loop, NEEDS_YOU/DECISIONS/PROGRESS protocol are generic and proven; phases, stack and facts about the product are project data | brain `CLAUDE.md` <= ~600 words; project manifest carries the rest |
| PROGRESS / NEEDS_YOU / DECISIONS / digest / ADR / lessons / gates file protocol | docs conventions | **PORT** | The strongest part of the sample; survives session loss; owner-readable | templates, ~600 words total |
| `.gitignore`d index and models | n/a | **REWRITE the policy** | A sub-second index needs no persistence; learned state (ledger, lessons) must be committed | n/a |

### B.7 Travel-journal hard-coding that a per-project manifest must parameterise

| Hard-coded item | Where |
|---|---|
| Sibling repo path `../Travel-Journal` | `SR/.claude/hooks/session-start.sh:12`; `SR/library/config.json:102, 173`; all engineering agent specs |
| Package manager and workspace layout (`pnpm`, `apps/*`, `packages/*`, `services/*`) | `SR/.claude/hooks/session-start.sh:17-18`; `SR/CLAUDE.md` §0, §9 |
| Protected owner files (`docs/MASTER_PLAN.md`, `KICKOFF_PROMPT.md`, `docs/NEEDS_YOU.md` heading "# Needs you") | `SR/.claude/hooks/protect-paths.sh:53-70` |
| Progress file path and its watched folder | `SR/.claude/hooks/checkpoint-reminder.sh:9, 25` |
| Ticket id patterns `TJ-NNN`, `R-Xnn` | `SR/payroll/payroll/hooks.py:17` |
| Owner's name in tool text, skills and block messages | `SR/library/mcp_server.py:26`; both `SKILL.md` files; `protect-paths.sh:55-64` |
| Corpus definitions, document kinds, authority priors | `SR/library/config.json:39-44, 53-174` |
| Code extensions limited to TS/JS/JSON/YAML/CSS | `SR/library/pipeline/ingest.py:21`; `SR/library/config.json:103-111` |
| English-only embedding model and porter stemmer | `SR/library/config.json:6, 36` (the owner's projects include Spanish and Japanese content) |
| Product description paragraph and stack rules inside 22 agent specs | e.g. `SR/.claude/agents/tech-lead.md` first body paragraph and "How you work" |
| Quality bar wording ("Apple first-party", "editorial"), Critic threshold, performance budgets | `SR/CLAUDE.md` §1.3, §9 |
| Phase list, gate definitions, idea numbering (`#081`), 500-idea coverage table | `SR/CLAUDE.md` §6, §9; `SR/orgdesign/demand.py:3-5` |
| Local stand-ins (Postgres, MinIO, PMTiles) | `SR/CLAUDE.md` §5 |
| Release rule and exact gate command for `javilfr/Travel-Journal` | `SR/CLAUDE.md` §11 |
| Role roster and default task classes | `SR/payroll/data/roles.json`, `salaries.json`; `SR/orgdesign/STANDING.md` |
| Model aliases and prices | `SR/payroll/data/prices.json:7-11` |
| Design-lab package name, viewports (`402x874@3`, `1512x982@2`), fonts | `SR/design-lab/package.json`; `SR/.claude/skills/reproduce-effect/SKILL.md:29` |
| Decisions reserved for the owner and their defaults | `SR/CLAUDE.md` §4 |

Suggested manifest fields (one small file in the project repo, e.g. `brain.project.json`): project name and type; owner-facing language rules; paths for progress, needs-owner, decisions, lessons; protected globs; knowledge globs with kind and prior; code languages; ticket id pattern; quality rubric and gate commands; release rule; model floors per task type; enabled optional plug-ins (dense retrieval, design lab); locally defined agents, skills and hooks.

---

## Summary of the most decision-relevant findings

1. Stdlib `sqlite3` has FTS5 here (SQLite 3.53.1); a zero-dependency BM25 index builds in 0.2 s and answers in under 2 ms.
2. On the sample's own 244-question golden set that baseline scores recall@5 0.87 and recall@10 0.93, against 0.914 for the full hybrid stack that takes about 2.45 s per query and several hundred MB of installs.
3. The sample's index, venv and models are gitignored, so each cold cloud session rebuilds them in the background while the MCP server it depends on cannot answer.
4. The MCP `search` result costs roughly 3,000 tokens per call; a compact CLI line format can cut that to about 600.
5. About 6,000 tokens of fixed overhead load every session (30 agent descriptions about 2,100, handbook about 3,300, MCP and skills about 800); in a brain attached to every project this is the number to minimise.
6. 30 agent specs total 27,082 words with about 3,500 words of pasted boilerplate; seven archetypes plus small lens files cover the same ground.
7. The payroll ledger holds only 10 seeded rows: metering never persisted, the gate never fired, every role is "uncalibrated".
8. The org-design engine (1,945 lines plus a 937 kB catalogue) produced plans that were not adopted and needed a retrieval penalty to stop polluting search.
9. The parts that clearly worked are the file protocol (PROGRESS, NEEDS_YOU, DECISIONS, digests, ADRs), the path-protection hook, the Stop reminder and the two-audience skill pattern.
10. Several rules in the handbook describe hooks that were never built (role path scopes, ADR check, ingest on merge); the brain should mechanise a rule or label it advice.
11. Thompson-sampling model routing from reviewer outcomes (`allocator.py`) is the one real learning mechanism and is worth porting with a persistent ledger.
12. "Quantum logic" and "machine learning systems" need honest reframing as deterministic scripts, retrieval, caching, routing statistics and an evaluation-gated, file-based learning loop that is the only writer to the brain.
