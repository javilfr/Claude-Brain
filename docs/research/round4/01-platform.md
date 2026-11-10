# 01 — The Claude Code platform, re-checked on 2026-11-10 (research round four, part 1)

Method: downloaded the official pages as raw Markdown with curl on 2026-11-10 and quoted them directly: `https://code.claude.com/docs/llms.txt` plus 67 pages under `https://code.claude.com/docs/en/*.md` (including the 1.2 MB changelog, newest entry v2.1.322 dated November 10, 2026), 12 pages under `https://platform.claude.com/docs/en/*.md`, and 2 pages plus the index under `https://claude.com/docs/` (`plugins/overview.md`, `plugins/platform-support.md`). No host was blocked; one page (`claude-tag.md`) answered with a redirect and was not needed. I also inspected this live cloud session read-only (one repository attached, the brain; Default environment; `claude --version` prints `2.1.322 (Claude Code)`) and ran experiments in a scratch copy of the brain. Nothing below is from memory.

Tags: **[doc: page]** = quoted from `https://code.claude.com/docs/en/<page>.md`; **[api: page]** = `https://platform.claude.com/docs/en/<page>.md`; **[claude.com: page]** = `https://claude.com/docs/<page>.md`; **[changelog vX]** = the entry for that version in `https://code.claude.com/docs/en/changelog.md`; **[observed]** = seen in this session; **[measured]** = computed from this session's transcripts or from a command I ran; **[inference]** = reasoned from the sources, not stated by them; **[unverified]** = no source could be opened for it, or it needs a live two-repository test.

---

## Headline

1. **The two-repository rule is unchanged, and two documented routes now reach around it.** A session with several repositories still reads no hooks, permission rules, `env` or `.mcp.json` from any repository. But (a) a skill's own `hooks` frontmatter is registered when the skill is invoked and runs for the rest of the session, and (b) plugins turned on for the owner's claude.ai account load in cloud sessions, with their hooks. Neither depends on a repository's settings file. The brain uses neither today.
2. **The route `NEEDS_YOU.md` item 5 points at (a setting in the cloud environment) has no documentation behind it.** The docs now say user settings are "not read" in a cloud session; the only file a setup script is documented to plant is `~/.claude/CLAUDE.md`.
3. **Workflows and ultracode are absent from the brain's method, and they are where this session's cost went.** Measured here: 17 workflow agents, every one on the session's model (Fable 5.2), about $112 at list prices, each starting from a prefix of about 65,000 tokens. The brain's own `scout` agent started from 5,489 tokens. A workflow script can name a brain agent, a model and an effort per call; nothing in the brain says so.
4. **Two defects found by running the platform's own tools.** `claude plugin validate` rejects the brain's plugin manifest (the name `claude-brain` is reserved). `brain adopt` on a repository that relies on `AGENTS.md` creates a `CLAUDE.md` that makes Claude Code stop reading `AGENTS.md`.
5. **Every platform fact the brain holds was re-checked.** 14 of 18 are still true as written, 4 need a correction (one materially: what breaks the prompt cache). Ticket CB-112 (does an effort change keep the cache?) can be closed from the docs plus a published Anthropic measurement.

---

## Q1. Every fact in `memory/facts.jsonl`, re-verified

| Fact id | Verdict | Source checked (fetched 2026-11-10) and the sentence |
|---|---|---|
| fact-two-repo-loading | **True; incomplete** | [doc: settings] "a session with several repositories starts above the clones and reads only the `enabledPlugins` and `extraKnownMarketplaces` keys from each repository's `.claude/settings.json`, not permission rules, hooks, `env`, or other keys." [doc: cloud-environments] `.mcp.json`: "Yes, in a session with one repository". Skills, agents, commands, rules: "Yes — Part of the clone". Missing from the fact: user settings are "not read"; account-synced skills and plugins do load; a Projects thread loads only `CLAUDE.md` (Q5, Q7). |
| fact-claudemd-cost | **True** | [doc: memory] "target under 200 lines per CLAUDE.md file"; "Imports … don't reduce its context cost". [doc: sub-agents] a subagent gets "every level of the CLAUDE.md hierarchy the main conversation loads" unless `omitClaudeMd`. One caveat for two-repository sessions is in Q3. |
| fact-skill-cost | **True** | [doc: skills] "the combined `description` and `when_to_use` text is truncated at 1,536 characters"; "the rendered `SKILL.md` content enters the conversation as a single message". The cap is now a setting, `skillListingMaxDescChars` (default 1536). |
| fact-cache-lifetime | **True**, and measured | [doc: prompt-caching] table: main conversation "One hour" on a subscription within plan usage, "Five minutes" on usage credits; everything else "Five minutes". [measured] this session: main conversation wrote 525,846 tokens to the one-hour cache and 0 to the five-minute cache; 13 helpers wrote 6,334,727 to the five-minute cache and 0 to the one-hour cache. New: both lifetimes can be set (`promptCacheTtl`, `subagentPromptCacheTtl`, v2.1.242). |
| fact-cache-breakers | **Changed** | Still breakers: model switch, fast-mode toggle, compaction. **No longer a breaker by default:** MCP server changes. [doc: prompt-caching] "Tools deferred: Claude Code keeps the tool list from the conversation's first request for the whole conversation, so a server connecting or disconnecting mid-session doesn't disturb anything already cached." Deferral is "the default on supported models". **Breakers the fact does not list:** "Enabling or disabling a plugin", "Denying an entire tool" (only when tool search is off), "Accumulating many images", "Upgrading Claude Code". |
| fact-claudemd-edit-timing | **True** | [doc: prompt-caching] "Editing them mid-session does not invalidate the cache, but the edit also doesn't apply … The new content loads on the next `/clear`, `/compact`, or restart." |
| fact-subagent-model | **True** | [doc: sub-agents] "1. The per-invocation `model` parameter 2. The subagent definition's `model` frontmatter … 3. The `CLAUDE_CODE_SUBAGENT_MODEL` environment variable … 4. The main conversation's model". Note: "Before v2.1.251, `CLAUDE_CODE_SUBAGENT_MODEL` came first". |
| fact-subagent-cold-start | **True** | [doc: prompt-caching] "Its first request doesn't read the parent's cache"; "A fork … inherits the parent's system prompt, tools, and conversation history exactly". [doc: sub-agents] "when 20 subagents are running in a session, spawning another … fails". New: "Sessions with ultracode active are exempt: the limit isn't enforced there." |
| fact-default-effort | **True; one clause incomplete** | [doc: model-config] "Fable 5.2, Opus 5.5, Sonnet 5.5, and Haiku 5.5 default to `medium`". [api: build-with-claude/effort] "Claude Fable 5.2 … The API default is `high`"; "Claude Sonnet 5.5 … `high` is the default on the Claude API"; Opus 5.5 and Haiku 5.5 default to medium. The fact says thinking cannot be turned off "on Fable 5.2 or Opus 5.5"; the docs now say "You can't turn thinking off on Opus 5.5, Sonnet 5.5, Haiku 5.5, or the Fable models." |
| fact-prices | **True** | [api: about-claude/pricing] Fable 5.2 $8 / $40, cache read $0.20; Opus 5.5 $4 / $20, $0.20; Sonnet 5.5 $2 / $10, $0.10; Haiku 5.5 $0.10 / $0.50, $0.01 up to 100,000 prompt tokens, $0.50 / $2.50 above. [changelog v2.1.321] "Added Claude Fable 5.2 … 1M context, $8/$40 per Mtok with $0.20/Mtok cache reads". |
| fact-cost-shape | Not a platform fact (a measurement of one earlier session); not re-run here. This session's own numbers are in "Measurements" below. |
| fact-bench-coding | **True** | [api: about-claude/models/optimizing-for-cost-and-intelligence] "Claude Opus 5.5 … at its default it solved 93.1% for $0.22 USD, at `high` 95.5% for $0.30 USD"; "At `low`, Fable 5.2 solved 94.6% for $0.39"; "at `high` … 96.3% of tasks for $1.39". The page now names the set: "463 of the 478 problems in the SWE-bench Pro subset". |
| fact-bench-escalation | **True** | Same page, table: "`low`, failures re-run at `high` — About 97% — About $0.17 USD"; "Everything at `high` — 95.3% — $0.29 USD". |
| fact-bench-orchestrator | **True** | Same page: "Claude Opus 5.5 with Claude Sonnet 5.5 subagents: 0.831 … $139 USD"; alone "at `high`: 0.850 … $236 USD"; "Claude Fable 5.2 with Claude Sonnet 5.5 subagents: 0.833 … $165 USD". Worth adding: with Haiku 5.5 subagents the same leads scored 0.677 and 0.716. |
| fact-effort-curves | **True; one digit changed** | Same page: "Claude Opus 5.5 scored 34 points lower at `low` than at `medium`"; Sonnet 5.5 "77.8% at its default, `high` … at `medium`, it scored 62.7%". The research figure is now "3.3 points higher at `high` than at `low` … for 3.2 times the cost" (the fact says 3.2 points). |
| fact-multi-agent-tokens | **Half re-verified** | [doc: costs] "Agent teams use approximately 7x more tokens than standard sessions when teammates run in plan mode". The "4 times" and "15 times" figures come from an Anthropic engineering post that I did not re-fetch: [unverified] today. |
| fact-fast-mode | **True** | [doc: fast-mode] "up to 2.5x faster"; "$16/$80 on Fable 5.2, $8/$40 on Opus 5.5"; "fast mode is available via usage credits only"; "It is not available on Sonnet, Haiku, or other models"; separate caches. |
| fact-fable-limits | **Second sentence true; first not re-checked here** | [doc: model-config] "After a fallback, the session continues on the fallback model." New detail: for a subagent, "the request re-runs on the fallback model, and your session's model is unchanged". The capability sentence is a model claim for the models memo. |

One structural weakness: every row's `source` is an internal memo section ("docs/research/02-claude-code-platform.md B1"), not a URL. A re-check has to go through the memo to find the page. Carrying the page URL in each fact would make the 30- and 60-day rechecks mechanical.

---

## Q2. Skills

**Frontmatter fields today** [doc: skills, "Frontmatter reference"]: `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context` (`fork`), `agent`, `background`, `hooks`, `paths`, `shell`, `metadata`, `license`, `compatibility`. "Claude Code ignores a field it doesn't recognize without reporting an error." The brain's ten skills use only `name` and `description` [measured: descriptions are 207 to 269 characters, bodies 22 to 35 lines].

**Can a skill carry hooks, tool grants, a model, a context setting?** Yes to all four.
- `hooks`: "Hooks that Claude Code registers when the skill is invoked and keeps running for the rest of the session." [doc: hooks] "Skill hooks: Claude Code registers them when you or Claude invoke the skill and keeps running them for the rest of the session, on turns after the skill's own turn as well." Trust: "Frontmatter hooks in a project skill follow the same workspace trust rule as hooks in settings files. Claude Code registers them when you or Claude invoke the skill, including in a `-p` run in a folder you haven't trusted." Limit: "The skills from one source can register at most 1,024 hooks."
- `allowed-tools`: "Tools Claude can use without asking permission during the turn that invokes this skill. The grant clears when you send your next message." `${CLAUDE_SKILL_DIR}` is substituted "in two places: the skill's markdown content, and Bash rules in the `allowed-tools` frontmatter" (not, by that sentence, in `hooks`).
- `model`: "applies for the rest of the current turn", and [doc: prompt-caching] "that turn is also a model switch: the next request reads the entire conversation history with no cache hits." Keep it out of brain skills.
- `context: fork` runs the skill as a subagent; `effort` sets the level for the turn.

**Dynamic context.** [doc: skills] "The `` !`<command>` `` syntax runs shell commands before the skill content is sent to Claude. The command output replaces the placeholder". Two sharp edges: "A failed command aborts the entire skill invocation", and outside auto mode "when a command's permission check returns anything other than allow, Claude Code aborts the invocation", so the command must be pre-approved with `allowed-tools`.

**How the always-loaded listing is budgeted.** [doc: skills] "The listing always contains every skill name, but if you have many skills, Claude Code drops some descriptions to fit the listing's character budget … The budget scales at 1% of the model's context window. When the listing overflows, Claude Code drops descriptions starting with the skills you invoke least". [doc: env-vars] "with a fallback of 8,000 characters". Each entry is capped at 1,536 characters. Settings: `skillListingBudgetFraction` (default 0.01), `skillListingMaxDescChars`, and `skillOverrides` ("name-only" lists a skill without its description). The brain's ten descriptions total about 2,400 characters, so they are not at risk. [observed] this session's listing also carries about 25 skills that are not the brain's (bundled ones and nine synced from the claude.ai account, several with descriptions over 1,000 characters): the account's skills cost more listing text than the brain's.

**After compaction.** [doc: context-window] "Invoked skill bodies: Re-injected, capped at 5,000 tokens per skill and 25,000 tokens total; oldest dropped first"; "Skill descriptions: Rebuilt from your current skills and re-injected. Requires Claude Code v2.1.304 or later". All brain skill bodies are under 2,600 bytes, so they come back whole.

**Two repositories in a cloud session.** [doc: cloud-environments] the row "Your repo's `.claude/skills/`, `.claude/agents/`, `.claude/commands/` — Yes — Part of the clone" has no one-repository condition, unlike the rows for hooks and `.mcp.json`. The mechanism matches added directories: [doc: skills] "When you add a directory with `--add-dir` or `/add-dir`, Claude Code loads the skills in that directory's `.claude/skills/`, along with its `.claude/commands/` and `.claude/agents/`." Name clashes: "An added directory's skill gets a prefix when its folder name clashes with an enterprise, personal, or project skill, or one in a directory added earlier" and runs as `/<prefix>:<skill-name>` (v2.1.309). The `brain-` prefix keeps the brain clear of this. A skill's `paths` field would not work across repositories: "Patterns are relative to Claude's current working directory, and files outside that directory don't match."

---

## Q3. Subagents

**Frontmatter fields today** [doc: sub-agents, "Frontmatter reference"]: `name`, `description`, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `autoCompactWindow`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `omitClaudeMd`, `effort`, `isolation` (`worktree`), `color`, `initialPrompt`, `experimental` (`cacheTtl`).

**Are `model`, `effort` and `omitClaudeMd` real and honoured?** Real, all three.
- `model`: "`sonnet`, `opus`, `haiku`, `fable`, a full model ID such as `claude-opus-5-5`, or `inherit`." One trap: "a family alias such as `opus` … resolves to the main conversation's model instead" when "The main conversation's model belongs to that family". On an Opus session, `model: opus` means the session's exact Opus.
- `effort`: "Overrides the session effort level, but not the `CLAUDE_CODE_EFFORT_LEVEL` environment variable." A per-call `effort` exists from v2.1.292. "On another model, that level doesn't apply. To choose its level, set the `effort` field." [observed] `CLAUDE_CODE_EFFORT_LEVEL` is not set in this session, so the agent files' levels apply.
- `omitClaudeMd`: "Set to `true` to start this subagent without the user, project, and local CLAUDE.md files in its initial context … Requires Claude Code v2.1.271 or later". [measured] the brain's `scout` started here with a first request of 5,489 tokens.
- **Caveat that matters for two repositories:** "For Explore, Plan, and subagents with `omitClaudeMd`, a subdirectory's `CLAUDE.md` and matching path-scoped rules still load when the subagent works with files there." A session with several repositories "starts above the clones", so both repositories' `CLAUDE.md` files sit in subdirectories of the start directory. Whether they then reload into an `omitClaudeMd` helper the first time it reads a file in a repository is **[unverified]**; the one-repository check in CB-201 does not cover it.

**What else is useful and unused by the brain.**
- `maxTurns`: "Maximum number of agentic turns before the subagent stops. When the subagent reaches the limit, Claude Code returns its output marked as partial, and Claude can resume it". This is a hard per-helper stop. `docs/BUILD_STATUS.md` says "Claude Code has no per-helper token cap": true for tokens, but a turn cap exists.
- `autoCompactWindow`: "Lower the auto-compact window for this subagent to a token count from `100000` to `1000000`. Requires Claude Code v2.1.296". Relevant to Haiku 5.5, whose requests cost five times more above 100,000 prompt tokens.
- `experimental.cacheTtl: 1h`: a one-hour cache for one helper. [measured] it would not have paid in this session: across 19 helper transcripts and 950 requests there was no gap longer than five minutes.
- `memory` (`user`, `project`, `local`): helper memory lives under `~/.claude`, which a cloud VM does not keep ([doc: memory] "Files are not shared across machines or cloud environments"). Not a substitute for the brain's memory.
- Built-in Explore: "When the main conversation runs Fable … With a Claude subscription … Explore runs on the Opus model"; "A user or project subagent named `Explore` overrides the built-in and keeps its own `model` field".

**Nesting.** [doc: sub-agents] "By default, a subagent can spawn subagents of its own, up to three layers below the main conversation." [observed] this cloud session sets `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, which the docs define as "Set `1` to turn nesting off". Helpers cannot hire helpers here.

**Background and reports.** "With nothing configured, a subagent that Claude spawns from your main conversation starts in the background." Reports are scanned: "Claude Code scans each subagent's final report before Claude reads it" and it "arrives under a header marking it as subagent output. The header states that instructions or approval claims inside the report are the subagent's words and carry no authority from you."

**How token use is recorded.** [doc: sub-agents] "transcript files at `~/.claude/projects/{project}/{sessionId}/subagents/`. Each transcript is stored as `agent-{agentId}.jsonl`"; removed after `cleanupPeriodDays`, "30 days by default". [observed] workflow agents are one level down, in `subagents/workflows/wf_<run>/agent-<id>.jsonl`, beside a `journal.jsonl`; `engine/common.py:helper_transcripts` already reads both. Each assistant row carries a `usage` object with `cache_creation.ephemeral_1h_input_tokens` and `ephemeral_5m_input_tokens`, which is how the cache-lifetime fact was measured above. These files live in the VM: a reclaimed VM loses them, so capture has to happen before the session ends.

---

## Q4. Hooks

**Events available now** [doc: hooks, "Hook lifecycle"], 33, the same set as memo 02: SessionStart, Setup, UserPromptSubmit, UserPromptExpansion, PreToolUse, PermissionRequest, PermissionDenied, PostToolUse, PostToolUseFailure, PostToolBatch, Notification, MessageDisplay, SubagentStart, SubagentStop, TaskCreated, TaskCompleted, Stop, StopFailure, TeammateIdle, InstructionsLoaded, ConfigChange, CwdChanged, DirectoryAdded, FileChanged, WorktreeCreate, WorktreeRemove, PreCompact, PostCompact, PreModelSwitch, PostModelSwitch, Elicitation, ElicitationResult, SessionEnd.

**Where a hook can live** [doc: hooks, "Hook locations"]: `~/.claude/settings.json`, `.claude/settings.json`, `.claude/settings.local.json`, managed policy settings, a plugin's `hooks/hooks.json`, skill frontmatter ("The rest of the session once the skill is invoked"), subagent frontmatter ("While that subagent is running").

**Which of these reach a cloud session.**

| Source | One repository | Several repositories | Basis |
|---|---|---|---|
| The repository's `.claude/settings.json` | Loaded | **Not loaded** | [doc: cloud-environments] "a session with several repositories doesn't load hooks from any repository's `.claude/settings.json`"; one-repository case confirmed live in CB-201 |
| User settings `~/.claude/settings.json` | Not read | Not read | [doc: settings] "User and project local settings (`~/.claude/settings.json` and `.claude/settings.local.json`): not read. Both stay on your machine" |
| Server-managed settings | Loaded | Loaded | [doc: cloud-environments] "Claude Code runs hooks from your organization's server-managed settings and, outside a project thread, from the repository." Team and Enterprise only; not the owner's plan |
| A skill's frontmatter `hooks` | Registered on invocation | Registered on invocation **[inference: the docs put no repository-count condition on it; untested]** | [doc: hooks] quoted in Q2 |
| A plugin turned on for the claude.ai account | Loaded | Loaded **[inference from the changelog line; untested with two repositories]** | [changelog v2.1.287] "Fixed SessionStart hooks from synced plugins not running in new cloud sessions" |
| A Projects thread | Not run | Not run | [doc: claude-projects] "Hooks in `.claude/settings.json` — Not run" |

**Can a cloud environment's settings or setup script install hooks for every repository?** Nothing documents it. The environment dialog has four things: network access, environment variables, network secrets, a setup script. The setup script "runs when a new cloud session starts, before Claude Code launches" as root, and the one configuration file it is documented to plant is user instructions: "add a setup script that writes `~/.claude/CLAUDE.md` … Claude Code loads that file as user instructions". For settings the same docs say user settings are "not read". [observed] this VM has no `~/.claude/settings.json`; the platform's own two hooks (a SessionStart script and a Stop git check) come from `~/.claude/launcher-settings.json`, which the session is denied permission to edit. So the route in `NEEDS_YOU.md` item 5 and ticket CB-106 is **[unverified] and undocumented**; the two documented routes are the skill and the account plugin. I did not test writing a user settings file here because it would have changed the configuration of a live session that other work was running in.

**One practical detail for either route.** Hook commands locate scripts with `${CLAUDE_PROJECT_DIR}`: "the project root where the session started". With several repositories the session "starts above the clones", so the brain's present commands (`python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/guard_paths.py`) would point at a folder that does not exist **[inference]**. A hook meant for that layout must search the start directory's children for the brain. [measured] a 9-line locator did this correctly in a simulated layout: with the scratch brain's learned zone locked it blocked a write to `brain/memory/_x.tmp` (exit 2, the brain's own message), allowed a write to the project, stepped aside when the start directory was the brain itself, and exited 0 with no brain present.

**Useful contract details** [doc: hooks]: `UserPromptSubmit` receives the `prompt` text and can add context ("`additionalContext` … String added to Claude's context alongside the submitted prompt"), with "a default timeout of 30 seconds"; `SessionStart` has a `compact` matcher ("Auto or manual compaction") and [doc: context-window] "SessionStart hooks that match the `compact` source: Claude Code runs them and adds their output to the compacted context". [measured] `brain boot "Continue"` takes 0.33 s and `brain resume` 0.12 s in the scratch copy, far inside those limits.

---

## Q5. Claude Code on the web (cloud sessions)

**Environments.** [doc: cloud-environments] "Each cloud session runs in a cloud environment. You can configure an environment to allow or deny network access, set environment variables for the session, store network secrets that sessions use without seeing them, and run a setup script before Claude starts working." "**Default** carries no configuration of its own". Environments are personal; the selector "appears only until you send a new session's first message", and a running session's environment is edited from "the caret after the session title … **Edit cloud environment**". [observed] this session's environment: Default, personal, no variables, no setup script, no network secrets, network "unrestricted" (the docs' "Full").

**Environment variables.** `.env` format; read "when you create it and again each time Claude Code starts in the session's VM afterward"; "Anyone who uses the environment can read the values". `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` cannot be set this way ("the value the session sets overrides one you add here"); `CLAUDE_CODE_AUTO_COMPACT_WINDOW` can.

**Network secrets (new since memo 02).** "A network secret is an API key or token you store on a cloud environment so Claude can call that API from any session in the environment without seeing the key. Anthropic's agent proxy adds the key to requests for the hosts you list, after each request leaves the session's VM". Available on Max. Never attached to GitHub, the Anthropic API, public package registries, or "Setup script requests".

**Setup scripts.** Root on Ubuntu 24.04; "a text file … up to 64 KB"; "Finish within five minutes" or "the environment isn't cached"; the snapshot is reused until "you change the environment's setup script or allowed network hosts, and when the cache reaches its expiry after roughly seven days"; "The environment's variables aren't set yet" when it runs. [changelog v2.1.314] "Changed cloud sessions from the web, desktop and mobile apps to start even when a setup script exits with an error, instead of failing to start".

**Network policy.** Levels None, Trusted (default), Full, Custom. Always reachable regardless of level: GitHub through its proxy, enabled connectors, hosts of network secrets, the Anthropic API. GitHub proxy: "rejects branch deletions and pushes of anything other than a branch, such as a tag. It doesn't limit which branches a push can update. To do that, use branch protection rules or rulesets on GitHub"; GraphQL is refused, so "`gh pr` and `gh issue`, get the same 403".

**Scheduled tasks (formerly routines).** [doc: routines] "Scheduled tasks are in research preview." A task is "a prompt, one or more repositories, and a set of connectors"; triggers: schedule, API, GitHub. A weekly run on one repository is set up at `claude.ai/code/routines` (preset "weekly", time in local zone) or conversationally: "Run `/schedule` in any session to create a scheduled task conversationally." Rules that matter:
- "Expressions that run more often than once per hour are rejected." Runs set exactly on the hour "can start several minutes late".
- "Each repository you add is cloned on every run. Claude starts from the repository's default branch unless your prompt specifies otherwise." "Claude pushes its work to a branch prefixed with `claude/` unless your prompt directs it to push to another branch."
- "When a run starts a new session on Anthropic's cloud, that session begins in auto mode unless auto mode is unavailable."
- The `ultracode` keyword "doesn't start a workflow" from "a scheduled task prompt" [doc: workflows].
- Limits: "Scheduled runs, including one-off runs — 100 per hour — Your account"; "**Run now**, API fires … 30 per hour — Each scheduled task". No daily cap is documented. "Scheduled tasks draw down subscription usage the same way interactive sessions do."
- A run's row says only how the session ended: "These outcomes say how the session ended, not whether Claude completed the work your prompt describes".
- [changelog v2.1.312] "Added an effort level to the model picker when you create or edit a routine that runs in the cloud". [changelog v2.1.314] "runs in Anthropic's cloud now load the plugins enabled on your claude.ai account".
- A one-repository task on the brain loads the brain's own hooks and `.mcp.json` (the one-repository rule; [doc: routines] "for a scheduled task with one repository, you can instead declare the server in a committed `.mcp.json`").
- [observed] this session has tools that create, list, update, fire and delete such triggers and that schedule a message back into the same session, so the brain can create the weekly run itself and show it to the owner, as `NEEDS_YOU.md` item 6 already promises.

**Several repositories in one session.** [doc: web-quickstart] "You can add multiple repositories to work across them in one session." What loads from each is the table in Q4 plus Q2: `CLAUDE.md`, unscoped rules, skills, agents and commands load; settings keys, `.mcp.json` and repository-declared plugins do not. New: Claude can add a repository to a running session ([changelog v2.1.312] "Improved the step shown when Claude adds a repository to a cloud session"; [changelog v2.1.316] "Fixed the SDK `register_repo_root` control request not loading the CLAUDE.md of a directory outside the working directory"; [observed] this session has that tool, described as loading the added repository's "CLAUDE.md, skills, and plugins … on the next turn"). And a session can start with none ([changelog v2.1.318] "Added a No repository option").

**Persistence.** [doc: cloud-environments] "after a few minutes without activity, a session's VM pauses with its files saved, and a paused VM can later be reclaimed." [doc: claude-code-on-the-web] on reopening a reclaimed session: "**Restored**: your conversation history. **Not restored**: background work that was still running or pending when the VM was reclaimed", namely shell commands, subagents (some resumable) and session-scoped scheduled tasks. Workflow results are kept: "Claude Code also saves the run's results with the session's conversation history, which survives when the session's VM is reclaimed." Files that were never pushed are not listed as restored, which is exactly why core rule 7 (checkpoint and push) is right. Resource ceilings: "4 vCPUs, 16 GB of RAM, 30 GB of disk" ([observed] `nproc` prints 4).

**A different product to stay out of.** [doc: claude-projects] "Cloud threads load each repository's `CLAUDE.md` instructions but not its skills, `.mcp.json` servers, or `.claude/settings.json`, whether the project has one repository or several." Agents and commands: "Not loaded." If the owner opens the brain inside a Project, its ten skills and six agents are missing. `OWNER_GUIDE.md` does not say so.

---

## Q6. Claude Code's own memory features

| Feature | What it is | In a cloud session | Could it replace part of the brain's memory? |
|---|---|---|---|
| Auto memory | [doc: memory] notes Claude writes itself under `~/.claude/projects/<project>/memory/`; "The first 200 lines of `MEMORY.md`, or the first 25KB, whichever comes first, are loaded at the start of every conversation" | "Auto memory is machine-local … Files are not shared across machines or cloud environments." A new VM starts empty | **No.** It would vanish with each VM. `autoMemoryDirectory` could point it at a path inside a repository, but that is a settings key (not read with several repositories), it loads up to 25 KB on every request against the brain's three recalled items, and it bypasses the brain's admission and evidence gates |
| `CLAUDE.md` imports (`@path`) | "Imported files are expanded and loaded into context alongside the CLAUDE.md that references them", "maximum depth of four hops" | Work | **No saving.** "Imports help you organize a long file but don't reduce its context cost" |
| `.claude/rules/` unscoped | "loaded at launch with the same priority as `.claude/CLAUDE.md`" | Loaded from each repository | Same cost as `CLAUDE.md`; nothing gained |
| `.claude/rules/` with `paths:` | Loads when Claude works with a matching file | **[unverified]** with several repositories; lost at compaction "until re-triggered" | Not for the brain's rules: its rules are not tied to file paths |
| Nested `CLAUDE.md` | "loads each one once Claude reads, writes, or edits another file in that subdirectory"; on-demand files over a size limit arrive truncated (150,000 characters on current 1M models) | Works | Useful inside a large project, not for the brain |
| `AGENTS.md` (new, v2.1.277) | Read "only when you have no `CLAUDE.md` in your working directory or above it"; with both present Claude reads "Your `CLAUDE.md` files only" | For directories added beside the start directory: "Their `CLAUDE.md` loads — Their `AGENTS.md` doesn't load" | Not a replacement, but a hazard for `brain adopt` (see below) |
| Subagent `memory` field | A per-agent directory under `~/.claude` | Not durable | No |
| Projects "project memory" | [doc: claude-projects] corrections "go into project memory and later cloud threads start with it" | Only in Projects threads, which do not load skills or agents | No |

Conclusion: none of these can take over the brain's memory in cloud use. The brain's design (memory in the repository, recalled by a script, changed through a gated pipeline) is the one that survives a new VM.

**The `AGENTS.md` hazard, reproduced.** [measured] In a scratch project containing only `AGENTS.md` ("Run `make test` before committing."), `brain adopt . --family software --title "Agents test"` printed "adopted proj-agents: family software; added 12 contract file(s); existing files untouched" and created a `CLAUDE.md` holding only the brain's pointer block; `grep -c AGENTS CLAUDE.md` printed 0. By the table above, Claude Code then reads the new `CLAUDE.md` and no longer reads `AGENTS.md`. The docs give the remedy: "A `CLAUDE.md` that already imports `AGENTS.md` — Your `CLAUDE.md`, with `AGENTS.md` included through the import".

---

## Q7. Plugins and marketplaces in cloud sessions

Three different things, with three different answers.

1. **Plugins a repository turns on: still no.** [doc: cloud-environments] "A cloud session doesn't install the plugins a repository turns on under `enabledPlugins`, including ones from the marketplaces it lists under `extraKnownMarketplaces`". [doc: plugins/loading] "because that requires the workspace trust dialog, which a cloud session never shows."
2. **Plugins installed on the owner's own machine: no.** [doc: plugins/install] a cloud session "doesn't load the plugins you installed on your own machine".
3. **Plugins turned on for the claude.ai account: yes.** [claude.com: plugins/platform-support] "A plugin you install on your account also appears in Claude Code as a synced plugin at the next session start"; hooks, agents and skills all "Load" in the Claude Code column. For cloud specifically: [changelog v2.1.287] "Fixed SessionStart hooks from synced plugins not running in new cloud sessions"; [changelog v2.1.314] scheduled runs "now load the plugins enabled on your claude.ai account"; [doc: claude-code-on-the-web] a suggested plugin's **Add** button will "turn it on for your claude.ai account, where it stays on after the session ends". [observed] `CLAUDE_CODE_SYNC_PLUGINS=1` and a `~/.claude/plugins/synced/` folder exist in this session (the folder is empty: the account has no plugin turned on).

**How the owner would add his own.** [claude.com: plugins/overview] "**Add > Add marketplace**: add a plugin marketplace, a Git repository that contains plugins … Enter a repository URL … or the `owner/repo` shorthand for GitHub … To add a private GitHub repository, connect your GitHub account when the dialog asks and give the Claude GitHub App access to the repository." Or "**Add > Upload plugin**" with a zip. Limits: "Up to 25 marketplaces that you add yourself … Each plugin can contain up to 5,000 files and 200 MB".

**What the brain repository lacks for that.** A marketplace needs `.claude-plugin/marketplace.json`; the brain has only `.claude-plugin/plugin.json`, and that file fails validation. [measured] `claude plugin validate .` in the scratch copy: "× Found 1 error: name: Plugin name "claude-brain" is reserved: it passes as one of Anthropic's own. A third party's plugin name cannot start with "claude-", "anthropic-" …" followed by "× Validation failed". The same command on `.claude/skills` and on `.claude/agents` printed "√ Validation passed". [measured] a draft marketplace named `brain-tools` listing a hooks-only plugin `brain-hooks` (a `plugin.json`, a `hooks/hooks.json` with the brain's PreToolUse and Stop entries, and the locator script from Q4) printed "√ Validation passed with warnings" (missing description) and "√ Validation passed".

**Why hooks-only.** If the account plugin also carried the brain's skills, a session with the brain attached would list every skill twice (`brain-start` from the repository and `<plugin>:brain-start` from the plugin). A plugin that carries only hooks, and finds the attached brain at run time, avoids that and stays a few hundred bytes.

The validator is itself a find: `claude plugin validate <dir>` runs offline inside the cloud VM and checks skill and agent frontmatter with the platform's own parser ([doc: skills] "To find `SKILL.md` files whose frontmatter doesn't parse, run `claude plugin validate`"). The brain's lint re-implements that parsing and has no test on the plugin manifest.

---

## Q8. Context management and the prompt cache

**Window size.** [doc: model-config] "Fable models, Sonnet 5 and later, Haiku 5.5, and Opus 4.7 and later run with the 1M window by default". "Models running with a native 1M window compact before the window fills, at about 967K tokens by default"; "Cloud sessions compact as the conversation approaches the model's limit", and [observed] the cloud sets `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=92`. So an unattended cloud session can grow to roughly 900,000 tokens before it compacts.

**Why that matters.** [doc: costs] "Claude Code sends your full conversation with every request"; "your first message after a break longer than the cache lifetime misses the cache and reprocesses your full context". On Fable 5.2 a one-hour cache write costs $16 per million tokens and a read $0.20 [api: about-claude/pricing]. Arithmetic: a return after more than an hour to a 900,000-token conversation rewrites about $14.40 of cache in one request; at 400,000 tokens, about $6.40; every request in between reads $0.18 against $0.08. [measured] this session's main conversation went from 86,208 prompt tokens on its first request to 296,898 after 35 minutes and 142 requests.

**Idle compaction does not cover cloud sessions.** [doc: settings-reference, `idleCompaction`] on by default only where "you're in an interactive terminal session, in the VS Code extension's chat panel, or in the desktop app's Code tab when the session runs on your machine or over SSH".

**The control that works in the cloud.** [doc: claude-code-on-the-web] "To change the auto-compact window instead, set `CLAUDE_CODE_AUTO_COMPACT_WINDOW` in your environment variables". Range "from `100000` to `1000000` tokens". Compaction itself is cheap while the cache is warm ("costs a fraction of what the context size suggests") and expensive cold. `/compact <focus>` and a "Compact instructions" section in `CLAUDE.md` steer the summary [doc: costs].

**What survives compaction** [doc: context-window]: "Project-root CLAUDE.md and unscoped rules — Re-injected from disk"; invoked skill bodies (5,000 tokens each, 25,000 total); "Files Claude read or edited — Claude Code re-reads up to five"; "Nested CLAUDE.md in subdirectories — Claude Code reloads them on demand". Whether a repository's `CLAUDE.md` counts as project-root or nested when the session starts above two clones is **[unverified]**; the brain-start skill body does come back and already says to run `BRAIN resume`.

**Cache lifetime.** Table in Q1. New controls [doc: prompt-caching]: `promptCacheTtl` / `CLAUDE_CODE_PROMPT_CACHE_TTL` for the main conversation, `subagentPromptCacheTtl` / `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` for everything else, each `5m` or `1h` (v2.1.242).

**What breaks the cache** [doc: prompt-caching, "Actions that invalidate the cache"]: switching models (including a skill whose frontmatter names another model, and "Automatic model fallback"); changing effort "On most models"; turning fast mode on or off; connecting or removing an MCP server only "when tool search is off or unavailable"; enabling or disabling a plugin (depends on its components); a bare-tool deny rule only without tool search; compaction (the conversation layer, by design); accumulating many images; upgrading Claude Code.

**What keeps it** ["Actions that keep the cache"]: editing repository files; editing `CLAUDE.md` mid-session (the edit "also doesn't apply"); changing permission mode; changing output style; invoking skills and commands; `/recap`; rewinding; spawning a subagent.

**Effort change, the open ticket CB-112.** [doc: prompt-caching] "With an API key or a Claude subscription, changing effort keeps the cache on Fable 5.1 and later, Opus 5.5, Sonnet 5.5, and Haiku 5.5." "Before v2.1.260, changing effort on Fable 5.1 with an API key or a Claude subscription also invalidated the cache." Published measurement [api: about-claude/models/optimizing-for-cost-and-intelligence, October 2026 test]: "With no change, and with a per-message effort change, the request read all 101,000 tokens and wrote none"; "A top-level effort change … read the 20,000-token system prompt and wrote 81,000 tokens." CB-112 can be closed from these two sources; the only thing a live check would add is the owner's own account.

**Tool-list change.** Covered by the MCP row: with deferred tools the list is frozen at the first request, so the session's cache does not move when a connector appears or disappears.

**Cache scope.** "In Claude Code, the cache is effectively scoped to one machine and directory"; "Sequential sessions share the prefix only when the git status snapshot taken at startup matches". A new chat therefore always starts by writing its prefix.

**Published numbers worth keeping** [api: optimizing-for-cost-and-intelligence]: delegation "came out ahead in only two situations: Routine work with a long cost tail … Work larger than one context window"; otherwise "the orchestrator's model alone at lower effort came out ahead in every case measured on earlier models". Output format: a one-line answer cost $0.49 per run, a six-section memo $1.40, "All three scored within run-to-run noise of each other". Haiku 5.5 helpers under an Opus 5.5 lead "cut cost per attempt by 32% and the pass rate by about 4 percentage points".

---

## Q9. Workflows and other multi-agent features

**Dynamic workflows** [doc: workflows]: "a JavaScript script that orchestrates many subagents at once"; "Intermediate results stay in script variables instead of landing in Claude's context."
- Opt-in: the keyword `ultracode` or a request in plain words in a prompt the user typed; or `/effort ultracode`, after which "Claude plans a workflow for each substantive task" and "each request uses more tokens and takes longer than the same request without a workflow." With ultracode on, the large-run warning does not appear and "The session's concurrent subagent limit isn't enforced".
- Limits: "Up to 16 concurrent agents by default, fewer when Claude Code has fewer CPUs available, including inside a CPU-limited container" (changeable with `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS`, 1 to 256, v2.1.269); "1,000 agents total per run"; "Up to 4,096 items in a single `parallel()` or `pipeline()` call"; "No mid-run user input"; no file or shell access from the script itself.
- Models: "Claude Code picks each workflow agent's model in the same order it uses for subagents … A model the script names for a stage counts as the per-invocation model … When nothing else assigns one, the agent runs on your session's model."
- Per-call options, from the bundled `/workflow-authoring` reference [observed, loaded in this session]: `agent(prompt, {label, phase, schema, model, effort, isolation, agentType})`; "opts.agentType uses a custom subagent type … resolved from the same registry as the Agent tool"; default agents "get the same CLAUDE.md files injected at start that you did"; concurrency is "capped at min(16, available CPUs - 2) per workflow"; a `budget` object exposes a per-turn token target that is "a HARD ceiling … once `spent()` reaches `total`, further `agent()` calls throw".
- Caching: "an agent that starts after a matching sibling's response has begun reads that sibling's cache on its first request"; workflow agents get the five-minute cache.
- Resume: "Resumable in the same session"; in the cloud the results survive a reclaimed VM (Q5).
- Cost: "a single run can use meaningfully more tokens than working through the same task in conversation"; warning above 25 agents or 1.5 million projected tokens; size guideline default `medium` ("Fewer than 10 agents").
- Saved scripts live in `.claude/workflows/` and become `/<name>` commands; whether they load from a second repository is still **[unverified]**.

**What this session shows** [measured]. The owner's request said "ultra code"; `CLAUDE_EFFORT=xhigh`. Six workflow runs started 17 agents. Every one ran on `claude-fable-5-2`. Their list-price equivalent at the moment of measurement was $111.59, against $1.04 for the one Agent-tool helper on Fable and under one cent for the brain's `scout` on Haiku. First requests: 65,300 to 67,500 prompt tokens for a workflow agent starting cold, about 53,600 read from a sibling's cache plus 12,000 written otherwise; 5,489 for `scout`. No run had more than 2 agents active at once (4 CPUs minus 2), although up to 11 were active across runs because several workflows were started side by side.

**The gap.** `CLAUDE.md`, the ten skills, `method/` and `playbooks/` do not contain the words "workflow" or "ultracode" [measured: grep printed nothing]. Core rule 4 (at most four helpers, hired through `BRAIN hr hire`, each with its own model) is silent on the mechanism that produced 17 Fable agents here.

**Agent teams**: still "experimental and disabled by default"; "approximately 7x more tokens". Not for the brain.

**Advisor tool** [doc: advisor]: "experimental". "The advisor tool lets Claude consult a second, typically stronger model at key moments during a task"; for an Opus 5 or Opus 5.5 main model the accepted advisors are "Fable, Opus 5 or later"; toggling it "keeps the cached prefix intact" [doc: prompt-caching]; "pairing a faster main model with a stronger advisor typically costs less than running the stronger model throughout." Set with `/advisor`, the `advisorModel` setting or `--advisor`. Whether `/advisor` works in a cloud session is **[unverified]** (the page does not mention cloud sessions).

**`/goal`** [doc: goal]: "sets a completion condition and Claude keeps working toward it without you prompting each step. After each turn, a model checks whether the condition holds." "The evaluator judges your condition against what Claude has surfaced in the conversation. It doesn't run commands or read files independently". It "works in non-interactive mode, in the desktop app, and through Remote Control"; a cloud session is mentioned only in passing, so availability from the phone is **[unverified]**.

---

## Q10. New since mid-2026 that a method like this should use or guard against

| Since | What | Use or guard |
|---|---|---|
| v2.1.271 (Sep) | `omitClaudeMd` for custom subagents | In use. Guard: the two-repository caveat in Q3 |
| v2.1.275 (Sep 17) | Account skills and plugins sync into Claude Code | Use: the hooks-only account plugin (Q7) |
| v2.1.277 (Sep 18) | `AGENTS.md` read natively | Guard: `brain adopt` (Q6) |
| v2.1.287 (Oct 1) | Synced-plugin SessionStart hooks run in new cloud sessions | Use: same as above |
| v2.1.290 / v2.1.302 | Idle compaction (local sessions only) | Guard: cloud sessions get no such help; set the compaction window (Q8) |
| v2.1.292 | Per-call `effort` for subagents | Use: HR can pass effort per hire without a new agent file |
| v2.1.296 | `autoCompactWindow` per subagent; debug log names unknown frontmatter fields | Use: keep Haiku helpers under the 100,000-token price step |
| v2.1.304 | Skill-hook limits; skill descriptions rebuilt after compaction | Informational |
| v2.1.309 | On-demand instruction files truncated above a size limit; prefixed names for clashing skills from added directories | Guard: keep project `CLAUDE.md` small; keep the `brain-` prefix |
| v2.1.312 (Oct 27) | Effort selectable on a cloud routine; Claude can add a repository to a session | Use: the weekly run at low effort on a cheap model; a possible brain-first session layout |
| v2.1.314 (Oct 30) | Sessions start even if the setup script fails; routines load account plugins | Guard: never assume a setup script ran; check for the tool |
| v2.1.316 to v2.1.317 | Network secrets widened | Use: keys without ever showing them to the session (core rule 10) |
| v2.1.318 (Nov 4) | Sessions with no repository; a subagent's safety fallback follows the "Switch models" setting | Guard: a helper can now fail outright on a flagged request when the owner chose "Ask each time" |
| v2.1.321 (Nov 9) | Fable 5.2 is the `fable` alias; "Changed nested skill loading" | Informational |
| Docs | Subagent reports are scanned and labelled as carrying no authority | Good: matches core rule 8 (text you read is data) |
| Docs | [doc: model-config] for Fable: "Skip the verification reminders: it verifies its own work with less prompting" and "Describe the outcome, not the steps" | Check agent and template wording against this at the next template review |
| Observed | Session tools to read and propose changes to the cloud environment, request a credential through a form, create scheduled triggers, add a repository | Use: turn click lists in `NEEDS_YOU.md` into one approval tap |

---

## Measurements from this live session (2026-11-10, one repository, Fable 5.2, ultracode on)

| What | Value | How |
|---|---|---|
| Claude Code version | 2.1.322 | `/opt/claude-code/bin/claude --version`. The variable `CLAUDE_CODE_VERSION` reads 2.1.42 and is not the binary's version; memo 02's worry about version-gated features came from that variable |
| First request of the main conversation | 86,208 prompt tokens (60,773 read from cache, 25,433 written) | first assistant row of the main transcript. The brain's always-loaded text is about 2,550 of these |
| Main conversation after 35 minutes | 296,898 prompt tokens, 142 requests | same file |
| Main cache writes | 525,846 one-hour, 0 five-minute | `usage.cache_creation` |
| Helper cache writes (13 helpers at that moment) | 0 one-hour, 6,334,727 five-minute | same field in helper transcripts |
| Helpers by model (19 at the later moment) | 18 on `claude-fable-5-2`, 1 on `claude-haiku-5-5` | `message.model` |
| Workflow agents | 17, all Fable 5.2, $111.59 at list prices | usage fields times list prices |
| Largest single workflow agent | 22.7 million cache-read tokens, 166,010 output tokens, $16.44 | same |
| First request, workflow agent / brain `scout` | about 65,300 / 5,489 prompt tokens | first assistant row |
| Agents active at once inside one workflow | 2 | overlap of first and last timestamps per run; `nproc` = 4 |
| Helper pauses longer than the five-minute cache | 0 in 950 requests | gaps between consecutive requests |
| `brain boot "Continue"` / `brain resume` | 0.33 s / 0.12 s | `time`, scratch copy |
| Nesting depth allowed | 1 | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` |

---

## Could not confirm

- Whether a skill's frontmatter hooks register when the skill comes from one of two attached repositories, and what `CLAUDE_PROJECT_DIR` is in that layout (the docs imply the directory above the clones).
- Whether an account-synced plugin's hooks run in a session with several repositories (the changelog proves cloud sessions; nothing mentions the repository count).
- Whether a setup script that writes `~/.claude/settings.json` has any effect (the docs say user settings are "not read"; not tested here on purpose).
- Whether `omitClaudeMd` still keeps both repositories' `CLAUDE.md` out of a helper once it reads a file inside a repository, and whether a repository's `CLAUDE.md` is re-injected after compaction in that layout.
- Whether `/advisor` and `/goal` are usable from the phone in a cloud session.
- Whether `.claude/workflows/` and path-scoped rules load from a second repository.
- The "4 times" and "15 times" multi-agent figures (source not re-fetched).

## Live checks to run in the first two-repository session (each a few minutes)

1. Invoke a brain skill that declares a PreToolUse hook; attempt a guarded write; expect the hook's message. Print `$CLAUDE_PROJECT_DIR` from the hook. (Closes CB-107.)
2. With the hooks-only plugin turned on for the account, repeat check 1 without invoking any skill, and confirm the Stop hook wrote a ledger record. (Replaces CB-106.)
3. Hire `scout` to read one project file; read its transcript's first request size and search it for the project's `CLAUDE.md` text. (Completes CB-105.)
4. Run `/compact`, then ask what the first core rule is; confirm the brain's `CLAUDE.md` is back without reading a brain file.
5. Start a session on the brain alone, have Claude add the project repository, and repeat checks 1 and 3 in that layout.

---

## What the brain should change

"Safe without a live two-repo test" means the change itself can be made and checked now; where its benefit still depends on a live check, the cell says so.

| # | Change | Evidence | Brain file it touches | Safe without a live two-repo test? |
|---|---|---|---|---|
| 1 | Give workflows and ultracode a rule: in any workflow script each `agent()` call names a brain agent (`agentType`), a model and an effort; the helper economics of core rule 4 apply to workflow agents too; `hr hire` prints the three values in a form a script can use | https://code.claude.com/docs/en/workflows.md ("When nothing else assigns one, the agent runs on your session's model"); measured here: 17 workflow agents, all Fable 5.2, $111.59 | `method/routing.md`, `.claude/skills/brain-build/SKILL.md`, `CLAUDE.md` rule 4, `engine/hr.py`, `engine/lint.py` | Yes. The saving shows in the next session's ledger |
| 2 | Rename the plugin (its name is reserved), add an author, and run `claude plugin validate` on the manifest, `.claude/skills` and `.claude/agents` in `doctor` whenever the `claude` binary is present | Command run: `claude plugin validate .` → "Plugin name "claude-brain" is reserved" → "× Validation failed"; https://code.claude.com/docs/en/skills.md (validator) | `.claude-plugin/plugin.json`, `engine/doctor.py`, `tests/` | Yes |
| 3 | Declare the guard and the session-capture hooks in the frontmatter of `brain-start`, `brain-new` and `brain-build`, with a command that finds the brain from the session's start directory and steps aside when the brain's own settings already run the hook | https://code.claude.com/docs/en/hooks.md ("Skill hooks: Claude Code registers them when you or Claude invoke the skill and keeps running them for the rest of the session") | three `SKILL.md` files, a small locator in `.claude/hooks/`, `docs/BUILD_STATUS.md` (CB-107) | The change is safe (hooks fail open; locator tested in a simulated layout). Its effect with two repositories needs live check 1 |
| 4 | Add a marketplace file and a hooks-only plugin, and replace `NEEDS_YOU.md` item 5 with the click path Customize → Plugins → Add → Add marketplace; drop the cloud-environment route | https://claude.com/docs/plugins/overview.md ("Add marketplace … To add a private GitHub repository …"); https://code.claude.com/docs/en/changelog.md v2.1.287 ("Fixed SessionStart hooks from synced plugins not running in new cloud sessions"); https://code.claude.com/docs/en/settings.md (user settings "not read") | `.claude-plugin/marketplace.json` (new), `plugins/brain-hooks/` (new), `NEEDS_YOU.md`, `docs/BUILD_STATUS.md` (CB-106) | Files: yes (draft passed the validator). Reliance on it: no, needs live check 2 |
| 5 | `adopt` and `init`: when the project has `AGENTS.md` and no `CLAUDE.md`, put `@AGENTS.md` under the pointer block and say so in the survey | https://code.claude.com/docs/en/memory.md ("An `AGENTS.md` and a `CLAUDE.md` … Your `CLAUDE.md` files only"); reproduced in a scratch project | `engine/contract.py`, `tests/` | Yes |
| 6 | Correct the cache-breakers fact and close CB-112 from the docs and Anthropic's October 2026 measurement | https://code.claude.com/docs/en/prompt-caching.md ("changing effort keeps the cache on Fable 5.1 and later, Opus 5.5, Sonnet 5.5, and Haiku 5.5"; "Tools deferred … doesn't disturb anything already cached") | `memory/facts.jsonl` (through `brain learn`), `method/efficiency.md`, `docs/BUILD_STATUS.md` | Yes |
| 7 | Propose one environment variable through the session's environment tool: `CLAUDE_CODE_AUTO_COMPACT_WINDOW` (start at 400000, record the choice as a decision, revisit with ledger data) | https://code.claude.com/docs/en/claude-code-on-the-web.md ("To change the auto-compact window instead, set `CLAUDE_CODE_AUTO_COMPACT_WINDOW` in your environment variables"); https://code.claude.com/docs/en/model-config.md (1M window, about 967K default) | `.claude/skills/brain-start/SKILL.md` or `brain-new`, `method/efficiency.md`, `NEEDS_YOU.md` | Yes (the owner approves a card). The best value is a judgment until measured |
| 8 | Raise per-workflow concurrency in the cloud to the brain's own helper cap: `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS=4` | https://code.claude.com/docs/en/workflows.md ("fewer when Claude Code has fewer CPUs available … set `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS`"); measured: 2 at once | same proposal as row 7 | Yes |
| 9 | Make the ledger report each helper's first-request size and model, and use it to finish CB-105 with two repositories | https://code.claude.com/docs/en/sub-agents.md ("a subdirectory's `CLAUDE.md` … still load when the subagent works with files there") | `engine/ledger.py`, `docs/BUILD_STATUS.md` | The measurement: yes. The answer: live check 3 |
| 10 | Fix the smaller stale statements and give every platform fact its page URL | Q1 table; https://code.claude.com/docs/en/model-config.md ("You can't turn thinking off on Opus 5.5, Sonnet 5.5, Haiku 5.5, or the Fable models") | `memory/facts.jsonl` (through `brain learn`), `docs/REQUIREMENTS.md` R-12, `README.md` line 14 | Yes |
| 11 | Use the session's own platform tools where `NEEDS_YOU.md` now gives click lists: environment changes, credentials, the weekly routine | Observed tool list and a live `get_environment` result; https://code.claude.com/docs/en/routines.md ("Run `/schedule` in any session to create a scheduled task conversationally") | `NEEDS_YOU.md` items 5 and 6, `.claude/skills/brain-learn/SKILL.md`, `playbooks/operations.md`, `OWNER_GUIDE.md` | Yes (every use is approved by the owner on a card) |
| 12 | Add a SessionStart hook with the `compact` matcher that prints `brain resume` (one-repository sessions and routines today; the plugin later) | https://code.claude.com/docs/en/context-window.md ("SessionStart hooks that match the `compact` source: Claude Code runs them and adds their output to the compacted context") | `.claude/settings.json`, `.claude/hooks/` | Yes (it only loads where hooks already load) |
| 13 | Tell the owner not to open the brain inside a Project | https://code.claude.com/docs/en/claude-projects.md ("Cloud threads load each repository's `CLAUDE.md` instructions but not its skills") | `OWNER_GUIDE.md` | Yes |
| 14 | Idea: bound helpers with `maxTurns`, and keep `scout` under Haiku's price step with `autoCompactWindow: 100000` | https://code.claude.com/docs/en/sub-agents.md (`maxTurns`, `autoCompactWindow`); https://platform.claude.com/docs/en/about-claude/pricing.md (Haiku 5.5 over 100,000 tokens) | `.claude/agents/*.md`, `docs/BUILD_STATUS.md` (HR note) | Yes |
| 15 | Idea: a project agent named `Explore` on a cheaper model, since the built-in one runs on Opus under a Fable lead | https://code.claude.com/docs/en/sub-agents.md ("A user or project subagent named `Explore` overrides the built-in") | `.claude/agents/` | Yes, but measure quality first: Haiku helpers scored 0.677 against 0.831 for Sonnet helpers on defect search |
| 16 | Idea: recommend Opus 5.5 with Fable 5.2 as advisor as a third starting choice | https://code.claude.com/docs/en/advisor.md ("typically costs less than running the stronger model throughout") | `NEEDS_YOU.md` item 3, `method/models.md` | No: availability in a cloud session is unverified |
| 17 | Idea: teach one phrase, `/goal the requirements check passes`, for unattended runs | https://code.claude.com/docs/en/goal.md ("a model checks whether the condition holds") | `OWNER_GUIDE.md`, `.claude/skills/brain-start/SKILL.md` | No: availability from the phone is unverified |
| 18 | Idea: let `brain-start` inject `brain boot` output itself with `` !`…` `` and a matching `allowed-tools` rule, saving one round trip per session | https://code.claude.com/docs/en/skills.md ("runs shell commands before the skill content is sent to Claude"; "A failed command aborts the entire skill invocation") | `.claude/skills/brain-start/SKILL.md` | No: a refused command would make the skill unusable; test live first |
| 19 | Idea: a brain-first layout (start on the brain alone so its hooks load, then have Claude add the project) | https://code.claude.com/docs/en/changelog.md v2.1.312 ("when Claude adds a repository to a cloud session") | `OWNER_GUIDE.md`, `.claude/skills/brain-start/SKILL.md` | No: live check 5 |

Recorded so the plan does not spend on it: a one-hour cache for helpers (`experimental.cacheTtl` or `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL`) would have cost more and saved nothing in this session (no helper paused longer than five minutes in 950 requests).
