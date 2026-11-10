# Round 4 / 02 - Claude Code platform behaviours (CB-207)

Retrieved 2026-11-10 via WebFetch of official pages. Surface: Claude Code (CLI) unless stated. WebFetch summarises pages with a small model, so quotes are as returned by the tool; the first 100,000 characters of the skills, sub-agents, model-config, hooks pages were covered (skills page tail re-read from offset 80,000).

## Answers

| # | Question | Status |
|---|---|---|
| 1 | Skill description budget and overflow | CONFIRMED |
| 2 | Skill frontmatter hooks run, and when | CONFIRMED |
| 3 | Sub-agent `effort` and `model` honoured; `omitClaudeMd` | CONFIRMED (with precedence caveats) |
| 4 | Mid-session effort/model change invalidates cache | CONFIRMED (model: yes; effort: model-dependent) |
| 5 | Cache lifetime | CONFIRMED |

### 1. Skill description budget
URL: https://code.claude.com/docs/en/skills (section "Skill descriptions are cut short" and frontmatter reference)
- "The listing always contains every skill name, but if you have many skills, Claude Code drops some descriptions to fit the listing's character budget... The budget scales at 1% of the model's context window. When the listing overflows, Claude Code drops descriptions starting with the skills you invoke least, so the skills you use most keep their full text."
- "each entry's combined text is capped at 1,536 characters regardless of budget. The cap is configurable with `skillListingMaxDescChars`." (`description` + `when_to_use` combined.)
- Raise budget: `skillListingBudgetFraction` setting (e.g. 0.02) or `SLASH_COMMAND_TOOL_CHAR_BUDGET` (fixed character count). `"name-only"` in `skillOverrides` lists a skill without description. A warning goes to the debug log (`--debug`) on overflow.
- Names are never dropped; descriptions are.

### 2. Skill frontmatter hooks
URLs: https://code.claude.com/docs/en/hooks (section "Hooks in skills and agents"); https://code.claude.com/docs/en/skills (frontmatter table)
- "Skill hooks: Claude Code registers them when you or Claude invoke the skill and keeps running them for the rest of the session, on turns after the skill's own turn as well. To have Claude Code remove a hook after its first successful run instead, set `once: true` on it."
- Subagent hooks (contrast): "run them only while that subagent is running and removes them when it finishes."
- Caveats: project-skill hooks follow the workspace trust rule, but are registered even in a `-p` run in an untrusted folder. When managed settings list `hooks` in `strictPluginOnlyCustomization`, a personal/project skill's frontmatter hooks "don't run" (skills page). v2.1.304+: max 1,024 hooks per skill source per session (hooks page, as summarised).

### 3. Sub-agent effort / model / omitClaudeMd
URL: https://code.claude.com/docs/en/sub-agents (frontmatter table; "choose a model")
- model: honoured. Resolution order: "1. per-invocation `model` parameter 2. the subagent definition's `model` frontmatter, where `inherit` selects the main conversation's model 3. `CLAUDE_CODE_SUBAGENT_MODEL` env var 4. the main conversation's model". With `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` on, "Claude Code ignores the `model` field in subagent definitions." Organization `availableModels` can substitute another model.
- effort: honoured. "Effort level when this subagent is active. Overrides the session effort level, but not the `CLAUDE_CODE_EFFORT_LEVEL` environment variable. Options: low, medium, high, xhigh, max; available levels depend on the model." Per-invocation parameter overrides the field (needs v2.1.292+); the env var beats both.
- omitClaudeMd: "Set to `true` to start this subagent without the user, project, and local CLAUDE.md files in its initial context; managed policy files still load, except for managed subagents. Use it for subagents that take everything they need from the delegation prompt. Ignored when the agent runs as the main session agent via `--agent` or the `agent` setting. Requires Claude Code v2.1.271 or later." Explore and Plan already skip CLAUDE.md; nested-directory CLAUDE.md and matching path-scoped rules still load when the subagent works with files there.

### 4. Cache invalidation on model/effort change
URL: https://code.claude.com/docs/en/prompt-caching (Claude Code); API view: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Model: "Each model has its own cache. Switching with `/model` means the next request reads the entire conversation history with no cache hits, even though the content is identical." Claude Code asks for confirmation only while the cache is warm (v2.1.238+). A skill/command frontmatter `model` differing from the session model "is also a model switch" for that turn; a `context: fork` skill sets the forked subagent's model instead (no parent-cache effect stated).
- Effort: "On most models, changing the effort level mid-session means the next request reads the entire conversation history with no cache hits. While the cache is still warm, Claude Code asks you to confirm the change first." Exception: "With an API key or a Claude subscription, changing effort keeps the cache on Fable 5.1 and later, Opus 5.5, Sonnet 5.5, and Haiku 5.5." Exception does not apply on Bedrock, Google Cloud Agent Platform, a Claude apps gateway, with `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`, or HIPAA configuration. Before v2.1.260, effort change on Fable 5.1 also invalidated.
- Subagents: "Its first request doesn't read the parent's cache, because the two prefixes differ"; parent's cache is unaffected by spawning one. (Same page, "Subagents and the cache".)
- Related: skills invocation appends as messages and keeps the cache; enabling/disabling plugin skills/agents/hooks keeps it.
- API: effort change "always invalidates message blocks", model-specific for tools/system; setting effort to the model's default equals omitting it (API page table).

### 5. Cache lifetime
- Claude Code: "The API offers two: a five-minute TTL, and a one-hour TTL". Defaults: main conversation = one hour on a Claude subscription within plan usage, five minutes with usage credits, API key or cloud provider. Everything else (subagents, workflows, compaction, titles) = five minutes (some server-controlled helpers get one hour on subscription). Override: `promptCacheTtl` / `CLAUDE_CODE_PROMPT_CACHE_TTL`, `subagentPromptCacheTtl` / `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` (v2.1.242+), `FORCE_PROMPT_CACHING_5M=1`, `ENABLE_PROMPT_CACHING_1H=1`; subagent frontmatter `experimental.cacheTtl` (v2.1.248+). Source: https://code.claude.com/docs/en/prompt-caching ("Cache lifetime")
- API: "By default, the cache has a 5-minute lifetime. The cache is refreshed for no additional cost each time the cached content is used." 1-hour option at additional cost. Source: https://platform.claude.com/docs/en/build-with-claude/prompt-caching

## Caveats / not checked
- Inference: for brain design, a sub-agent with a different `model` has its own cache anyway (separate conversation); not stated as such by docs beyond "its own cache" wording.
- Not read: the last ~17-65k characters of the skills, sub-agents, model-config, API prompt-caching pages; the hooks page beyond the first 100k (only the targeted section was returned). Model-config page said nothing on caching.
- Not checked: CB-201 live observations against these docs; release notes/changelog; settings-reference pages for `skillListingBudgetFraction` and `skillListingMaxDescChars`.
- Model and version names (Fable 5.1, Opus 5.5, Sonnet 5.5) are as the docs list them today.

END OF MEMO
