# Round 4, 01: re-check of memory/facts.jsonl (18 facts) and memory/models.json

Contract h-20261110-454544 (CB-207). Date read for every page below: 2026-11-10. Reader: the lead, who records changes through the learning pipeline. This memo edits nothing in memory/.

Answer: 16 of 18 facts are confirmed as written. 2 are confirmed only in part or with a changed detail (fact-two-repo-loading, fact-effort-curves), 1 contains a part that cannot be checked against an official page (fact-cost-shape, measured locally), and 2 more carry a wording caveat worth fixing (fact-prices, fact-cache-breakers). models.json: every model id, input/output price, cache read/write price confirmed. One gap: models.json has no Haiku 5.5 over-100K tier. models.json has no context-limit field. Confidence: high for prices, ids, effort defaults, fast mode, cache rules (all read from current official pages); medium for fact-two-repo-loading (the docs do not state the skills/agents/commands case for a plain multi-repo session in so many words).

Surfaces: API = Claude API (platform.claude.com). CC = Claude Code (code.claude.com). Cloud = Claude Code cloud sessions. Plan = subscription tier.

Status key: CONFIRMED / CHANGED (new value) / PARTLY (confirmed with a caveat) / UNVERIFIABLE.

## Summary table

| # | Fact id | Status |
|---|---|---|
| 1 | fact-two-repo-loading | PARTLY |
| 2 | fact-claudemd-cost | CONFIRMED (nuance: billed at cache-read rate) |
| 3 | fact-skill-cost | CONFIRMED |
| 4 | fact-cache-lifetime | CONFIRMED |
| 5 | fact-cache-breakers | PARTLY (MCP clause needs a condition) |
| 6 | fact-claudemd-edit-timing | CONFIRMED |
| 7 | fact-subagent-model | CONFIRMED |
| 8 | fact-subagent-cold-start | CONFIRMED |
| 9 | fact-default-effort | CONFIRMED |
| 10 | fact-prices | CONFIRMED (wording: the 100K rule is Haiku-only) |
| 11 | fact-cost-shape | PARTLY: the 200x ratio confirmed by arithmetic; the session percentages UNVERIFIABLE |
| 12 | fact-bench-coding | CONFIRMED |
| 13 | fact-bench-escalation | CONFIRMED |
| 14 | fact-bench-orchestrator | CONFIRMED |
| 15 | fact-effort-curves | CHANGED (minor: 3.3 points, not 3.2) |
| 16 | fact-multi-agent-tokens | CONFIRMED |
| 17 | fact-fast-mode | CONFIRMED |
| 18 | fact-fable-limits | CONFIRMED |

## Facts

### 1. fact-two-repo-loading: PARTLY (Cloud, plain multi-repo session; not Projects)

Claim: with two repos, each repo's CLAUDE.md, unscoped rules, skills, agents and commands load; hooks, permissions, other settings, .mcp.json and plugins do not.

Confirmed part (not loaded):
- https://code.claude.com/docs/en/settings.md ("Settings in cloud sessions"): "in an Anthropic-hosted environment, a session with several repositories starts above the clones and reads only the `enabledPlugins` and `extraKnownMarketplaces` keys from each repository's `.claude/settings.json`, not permission rules, hooks, `env`, or other keys. The marketplaces and plugins those two keys declare still don't load in a cloud session."
- https://code.claude.com/docs/en/cloud-environments.md ("What carries over from your setup"): ".mcp.json MCP servers: Yes, in a session with one repository"; plugins declared in the repo's settings: "No".

Confirmed in part (loaded): the same table lists "Your repo's `CLAUDE.md`: Yes", "`.claude/rules/`: Yes", and "`.claude/skills/`, `.claude/agents/`, `.claude/commands/`: Yes, Part of the clone". The table gives no multi-repo qualifier on those rows (it does on the settings and .mcp.json rows). So the docs do not say in words that skills/agents/commands load from the second repo. The earlier memo (docs/research/02-claude-code-platform.md:89) rests that row on the table plus an observation in a live session. Label: inference plus observation, not a documented guarantee.

Caveat, different surface: https://code.claude.com/docs/en/claude-projects.md ("What threads pick up from your repositories"): "Cloud threads load each repository's `CLAUDE.md` instructions but not its skills, `.mcp.json` servers, or `.claude/settings.json`, whether the project has one repository or several." Agents and commands are "Not loaded" there; only root-level CLAUDE.md, .claude/CLAUDE.md and non-path-specific rules load. Projects is in public beta (Pro, Max, Ultra). If the owner ever works in a Project thread, this fact is wrong for skills, agents and commands.

Suggested rewording (for the lead): add "in an ordinary multi-repo cloud session; in a Project thread skills, agents and commands do not load".

### 2. fact-claudemd-cost: CONFIRMED (CC and Cloud)

- https://code.claude.com/docs/en/memory.md: "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence." and "Imports help you organize a long file but don't reduce its context cost, because imported files load together with the CLAUDE.md that imports them."
- https://code.claude.com/docs/en/sub-agents.md: a subagent loads "every level of the CLAUDE.md hierarchy the main conversation loads ... The built-in Explore and Plan agents skip this." `omitClaudeMd`: "Set to `true` to start this subagent without the user, project, and local CLAUDE.md files in its initial context; managed policy files still load". Requires Claude Code v2.1.271 or later.
- Nuance: https://code.claude.com/docs/en/costs.md says the full conversation is re-read each request "at the cached token rate", so "paid on every request" means paid at the cache-read rate while the cache is warm.

### 3. fact-skill-cost: CONFIRMED (CC)

https://code.claude.com/docs/en/skills.md: "the combined `description` and `when_to_use` text is truncated at 1,536 characters in the skill listing"; "a skill's body loads only when it's used"; "When you or Claude invoke a skill, the rendered `SKILL.md` content enters the conversation as a single message". Cache holds: https://code.claude.com/docs/en/prompt-caching.md "Skills and commands inject their instructions as user messages at the point of invocation. Nothing earlier in the conversation changes."

### 4. fact-cache-lifetime: CONFIRMED (CC; subscription vs API key/credits)

https://code.claude.com/docs/en/prompt-caching.md, table "Which TTL each request gets": Main conversation: "One hour" on "Claude subscription, within plan usage"; "Five minutes" on "Usage credits, API key, or cloud provider". "Everything else": "Five minutes, except the server-controlled helper requests, which get one hour". "Everything else" is defined as "subagents, workflows, in-process teammates, forks, compaction, and session titles". Also: "Once you go over your plan's usage limit and Claude Code draws on usage credits ... Claude Code drops the main conversation to the five-minute TTL". Override settings exist (`promptCacheTtl`, `subagentPromptCacheTtl`, v2.1.242+), so "lasts" is the default, not a fixed rule.

### 5. fact-cache-breakers: PARTLY (CC)

Confirmed items, https://code.claude.com/docs/en/prompt-caching.md:
- Model switch: "Each model has its own cache. Switching with /model means the next request reads the entire conversation history with no cache hits". Skill naming another model: "When a skill or command's frontmatter names a model other than the session's current model, that turn is also a model switch". Safety fallback: "Automatic model fallback on Fable models, Opus 5.5, Sonnet 5.5, and Opus 5 is also a model switch."
- Fast mode: "Fast mode and standard speed keep separate caches".
- Compaction: "By design, this invalidates the conversation layer".
- Keeps: effort ("With an API key or a Claude subscription, changing effort keeps the cache on Fable 5.1 and later, Opus 5.5, Sonnet 5.5, and Haiku 5.5"), skills, subagents ("From the parent's side, the subagent's call and result append to the conversation, leaving the parent's prefix intact"), repo edits.

Caveat on "adding or removing MCP servers": same page: "Tools deferred: Claude Code keeps the tool list from the conversation's first request for the whole conversation, so a server connecting or disconnecting mid-session doesn't disturb anything already cached." Invalidation applies when MCP tools "load upfront" (tool search off or unavailable). Tool search is the default on supported models (https://code.claude.com/docs/en/costs.md: "MCP tool definitions are deferred by default"). Effort-keeps clause does not hold on Bedrock, Google Cloud Agent Platform, a Claude apps gateway, or with HIPAA configuration. Suggested rewording: "adding or removing MCP servers when tools are loaded upfront (not the default)".

### 6. fact-claudemd-edit-timing: CONFIRMED (CC)

https://code.claude.com/docs/en/prompt-caching.md: "Editing them mid-session does not invalidate the cache, but the edit also doesn't apply. Claude keeps working with the version that was loaded at session start. The new content loads on the next /clear, /compact, or restart." Exception worth knowing: nested CLAUDE.md files and path-scoped rules load later on demand.

### 7. fact-subagent-model: CONFIRMED (CC)

https://code.claude.com/docs/en/sub-agents.md: "Claude Code resolves the subagent's model in this order: 1. The per-invocation `model` parameter 2. The subagent definition's `model` frontmatter, where `inherit` selects the main conversation's model 3. The `CLAUDE_CODE_SUBAGENT_MODEL` environment variable ... 4. The main conversation's model". Note: "Before v2.1.251, `CLAUDE_CODE_SUBAGENT_MODEL` came first". The last sentence of the fact ("on a Fable session unlabelled helpers run on Fable") is an inference from step 4; the fetched page text does not say it for Fable specifically. Not checked: built-in Explore agent's model on a subscription (the earlier memo said it may run on Opus; that part of sub-agents.md was not re-read).

### 8. fact-subagent-cold-start: CONFIRMED (CC)

https://code.claude.com/docs/en/prompt-caching.md ("Subagents and the cache"): "Its first request doesn't read the parent's cache, because the two prefixes differ, and it warms a cache of its own across its turns." "A fork ... inherits the parent's system prompt, tools, and conversation history exactly, so its first request reads the parent's cache." https://code.claude.com/docs/en/sub-agents.md: "By default, when 20 subagents are running in a session, spawning another with the Agent tool fails with `Concurrent subagent limit reached`" (override: `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`).

### 9. fact-default-effort: CONFIRMED (CC and API differ)

- CC: https://code.claude.com/docs/en/model-config.md: "Fable 5.2, Opus 5.5, Sonnet 5.5, and Haiku 5.5 default to `medium`".
- API: https://platform.claude.com/docs/en/models/overview.md table, Default effort: Fable 5.2 `high`, Opus 5.5 `medium`, Sonnet 5.5 `high`, Haiku 5.5 `medium`. The table note: "The effort parameter's default on the Claude API."
- Thinking: https://platform.claude.com/docs/en/models/fable-5-2/overview.md: "Adaptive thinking is always on and can't be turned off." Models overview table: Opus 5.5 "Adaptive (always on)". CC: "You can't turn thinking off on Opus 5.5, Sonnet 5.5, Haiku 5.5, or the Fable models" (model-config.md). So in CC the restriction also covers Sonnet 5.5 and Haiku 5.5; the fact lists only two of the four, which is true but incomplete.

### 10. fact-prices: CONFIRMED (API list prices) with one wording fix

https://platform.claude.com/docs/en/about-claude/pricing.md (table, USD per MTok; input / cache 5m write / cache 1h write / cache hit / output):
- Fable 5.2: $8 / $10 / $16 / $0.20 / $40
- Opus 5.5: $4 / $5 / $8 / $0.20 / $20
- Sonnet 5.5: $2 / $2.50 / $4 / $0.10 / $10
- Haiku 5.5 up to 100,000 tokens: $0.10 / $0.125 / $0.20 / $0.01 / $0.50
- Haiku 5.5 over 100,000 tokens: $0.50 / $0.625 / $1 / $0.05 / $2.50

Wording fix: the fact reads "Haiku 5.5 $0.10/$0.50 (five times higher above a 100K-token prompt)". The pricing page says "Claude 4.6 and later models (except Claude Haiku 5.5) ... include the full 1M token context window at standard pricing." So the 100K surcharge is Haiku 5.5 only; Fable, Opus and Sonnet are flat to 1M. A reader could take the parenthesis to apply to all four.
Cache reads "$0.20, $0.20, $0.10, a tenth of input": confirmed. Multipliers per https://platform.claude.com/docs/en/models/overview.md: "prompt cache reads cost 10% of the base input price (2.5% on Claude Fable 5.2 ... 5% on Claude Opus 5.5 and Claude Sonnet 5.5)". Haiku is the 10% case.
Fast mode prices are separate (fact 17).

### 11. fact-cost-shape: PARTLY

- "One output token costs as much as 200 cached-input tokens on Fable 5.2": computed from the pricing page above, $40 / $0.20 = 200. Confirmed by arithmetic (my computation).
- "cache reads were 91% of tokens but 7% of cost; cache writes 36%; output 57%": this is a local measurement of one session (docs/research/03-token-efficiency.md B0). No official page covers it. UNVERIFIABLE against official docs, and I did not recompute it. (The costs.md example line "91% of input tokens from cache" is an illustrative output sample in the docs, not a source for this.)

### 12. fact-bench-coding: CONFIRMED (API; Anthropic-internal benchmark)

https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence.md ("Coding subset (463 SWE-bench Pro problems)"): Opus 5.5 `medium`: 93.1% solved, $0.22 per solved task; Opus 5.5 `high`: 95.5%, $0.30; Fable 5.2 `low`: 94.6%, $0.39; Fable 5.2 `high`: 96.3%, $1.39. (The page identifies the set as SWE-bench Pro; the fact calls it "Anthropic coding subset".)

### 13. fact-bench-escalation: CONFIRMED (API; Opus 5.5 on SWE-bench Pro)

Same page: "`low` with failures re-run at `high`: about 97% solved, about $0.17 per task. Everything at `high`: 95.3% solved, $0.29 per task." My computation: (0.29-0.17)/0.29 = 41%, consistent with "about 40% less". Caveat on the page: most of the small lift comes from the second attempt, not from the escalation itself. The result is for one model (Opus 5.5) on one benchmark; the fact is stated generally.

### 14. fact-bench-orchestrator: CONFIRMED (API; internal defect-search benchmark)

Same page, results list: "Claude Opus 5.5 with Claude Sonnet 5.5 subagents: 0.831 (0.814 to 0.850), $139 USD"; "Claude Opus 5.5 alone at `high`: 0.850 (0.829 to 0.876), $236 USD"; "Claude Fable 5.2 with Claude Sonnet 5.5 subagents: 0.833 (0.795 to 0.856), $165 USD". Text: "Claude Fable 5.2 as the orchestrator in Claude Opus 5.5's place cost 19% more and scored about the same." (165/139 = 1.187, my computation.) The page says the delegation result applies to "work larger than one context window"; the fact omits that condition. Confidence intervals overlap, so "scored about the same" is the page's own reading.

### 15. fact-effort-curves: CHANGED (minor)

- Opus 5.5 low vs medium: confirmed. "Claude Opus 5.5 scored 34 points lower at `low` than at `medium`, for about a fifth of the cost" (defect-search benchmark, 10 runs per setting).
- Sonnet 5.5: confirmed. "Sonnet 5.5 at `medium`: 62.7%. At `high`: 77.8%" (internal agentic coding, single attempt per task).
- Deep research: CHANGED. Page text: "Claude Fable 5.2 scored 3.3 points higher at `high` than at `low` on DeepResearch Bench II, for 3.2 times the cost". The fact says 3.2 points. 57.7 - 54.5 = 3.2 from the rounded scores in the table (54.5 / 55.0 / 57.7), but the page's stated gain is 3.3 (a paired difference). The 3.2 in the page is the cost ratio. New value: 3.3 points for 3.2 times the cost, comparing `high` with `low` (not with `medium`).
Source: https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence.md. Note that the same sentence set also says Opus 5.5 scored 13.3 points lower at `low` than at `medium` on DRACO, so "low effort is bad" is task-specific.

### 16. fact-multi-agent-tokens: CONFIRMED

- https://www.anthropic.com/engineering/multi-agent-research-system: "agents typically use about 4× more tokens than chat interactions"; "multi-agent systems use about 15× more tokens than chats".
- https://code.claude.com/docs/en/costs.md (CC): "Agent teams use approximately 7x more tokens than standard sessions when teammates run in plan mode". Agent teams are "disabled by default".

### 17. fact-fast-mode: CONFIRMED (API and CC; not on Sonnet/Haiku)

- https://platform.claude.com/docs/en/build-with-claude/fast-mode.md (API): "Fast mode delivers up to 2.5x higher output tokens per second at premium pricing." Prices: Fable 5.2 $16 / $80, Opus 5.5 $8 / $40 (twice the standard $8 / $40 and $4 / $20). "Requests at different speeds do not share cached prefixes." Supported models listed: Fable 5.2, Mythos 5.2, Opus 5.5, Opus 5, Opus 4.8.
- https://code.claude.com/docs/en/fast-mode.md (CC): "fast mode is supported on Fable 5.2, Opus 5.5, Opus 5, and Opus 4.8, but not on Sonnet, Haiku, or other models." "For Claude Code users on subscription plans (Pro/Max/Ultra/Team/Enterprise), fast mode is available via usage credits only and not included in the subscription rate limits." "Fast mode usage draws directly from usage credits, even if you have remaining usage on your plan." Fast mode on Fable 5.2 "requires Claude Code v2.1.321 or later".
- Status notes: Opus 5 and Opus 4.8 fast mode is a research preview; Opus 4.8 fast mode "was deprecated on October 30, 2026, and will be removed on November 30, 2026". Fast mode for Fable 5.2 and Opus 5.5 is not marked preview.
- Speed claim is "up to"; the gain is output tokens per second, not time to first token (API page).

### 18. fact-fable-limits: CONFIRMED (apps/API announcement; CC fallback)

- https://www.anthropic.com/claude-fable-and-mythos-5-2: in areas "including accelerator kernel optimization and improving large language model architectures" the models "perform at about the level of Opus 5.5"; "safety classifiers that block high-risk cyber activities" (penetration testing, exploit generation), and "most tasks in research biology". Fallback: "users will instead receive a response from Opus 4.8 for cybersecurity and Opus 5 for biology"; fallbacks to Opus 5 also apply to "a small set of topics" in AI R&D. (Quotes are from the fetch tool's extract of the page, not the full page text.)
- CC: https://code.claude.com/docs/en/model-config.md: "After a fallback, the session continues on the fallback model. To return to your original model, run /model."

## models.json

File fields: models (id, alias, in, out, cache_read, cache_write_5m, cache_write_1h), fallback_price, roles, escalation, limits. There are no context-limit or max-output fields and no effort-level table beyond the role map, so those checks apply to the official values below, which the lead may want to add.

### Model ids and aliases: CONFIRMED
- https://platform.claude.com/docs/en/models/overview.md, "Claude API ID": `claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`. Status Active; retirement "Not sooner than" Nov 9 2027 (Fable 5.2), Sep 22 2027 (Opus 5.5), Sep 28 2027 (Sonnet 5.5), Oct 7 2027 (Haiku 5.5).
- Aliases, CC, https://code.claude.com/docs/en/model-config.md: on the Anthropic API `opus` = Opus 5.5, `sonnet` = Sonnet 5.5, `haiku` = Haiku 5.5. `fable`: "Unless you set `ANTHROPIC_DEFAULT_FABLE_MODEL`, the `fable` alias resolves to Fable 5 in Claude apps gateway sessions and to Fable 5.2 everywhere else." On Bedrock, Google Agent Platform, Foundry the sonnet/haiku aliases resolve to older models (Sonnet 4.5, Haiku 4.5), and on Foundry `opus` is Opus 4.6; models.json assumes the Anthropic API provider.

### Prices: CONFIRMED
All 16 values (in, out, cache_read, cache_write_5m, cache_write_1h for 4 models) match the pricing.md table in fact 10. Specifically Fable 8/40/0.2/10/16; Opus 4/20/0.2/5/8; Sonnet 2/10/0.1/2.5/4; Haiku 0.1/0.5/0.01/0.125/0.2. fallback_price equals the Opus 5.5 row; that is an internal choice, not an official claim, and I did not check it against any page.

Gap, Haiku long prompts: pricing.md lists "Claude Haiku 5.5 (for prompts over 100,000 tokens)": $0.50 in, $0.625 / $1 cache write, $0.05 cache read, $2.50 out. models.json records only the up-to-100K tier. Any cost routing that sends Haiku a prompt over 100K tokens under-prices it by 5x. This matches the earlier memo's point (docs/research/01-models.md B4) that Haiku prompts should stay at or under 100K.
Batch (50% off) and fast mode prices are not in models.json; fast mode prices are in fact 17.

### Context limits: CONFIRMED (not stored in models.json)
https://platform.claude.com/docs/en/models/overview.md: context window 1M tokens and max output 128K tokens for all four models (synchronous Messages API). Batch API: Opus 5.5, Sonnet 5.5, Haiku 5.5 "support up to 300k output tokens with the output-300k-2026-03-24 beta header"; Fable 5.2 is not in that list. Haiku 5.5 carries the over-100K price tier above.

### Effort levels: CONFIRMED
- Levels per model, https://code.claude.com/docs/en/model-config.md: Fable models, Opus 5.5, Sonnet 5.5, Haiku 5.5 all support `low`, `medium`, `high`, `xhigh`, `max`. Every effort value in models.json roles and escalation (low, medium, high) is valid on all four.
- Defaults: see fact 9 (CC `medium` for all four; API Fable `high`, Opus `medium`, Sonnet `high`, Haiku `medium`).
- Not checked: the `effortLevel` setting accepting only `low` to `xhigh`, not `max` (a claim in docs/research/01-models.md B2, outside this task's list).

### Roles and escalation: out of scope
Role-to-model mappings and `limits` (max_parallel_helpers 4, etc.) are design choices, not official claims. Related official limit: 20 concurrent subagents by default (fact 8), so 4 is within it.

## What I did not check or could not reach

- Individual model pages (platform.claude.com/docs/en/models/opus-5-5/overview and the Sonnet/Haiku equivalents): I used the Fable 5.2 page and the models overview table instead. The Fable 5.2 system card was not fetched.
- Several fetches were truncated by the fetch tool: model-config.md (read 0-100000 of 132,827 chars), sub-agents.md (0-100000 of 116,972), skills.md (0-100000 of 118,895), optimizing-for-cost-and-intelligence.md (all but the last 14,126 of 214,126). Content after those offsets was not read.
- Fetch results came through a summarising tool; quotes marked as page text are what the tool returned, and the announcement-page quotes (fact 18) are short extracts. A second look at the full announcement text is advisable before the wording of fact 18 is changed.
- Local measurement behind fact-cost-shape was not recomputed.
- The built-in Explore agent's model on a subscription was not re-read.
- Claude apps (claude.ai) usage limits and plan-tier Fable allowances were not checked; none of the 18 facts depends on them except the usage-credit billing line in fact 17. https://code.claude.com/docs/en/model-config.md says "Depending on your plan and seat tier, Fable usage can bill to usage credits instead of drawing on your plan's included limits", which is the same surface question the earlier memo left open for Max.

## Pages fetched (all on 2026-11-10)

https://platform.claude.com/docs/en/models/fable-5-2/overview.md
https://platform.claude.com/docs/en/models/overview.md
https://platform.claude.com/docs/en/about-claude/pricing.md
https://platform.claude.com/docs/en/build-with-claude/fast-mode.md
https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence.md
https://code.claude.com/docs/en/model-config.md
https://code.claude.com/docs/en/fast-mode.md
https://code.claude.com/docs/en/prompt-caching.md
https://code.claude.com/docs/en/sub-agents.md
https://code.claude.com/docs/en/costs.md
https://code.claude.com/docs/en/skills.md
https://code.claude.com/docs/en/memory.md
https://code.claude.com/docs/en/settings.md
https://code.claude.com/docs/en/cloud-environments.md
https://code.claude.com/docs/en/claude-projects.md
https://code.claude.com/docs/en/claude-code-on-the-web.md
https://www.anthropic.com/claude-fable-and-mythos-5-2
https://www.anthropic.com/engineering/multi-agent-research-system

END OF MEMO
