# 02 — Claude Code platform as of 2026-11-10 (analyst 2 of 10)

Method: downloaded the raw Markdown of the official docs (`https://code.claude.com/docs/llms.txt` and ~50 pages under `https://code.claude.com/docs/en/*.md`) with curl and quoted them directly; nothing below is from memory. Local copies: `/tmp/claude-0/-home-user/ad24da2f-7dc0-51cf-aa28-dee6f5e57a4f/scratchpad/research/dl02/`. I also inspected this live two-repo cloud session (read-only) as a test bed.

Tags: **[doc: page]** = quoted from `https://code.claude.com/docs/en/<page>`; **[observed]** = seen in this session; **[inference]** = reasoned from docs, not stated; **[untested]** = needs an experiment before the plan relies on it.

---

## HEADLINE CORRECTION (affects the whole plan)

The briefing's "Known context" says both repos' hooks and `.mcp.json` are loaded. **The docs say the opposite for a session with several repositories, and this session confirms the docs.**

- [doc: settings#settings-in-cloud-sessions] "in an Anthropic-hosted environment, a session with several repositories starts above the clones and reads only the `enabledPlugins` and `extraKnownMarketplaces` keys from each repository's `.claude/settings.json`, not permission rules, hooks, `env`, or other keys. The marketplaces and plugins those two keys declare still don't load in a cloud session."
- [doc: cloud-environments#limitations-in-cloud-sessions] "a session with several repositories doesn't load hooks from any repository's `.claude/settings.json`, so a SessionStart hook you define there doesn't run. Install dependencies for those sessions with a setup script instead."
- [doc: cloud-environments#what-carries-over-from-your-setup] `.mcp.json`: "Yes, in a session with one repository ... found from the session's working directory."
- [observed] This session's working directory is `/home/user` (above both clones). The sample repo's `SessionStart` hook would have created `library/.venv`; it does not exist, and `/tmp/library-rebuild.log` is absent. No `mcp__library__*` tool is in the tool list although the sample repo's `.mcp.json` declares a `library` server. The only active hooks are the platform's own (`/root/.claude/launcher-settings.json`: one SessionStart, one Stop). Agents and skills from the sample repo ARE present. `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` is set, which is the documented switch that loads CLAUDE.md from added directories.

Consequence: in the owner's stated operating mode (always two repos), **settings.json hooks, permission rules, `env`, `.mcp.json` servers, statusline, output-style settings and repo-declared plugins from the Brain repo do nothing.** The sample repo's hooks (path protection, payroll gate/meter, checkpoint reminder, session-start) and its Library MCP server were inert in every two-repo cloud session. The Brain must be designed around what actually loads.

---

## PART A — Requirement extraction from owner message 2

| # | Requirement / constraint / expectation | Exact words |
|---|---|---|
| A1 | The sample repo functioned as a "brain"; the new thing generalises that role | "I essentially used this repo as a brain to create everything in my travel journal in the best possible way" |
| A2 | Create a new repository that plays that role | "I want now to create a repo that will act as that" |
| A3 | It is an orchestrator, and a very elaborate one | "(essentially a mega complex orchestrator)" |
| A4 | Scope is universal and open-ended in time | "to build anything I will ever need from now on" |
| A5 | Fixed usage pattern: two repos per chat | "When using it I will always use two repos in a chat" |
| A6 | Repo 1 is the Claude Brain | "one of them the Claude brain" |
| A7 | The Brain is modified only by its own learning systems, not by hand and not by project work | "which will be only modified by its own machine learning systems" |
| A8 | The Brain improves continuously from every use | "as it improves by learning with everything I use it for" |
| A9 | Repo 2 is where the project is built | "the other repo will be where the project will be built" |
| A10 | The project repo may carry project-specific files and tools that complement the Brain | "which can also hold files and tools to complement the Claude brain functionality that are specific to that project" |
| A11 | Both are always used together | "both will always be worked together from now on" |
| A12 | Durable compatibility contract between the two | "so the project must be built to work perfectly with it forever" |
| A13 | Deliverable 1: a very long, very detailed plan | "you will create a super long, super detailed plan on how to build this" |
| A14 | The plan must rest on thorough model research | "based on very comprehensive research about Claude fable 5.2 and opus 5.5" |
| A15 | Those two are the primary models | "(the main models ai will use it with)" — "ai" is almost certainly a typo for "I" |
| A16 | Reuse every lesson from the sample repo | "also using everything we learned with the sample repo I attached" |
| A17 | But do not copy its narrow scope | "(obviously having present that the current Claude brain's scope for creating stuff is much bigger)" |
| A18 | Review memory and all prior chats in detail | "you must look at all your memory in detail and all our chats" |
| A19 | Everything he has ever asked for must be something the Brain can complete | "consider everything I have ever asked you to build on Claude or any question I have ever asked you can be successfully processed to completion" |
| A20 | Top priority: efficiency | "Also VERY IMPORTANT, you MUST MAKE THIS THE MOST EFFICIENT CLAUDE TOOL EVER" |
| A21 | Token efficiency via specific means | "much more efficient in tokens through plugins and algorithms and quantum logic and many other thing you must research" |
| A22 | Speed | "super efficient token wise and super fast" |
| A23 | Quality must not be traded away | "while delivering the absolutely highest quality work with absolute attention to detail" |
| A24 | Three named quality axes | "(focus a lot on accuracy, creativity and extreme attention to detail)" |
| A25 | Plan must also draw on all earlier builds | "considering also all our previous builds in Claude" |
| A26 | Deliverable 2: build to completion after the plan, without a stop for approval | "and then start building until completion once you have a full plan based on extremely extensive research" |
| A27 | Process: ten independent analyses of this prompt | "Make sure you analyze this prompt by 10 independent agents and extract everything I said in full detail" |
| A28 | Standard of execution | "you can execute to perfection by planning perfectly and researching and analyzing heavily everything" |
| A29 | Implied (message 1): the sample repo is read-only | "we will not modify or touch this repo at all in this chat, just read it" |

Implied expectations (not stated, but follow from the text and context):
- I1. Non-technical operation: he clicks and reads; he never runs commands. Any setup step the Brain needs from him must be a short click path.
- I2. The Brain must work in cloud sessions on a Max subscription, so "cost" means plan usage and rate limits, not dollars.
- I3. A project repo needs a standard, small "adapter" so any new repo plugs into the Brain the same way (A10 + A12).
- I4. "Forever" implies versioning of the Brain-to-project contract and a compatibility check at session start.
- I5. "Learning" must be safe: it must not degrade the Brain, so it needs evaluation and rollback.

Items needing honest reframing or flagged as impossible:
- R1. **"machine learning systems" (A7)**. Nothing in Claude Code trains or fine-tunes a model. What is achievable: a disciplined, file-based learning loop (lessons, skills, rules and evals committed to the Brain repo by a dedicated learning job). Say so plainly and name it accurately.
- R2. **"only modified by its own machine learning systems" (A7)**. No platform control enforces this in a two-repo cloud session: repo hooks and permission rules do not load there (see headline), and the GitHub proxy "doesn't limit which branches a push can update" [doc: cloud-environments#github-proxy]. Enforcement has to come from GitHub branch protection or rulesets on the Brain repo plus a convention (learning goes through a dedicated branch or scheduled task). Also note the first build is necessarily written by a session, not by the learning system.
- R3. **"quantum logic" (A21)**. There is no quantum computing available to Claude Code and no documented feature by that name. Reframe as: research classical techniques that do reduce tokens (retrieval instead of loading, caching, deferred loading, deterministic scripts) and state that quantum methods are not applicable. Do not invent a "quantum" component.
- R4. **"THE MOST EFFICIENT CLAUDE TOOL EVER" (A20)**. Not verifiable as a superlative. Reframe as measurable targets: always-loaded tokens at session start, tokens per completed task, cache hit rate, compared against the sample repo as baseline.
- R5. **"all our chats" / "all your memory" (A18, A19)**. A cloud session can only read what is exposed to it (repos, any memory files, attached material). Prior claude.ai chat history is not readable from here unless provided. State what was actually reviewed and what was not.
- R6. **"anything I will ever need" / "forever" (A4, A12)**. Unbounded. Reframe as an extensible core with a domain-pack mechanism and a versioned contract; the platform itself changes (several features below are labelled experimental or research preview).
- R7. **"execute to perfection" / "absolutely highest quality" with maximum token efficiency (A20, A23, A28)**. These pull against each other: the docs say workflows and agent teams use "meaningfully more tokens" and "approximately 7x more tokens". The plan must state the trade rule (quality gates are fixed; efficiency is optimised subject to them).
- R8. **"plugins" as the efficiency mechanism (A21)**. Repo-declared plugins do not load in cloud sessions (Part B.3). Plugins are still usable through other routes, but this must be designed, not assumed.
- R9. **"build until completion" (A26)**. A session can end or be reclaimed; "completion" needs a definition and a checkpoint/resume file, as the sample repo did.

Ambiguities to resolve by assumption (record, do not ask): whether "Claude" in "everything I have ever asked you to build on Claude" means claude.ai chat, Claude Code, or both; whether the Brain repo is private; whether the Brain should also be usable in single-repo or local sessions (where hooks DO load); whether non-software deliverables (documents, research, decks) are in scope (A4 suggests yes).

---

## PART B — Platform findings

### B1. Two repos in one cloud session: what loads

Mechanism [inference from doc + observed]: the session "starts above the clones", and the clones behave like added directories. The local-CLI rule for added directories matches what is seen: [doc: skills#skills-from-additional-directories] "When you add a directory with `--add-dir` ... Claude Code loads the skills in that directory's `.claude/skills/`, along with its `.claude/commands/` and `.claude/agents/`." and [doc: permissions] the section is titled "Additional directories grant file access, not configuration".

| Item (per repo) | Two-repo cloud session | Basis |
|---|---|---|
| Root `CLAUDE.md`, `.claude/CLAUDE.md` | Loaded from both | [doc: cloud-environments] "Your repo's `CLAUDE.md` — Yes"; [observed] |
| `.claude/rules/*.md` without `paths` | Loaded | [doc: memory#load-from-additional-directories] "This loads `CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/rules/*.md`" |
| `.claude/rules/` with `paths:` | **[untested]** in this layout | docs describe on-demand loading generally; not stated for multi-repo |
| `.claude/skills/`, `.claude/agents/`, `.claude/commands/` | Loaded from both | [doc: cloud-environments] "Yes — Part of the clone"; [observed] |
| `.claude/settings.json` hooks, permissions, `env`, other keys | **Not loaded** | [doc: settings] quoted in headline; [observed] |
| `.mcp.json` | **Not loaded** | [doc: cloud-environments] "Yes, in a session with one repository"; [observed] |
| Plugins via `enabledPlugins` / `extraKnownMarketplaces` | **Not installed** (keys are read, nothing loads) | [doc: cloud-environments] "A cloud session doesn't install the plugins a repository turns on under `enabledPlugins`, including ones from the marketplaces it lists under `extraKnownMarketplaces`" |
| Plugin folder inside a repo's `.claude/skills/` (`@skills-dir`) | **Probably not as a plugin** [inference]; its root `SKILL.md` still loads as a plain skill | [doc: plugins/loading] "Claude Code reads the `.claude/skills/` of the session's primary working directory and ... doesn't search parent directories for plugins"; also gated by a trust dialog a cloud session never shows |
| `.claude/workflows/*.js` | **[untested]** | [doc: workflows] loads "from every `.claude/workflows/` along that path" between working directory and repo root; multi-repo not addressed |
| User `~/.claude/*` from his own computer | Not available | [doc: cloud-environments] "Lives on your machine, not in the repo" |
| Skills enabled on his claude.ai account | Loaded | [doc: cloud-environments] "Cloud sessions automatically load skills you enable on claude.ai"; [observed] `/root/.claude/skills/synced/` |
| Plugins enabled on his claude.ai account | **[untested]**; docs name only Cowork and terminal | [doc: plugins/loading] "Synced plugins load in Cowork sessions and in terminal sessions"; [observed] an empty `/root/.claude/plugins/synced/` and `CLAUDE_CODE_SYNC_PLUGINS=1` exist here |
| Auto memory | Does not persist | [doc: memory] "Auto memory is machine-local ... Files are not shared across machines or cloud environments." |
| Agent frontmatter `hooks` / inline `mcpServers` in repo agents | Probably not [inference] | [doc: permissions#what-runs-before-you-trust-a-folder] "Not used" without the trust dialog; [doc: plugins/loading] "the workspace trust dialog, which a cloud session never shows" |
| **Skill frontmatter `hooks`** in a repo skill | **Probably YES** [inference, untested] | same table: "a project skill's hooks and `allowed-tools` — Used" in the never-trusted column; [doc: hooks] skill hooks are registered "when you or Claude invoke the skill and ... for the rest of the session" |

A different product, **Projects** (public beta), is stricter still: [doc: claude-projects] "Cloud threads load each repository's `CLAUDE.md` instructions but not its skills, `.mcp.json` servers, or `.claude/settings.json`". The Brain should target ordinary multi-repo sessions, not Project threads.

Routes that could restore hooks, MCP and plugins for the Brain in two-repo sessions (ranked; all need a 10-minute test):
1. **Skill-scoped hooks.** A Brain skill (for example `brain-boot`) whose frontmatter declares the hooks; the Brain `CLAUDE.md` tells Claude to invoke it first. Stays inside the repo, needs nothing from Javier. Limits: [doc: hooks] 1,024 hooks per skill source; `SessionStart` cannot be covered this way because the skill is invoked after start.
2. **Cloud environment setup script** (he pastes it once into the environment dialog). Documented use: [doc: cloud-environments] "add a setup script that writes `~/.claude/CLAUDE.md` ... Claude Code loads that file as user instructions". Extending this to copy the Brain's plugin folder into `~/.claude/skills/<name>/` (a user-level skills-directory plugin: [doc: plugins/loading] "Neither the trust check nor these component limits apply to a plugin under your own `~/.claude/skills/`") or to write `~/.claude/settings.json` is [untested]. Caveat: the result is frozen in the environment snapshot for up to about seven days.
3. **Environment variable `CLAUDE_CODE_PLUGIN_DIRS`** set on the cloud environment to the Brain's plugin path. [doc: env-vars] "Plugin directories to load for the session, each loaded the way a `--plugin-dir` flag loads it ... absolute path". Whether a cloud session honours it is [untested].
4. **MCP without `.mcp.json`**: claude.ai connectors (traffic "travels through Anthropic's servers" [doc: cloud-environments]) or, cheaper, a plain command-line script in the Brain repo that Claude runs with Bash.

### B2. Cheapest way to ship a large instruction body

| Mechanism | Always in context | On demand | Notes |
|---|---|---|---|
| CLAUDE.md | Whole file, every request | — | [doc: memory] "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence." Survives compaction ("re-injected from disk"). Block HTML comments are stripped before injection (free maintainer notes). With two repos, both files are paid for on every request and by every non-Explore subagent. |
| `@imports` | Same as CLAUDE.md | — | [doc: memory] "Imports help you organize a long file but don't reduce its context cost, because imported files load together"; max depth "four hops". No saving. |
| `.claude/rules/` unscoped | Whole file | — | "loaded at launch with the same priority as `.claude/CLAUDE.md`" |
| `.claude/rules/` with `paths:` | Nothing | When Claude reads or edits a matching file | Lost at compaction until re-triggered: [doc: context-window] "compaction summarizes them away" |
| Skills | Name + description only | Body on invocation; supporting files only when read | [doc: skills] description+`when_to_use` "truncated at 1,536 characters"; listing budget "scales at 1% of the model's context window"; overflow drops descriptions of least-used skills. "Keep `SKILL.md` under 500 lines." After compaction: "first 5,000 tokens of each ... combined budget of 25,000 tokens". `disable-model-invocation: true` gives "Description not in context" (zero standing cost, but only the user can invoke it). `skillOverrides: "name-only"` lists a skill without its description. |
| Subagents | Name + description in the Agent tool listing [inference] | Body is the subagent's system prompt, in its own window | [doc: sub-agents] a subagent also gets "every level of the CLAUDE.md hierarchy" unless `omitClaudeMd: true`; `skills:` preloads "the full skill content". Only the final summary returns to the main context. |
| MCP | "Only tool names and server instructions" | Full schemas via tool search | [doc: mcp] deferred by default; server instructions capped at 4,096 chars; results over 25,000 tokens limited (`MAX_MCP_OUTPUT_TOKENS`). [doc: costs] CLI tools "are still more context-efficient than MCP servers because they don't add any per-tool listing". |
| Hooks | Zero | Only what the hook returns | [doc: features-overview] "Zero, unless hook returns additional context" |
| Plain files read on demand | Zero | Cost of the read | A one-line pointer in a skill is enough. |

Ranking for a big corpus [inference]: script or retrieval tool run through Bash (zero standing cost) < skills with short descriptions and supporting files < path-scoped rules < subagent bodies < MCP server < CLAUDE.md. The Brain's CLAUDE.md should be a short router; everything procedural belongs in skills; reference knowledge belongs in files reached through a retrieval script.

Prompt-cache facts that shape design [doc: prompt-caching]: main conversation gets a one-hour cache on a subscription, subagents and workflow agents five minutes; "Each model has its own cache. Switching with `/model` means the next request reads the entire conversation history with no cache hits"; a skill whose frontmatter names another `model` "is also a model switch" (use `context: fork` instead); changing effort keeps the cache on Fable 5.1+ and Opus 5.5; editing CLAUDE.md mid-session "doesn't apply" until `/clear`, `/compact` or restart.

### B3. Plugins and marketplaces

- Plugin layout [doc: plugins/manifest-reference#standard-layout]: `.claude-plugin/plugin.json` (optional manifest), `skills/`, `commands/`, `agents/`, `hooks/hooks.json`, `.mcp.json`, `.lsp.json`, `output-styles/`, `workflows/`, `themes/`, `monitors/monitors.json`, `bin/`, `settings.json`. "A `CLAUDE.md` at the plugin root isn't loaded as context."
- Marketplace [doc: plugins/create-marketplace]: "A marketplace is a directory with a `.claude-plugin/marketplace.json` file, plus the plugins it lists." The file "requires a `name`, an `owner`, and a `plugins` array"; each entry "needs a `name` and a `source`" (relative path, `github`, `url`, `git-subdir`, `npm`, `archive`, `command`). So one Git repo can be both marketplace and plugin.
- Cross-repo enablement in principle: the project repo's `.claude/settings.json` lists the Brain under `extraKnownMarketplaces` (source `github`, fields `repo`, `ref`, `path`) and turns it on under `enabledPlugins` as `"<name>@<marketplace>": true`.
- **In cloud sessions this does not work**: [doc: plugins/install] a cloud session "has no plugin browser and doesn't load the plugins you installed on your own machine or the ones your repository's `.claude/settings.json` turns on"; [doc: plugins/loading] "A cloud session doesn't add the marketplaces a repository lists under `extraKnownMarketplaces`, because that requires the workspace trust dialog, which a cloud session never shows."
- Plugin agents are weaker: `permissionMode`, `mcpServers` and `hooks` frontmatter are "Ignored for plugin subagents" [doc: sub-agents].
- Recommendation [inference]: lay the Brain out so it is simultaneously a plain `.claude/` repo (works today in two-repo cloud sessions for CLAUDE.md, skills, agents, commands) and a valid plugin/marketplace (for local, desktop and any future cloud support). Do not make any required behaviour depend on plugin loading.

### B4. Hooks

Deterministic, no model tokens: handler types `command`, `http`, `mcp_tool` run outside the model; `prompt` and `agent` hooks do spend tokens [doc: hooks#hook-handler-fields]. Events (33): SessionStart, Setup, UserPromptSubmit, UserPromptExpansion, PreToolUse, PermissionRequest, PermissionDenied, PostToolUse, PostToolUseFailure, PostToolBatch, Notification, MessageDisplay, SubagentStart, SubagentStop, TaskCreated, TaskCompleted, Stop, StopFailure, TeammateIdle, InstructionsLoaded, ConfigChange, CwdChanged, DirectoryAdded, FileChanged, WorktreeCreate, WorktreeRemove, PreCompact, PostCompact, PreModelSwitch, PostModelSwitch, Elicitation, ElicitationResult, SessionEnd.

Contract [doc: hooks]:
- stdin: JSON with `session_id`, `transcript_path`, `cwd`, `scratchpad_dir`, `permission_mode`, `effort`, `hook_event_name`, plus event fields (`tool_name`/`tool_input`, `prompt`, `source`, `agent_type`, `last_assistant_message`, ...).
- Exit 0 = success; exit 2 = block where the event can block (stderr is the reason); other codes = non-blocking error.
- stdout JSON: universal `continue`, `stopReason`, `systemMessage`; top-level `decision: "block"` + `reason` (UserPromptSubmit, PostToolUse, Stop, SubagentStop, PreCompact ...); `hookSpecificOutput` with `hookEventName`.
- Inject context: `hookSpecificOutput.additionalContext` ("wraps the string in a system reminder"); plain stdout also becomes context on UserPromptSubmit and SessionStart. Cap: "capped at 10,000 characters"; over that, a file path plus a 2,000-character preview.
- Rewrite: PreToolUse `updatedInput` ("Replaces the entire input object") with `permissionDecision` allow/deny/ask/defer; PostToolUse `updatedToolOutput` "Replaces the tool's output". "`UserPromptSubmit`: can't replace the prompt".
- Stop hooks can force continuation, with an "8-consecutive-continuation cap" and `stop_hook_active`.
- PreCompact stdout "becomes instructions for the compaction summary"; SessionStart with matcher `compact` re-injects after compaction.
- SessionStart extras: `additionalContext`, `sessionTitle`, `watchPaths`, `reloadSkills`; `CLAUDE_ENV_FILE` to persist variables.
- Timeouts: 600 s default for command hooks, 30 s on UserPromptSubmit.
- The official token-saving example is a PreToolUse hook that rewrites test commands to show only failures [doc: costs#offload-processing-to-hooks-and-skills].

Cloud limits: all of the above is unavailable from repo settings in a two-repo session (headline). Setup script vs SessionStart hook [doc: cloud-environments]: setup script is configured in the environment dialog, runs "Before Claude Code launches, skipped when a cached environment exists", must finish in "roughly five minutes" to be cached, cache "expiry after roughly seven days", runs before the environment's variables are set, and "Anyone who uses the environment can read its ... setup script". For multi-repo sessions the docs name the setup script as the replacement for SessionStart hooks.

### B5. Subagents and workflows (cost mechanics)

- Frontmatter [doc: sub-agents#frontmatter-reference]: `name`, `description`, `tools`, `disallowedTools`, `model` (`sonnet`/`opus`/`haiku`/`fable`/full ID/`inherit`), `permissionMode`, `maxTurns`, `autoCompactWindow`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `omitClaudeMd`, `effort` (`low`..`max`), `isolation: worktree`, `color`, `initialPrompt`, `experimental.cacheTtl`. Unknown fields are silently ignored.
- Model resolution: per-invocation parameter > frontmatter > `CLAUDE_CODE_SUBAGENT_MODEL` > main model. Effort: per-invocation > frontmatter; `CLAUDE_CODE_EFFORT_LEVEL` beats both. A subagent on a different model does not inherit the session effort; set `effort` explicitly.
- Defaults: Fable 5.2 and Opus 5.5 default to `medium` effort [doc: model-config]. Thinking cannot be turned off on these models [doc: costs].
- Built-in Explore and Plan "start without your CLAUDE.md files and the git status snapshot"; on a subscription with Fable as main model, Explore runs on Opus. A project agent named `Explore` with `model: haiku` overrides it.
- `omitClaudeMd: true` removes both repos' CLAUDE.md from a worker's context — a direct saving for every bounded worker.
- Background is the default for subagents spawned from the main conversation; results arrive as a later notification. Background agents have "a smaller built-in tool set".
- Concurrency: 20 running subagents by default (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`). Nesting: documented default three layers; [observed] this cloud session sets `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, so workers cannot spawn workers here.
- Resume: `SendMessage` to an agent ID resumes it with "full conversation history" and can reuse its warmed cache; Explore/Plan are one-shot. After a cloud VM is reclaimed, conversation history is restored and stopped subagents can be resumed [doc: claude-code-on-the-web#environment-expired].
- Subagent `memory` field stores under `~/.claude` — not durable in the cloud [inference].
- Workflows [doc: workflows]: "a JavaScript script that orchestrates many subagents"; "Intermediate results stay in script variables instead of landing in Claude's context"; `agent()`, `parallel()`, `pipeline()`; `schema` on `agent()` returns validated JSON (five retries); limits "Up to 16 concurrent agents by default", "1,000 agents total per run", 4,096 items per call; no shell or file access from the script itself; resumable in the same session, and in cloud "saves the run's results with the session's conversation history". Saved to `.claude/workflows/` and run as `/<name>`; distributable in a plugin. Fan-out agents share a prompt-cache prefix. Opt-in needed: the user asks for a workflow or types `ultracode`; "It doesn't start a workflow" from a scheduled-task prompt. Cost: "a single run can use meaningfully more tokens"; warning above 25 agents or 1.5 million projected tokens; size guideline default `medium` (fewer than 10 agents).
- Agent teams: "experimental and disabled by default"; "approximately 7x more tokens than standard sessions when teammates run in plan mode". Enabling needs an environment variable on the cloud environment. Not a default mechanism for an efficiency-first Brain.

### B6. Cloud specifics

- VM: "fresh virtual machine (VM) running Ubuntu 24.04"; about 4 vCPU, 16 GB RAM, 30 GB disk; idle VMs pause and can be reclaimed; conversation history is restored, background work is not.
- Network: levels None / Trusted (default allowlist of registries) / Full / Custom. GitHub and enabled connectors bypass the allowlist.
- GitHub proxy: scoped to "the repositories attached to the session"; "rejects branch deletions and pushes of anything other than a branch, such as a tag. It doesn't limit which branches a push can update"; GraphQL blocked, so `gh pr` and `gh issue` fail — use the built-in GitHub tools or `gh api`.
- Two repos, one session: both are cloned side by side and both are pushable through the proxy, each with ordinary git from its own directory [inference from "Repository scope" text + observed layout]. Default working branches are `claude/`-prefixed; protecting the Brain's `main` is done with GitHub branch protection or rulesets, not with Claude Code.
- Auto-compaction in cloud is preset: [observed] `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=92`; the docs say a value you add is overridden. `CLAUDE_CODE_AUTO_COMPACT_WINDOW` on the environment is the adjustable control.
- `/config`, `/plugin`, `/resume` and similar terminal-only commands are not available in the browser; per-session settings come from environment variables on the cloud environment.
- Scheduled tasks (formerly routines) [doc: routines]: "research preview"; "a prompt, one or more repositories, and a set of connectors"; triggers: schedule, API, GitHub events; minimum interval one hour; "Each repository you add is cloned on every run. Claude starts from the repository's default branch"; pushes to a `claude/` branch "unless your prompt directs it to push to another branch"; runs start in auto mode; model and effort are chosen per task; "draw down subscription usage the same way interactive sessions do". A nightly learning job is therefore feasible: one task, Brain repo (plus optionally project repos), a self-contained prompt, a cheaper model. Constraints: a multi-repo task inherits the same no-hooks/no-MCP rule; a single-repo task on the Brain alone would load its hooks and `.mcp.json` [inference from the one-repository rule]; the prompt cannot trigger a workflow by keyword.

### B7. Documented token-reduction guidance

From [doc: costs#reduce-token-usage] and [doc: context-window]:
1. "Token costs scale with context size". `/clear` between unrelated tasks ("costs nothing"); `/compact <focus>`; a "Compact instructions" section in CLAUDE.md steers summaries.
2. "Aim to keep CLAUDE.md under 200 lines"; "moving specialized instructions into skills keeps your base context smaller."
3. "For simple subagent tasks, specify `model: haiku`"; "Reserve Opus for complex architectural decisions".
4. MCP: deferred by default; "Prefer CLI tools when available"; disable unused servers.
5. "Custom hooks can preprocess data before Claude sees it ... reducing context from tens of thousands of tokens to hundreds."
6. "Delegate verbose operations to subagents so the verbose output stays in the subagent's context".
7. Lower effort for simple work; "Thinking tokens are billed as output tokens".
8. Code-intelligence (LSP) plugins: "A single 'go to definition' call replaces ... a grep followed by reading multiple candidate files" (plugin loading caveat applies in cloud).
9. Why long sessions cost more: "Claude Code sends your full conversation with every request"; cache misses after a break longer than the cache lifetime; "`/compact` reads the conversation it summarizes, so compacting a large context is itself a large request".
10. Measuring: `/context` (live breakdown by category), `/usage` (attribution and recommendations), `/skill-doctor` ("what each of your skills costs and how often it gets used"), `/doctor` (trim proposals for CLAUDE.md). Bash output is capped at 30,000 characters by default.

### Could not confirm
- Whether a status line or output-style setting can be applied in a browser cloud session with two repos (both are settings keys, which are not read from repos there).
- Any per-day cap on scheduled-task runs (only hourly limits are documented on the page read).
- Whether user-level `~/.claude/settings.json` written inside the VM by a setup script is honoured.
- Version note: this session reports `CLAUDE_CODE_VERSION=2.1.42` while the docs cite features up to v2.1.322; treat version-gated features as needing a live check.

### Test list before the plan locks (each is a few minutes in a two-repo session)
1. Skill frontmatter hooks fire after invocation (PreToolUse deny + additionalContext).
2. Path-scoped rules in each repo load on matching file reads.
3. `.claude/workflows/` in the Brain repo shows up as a command.
4. `CLAUDE_CODE_PLUGIN_DIRS` on the environment loads a Brain plugin (hooks + MCP).
5. Setup script copying a plugin into `~/.claude/skills/` loads it; same for `~/.claude/settings.json`.
6. A claude.ai-account plugin appears in a cloud session.
7. Subagent `omitClaudeMd`, `model`, `effort` are honoured (check with `/tasks` or the transcript).
8. Pushing to both repos from one session, and that branch protection on the Brain's `main` blocks a direct push.
