# 03 — Token efficiency and speed for Claude Brain (analyst 3 of 10)

Date: 2026-11-10. Lens: fewer tokens and less wall-clock time with quality held constant or improved.

Claim tags: **[local-doc]** = bundled claude-api reference under `/tmp/claude-0/bundled-skills/2.1.322/.../claude-api/shared/`; **[web: URL]** = fetched this session; **[local-obs]** = measured on this machine this session; **[inference]** = my reasoning, not a sourced fact; **[recalled]** = from memory, not re-fetched, treat as unverified.

Every measured number below is Anthropic's or a paper's result on *their* workload. None is a promise for Claude Brain. The brain's own ledger (section B5) is what makes a number true for Javier.

---

## PART A — Extraction of the owner's message 2

### A1. Requirements (what must exist)

| # | Requirement | Exact words |
|---|---|---|
| 1 | A new repo that plays the role the sample repo played | "create a repo that will act as that" |
| 2 | It is an orchestrator, and a large one | "essentially a mega complex orchestrator" |
| 3 | Scope is universal, not one product | "to build anything I will ever need from now on" |
| 4 | Two repos attached in every chat | "I will always use two repos in a chat" |
| 5 | Repo one is the brain | "one of them the Claude brain" |
| 6 | The brain changes only through its own learning machinery | "which will be only modified by its own machine learning systems" |
| 7 | The brain improves from every use | "as it improves by learning with everything I use it for" |
| 8 | Repo two is where the project is built | "the other repo will be where the project will be built" |
| 9 | The project repo may carry project-specific extensions to the brain | "which can also hold files and tools to complement the Claude brain functionality that are specific to that project" |
| 10 | A permanent brain-to-project contract | "both will always be worked together from now on so the project must be built to work perfectly with it forever" |
| 11 | Deliverable one: a plan, very long and very detailed | "create a super long, super detailed plan on how to build this" |
| 12 | The plan rests on model-specific research | "based on very comprehensive research about Claude fable 5.2 and opus 5.5 (the main models ai will use it with)" |
| 13 | The plan reuses the sample repo's lessons | "using everything we learned with the sample repo I attached" |
| 14 | The plan generalises beyond the sample's scope | "obviously having present that the current Claude brain's scope for creating stuff is much bigger" |
| 15 | Mine memory and every past chat | "you must look at all your memory in detail and all our chats" |
| 16 | Coverage test: every past request and question must be completable by the brain | "consider everything I have ever asked you to build on Claude or any question I have ever asked you can be successfully processed to completion" |
| 17 | Efficiency is the top-priority constraint | "Also VERY IMPORTANT, you MUST MAKE THIS THE MOST EFFICIENT CLAUDE TOOL EVER" |
| 18 | Token efficiency through specific means | "much more efficient in tokens through plugins and algorithms and quantum logic and many other thing you must research" |
| 19 | Speed | "super efficient token wise and super fast" |
| 20 | Quality is not traded away | "while delivering the absolutely highest quality work with absolute attention to detail" |
| 21 | Three named quality axes | "focus a lot on accuracy, creativity and extreme attention to detail" |
| 22 | The plan also draws on earlier Claude builds | "considering also all our previous builds in Claude" |
| 23 | Deliverable two: build it, to completion, after the plan | "then start building until completion once you have a full plan based on extremely extensive research" |
| 24 | Process requirement: ten independent analyses of the prompt | "Make sure you analyze this prompt by 10 independent agents and extract everything I said in full detail" |
| 25 | Execution standard | "you can execute to perfection by planning perfectly and researching and analyzing heavily everything" |

### A2. Constraints

26. The sample repo is read-only. Message 1: "we will not modify or touch this repo at all in this chat, just read it".
27. Two models are the design targets: "Claude fable 5.2 and opus 5.5 (the main models ai will use it with)". ("ai" reads as a typo for "I".)
28. The brain must not be hand-edited during project work (item 6). This implies a write-path policy: project sessions write to the project repo; the brain repo accepts writes only from its learning pipeline.
29. Order of work: plan first, then build ("once you have a full plan").

### A3. Preferences and implied expectations

30. Javier does not want to re-explain himself per project. Implied by "from now on" and "forever": the brain carries his standing preferences. [inference]
31. He expects the sample repo's proven parts to carry over: handbook, resume loop, NEEDS_YOU, ADRs, the Library RAG and MCP server, agent roster, hooks, payroll ledger. Implied by "used this repo as a brain to create everything in my travel journal in the best possible way". [inference; the sample repo contains all of these, plus a `payroll/` token ledger fed by a `SubagentStop` hook — local-obs]
32. He works by clicking and reading, never by shell. From the known context and the sample CLAUDE.md, so every measurement or control the brain offers must be a file or a button. [local-obs]
33. "plugins" suggests he expects Claude Code plugin packaging, or at least installable extensions. [inference]
34. "learning" implies visible evidence of improvement over time. A ledger with before/after numbers is the natural proof. [inference]
35. "super long" applies to the plan document. It does not apply to always-loaded instruction files, where length is a recurring cost (B3, T3). The plan must say this plainly so length in one place is not copied into the other. [inference]

### A4. Ambiguities

36. "machine learning systems" — no model training is possible from inside a repo. See A5.
37. "only modified by its own machine learning systems" versus the initial build, where a lead session writes the brain. Does the rule start after v1? Assumed yes.
38. "all our chats" — which surfaces? claude.ai chat history, Claude Code session transcripts, project memory? Access differs by surface.
39. "plugins" — Claude Code plugins, MCP servers, or a loose word for add-ons?
40. "build anything" — software only, or also documents, research, design, data analysis? The breadth of "any question I have ever asked" suggests all of them.
41. "start building until completion" — completion of the brain v1, with what acceptance test? The message gives none. The plan needs an explicit gate list.
42. "the project must be built to work perfectly with it forever" — who owns the interface version when the brain evolves and old project repos do not?
43. "10 independent agents" — independent of each other (no shared context), which is how this run is set up.

### A5. Impossible as stated, or needing an honest reframe

| Phrase | Problem | Honest reframe |
|---|---|---|
| "quantum logic" | No quantum hardware or quantum algorithm is reachable from Claude Code. Nothing in the fetched Anthropic docs or papers uses one. | Say so directly. Offer what the phrase is reaching for: classical algorithms that cut work, namely ranked retrieval (BM25 + dense + rerank), graph ranking for repo maps, cascades and routing, caching, and parallel exploration of alternatives. Do not label anything in the repo "quantum". |
| "its own machine learning systems" | A repo cannot retrain Claude. | A file-based learning loop: token ledger, lessons, evals, a golden set, and a gated pipeline that proposes edits to skills, cards and routing tables and keeps them only when an eval holds. That is learning in the operational sense, and it is measurable. |
| "THE MOST EFFICIENT CLAUDE TOOL EVER" | Unverifiable superlative. | A measurable target: tokens and minutes per completed task, tracked per task class in the ledger, with a stated baseline and trend. |
| "all your memory … all our chats" | A session sees only what is attached or reachable. It cannot guarantee complete recall of every past chat. | Mine everything reachable, list what was reachable and what was not, and let Javier add missing items to a file. |
| "can be successfully processed to completion" for "anything" | No system can guarantee completion of arbitrary tasks. | A coverage matrix: each past request class maps to a brain capability, with gaps listed. |
| "forever" | Models, Claude Code and the API change. Fable 5.2 already enforces rules Fable 5 did not [local-doc]. | A versioned brain-to-project contract plus a scheduled re-audit when a model or Claude Code version changes. |
| "super long … plan" and "10 independent agents" versus "most efficient" | These pull in opposite directions. Anthropic measured multi-agent systems at about 15× the tokens of chat [web: https://www.anthropic.com/engineering/multi-agent-research-system]. | Spend heavily once on design, since it is a one-off. Make the *runtime* frugal. State this trade openly in the plan. |
| "absolutely highest quality" and "most efficient" at once | On hard work there is a real cost–quality curve (B2, T20). | Free wins first, which cost no quality. Trade-off levers only with an eval. Default to quality when unmeasured. |

---

## PART B — Catalogue of token and time levers

### B0. Where the tokens actually go (read this first)

**Price structure.** Fable 5.2: $8 input, $40 output, $0.20 cache read (0.025×), $10 five-minute cache write, $16 one-hour cache write, per million tokens. Opus 5.5: $4 / $20, cache read $0.20 (0.05×). Sonnet 5.5: $2 / $10, cache read $0.10. Haiku 5.5: $0.10 / $0.50 up to 100K prompt tokens, then $0.50 / $2.50. [local-doc: models.md]

Consequences on Fable 5.2 [inference from those prices]:

- One output token costs as much as 200 cached-read tokens.
- One one-hour cache-write token costs as much as 80 cached-read tokens.
- Thinking is billed as output. [web: https://code.claude.com/docs/en/costs]

So the order of concern is: output and thinking first, cache writes and cache misses second, uncached input third, cached re-reads last.

**Measured on this very session** [local-obs: lead transcript `/root/.claude/projects/-home-user/ad24da2f-….jsonl`, 38 assistant requests]:

| Meter | Tokens | Cost at Fable 5.2 list price | Share |
|---|---|---|---|
| Uncached input | 83 | $0.00 | 0% |
| Cache read | 5,218,870 | $1.04 | 7% |
| Cache write (1-hour) | 322,108 | $5.15 | 36% |
| Output (thinking included) | 203,926 | $8.16 | 57% |

Cache reads are 91% of the token count and 7% of the cost. Output is 3.5% of the tokens and 57% of the cost. A plan that optimises raw token counts will optimise the wrong thing. (A Max subscriber is not billed these dollars; how plan limits weight each meter is not published, so dollars are used here as the best available proxy. [inference])

**Quadratic growth.** Every turn resends the whole conversation, so "a 40-turn task sends its first turn 40 times and task cost grows with roughly the square of turn count". Caching reprices the resend; it does not remove it. [local-doc: cost-optimization.md §2.1]

**Time.** `task time = calls × time to first token + output tokens ÷ output speed + everything else`. Five ways to go faster: fewer calls, shorter time to first token, fewer output tokens, faster output, less time outside the model. [local-doc: latency-optimization.md]

**Unit of account.** "cost per completed task, not cost per token". A cheap attempt that fails bills its tokens, then the retry. [local-doc: cost-optimization.md]

### B1. Technique catalogue

"CC" = controllable from inside a Claude Code repo. "API" = needs direct API access, which Claude Code manages for you.

#### Group 1 — Keep the prompt cache intact

**T1. Never break the cached prefix mid-session.**
- Mechanism: caching is an exact prefix match over tools → system → messages. Any change early invalidates all that follows. [local-doc: prompt-caching.md]
- Saving: cached input and time to first token.
- Measured: without caching, cost was 3.3× (SWE-bench Pro, Opus 5.5), 3.1× (Sonnet 5.5), 7.3× (triage agent). DeepResearch Bench II on Fable 5.1 fell from $40.58 to $5.64 per task with caching. A healthy loop reads a median 84% of input from cache; below about 80%, look for a breaker. A system-prompt edit on a 100K cached conversation cost up to $1.26, 25–50× the same text sent as a message. A 25-token status line at the front of the system prompt made every request rewrite the whole conversation. [web: https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence.md]
- Quality risk: none.
- Control: CC, by avoiding the breakers Claude Code documents: model switch, fast-mode toggle, adding or removing upfront-loaded tools, plugin MCP changes, bare-tool deny rules without tool search, compaction, image accumulation. [web: https://code.claude.com/docs/en/prompt-caching]
- Brain sketch: a `cache-hygiene` rule in the handbook. Choose model at session start and keep it. No `/model` mid-task. No MCP connect or disconnect mid-task. A `PreModelSwitch` hook that warns. A CI lint that rejects timestamps, counters or "last updated" lines in `CLAUDE.md` and other always-loaded files.

**T2. Do not put a different `model:` in skill frontmatter.**
- Mechanism: "When a skill or command's frontmatter names a model other than the session's current model, that turn is also a model switch: the next request reads the entire conversation history with no cache hits." [web: https://code.claude.com/docs/en/prompt-caching]
- Saving: avoids a full cold re-read, twice (switch out, switch back). At 300K context on Fable that is roughly 300K × $16/M ≈ $4.80 per cold write against $0.06 for a cached read. [inference from prices]
- Measured: "Switching from Opus to Haiku 100k tokens into a conversation can cost more than letting Opus answer." [web: https://claude.dev/blog/lessons-from-building-claude-code-prompt-caching-is-everything/]
- Control: CC. Use `context: fork` with `agent:` so the cheaper model runs in a subagent with its own small prefix.
- Brain sketch: lint rule: a skill may set `model:` only together with `context: fork`.

**T3. Stable, small always-loaded files; dynamic state by reference.**
- Mechanism: `CLAUDE.md` loads at session start and into most subagents. Content there is paid on every request (cached) and written once per session and per subagent (uncached write).
- Saving: cache writes, cached input, and attention.
- Measured: guidance to "keep CLAUDE.md under 200 lines"; `/usage` flags rows such as "Trim CLAUDE.md · 49k tokens per request". [web: https://code.claude.com/docs/en/costs] Prompts carried over unaudited to a newer model cost more at no accuracy gain; removing "verify twice" and "be maximally thorough" cut cost per ticket; removing stale and contradictory rules restored accuracy. [web: optimizing-for-cost-and-intelligence.md]
- Quality risk: low, and often positive. Risk appears if a rule the model needs every time is moved behind a lookup.
- Control: CC.
- Brain sketch: brain `CLAUDE.md` of at most 150 lines holding identity, prime directives, the routing table and pointers. `PROGRESS.md`-style state is read on demand, never inlined. The sample `CLAUDE.md` is 16.5 KB [local-obs]; with two repos attached, both handbooks load in every session and in every non-Explore subagent, so the budget applies to the sum.

**T4. Effort changes are cache-safe on these models; use them instead of model switches.**
- Mechanism: "With an API key or a Claude subscription, changing effort keeps the cache on Fable 5.1 and later, Opus 5.5, Sonnet 5.5, and Haiku 5.5." [web: https://code.claude.com/docs/en/prompt-caching]
- Saving: thinking and output tokens on easy turns, without a cache rebuild.
- Measured: see T20.
- Control: CC (`/effort`, skill `effort:` frontmatter, subagent `effort:`).

**T5. Compact at task boundaries, rewind instead of compacting a dead end, clear between unrelated tasks.**
- Mechanism: compaction rebuilds the conversation layer. `/rewind` returns to a prefix that is already cached. `/clear` costs nothing. [web: https://code.claude.com/docs/en/prompt-caching]
- Measured: compaction saved 32% on a long run and nothing on a 20-issue run. A compaction trigger of 90,000 cost 70% less per request than 150,000 on 10,000-token turns. Compaction timed after a natural break cost $0.75 per triage session against $0.95 mid-session. [web: optimizing-for-cost-and-intelligence.md]
- Quality risk: compaction loses detail. Mitigate with durable notes (T12) and compact instructions.
- Control: CC: a "Compact instructions" section in `CLAUDE.md`, a `PreCompact` hook whose stdout becomes summary instructions [web: https://code.claude.com/docs/en/hooks], and `autoCompactWindow` in subagent frontmatter (100,000–1,000,000) [web: https://code.claude.com/docs/en/sub-agents].
- Brain sketch: the resume loop ends each ticket by checkpointing to files. A `PreCompact` hook emits "keep: ticket id, decisions, open file paths, failing test names".

**T6. Cache lifetime awareness.**
- Mechanism: on a subscription within plan usage the main conversation gets a one-hour TTL; subagents get five minutes unless `experimental.cacheTtl: 1h` or `subagentPromptCacheTtl` is set. [web: https://code.claude.com/docs/en/prompt-caching]
- Saving: avoids cold re-reads after pauses.
- Measured: a one-hour write on Opus 5.5 at 100,000 tokens cost $0.80 against $0.02 for a turn that read the cache. [web: optimizing-for-cost-and-intelligence.md]
- Control: CC, partially. Javier's pauses are his own.
- Brain sketch: resumed subagents idle past five minutes start cold, so the lead should send follow-ups promptly or start fresh with a file handoff. Tell Javier in the user guide that returning within an hour is cheaper than returning after two.

#### Group 2 — Send less input

**T7. Skills for progressive disclosure.**
- Mechanism: only the description sits in context; the body loads on invocation, appended as a message, so the cache holds. [local-doc: agent-design.md; web: https://code.claude.com/docs/en/prompt-caching]
- Saving: input, cache writes.
- Measured: no single percentage for skills. Facts that bound the design: description plus `when_to_use` is truncated at 1,536 characters; `SKILL.md` should stay under 500 lines; after compaction each skill keeps its first 5,000 tokens within a shared 25,000-token budget; `disable-model-invocation: true` removes the description from context. [web: https://code.claude.com/docs/en/skills]
- Quality risk: a skill that fails to trigger means missing guidance. A deferred document can cost "discovery turns". [local-doc: cost-optimization.md §2.2]
- Control: CC.
- Brain sketch: one skill per workflow. The first 5,000 tokens hold the rules that must survive compaction. Long references live in sibling files. Rarely used, owner-triggered skills get `disable-model-invocation: true`.

**T8. Tool search and deferred MCP tools.**
- Mechanism: only names and server instructions load until a tool is needed. Definitions are appended, so the cache holds. [web: https://code.claude.com/docs/en/costs]
- Measured: about 85% fewer tool-definition tokens (roughly 77K down to 8.7K); accuracy on MCP evaluations rose from 49% to 74% (Opus 4) and 79.5% to 88.1% (Opus 4.5). [web: https://www.anthropic.com/engineering/advanced-tool-use] At 502 tools, run cost stayed at $0.56 with tool search against $1.02 with all tools loaded. [web: optimizing-for-cost-and-intelligence.md] Pays above about 10K schema tokens; below that the search step is overhead. [local-doc]
- Control: CC. It is the default. Do not disable it.
- Brain sketch: keep the Library MCP surface to five or six tools with short server instructions, since instructions are always loaded.

**T9. Prefer a CLI or script over an MCP tool when both exist.**
- Mechanism: CLI tools "don't add any per-tool listing". [web: https://code.claude.com/docs/en/costs]
- Measured: no number found.
- Control: CC.
- Brain sketch: brain utilities ship as scripts under `scripts/` called through Bash. MCP is reserved for retrieval, where typed arguments and result shaping earn their place.

**T10. Token-efficient tool results (the retrieval server above all).**
- Mechanism: return ranked snippets with stable readable ids, a `response_format` of concise or detailed, `limit`, pagination and truncation with a hint on how to get more.
- Measured: a concise response used about a third of the tokens of a detailed one (72 against 206). Claude Code caps tool responses at 25,000 tokens by default. Resolving UUIDs to readable names reduced hallucination. [web: https://www.anthropic.com/engineering/writing-tools-for-agents] Rewriting flawed tool descriptions cut later agents' task time by 40%. [web: https://www.anthropic.com/engineering/multi-agent-research-system]
- Quality risk: over-truncation hides the needed passage. Mitigate with `get_section(id)` for the full text.
- Control: CC (the MCP server is the brain's own code).
- Brain sketch: `search` returns at most five hits by default, each with id, title, a 40–80 token snippet and a score; hard cap near 1,500 tokens. `get_section` returns one section. `cite` returns only path and anchor. Errors say what to do next.

**T11. Retrieval instead of inlined reference material.**
- Mechanism: just-in-time loading through lightweight identifiers. [web: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents]
- Measured: a 1,862-row CSV pasted into the prompt scored 7 of 25 at $5.01; the same data queried through code scored 25 of 25 at $0.40. [web: optimizing-for-cost-and-intelligence.md] Chroma's "context rot" study found all 18 tested models degrade as input grows, even with task difficulty held constant. [web, via search summaries of the Chroma report; primary not fetched] Hybrid BM25 plus contextual embeddings plus rerank reducing retrieval failures by 49–67%. [recalled: Anthropic contextual retrieval post]
- Quality risk: retrieval misses. "a document in the cached prefix is cheap" when most calls need most of it. [local-doc]
- Control: CC.
- Brain sketch: keep the sample's design (FTS5 + sqlite-vec + RRF + rerank 20→5, golden set, recall@5 ≥ 0.9) [local-obs: sample CLAUDE.md §7]. Add a per-query token cost column to the eval so recall and tokens are tracked together.

**T12. Durable notes outside the context window.**
- Mechanism: the agent writes state to files and reloads only what it needs. [web: effective-context-engineering]
- Measured: memory tool plus context editing improved an agentic search eval by 39% over baseline. [web: https://claude.com/blog/context-management]
- Control: CC: files, plus subagent `memory: project`.
- Brain sketch: `PROGRESS.md` under 40 lines, a per-ticket scratch note, and a lessons index that is searched, never loaded whole.

**T13. Hooks and scripts that filter before the model sees anything.**
- Mechanism: a `PreToolUse` hook rewrites a command through `updatedInput` so only failures return.
- Measured: "reducing context from tens of thousands of tokens to hundreds" (illustrative, in the docs). [web: https://code.claude.com/docs/en/costs]
- Quality risk: a filter that hides the one line that mattered. Keep the full log on disk and print its path.
- Control: CC. Hook-injected context is capped at 10,000 characters; beyond that the model gets a path and a 2,000-character preview. `command` hooks cost no model tokens; `prompt` and `agent` hooks do. [web: https://code.claude.com/docs/en/hooks]
- Brain sketch: wrappers `brain test`, `brain lint`, `brain build` that print a 20-line verdict and a log path. Use `command` hooks only on the hot path.

**T14. Repo map and symbol navigation instead of exploratory reads.**
- Mechanism: a ranked symbol outline (aider: tree-sitter tags, PageRank over the reference graph, rendered to a token budget of about 1K by default) [web, via secondary sources on aider; primary docs not fetched]. Claude Code's code-intelligence plugins make "go to definition" one call in place of "a grep followed by reading multiple candidate files". [web: https://code.claude.com/docs/en/costs]
- Measured: no measured number found for either.
- Control: CC.
- Brain sketch: a script generates `docs/MAP.md` in each project repo (tree plus exported symbols, capped near 1,500 tokens), refreshed by a post-merge hook and fetched on demand. Enable the LSP plugin for typed projects.

**T15. Size images and files before they enter context.**
- Mechanism: vision cost scales with pixel area, about one token per 28×28 patch; 1280×720 caps an image near 1,200 tokens. [local-doc] Accumulated images also force batch removals that break the cache. [web: prompt-caching page]
- Control: CC.
- Brain sketch: a screenshot helper that downsizes before Read; design critique runs in a subagent so images never enter the lead's context.

**T16. Specific task statements.**
- Mechanism: "Vague requests … trigger broad scanning." [web: costs page]
- Measured: no number found.
- Brain sketch: an intake skill turns a loose request into a ticket with paths, an acceptance test and a verification target before any work starts. This is where "accuracy" and "efficiency" align.

#### Group 3 — Fewer turns, and turns that overlap

**T17. Parallel independent tool calls in one message.**
- Mechanism: each avoided turn saves a full context re-read and a time-to-first-token. Read-only tools are parallel-safe. [local-doc: agent-design.md, levers.md]
- Measured: parallel tool calling "cut research time by up to 90% for complex queries". [web: multi-agent-research-system]
- Quality risk: none for independent reads.
- Control: CC, by instruction.

**T18. Move control flow into code.**
- Mechanism: a script loops, filters and aggregates; only the result enters context.
- Measured: 37% fewer tokens on complex research tasks (43,588 to 27,297), with accuracy up; 20 tool calls in one block remove 19 inference passes. [web: advanced-tool-use] 24% fewer input tokens on agentic search with a higher score. [web: optimizing-for-cost-and-intelligence.md] An illustrative MCP case went from 150,000 to 2,000 tokens (98.7%); the article's own example, not a benchmark. [web: https://www.anthropic.com/engineering/code-execution-with-mcp]
- Quality risk: the model reasons over less intermediate data. Poor fit when each step depends on reading the last.
- Control: programmatic tool calling proper is API. The equivalent in CC is Bash plus scripts, and it is fully available.
- Brain sketch: a "write a script when you would make more than three similar calls" rule. Proven scripts are promoted into `scripts/` by the learning pipeline, which is the skill-accumulation pattern the MCP article describes.

**T19. Prefetch predictable context.**
- Mechanism: run the predictable first calls before the model starts. [local-doc: levers.md]
- Measured: no number found.
- Control: CC: skill dynamic injection with `` !`command` `` and `SessionStart` hook stdout. [web: skills page, hooks page]
- Quality risk: prefetching things that are not needed adds input to every later turn. Keep it under about 500 tokens.
- Brain sketch: `SessionStart` prints branch, current ticket and blockers in ten lines. Note the sample's hook has a 900-second timeout [local-obs]; anything slow there delays every session.

**T19b. Plan before executing; course-correct early.**
- Mechanism: prevents "expensive re-work when the initial direction is wrong". [web: costs page]
- Measured: no number found.
- Control: CC.

#### Group 4 — Fewer output and thinking tokens

**T20. Match effort to the task class.**
- Mechanism: effort scales thinking, text and tool-call depth.
- Measured [web: optimizing-for-cost-and-intelligence.md]:
  - Opus 5.5, SWE-bench Pro subset: low 87.4% at $0.11; medium 92.8% at $0.21; high 95.3% at $0.29; xhigh 96.7% at $0.74.
  - Fable 5.2, same subset: low 94.6% at $0.39; high 96.3% at $1.39.
  - Fable 5.2, DeepResearch Bench II: low 54.5% at $1.49; medium 55.0% at $2.16; high 57.7% at $4.82. High bought 3.3 points for 3.2× the cost.
  - Opus 5.5 low against medium: DRACO 84% less time but 13.3 points lower; internal defect search 34 points lower at a fifth of the cost. Low effort is not safe everywhere.
- Quality risk: real, and workload-specific.
- Control: CC, and cache-safe (T4).
- Brain sketch: a routing table keyed by task class (mechanical edit, search, routine implementation, architecture, critique, security) giving model and effort. The learning pipeline may only lower a cell when the ledger and an eval both hold.

**T21. Escalate on failure instead of running everything high.**
- Mechanism: run low, re-run only failures higher. Needs a reliable failure signal.
- Measured: low then high on failures solved about 97% at about $0.17 per task, against 95.3% at $0.29 for everything at high: about 40% less at the same pass rate. [web: optimizing-for-cost-and-intelligence.md]
- Quality risk: low when tests are trustworthy. Adds latency on failures.
- Control: CC, by orchestration.
- Brain sketch: this is the strongest argument for the brain insisting on a verification target per ticket. Tests are the failure signal that unlocks the cheap path.

**T22. Specify output shape; write to files; return references.**
- Mechanism: the model stops narrating. Subagents store work externally and "pass lightweight references back". [web: multi-agent-research-system]
- Measured: a one-line format cost $0.49 per run, a two-line format $0.57, a six-section memo $1.40, all 78–85% correct. [web: optimizing-for-cost-and-intelligence.md] Sub-agents return "a condensed summary of about 1,000–2,000 tokens". [web: effective-context-engineering]
- Quality risk: a shape can cut content the task needs. [local-doc]
- Control: CC.
- Brain sketch: every agent spec ends with a return contract: a word cap, fixed fields, and file paths for the detail. Reports for Javier are files; chat replies are short.

**T23. Edit by diff, never rewrite whole files.**
- Mechanism: output tokens scale with the changed region.
- Measured: no Anthropic number found. Aider reported that unified diffs made GPT-4 Turbo markedly less "lazy" [recalled; a search this session did not confirm the figure].
- Control: CC: prefer Edit over Write for existing files; generate large boilerplate with scripts.

**T24. Do not ask for visible reasoning or redundant verification.**
- Mechanism: "show your thinking" adds output and can trigger a refusal on some models. [local-doc: levers.md]
- Measured: removing "verify twice" cut Opus 5's cost per ticket; removing "be maximally thorough" cut it almost as much. [web: optimizing-for-cost-and-intelligence.md]
- Brain sketch: run a prompt audit on every brain file at each model change. The owner's own wording ("absolute attention to detail", "perfectly") must not be pasted into agent prompts as intensifiers; encode it as checks instead.

**T25. Tell the agent that time matters and show elapsed time.**
- Measured: Opus 5.5 at medium, median DRACO task: 47% less time, 60% less cost, 4.1 points lower. [web: optimizing-for-cost-and-intelligence.md]
- Quality risk: yes, a measured score cost.
- Control: CC, as an appended message from a hook, never in `CLAUDE.md`.
- Verdict: a trade-off; use only for low-stakes task classes.

#### Group 5 — Delegation and routing

**T26. Subagents for bulky, self-contained steps.**
- Mechanism: the subagent absorbs heavy tool output and returns a summary. [web: costs page]
- Saving: the lead's context stays small, so every later lead turn is cheaper and sharper.
- Measured cost of overuse: agents use about 4× the tokens of chat, multi-agent about 15×. [web: multi-agent-research-system] Agent teams use about 7× a standard session when teammates run in plan mode. [web: costs page] A subagent "starts a fresh prefix with no cache shared with the parent". [local-doc]
- Measured benefit: 90.2% better than single-agent on Anthropic's research eval, where token usage alone explained 80% of the variance, so the gain is bought with tokens. [web: multi-agent-research-system]
- Poor fit: "Most coding tasks", tasks with shared context, tasks with many dependencies. [web: same]
- Control: CC.
- Brain sketch: a delegation test with three questions. Is the step self-contained? Is its raw output large compared with what the lead needs? Can the result be checked? Two yeses to delegate.

**T27. Cheaper model for worker subagents.**
- Measured [web: optimizing-for-cost-and-intelligence.md]: Opus 5.5 with Sonnet 5.5 subagents matched Opus 5.5 alone on defect search for about a third less. Haiku 5.5 subagents under an Opus 5.5 orchestrator cut cost per attempt 32% with the pass rate about 4 points lower. Fable 5.2 as orchestrator in place of Opus 5.5 cost 19% more for about the same score. Sonnet 5.5 at default solved 87.6% of a SWE-bench Pro subset at $0.11; Opus 5.5 at medium 92.8% at $0.22; Fable 5.2 at high 96.3% at $1.39. Anthropic's starting advice: Opus 5.5 at medium for most agent work; Fable 5.2 when Opus at higher effort still falls short; Haiku 5.5 for high-volume checkable work.
- Third-party routing results, best cases on their benchmarks: RouteLLM "up to 85%" cost reduction on MT Bench at 95% of GPT-4 quality, 45% on MMLU, 35% on GSM8K; FrugalGPT "up to 98%". [web, via search of the project pages and abstracts] Treat both as upper bounds.
- Quality risk: real. "Price the tail, not the median": on one 20-problem run two problems carried 43% of spend. [local-doc]
- Control: CC: subagent `model:` and `effort:` frontmatter; `CLAUDE_CODE_SUBAGENT_MODEL` as a default. [web: sub-agents page]
- Brain sketch: lead on Opus 5.5 medium by default, Fable 5.2 for architecture, hard debugging and final critique. Workers on Sonnet 5.5; search and fixtures on Haiku 5.5, kept under 100K context because Haiku's price rises 5× above that [local-doc]. Note the built-in Explore agent runs on the Opus alias for subscribers, not Haiku; define a project `Explore` with `model: haiku` if cheap exploration is wanted. [web: sub-agents page]

**T28. Lean subagent start-up.**
- Mechanism: most subagents load all `CLAUDE.md` files and a git snapshot; Explore and Plan skip them; `omitClaudeMd: true` skips them for a custom agent; `tools:` narrows the tool list; `skills:` preloads full skill bodies. Combined custom-agent descriptions above 15,000 tokens trigger a warning. [web: sub-agents page]
- Saving: a cold cache write per subagent, at 1.25× input price.
- Measured: no number found. Size it locally: two handbooks of about 4,500 tokens each, times ten analysts, is about 90K tokens of cold writes that a self-contained brief would avoid. [inference from local-obs]
- Quality risk: a worker without the handbook may break a house rule. Put the two or three rules it needs in its own prompt.
- Control: CC.
- Brain sketch: worker specs set `omitClaudeMd: true`, an explicit `tools:` list, `maxTurns`, and a one-line description. The sample's 30 agent files total 184 KB, but only descriptions load until use [local-obs]; keep descriptions under about 200 characters.

**T29. Fork when the child needs the parent's context; fresh subagent when it does not.**
- Mechanism: a fork "inherits the parent's system prompt, tools, and conversation history exactly, so its first request reads the parent's cache". [web: prompt-caching page]
- Trade: a fork starts warm but re-reads the whole parent context on each of its turns; a fresh agent starts cold but small. [inference]
- Control: CC (`context: fork`, `CLAUDE_CODE_FORK_SUBAGENT`).

**T30. Reuse plans and prior results.**
- Mechanism: store plan templates from completed runs; match new requests; adapt with a light model.
- Measured: agentic plan caching cut cost 50.31% and latency 27.28% across five workloads while keeping 96.61% of optimal performance. [web: https://arxiv.org/abs/2506.14852, v2 figures]
- Quality risk: a stale or mismatched template. Keep a human-readable match reason and an expiry.
- Control: CC, through the Library.
- Brain sketch: a `playbooks/` collection, one per task class, written by the learning pipeline from successful tickets and retrieved with `search` before planning. This is the most concrete form of "learning with everything I use it for".

#### Group 6 — Techniques that are mostly out of reach or poor fits

**T31. Prompt compression (LLMLingua and similar).** Up to 20× compression with a 1.5-point loss on GSM8K and BBH; 3–9× on conversation and summarisation. [web: Microsoft Research blog and arXiv 2310.05736 via search] In Claude Code the always-loaded text is already repriced to a fortieth by caching, and lossy token dropping on instructions risks exactly the accuracy the owner ranks first. Marginal at best for raw tool output, where deterministic filtering (T13) is safer. [inference]

**T32. Semantic response caching.** No measured number verified this session. Claude Code exposes no response cache. The useful analogue is T30 plus Library lookups of prior decisions.

**T33. Batch API (50% off).** [local-doc] API only; not available to an interactive Claude Code subscriber.

**T34. Message threads, explicit cache breakpoints, task budgets, stop sequences, `max_tokens` tuning, per-message effort fields, advisor tool configuration.** API-level. Claude Code manages these. Listed so the plan does not promise them. Advisor results were weak in any case: +1.7 points at 2.1× cost on coding, and no consultation at all on two other benchmarks. [web: optimizing-for-cost-and-intelligence.md]

**T35. Terse serialisation formats (for example TOON) in place of JSON.** No measured number verified this session. Low-risk only inside the brain's own tool results, as compact line-oriented text. Never invent a house shorthand for prose (see "do not do").

### B2. Ranking

**Free wins (no quality cost; do all of them)**

1. T1 cache discipline, including T2 (no `model:` in inline skills) and T4 (effort, not model, for mid-session changes).
2. T3 small, stable always-loaded files across both repos.
3. T7 skills for everything workflow-specific.
4. T10 token-shaped Library results with `get_section` for depth.
5. T13 filter-first wrappers and hooks for tests, builds and logs.
6. T17 parallel read-only calls.
7. T22 return contracts and file handoffs.
8. T23 diff edits.
9. T24 prompt audit: no intensifiers, no "verify twice".
10. T5 compact at boundaries, rewind dead ends, clear between tasks.
11. T12 durable notes.
12. T8 leave tool search on; T9 prefer scripts to MCP.
13. T16 intake that produces a specific ticket with a verification target.
14. The ledger itself (B5); without it nothing else can be learned.

**High leverage, with trade-offs (apply by task class, confirm with ledger and eval)**

15. T20 effort routing.
16. T21 escalate on failure.
17. T27 cheaper worker models.
18. T26 delegation of bulky steps.
19. T28 lean subagent start-up (`omitClaudeMd`).
20. T18 scripts in place of tool-call chains.
21. T30 playbook reuse.
22. T11 retrieval over inlining, with the "most calls need most of it" exception.
23. T14 repo map and LSP.
24. T19 small prefetch.

**Marginal**

25. T25 time-pressure messages (measured score cost).
26. T6 TTL tuning.
27. T29 fork versus fresh, case by case.
28. T15 image sizing (large only for design-heavy projects).
29. T35 compact serialisation in tool results.
30. T31 compression of raw tool output.

**Do not do**

| Anti-pattern | Why |
|---|---|
| Rewriting or pruning earlier conversation history | Breaks the cache and, on Fable 5.2 and Opus 5.5, invalidates thinking blocks tied to the conversation. Fable 5.2 enforces the history-editing check for every account. [local-doc: models.md, cost-optimization.md §2.3] |
| Volatile content in always-loaded files (dates, counters, "current ticket", status) | Changes the project-context layer each session; the measured 25-token status line case rewrote the whole conversation each request. [web] |
| Switching model mid-session, including through skill `model:` frontmatter or `opusplan` | Full cold re-read each way. [web: prompt-caching page] |
| Connecting or removing MCP servers, or toggling plugins that ship MCP servers, mid-task | Tool-definition change where tools load upfront. [web] |
| Over-delegation and agent teams by default | About 15× tokens for multi-agent; about 7× for teams; "most coding tasks" are a poor fit. [web] |
| Fable 5.2 as the default orchestrator | 19% more for about the same score in the measured defect-search setup; 2.9× Opus 5.5's cost for a lower score on DeepResearch Bench II. [web] Use it where it wins. |
| Low effort everywhere | 13–34 point drops on some workloads. [web] |
| Context editing as a savings lever | Added 73% to cost on the 20-issue run. It is a window-management tool. [web] |
| A tight output cap to save money | 16,384 tokens cut off 85% of Fable 5.2 attempts; cost per solved task did not improve. [web] |
| Lossy compression or private shorthand in instructions | Risks accuracy for tokens that already cost a fortieth. [inference] |
| `prompt` or `agent` hooks on hot events such as every tool call | Each fires a model call. [web: hooks page] |
| Heavy `SessionStart` or prefetch dumps | Paid on every later turn; output above 10,000 characters is replaced by a preview anyway. [web] |
| Idle loops, scheduled tasks and goal check-ins left running | Each firing resends the full context. [web: costs page] |
| Restating tool descriptions in prose | "Tool schemas already render into the request; prose restating them only inflates the prefix." [local-doc] |
| Long-running one giant session across unrelated tasks | Each turn re-reads everything; quality falls with context length. [web] |

### B3. Design consequences specific to the two-repo setup [inference unless tagged]

- Both repos' `CLAUDE.md`, agent descriptions, skill descriptions and MCP server instructions load together. Set one combined always-loaded budget, for example 3,000 tokens, and split it: brain about 2,000, project about 1,000. Enforce with a counting script in CI. Use the real `count_tokens` endpoint where a key exists; "Do not use tiktoken. … It undercounts Claude tokens by ~15-20% on typical text" [local-doc: token-counting.md]. Without a key, read actual figures from the transcript's first-request `cache_creation_input_tokens` [local-obs].
- The project repo extends the brain through skills and scripts, not through a second long handbook.
- The brain's learning pipeline writes to the brain between tasks. Edits to `CLAUDE.md` do not reach a running session anyway: they load "on the next `/clear`, `/compact`, or restart" [web: prompt-caching page]. So learning commits are naturally cache-safe if made at session end.
- Sessions in different directories "build different prefixes and miss each other's cache" [web]. Cross-session cache sharing is not something to design around.

### B4. What "plugins and algorithms" can honestly mean

- Plugins: package the brain's skills, agents, hooks and the Library MCP as a Claude Code plugin so a project attaches it in one step. Plugin skills, commands, agents and hooks never invalidate the cache; plugin MCP servers follow MCP rules. [web: prompt-caching page]
- Algorithms: BM25 + dense + reciprocal-rank fusion + rerank for retrieval; graph ranking for the repo map; a cascade (cheap attempt, verify, escalate); keyword-matched playbook reuse; a bandit-style or simple threshold rule that adjusts the routing table from ledger data. All classical, all implementable in Python inside the repo.

### B5. What a Max-subscription user can actually measure

**In the product**

- `/usage`: a session block (tokens by model, a notional cost at list price, a `Prompt cache (main)` line with the share of input read from cache, misses and likely cause), plus, for subscribers, plan usage bars, an attribution of recent usage to skills, subagents, plugins and MCP servers, and recommendations for anything behind 10% or more of usage. Local to the machine; main conversation only for the cache line. [web: https://code.claude.com/docs/en/costs]
- `/context`: what occupies the window. [web: same]
- `/insights`: an HTML report over up to 200 recent sessions; it spends tokens. [web: same]
- Status line JSON: `cost.total_cost_usd`, `context_window.current_usage`, `context_window.used_percentage`, a `prompt_cache` object, and for subscribers `rate_limits.five_hour.used_percentage` and `rate_limits.seven_day.used_percentage` with reset times. [web: https://code.claude.com/docs/en/statusline] For a Max user the five-hour and seven-day percentages are the true budget, more than dollars. Whether the status line renders in claude.ai/code cloud sessions was not confirmed.

**In files**

- Transcripts: one JSONL per session, plus `subagents/agent-<id>.jsonl` and a `.meta.json` with agent type and model. Each assistant row carries `message.usage` with `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `cache_creation.ephemeral_1h_input_tokens` / `ephemeral_5m_input_tokens`, `output_tokens`, `output_tokens_details.thinking_tokens`, `server_tool_use`, `speed`, and row-level `effort`, `requestedModel`, `attributionSkill`, `attributionMcpServer`, `timestamp`. [local-obs, this cloud session] Third-party posts claim `input_tokens` is sometimes a streaming placeholder [web, unverified blogs]; here the tiny values are consistent with a fully cached prefix, but the ledger should de-duplicate by `requestId` and sanity-check totals against `/usage`.
- Hooks receive `session_id` and `transcript_path` on `Stop`, `SubagentStop`, `SessionEnd`, `PreCompact`. [web: hooks page] The sample repo already meters subagents this way into `payroll/data/ledger.jsonl`. [local-obs]
- Cloud caveat: the container's `~/.claude/projects` is not durable. The ledger must be written into a repo and committed by the session, or the data is lost. [inference]

**Telemetry**

- OpenTelemetry: `CLAUDE_CODE_ENABLE_TELEMETRY=1`; metrics `claude_code.token.usage` (type input, output, cacheRead, cacheCreation; model; effort) and `claude_code.cost.usage`; event `claude_code.api_request` with tokens, `cost_usd`, `duration_ms`. Console exporter exists. [web: https://code.claude.com/docs/en/monitoring-usage] It needs an endpoint and environment setup, which is a poor fit for a non-technical owner; the transcript ledger gives the same fields with no setup. [inference]

**Not available to him**: the Admin usage and cost API ("not available for individual accounts") [local-doc], and the Batch API.

**Ledger design sketch**

- `Stop` and `SubagentStop` command hooks run a Python script that reads new transcript rows since a stored offset and appends one line per request group to `ledger/YYYY-MM.jsonl`: session, ticket id, task class, agent type, model, effort, the four meters plus thinking tokens, cache-read share, turns, wall-clock, and outcome (tests passed, critic score, rework count).
- A weekly rollup script writes `ledger/REPORT.md`: tokens and minutes per completed ticket by task class, cache-read share, top five outliers, and one proposed routing change with its evidence. Javier reads a file; he runs nothing.
- Health alarms, checked by the hook with no model call: main-conversation cache-read share below 80%; more than one unexpected cache miss per session; a subagent returning more than 2,000 tokens; always-loaded size above budget.
- Learning rule: a routing cell (model, effort, delegate or not) changes only when at least N tickets of that class show lower cost at equal or better outcome, and the change is recorded as an ADR-style entry so it can be reverted. Never "keep or revert on a one-case swing". [local-doc]

### B6. The ten rules a token-frugal orchestrator follows

Each rule has a test the ledger or a lint can run.

1. **One model per session.** Test: zero `PostModelSwitch` events and one distinct main-conversation model per transcript; no inline skill sets `model:`.
2. **Always-loaded text stays under budget and contains nothing volatile.** Test: combined brain plus project always-loaded size ≤ 3,000 tokens; lint finds no dates, counters or status lines in those files.
3. **Cache-read share ≥ 80% of main-conversation input after the third request.** Test: computed per session from transcript usage; lower values open a lesson.
4. **Every ticket has a verification target before work starts.** Test: the ticket file has a non-empty `verify:` field; this is what permits rules 7 and 8.
5. **Independent read-only calls go out together.** Test: ratio of single-tool turns that were immediately followed by another read-only single-tool turn stays under a threshold.
6. **Bulk output never enters the lead's context raw.** Test: no tool result above 5,000 tokens in the main conversation, except a deliberate file read; tests and builds run through the filter wrappers.
7. **Start at the routed model and effort for the task class; escalate only on a failed check.** Test: every escalation row in the ledger links to a failing verification.
8. **Delegate only self-contained, bulky, checkable steps, with a brief that carries everything needed and a return cap.** Test: subagent returns ≤ 2,000 tokens; detail is in a named file; workers set `omitClaudeMd` and an explicit tool list.
9. **Search the Library for a playbook or prior decision before planning or researching.** Test: a `search` call precedes the first plan in each ticket; reuse rate is reported.
10. **Checkpoint to files at each ticket boundary, then compact or clear there and nowhere else.** Test: compaction events fall within one turn of a `PROGRESS.md` write; no auto-compaction mid-ticket.

A meta-rule above all ten: **no trade-off lever is applied on a hunch.** Lower effort, cheaper models and time pressure are adopted per task class only when the ledger shows equal or better outcomes. Unmeasured, the brain defaults to quality.

### B7. Gaps and things not verified

- Fable 5.2 effort curves at `xhigh` and `max`, and Opus 5.5 at `max`, were not measured on the fetched page.
- The cost-optimization page and several docs pages were longer than one fetch; later sections (the full lever table, skill description budget variable, PostToolUse output rewriting) were not read.
- Aider's diff-format and repo-map numbers, Chroma's report, TOON and semantic-cache figures come from search summaries or memory, as tagged.
- How a Max plan weights cache reads, writes and output against its limits is not published in anything fetched.
- Whether `/usage`, the status line and `/insights` are reachable in claude.ai/code cloud sessions was not tested.

### Sources

Local: `shared/cost-optimization.md`, `latency-optimization.md`, `latency-optimization/levers.md`, `prompt-caching.md`, `agent-design.md`, `tool-use-concepts.md`, `token-counting.md`, `message-threads.md`, `models.md`.

Web:
- https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence.md
- https://code.claude.com/docs/en/costs
- https://code.claude.com/docs/en/prompt-caching
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/statusline
- https://code.claude.com/docs/en/monitoring-usage
- https://claude.dev/blog/lessons-from-building-claude-code-prompt-caching-is-everything/
- https://www.anthropic.com/engineering/advanced-tool-use
- https://www.anthropic.com/engineering/multi-agent-research-system
- https://www.anthropic.com/engineering/code-execution-with-mcp
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- https://www.anthropic.com/engineering/writing-tools-for-agents
- https://claude.com/blog/context-management
- https://arxiv.org/abs/2506.14852 (agentic plan caching)
- https://arxiv.org/abs/2310.05736 and the Microsoft Research LLMLingua blog
- https://arxiv.org/abs/2305.05176 (FrugalGPT); https://sky.cs.berkeley.edu/project/routellm/ (RouteLLM)
