# Round 4, 02: re-check of memory/facts.jsonl and memory/models.json against official pages

Date of check: 2026-11-10. Contract h-20261110-1f9d40 (CB-207). Nothing in memory/ was changed.

## Answer

Confidence: medium-high on the verdicts below. Pages were read through WebFetch, which runs a small model over each page, so quoted sentences are as extracted and not byte-checked. Where I paraphrase, I say so.

- 18 facts: 8 confirmed, 5 changed (text needs a correction), 1 partly changed and partly unconfirmed (fact-two-repo-loading), 4 not found on any official page (fact-cost-shape, the three benchmark facts, and the "declines most" half of fact-fable-limits is counted under changed).
- Exact tally is in the table. The rule I used: confirmed means every clause is on an official page; changed means at least one clause is contradicted or needs a qualifier; not found means no official page states it.
- models.json: all 4 model ids, 4 aliases, and every price (in, out, cache_read, cache_write_5m, cache_write_1h) are confirmed. One thing is missing, not wrong: Haiku 5.5 has a higher price tier above 100,000 prompt tokens that the file does not record. models.json has no default-effort field. The roles table sets effort levels as policy, so there is nothing to confirm there.

## Summary table (facts.jsonl)

| id | verdict |
|---|---|
| fact-two-repo-loading | changed (and partly unconfirmed) |
| fact-claudemd-cost | changed (small) |
| fact-skill-cost | confirmed |
| fact-cache-lifetime | confirmed (one nuance) |
| fact-cache-breakers | changed (two qualifiers) |
| fact-claudemd-edit-timing | confirmed |
| fact-subagent-model | confirmed |
| fact-subagent-cold-start | confirmed |
| fact-default-effort | confirmed (incomplete, not wrong) |
| fact-prices | changed (two clauses wrong; dollar figures right) |
| fact-cost-shape | not found (own measurement; one clause is arithmetic) |
| fact-bench-coding | not found |
| fact-bench-escalation | not found |
| fact-bench-orchestrator | not found |
| fact-effort-curves | not found |
| fact-multi-agent-tokens | confirmed (with a scope caveat) |
| fact-fast-mode | confirmed |
| fact-fable-limits | changed (one clause unsupported) |

Counts: confirmed 8 (skill-cost, cache-lifetime, claudemd-edit-timing, subagent-model, subagent-cold-start, default-effort, multi-agent-tokens, fast-mode); changed 5 (claudemd-cost, cache-breakers, prices, fable-limits, two-repo-loading); not found 5 (cost-shape, bench-coding, bench-escalation, bench-orchestrator, effort-curves). 8+5+5 = 18.

## Per-fact detail

### fact-two-repo-loading: CHANGED (partly unconfirmed)
Claim: in a cloud session with two repos, each repo's CLAUDE.md, unscoped rules, skills, agents and commands load; hooks, permissions, settings, .mcp.json and plugins do not.
- Contradicted for cloud threads inside a Project. https://code.claude.com/docs/en/claude-projects ("What threads pick up from your repositories"): "Cloud threads load each repository's `CLAUDE.md` instructions but not its skills, `.mcp.json` servers, or `.claude/settings.json`, whether the project has one repository or several." Table rows: skills under .claude/skills/ "Not loaded"; "Agents and commands under `.claude/`" "Not loaded"; root CLAUDE.md, .claude/CLAUDE.md and non-path-specific .claude/rules/ "Loaded from every repository"; subdirectory CLAUDE.md and path-specific rules "aren't loaded".
- Not stated for a plain (non-Project) session with several repos. https://code.claude.com/docs/en/cloud-environments ("What carries over from your setup") says skills, agents, commands, rules and CLAUDE.md are "Yes ... Part of the clone", but says hooks, permission rules and .mcp.json are "Yes, in a session with one repository" and points to the settings page for several. https://code.claude.com/docs/en/settings ("Settings in cloud sessions"): "a session with several repositories starts above the clones and reads only the `enabledPlugins` and `extraKnownMarketplaces` keys from each repository's `.claude/settings.json`, not permission rules, hooks, `env`, or other keys." That plugins "still don't load in a cloud session." So the "does not load" half is confirmed; whether skills, agents and commands load from each repo in a multi-repo non-Project session is UNCONFIRMED (I found no sentence that says so).
- Corrected text: "In a Project's cloud thread, each repository's root CLAUDE.md, .claude/CLAUDE.md and non-path-specific .claude/rules/ load; its skills, agents, commands, .mcp.json, hooks, permissions, env and plugins do not. In a plain multi-repo cloud session only plugin keys are read from each repo's settings; loading of skills, agents and commands is not documented."
- Also: the original source file is docs/research/02-claude-code-platform.md B1; I did not re-read it.

### fact-claudemd-cost: CHANGED (small)
- "Imports do not reduce the cost": confirmed. https://code.claude.com/docs/en/memory: "[Imports] help you organize a long file but don't reduce its context cost, because imported files load together with the CLAUDE.md that imports them."
- "under 200 lines": confirmed. Same page: "target under 200 lines per CLAUDE.md file." Also https://code.claude.com/docs/en/costs: "Aim to keep CLAUDE.md under 200 lines".
- "loaded by every sub-agent unless the agent sets omitClaudeMd": needs a qualifier. https://code.claude.com/docs/en/sub-agents: "Explore and Plan start without your CLAUDE.md files and the git status snapshot to keep research fast and inexpensive. Other built-in and custom subagents load both, unless you set `omitClaudeMd` in a custom subagent's definition". `omitClaudeMd` requires Claude Code v2.1.271 or later (same page).
- "paid on every request": the page says CLAUDE.md is "loaded into context at session start" (costs page) and the full context is re-sent each request and re-read at the cached rate (https://code.claude.com/docs/en/prompt-caching). So it is paid every request, at the cache-read rate when the cache is warm. The fact does not say "at cache rate"; consider adding it.
- Corrected text: "CLAUDE.md from both repos is in the context of every request (billed at the cache-read rate while the cache is warm) and loaded by every sub-agent except the built-in Explore and Plan and any custom agent that sets omitClaudeMd (v2.1.271+). Imports do not reduce the cost. Anthropic advises under 200 lines per file."

### fact-skill-cost: CONFIRMED
https://code.claude.com/docs/en/skills: "the combined `description` and `when_to_use` text is truncated at 1,536 characters in the skill listing to reduce context usage." And "a skill's body loads only when it's used". https://code.claude.com/docs/en/prompt-caching: "Skills and commands inject their instructions as user messages at the point of invocation. Nothing earlier in the conversation changes." Nuance, not a contradiction: skills.md says "Every skill in the [skill listing] adds to your context on every turn" and once loaded, a skill's content "stays in context across turns".

### fact-cache-lifetime: CONFIRMED
https://code.claude.com/docs/en/prompt-caching ("Which TTL each request gets"): table: Main conversation, Claude subscription within plan usage "One hour"; usage credits/API key/cloud provider "Five minutes". Everything else (subagents, workflows, teammates, forks, compaction): "Five minutes, except the server-controlled helper requests, which get one hour". Also: "Claude Code drops the main conversation to the five-minute TTL" once you go over plan usage and draw usage credits.
Nuance to add: a small set of server-controlled helper requests get one hour on subscription. The TTL can be changed with `promptCacheTtl` / `subagentPromptCacheTtl` (v2.1.242+).

### fact-cache-breakers: CHANGED (two qualifiers)
https://code.claude.com/docs/en/prompt-caching.
- Confirmed: model switch ("Each model has its own cache"); skill whose frontmatter names another model ("that turn is also a model switch"); automatic model fallback ("is also a model switch"); fast mode ("Fast mode and standard speed keep separate caches"); compaction ("By design, this invalidates the conversation layer"). Keeps: invoking skills, spawning a subagent, editing repository files, and editing CLAUDE.md all confirmed.
- Changed 1, MCP servers: not always. "Tools deferred: Claude Code keeps the tool list from the conversation's first request for the whole conversation, so a server connecting or disconnecting mid-session doesn't disturb anything already cached." Deferral is the default on supported models. "Tools loaded upfront: adding a definition invalidates the cache, and so does removing one on purpose."
- Changed 2, effort: keeps the cache only on some models and setups. "With an API key or a Claude subscription, changing effort keeps the cache on Fable 5.1 and later, Opus 5.5, Sonnet 5.5, and Haiku 5.5." On Bedrock, Google Cloud's Agent Platform, a Claude apps gateway, with CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS, or under HIPAA config, "it works as on most models" (invalidates).
- Not listed in the fact but documented as breakers: enabling/disabling plugins that provide MCP servers, denying a whole tool when tool search is off, accumulating many images, upgrading Claude Code.
- Corrected text: "These break the prompt cache: switching model (including a skill naming another model or a safety fallback), toggling fast mode, compaction, and, when MCP tools are loaded upfront rather than deferred, adding or removing an MCP server. These keep it: invoking skills, spawning sub-agents, editing repo files, and, with an API key or subscription on Fable 5.1+/Opus 5.5/Sonnet 5.5/Haiku 5.5, changing effort."

### fact-claudemd-edit-timing: CONFIRMED
https://code.claude.com/docs/en/prompt-caching: "Editing them mid-session does not invalidate the cache, but the edit also doesn't apply. Claude keeps working with the version that was loaded at session start. The new content loads on the next `/clear`, `/compact`, or restart." Applies to project-root and user-level CLAUDE.md; nested CLAUDE.md and path-scoped rules load on demand.

### fact-subagent-model: CONFIRMED
https://code.claude.com/docs/en/sub-agents: "Claude Code resolves the subagent's model in this order: 1. The per-invocation `model` parameter 2. The subagent definition's `model` frontmatter, where `inherit` selects the main conversation's model 3. The `CLAUDE_CODE_SUBAGENT_MODEL` environment variable, when you set it to a model alias or model ID 4. The main conversation's model". Version caveat: "Before v2.1.251, `CLAUDE_CODE_SUBAGENT_MODEL` came first". The "unlabelled helpers run on Fable" part follows from item 4 (my inference; I did not find a sentence naming Fable). The page quotes were relayed through the fetch tool; the built-in Explore agent's own model was not checked.

### fact-subagent-cold-start: CONFIRMED
https://code.claude.com/docs/en/prompt-caching ("Subagents and the cache"): "Its first request doesn't read the parent's cache, because the two prefixes differ"; "A fork ... inherits the parent's system prompt, tools, and conversation history exactly, so its first request reads the parent's cache." https://code.claude.com/docs/en/sub-agents: "By default, when 20 subagents are running in a session, spawning another with the Agent tool fails with `Concurrent subagent limit reached`"; changeable with CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS. Ultracode sessions are exempt.

### fact-default-effort: CONFIRMED (incomplete, not wrong)
- Claude Code: https://code.claude.com/docs/en/model-config: "Fable 5.2, Opus 5.5, Sonnet 5.5, and Haiku 5.5 default to `medium`, and Opus 4.7 defaults to `xhigh`."
- API: https://platform.claude.com/docs/en/models/overview, "Default effort" row: Fable 5.2 `high`, Opus 5.5 `medium`, Sonnet 5.5 `high`, Haiku 5.5 `medium`. https://platform.claude.com/docs/en/build-with-claude/effort agrees: "`high`: The default on every model that supports effort except Claude Opus 5.5 and Claude Haiku 5.5."
- Thinking: https://platform.claude.com/docs/en/models/fable-5-2/overview and .../opus-5-5/overview: "Adaptive thinking is always on and can't be turned off." Incomplete: https://code.claude.com/docs/en/costs says "You can't turn off thinking on Opus 5.5, Sonnet 5.5, Haiku 5.5, or the Fable models" in Claude Code, and the models overview says the Models API reports `thinking.types.disabled.supported` as `false` for Sonnet 5.5. So the fact's list (Fable 5.2, Opus 5.5) is true but omits Sonnet 5.5 and Haiku 5.5 in Claude Code.
- Extra caveat: model-config: "a top-level `effortLevel` in your user settings file doesn't count for Opus 5.5."

### fact-prices: CHANGED (dollar figures right; two clauses wrong)
Source: https://platform.claude.com/docs/en/about-claude/pricing and https://platform.claude.com/docs/en/models/overview.
- Confirmed input/output per MTok: Fable 5.2 $8/$40, Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50 (for prompts up to 100,000 tokens).
- Cache read dollar figures confirmed: $0.20, $0.20, $0.10 (and Haiku $0.01).
- Wrong 1, "a tenth of input": pricing page footnotes: "Cache hits and refreshes on Claude Fable 5.2 ... are priced at 0.025x the base input price." and "Cache hits and refreshes on Claude Opus 5.5 and Claude Sonnet 5.5 are priced at 0.05x the base input price." Only Haiku 5.5 is 0.1x ($0.01 on $0.10). So $0.20/$0.20/$0.10 are 2.5%, 5%, 5% of input.
- Wrong 2, "five times higher above a 100K-token prompt": applies to Haiku 5.5 only. Pricing page: "Claude Haiku 5.5 is priced by prompt length: a request whose prompt is over 100,000 tokens pays higher prices." Haiku over 100K: $0.50 in / $2.50 out / $0.05 cache read. Other models: "Claude 4.6 and later models (except Claude Haiku 5.5) ... include the full 1M token context window at standard pricing." The prompt length counts cache reads and writes.
- Corrected text: "List prices per million tokens, input/output: Fable 5.2 $8/$40, Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50. Haiku 5.5 only is five times higher for prompts over 100,000 tokens ($0.50/$2.50); the others are flat across the 1M window. Cache reads: $0.20 (Fable, 0.025x input), $0.20 (Opus, 0.05x), $0.10 (Sonnet, 0.05x), $0.01 (Haiku, 0.1x)."
- Also relevant: Batch is 50% off; US-only inference_geo is 1.1x.

### fact-cost-shape: NOT FOUND
Measurement of one local session; no official page can confirm it. Only derived clause: "One output token costs as much as 200 cached-input tokens on Fable 5.2" = $40 / $0.20 = 200, which follows from the confirmed prices (my arithmetic). The 91% / 7% / 36% / 57% shares were not checked. Suggest reclassifying trust as "measured", not "derived from official page".

### fact-bench-coding: NOT FOUND
Looked for: 463 problems, 93.1%, $0.22; 95.5%, $0.30; 94.6%, $0.39; 96.3%, $1.39. Checked https://www.anthropic.com/news/claude-opus-5-5, https://platform.claude.com/docs/en/models/opus-5-5/overview, https://www.anthropic.com/claude-fable-and-mythos-5-2, https://platform.claude.com/docs/en/build-with-claude/effort (grep for the figures: no match), and a web search (no match). Related but different figures exist: the Fable 5.2 announcement says "Fable 5.2 at High effort scored about level with Opus 5.5 at Max effort, for roughly half the cost per task" (FrontierCode 2.0); the Opus 5.5 announcement says FrontierCode (main set) Opus 5.5 54.6% at default (medium) effort. These do not confirm or contradict the fact. Possibly from a source that is not an official page (the fact says "Anthropic coding subset"); the provenance is docs/research/01-models.md B10, which I did not re-read.

### fact-bench-escalation: NOT FOUND
97% at ~$0.17 vs 95.3% at $0.29, ~40% less cost. Same pages searched; no match. Note arithmetic: (0.29-0.17)/0.29 = 41%, so "about 40%" is consistent with the fact's own figures (my calculation).

### fact-bench-orchestrator: NOT FOUND
0.831 at $139 vs 0.850 at $236; Fable lead 0.833 at $165, "19% more than the Opus lead". Not on any page searched. Arithmetic: 165/139 = 1.187, so 19% is consistent with the fact's own numbers (my calculation).

### fact-effort-curves: NOT FOUND
34 points below medium; Sonnet 5.5 62.7% to 77.8%; Fable 5.2 high 3.2 points for 3.2x cost. Not found. The Opus 5.5 announcement says only that Opus 5.5 at its lowest effort "still performed well in some customer evaluations" with no gap figure (paraphrase via the fetch tool).

### fact-multi-agent-tokens: CONFIRMED (scope caveat)
https://www.anthropic.com/engineering/multi-agent-research-system: "agents typically use about 4× more tokens than chat interactions" and "multi-agent systems use about 15× more tokens than chats" (the fetch tool returned these as two fragments; a web search also reports them via secondary sources). The 7x: https://code.claude.com/docs/en/costs: "Agent teams use approximately 7x more tokens than standard sessions when teammates run in plan mode".
Caveat (my observation): the 4x/15x come from the 2025 research-system post about Anthropic's own multi-agent research product, not from current models in Claude Code.

### fact-fast-mode: CONFIRMED
https://code.claude.com/docs/en/fast-mode: "making the model up to 2.5x faster at a higher cost per token"; "fast mode is supported on Fable 5.2, Opus 5.5, Opus 5, and Opus 4.8, but not on Sonnet, Haiku, or other models"; "Fast mode and standard speed keep separate caches"; "For Claude Code users on subscription plans ... fast mode is available via usage credits only and not included in the subscription rate limits." Price: Fable 5.2 $16/$80 vs standard $8/$40; Opus 5.5 $8/$40 vs $4/$20, so exactly 2x (https://platform.claude.com/docs/en/about-claude/pricing). Note: Opus 4.8 fast mode is removed Nov 30, 2026 (fast-mode page). Fast mode on Mythos 5.2 also exists. Fast mode is not available on Bedrock, Foundry or Claude Platform on AWS.

### fact-fable-limits: CHANGED (one clause unsupported)
- Kernel and architecture: https://www.anthropic.com/claude-fable-and-mythos-5-2 (extracted): "Fable 5.2 and Claude Mythos 5.2 perform at about the level of Opus 5.5." The page says training was adjusted to limit gains in these AI-research areas (paraphrase via fetch tool). Confirmed in substance.
- "declines most cybersecurity and research-biology tasks": not supported. The only figures found say the opposite direction on blocks: "about 55% fewer blocks with Fable 5.2 compared with Fable 5.1 ... about 60% fewer in cybersecurity and 40% fewer in biology." https://code.claude.com/docs/en/model-config: "Fable models, Opus 5.5, Sonnet 5.5, and Opus 5 run with safety classifiers, which most often flag cybersecurity and biology content." Nothing says "most" tasks are declined.
- Safety fallback: confirmed. model-config: "After a fallback, the session continues on the fallback model." Details: "Fable models and Opus 5.5: biology-flagged requests re-run on Opus 5, and cybersecurity-flagged requests re-run on Opus 4.8." Sonnet 5.5 re-runs cyber on Sonnet 5 and ends biology with a refusal. Requires v2.1.219+.
- Corrected text: "Fable 5.2 performs at about Opus 5.5's level on accelerator kernel optimisation and LLM architecture work (training was adjusted to limit gains there). Its safety classifiers most often flag cybersecurity and biology content, with about 55% fewer blocks than Fable 5.1 in early testing. In Claude Code a flagged request re-runs on a fallback model (biology: Opus 5; cybersecurity: Opus 4.8) and the session stays on it until you run /model."

## models.json

Sources: https://platform.claude.com/docs/en/about-claude/pricing (table), https://platform.claude.com/docs/en/models/overview, https://code.claude.com/docs/en/model-config.

| model id | alias | in / out | cache_read | cache_write_5m | cache_write_1h | verdict |
|---|---|---|---|---|---|---|
| claude-fable-5-2 | fable | 8 / 40 | 0.2 | 10 | 16 | confirmed (pricing page row: $8, $10, $16, $0.20, $40) |
| claude-opus-5-5 | opus | 4 / 20 | 0.2 | 5 | 8 | confirmed (row: $4, $5, $8, $0.20, $20) |
| claude-sonnet-5-5 | sonnet | 2 / 10 | 0.1 | 2.5 | 4 | confirmed (row: $2, $2.50, $4, $0.10, $10) |
| claude-haiku-5-5 | haiku | 0.1 / 0.5 | 0.01 | 0.125 | 0.2 | confirmed for prompts up to 100,000 tokens (row: $0.10, $0.125, $0.20, $0.01, $0.50) |

- Model ids: the models overview lists "Claude API ID" `claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`. Confirmed.
- Aliases: model-config alias table: `fable` "Uses the Fable model for your provider"; `sonnet` "Uses the latest Sonnet model"; `opus` "Uses the latest Opus model"; `haiku` "Uses the fast and efficient Haiku model". On the Anthropic API they resolve to Opus 5.5, Sonnet 5.5, Haiku 5.5, and "the `fable` alias resolves to Fable 5 in Claude apps gateway sessions and to Fable 5.2 everywhere else." All four aliases confirmed. Caveat: on Bedrock/Vertex, Sonnet and Haiku resolve to 4.5, and on Foundry opus resolves to 4.6, so the aliases only map to these ids on the Anthropic API (and Fable in a Claude apps gateway is 5, not 5.2).
- Gap, Haiku 5.5 over 100K: pricing page: $0.50 in / $0.625 5m write / $1 1h write / $0.05 read / $2.50 out. The file has no field for this. If the cost tooling bills Haiku calls with long prompts, it will under-count by 5x.
- Fallback price: `fallback_price` equals the Opus 5.5 row. This is an internal default, not an Anthropic fact; not checked.
- Effort defaults: models.json has none. The roles table (lead opus medium, builder sonnet medium, scout haiku low, and so on) is internal policy. All levels used (`low`, `medium`, `high`) are valid for those models (model-config levels table). For reference, the API default for sonnet is `high` while the builder/researcher roles pin `medium`, which matches the Claude Code default.
- Not checked: `escalation`, `limits` (max_parallel_helpers 4, helper_reply_tokens, recall_budget_tokens). These are internal design values. Note the Anthropic default for concurrent sub-agents is 20, so 4 is a deliberate lower limit.

## Searched but could not reach or confirm
- No official page found for the 463-problem coding subset, the escalation result, the orchestrator defect-search result, or the effort-curve figures (4 facts). They may be from a system card, a PDF, or a customer or internal source; the system cards (https://www.anthropic.com/document/claude-fable-5-2-mythos-5-2-system-card, https://www.anthropic.com/claude-opus-5-5-system-card) were not opened.
- The model-config and sub-agents pages are long; the tool returned only the first 100,000 characters of each, so the final ~17K to ~33K characters were not read.
- docs/research/*.md (the facts' provenance files) were not re-read.
- The anthropic.com engineering post was fetched once; its exact full sentence was returned in fragments.

END OF MEMO
