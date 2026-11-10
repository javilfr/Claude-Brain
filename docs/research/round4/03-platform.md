# Round 4 / 03 - Claude Code platform facts, official docs only

Fetched 2026-11-10 from code.claude.com (primary). docs.claude.com was not needed. Quotes are as returned by the fetch tool, which summarises pages with a small model; quotes marked "verbatim" came back in quotation form, and the exact wording is worth one re-check before the lead records it as a fact. Pages over 100,000 characters were read only in part (noted per item).

## Answers in brief (confidence: high for 1, 2, 4, 5; medium for 3)

1. Skill listing: every skill name is always listed; each entry's description plus when_to_use is capped at 1,536 characters; total listing budget is 1% of the model's context window; all three are configurable.
2. Effort change: it depends on the model and provider. On most models it invalidates the cache. With an API key or Claude subscription on Fable 5.1 and later, Opus 5.5, Sonnet 5.5 and Haiku 5.5, it keeps the cache. This differs from a blanket "changing effort keeps the cache" (see "Conflict with memory" below).
3. Project hooks in .claude/settings.json run in cloud sessions only when the session has one repository and is not a project thread. Hook events are not listed per event for the cloud; the docs say SessionStart behaves the same as locally. PreToolUse, Stop, SubagentStop in cloud: not documented individually.
4. Skill frontmatter hooks exist (`hooks` field). They register when the skill is invoked and persist for the rest of the session.
5. Subagent frontmatter has `model`, `effort` and `omitClaudeMd` (needs v2.1.271 or later).

## 1. Skill names and descriptions in context

Source: https://code.claude.com/docs/en/skills (troubleshooting section "Skill descriptions are cut short" and the frontmatter reference).

- "Every skill in the [skill listing] adds to your context on every turn, whether or not Claude ever uses it." The page gives no per-skill token figure (not documented).
- "in a regular session, skill descriptions are loaded into context so Claude knows what's available, but full skill content only loads when invoked."
- "The listing always contains every skill name, but if you have many skills, Claude Code drops some descriptions to fit the listing's character budget... The budget scales at 1% of the model's context window. When the listing overflows, Claude Code drops descriptions starting with the skills you invoke least."
- "the combined `description` and `when_to_use` text is truncated at 1,536 characters in the skill listing to reduce context usage." "`when_to_use` ... counts toward the 1,536-character cap." The cap "is configurable with `skillListingMaxDescChars`" (https://code.claude.com/docs/en/settings-reference#skilllistingmaxdescchars).
- To raise the budget: "set the `skillListingBudgetFraction` setting (for example, `0.02` = 2%) or the `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment variable to a fixed character count." Setting entries to `"name-only"` in `skillOverrides` lists them without a description.
- `/doctor` estimates the listing's context cost; the Skills row in `/context` reports the listing size after the budget is applied (accurate since v2.1.196).

Matches memory fact-skill-cost on the 1,536 figure. The 1%-of-context budget and the three setting names are new relative to memory.

## 2. Reasoning effort change and the prompt cache

Source: https://code.claude.com/docs/en/prompt-caching (sections "How the cache is organized" and "Changing effort level").

- "Effort level: on most models, each effort level has its own cache, so changing effort mid-session recomputes the entire request. With an API key or a Claude subscription, the cache stays intact by default on Fable 5.1 and later, Opus 5.5, Sonnet 5.5, and Haiku 5.5."
- "On most models, changing the effort level mid-session means the next request reads the entire conversation history with no cache hits. While the cache is still warm, Claude Code asks you to confirm the change first."
- "With an API key or a Claude subscription, changing effort keeps the cache on Fable 5.1 and later, Opus 5.5, Sonnet 5.5, and Haiku 5.5. Claude Code applies the new level without asking. On Amazon Bedrock, Google Cloud's Agent Platform, or a Claude apps gateway, or when you set `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` or your organization has a HIPAA configuration, it works as on most models."
- "Before v2.1.260, changing effort on Fable 5.1 with an API key or a Claude subscription also invalidated the cache."
- Timing of the change: https://code.claude.com/docs/en/model-config.md says the new level "starts with your next message at the latest." The page has no passage on cache invalidation (it only links to the caching page).

Conflict with memory: memory/facts.jsonl `fact-cache-breakers` says "These keep it: changing effort". That holds only for the model/provider combination above (Fable 5.1+, Opus 5.5, Sonnet 5.5, Haiku 5.5 on API key or subscription, Claude Code v2.1.260 or later). On Bedrock, Vertex-type providers, a Claude apps gateway, with `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`, or under HIPAA config, effort changes invalidate the cache. Suggest qualifying the fact. The other breakers in that fact (model switch, fast mode, MCP, compaction) match the page; the page also lists plugins with MCP servers, denying an entire tool without tool search, many images, and Claude Code upgrades. A skill frontmatter `model` naming another model is a model switch, as memory says.

## 3. Project hooks in .claude/settings.json in cloud / web sessions

Sources: https://code.claude.com/docs/en/cloud-environments (table "what carries over"; section "Setup scripts vs. SessionStart hooks"), https://code.claude.com/docs/en/settings#settings-in-cloud-sessions, https://code.claude.com/docs/en/hooks (section "Cloud and web sessions").

- Cloud environments table: "Your repo's `.claude/settings.json` hooks and permission rules | Yes, in a session with one repository | Part of the clone. For a session with several repositories, see [which settings it reads]".
- settings page: "Shared project settings (`.claude/settings.json`): read in a session with one repository outside a project's threads, because the file is part of the clone and the session starts inside it."
- "in a cloud thread in a project, none of a repository's `.claude/settings.json` permission rules, hooks, or `env` apply, however many repositories the project has."
- "a session with several repositories starts above the clones and reads only the `enabledPlugins` and `extraKnownMarketplaces` keys from each repository's `.claude/settings.json`, not permission rules, hooks, `env`, or other keys."
- User (`~/.claude/settings.json`) and `.claude/settings.local.json` are "not read" in cloud sessions.
- Anthropic-hosted: "Claude Code runs hooks from your organization's server-managed settings and, outside a project thread, from the repository." Claude Tag sessions do not receive server-managed settings.
- Hooks page: "`$CLAUDE_CODE_REMOTE` environment variable is `"true"` in remote web environments and not set in the local CLI."
- SessionStart specifically: "SessionStart hooks behave the same in the cloud as locally, with these caveats" (no cloud-only scoping; needs network access for installs; adds startup latency). Command hooks are cancelled after 600 seconds unless `timeout` is set; the timeout is not enforced for `async: true` hooks. The docs give a worked example of a repo `.claude/settings.json` SessionStart hook with matcher `startup|resume`.

Per event:
- SessionStart: documented as running in the cloud (above). Confirmed.
- PreToolUse, Stop, SubagentStop: all three exist as hook events (https://code.claude.com/docs/en/hooks lifecycle table: PreToolUse "Before a tool call executes. Can block it"; Stop "When Claude finishes responding"; SubagentStop "When a subagent finishes"). No page says they run, or do not run, in a cloud session. The general rule that repo `.claude/settings.json` hooks are loaded applies, and no per-event exclusion is stated. Whether they fire in the cloud: not documented per event; inference (my estimate): they run when the repo hooks load. Not tested.

Conflict check with memory: fact-two-repo-loading ("hooks ... do not [load]" with two repos) agrees with the settings page. It does not mention the single-repo case or project threads, where hooks are also not loaded; worth adding.

## 4. Hooks in skill frontmatter

Sources: https://code.claude.com/docs/en/skills (frontmatter reference), https://code.claude.com/docs/en/hooks (section "Hooks in skills and agents"). The hooks page was read only up to character 100,000 of 293,226; the full per-event reference was not read.

- skills page: the `hooks` field holds "Hooks that Claude Code registers when the skill is invoked and keeps running for the rest of the session."
- hooks page: "hooks can be defined directly in skills and subagents using frontmatter, in the same configuration format as settings-based hooks."
- "Skill hooks: Claude Code registers them when you or Claude invoke the skill and keeps running them for the rest of the session, on turns after the skill's own turn as well. To have Claude Code remove a hook after its first successful run instead, set `once: true` on it." `once` is "Only honored for hooks declared in skill frontmatter; ignored in settings files and agent frontmatter."
- Example in the docs: a `hooks:` block with `PreToolUse`, `matcher: "Bash"`, `type: command`.
- Limits: under the `strictPluginOnlyCustomization` managed setting a non-plugin, non-bundled, non-managed skill's hooks do not run. From v2.1.304, each skills source (project, personal folder, each plugin) can register at most 1,024 hooks, matchers totalling at most 16,384 characters.
- Project-skill frontmatter hooks follow the workspace-trust rule, but "Claude Code registers them when you or Claude invoke the skill, including in a `-p` run in a folder you haven't trusted."
- Which events are valid in skill frontmatter: only the PreToolUse example is shown; a complete list is not documented in what I read (unconfirmed).

## 5. Subagent definitions: model, effort, omitting CLAUDE.md

Source: https://code.claude.com/docs/en/sub-agents (frontmatter table; read characters 0 to 100,000 of 116,972). Exact field names ("Field names are case-sensitive and must match the table exactly. Claude Code ignores unrecognized fields without reporting an error."):

- `model` (optional): "`sonnet`, `opus`, `haiku`, `fable`, a full model ID such as `claude-opus-5-5`, or `inherit`. When you omit it, Claude Code picks the model in the subagent model order."
- `effort` (optional): "Effort level when this subagent is active. Overrides the session effort level, but not the `CLAUDE_CODE_EFFORT_LEVEL` environment variable. Options: `low`, `medium`, `high`, `xhigh`, `max`; available levels depend on the model."
- `omitClaudeMd` (optional): "Set to `true` to start this subagent without the user, project, and local CLAUDE.md files in its initial context; managed policy files still load, except for managed subagents... Ignored when the agent runs as the main session agent via `--agent` or the `agent` setting. Requires Claude Code v2.1.271 or later."
- Also relevant: `hooks` (lifecycle hooks scoped to the subagent; ignored for plugin subagents; a `Stop` hook there is converted to `SubagentStop`), and an `experimental` field with `cacheTtl` (v2.1.248 or later; per the caching page).

Matches memory fact-claudemd-cost and fact-subagent-model on `omitClaudeMd` and `model`. The subagent model resolution order in memory was not re-verified here (the sub-agents page points to a "subagent model order" section I did not read).

## Not found / not checked

- Per-skill token cost: not documented.
- Per-event (PreToolUse, Stop, SubagentStop) behaviour in cloud sessions: not documented.
- Full list of events valid in skill frontmatter: not read.
- Hooks page characters 100,000 to 293,226, skills page body before the troubleshooting section, sub-agents page after character 100,000 and docs.claude.com: not read.
- Nothing was run or tested; all items are doc statements, not observed behaviour. Fetch summaries came through a small model, so wording is near-verbatim, not guaranteed.

END OF MEMO
