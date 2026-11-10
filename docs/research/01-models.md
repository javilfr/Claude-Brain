# Analyst 1 report: owner-prompt extraction and the two-model briefing

Date: 2026-11-10. Author: analyst 1 of 10 (independent). Scope: Part A extracts every requirement from the owner's message 2. Part B is a sourced briefing on Claude Fable 5.2 and Claude Opus 5.5 (plus Sonnet 5.5 and Haiku 5.5 as worker tiers) for the design of the "Claude Brain" orchestrator.

Source tags used on every claim:

- `[local-doc]` = the bundled reference at `/tmp/claude-0/bundled-skills/2.1.322/abe77d722f7cc0e8bbf4058a7be92fb3/claude-api/shared/` (files named where useful).
- `[web: URL]` = a page fetched live on 2026-11-10.
- `[inference]` = my own reasoning from the sourced facts. Treat these as proposals to test, not facts.

Source limits to know before reading:

- `SKILL.md` does not exist in the local reference directory (only `shared/` and per-language folders). Every local pointer of the form "SKILL.md -> Fast Mode / Thinking & Effort / Task Budgets" could not be followed locally. I filled those gaps from the live web pages.
- `https://www.anthropic.com/news/claude-fable-5-2` returned HTTP 404. The real announcement is `https://www.anthropic.com/claude-fable-and-mythos-5-2`, which I read.
- Web pages were read through a summarising fetch tool. Numbers below were returned by that tool from the named page. Two long pages were truncated (the cost page's last ~14K characters, the Claude Code model-config page's last ~33K, the sub-agents page's last ~17K). I did not read the Fable 5.2 system card PDF.
- All benchmark numbers are Anthropic-internal and described by Anthropic as directional. None was measured on the owner's workload.

---

## PART A. Extraction of the owner's message 2

### A1. Explicit requirements, constraints and preferences (numbered, with the exact words)

1. **The sample repo is the precedent to generalise.** "I essentially used this repo as a brain to create everything in my travel journal in the best possible way."
2. **Build a new repo that plays the same role.** "I want now to create a repo that will act as that".
3. **It is an orchestrator, and a large one.** "(essentially a mega complex orchestrator)".
4. **Scope is universal, not one product.** "but to build anything I will ever need from now on."
5. **Fixed operating mode: two repos per chat.** "When using it I will always use two repos in a chat".
6. **Repo 1 is the brain.** "one of them the Claude brain".
7. **The brain changes only through its own learning process.** "which will be only modified by its own machine learning systems".
8. **The brain must improve with use.** "as it improves by learning with everything I use it for".
9. **Repo 2 is where the project is built.** "the other repo will be where the project will be built".
10. **The project repo may carry project-specific extensions to the brain.** "which can also hold files and tools to complement the Claude brain functionality that are specific to that project".
11. **The pairing is permanent.** "both will always be worked together from now on".
12. **Every project must be built for long-term compatibility with the brain.** "so the project must be built to work perfectly with it forever."
13. **Deliverable 1: a plan, very long and very detailed.** "Now you will create a super long, super detailed plan on how to build this".
14. **The plan must rest on deep research of two named models.** "based on very comprehensive research about Claude fable 5.2 and opus 5.5".
15. **Those two are the models the owner will run it on.** "(the main models ai will use it with)". Note: "ai" is almost certainly a typo for "I".
16. **The plan must reuse every lesson from the sample repo.** "and also using everything we learned with the sample repo I attached".
17. **The new scope is much wider than the sample's.** "(obviously having present that the current Claude brain's scope for creating stuff is much bigger)".
18. **Consult all memory, in detail.** "Also you must look at all your memory in detail".
19. **Consult all past chats.** "and all our chats".
20. **Coverage test: every past build request and every past question must be something the brain can finish.** "and consider everything I have ever asked you to build on Claude or any question I have ever asked you can be successfully processed to completion."
21. **Top priority: efficiency.** "Also VERY IMPORTANT, you MUST MAKE THIS THE MOST EFFICIENT CLAUDE TOOL EVER".
22. **Token efficiency by named means.** "it should be much more efficient in tokens through plugins and algorithms and quantum logic".
23. **Open-ended research mandate on efficiency.** "and many other thing you must research to see how you can make this super efficient token wise".
24. **Speed.** "and super fast".
25. **Quality must not be traded away.** "while delivering the absolutely highest quality work with absolute attention to detail".
26. **Three named quality dimensions.** "(focus a lot on accuracy, creativity and extreme attention to detail)".
27. **The plan must also use all earlier builds.** "Create now the super long and super detailed plan considering also all our previous builds in Claude".
28. **Deliverable 2: build it, to the end, after the plan.** "and then start building until completion".
29. **Ordering gate: plan first, and the plan must come from research.** "once you have a full plan based on extremely extensive research."
30. **Process requirement: ten independent analyses of this prompt.** "Make sure you analyze this prompt by 10 independent agents".
31. **Completeness of extraction.** "and extract everything I said in full detail".
32. **Execution standard.** "and you can execute to perfection by planning perfectly and researching and analyzing heavily everything".

From message 1 (context that still binds this work):

33. **The sample repo is read-only.** "we will not modify or touch this repo at all in this chat, just read it".

### A2. Implied expectations (not stated, but required for the stated items to hold)

Each is `[inference]` from the quoted words and the known context in `OWNER_PROMPT.md`.

34. **Autonomy without questions.** "start building until completion" plus the sample repo's "Never block" directive imply the brain decides, records the decision, and continues. Questions go to a file, not to the chat.
35. **No command-line work for the owner.** The context says the owner "prefers clicking/reading files, never shell commands". Every owner action must be a file to read or a button to click.
36. **Resume from files alone.** "from now on" and "forever" across many chats means each session must be able to restart from the repo state with no chat memory.
37. **A stable brain-to-project contract.** "work perfectly with it forever" needs a versioned interface between the two repos (what the brain expects in a project, what a project may override, how an old project meets a newer brain).
38. **A defined precedence rule.** "files and tools to complement the Claude brain functionality that are specific to that project" means project additions extend the brain. The plan must say which side wins on conflict.
39. **Domain generality.** "anything I will ever need" covers software, but also research, documents, data work, design and questions. The brain cannot be shaped only around a web-app build.
40. **Learning must be safe.** "only modified by its own machine learning systems" implies gates on self-modification: evidence, review, tests, version history and rollback.
41. **Efficiency must be measured.** "THE MOST EFFICIENT CLAUDE TOOL EVER" is only meaningful with a baseline, a metric (tokens and time per completed task at a fixed quality bar) and a regression check.
42. **Quality is the constraint, cost is the objective.** Items 21 to 26 together mean: minimise tokens and time subject to the quality bar, never the reverse.
43. **Model-specific tuning must be isolated.** The named models will be replaced. Model facts (effort defaults, prompt text, prices) should live in one replaceable layer.
44. **Works on the owner's subscription.** The owner has Claude Max. Features that bill outside the plan (see B7 fast mode, B1 Fable usage) should be off by default.
45. **Honest reporting.** "accuracy" and "execute to perfection" imply reports that state what was verified and what was not.

### A3. Ambiguities the plan must resolve (and record as assumptions)

46. **"plugins"** could mean Claude Code plugins (a real packaging mechanism for skills, agents, hooks and MCP servers) or "add-ons" in a loose sense. Assume the real mechanism.
47. **"its own machine learning systems"**: who may write to the brain repo? Options: (a) only a dedicated learning routine run by Claude; (b) any Claude session, but only through that routine; (c) the owner never edits by hand. The words support (b) with (c). Also unclear: may a project session push brain changes directly, or only propose them for a later consolidation step?
48. **"forever"**: no system can promise this. Define it as "versioned contract plus migration notes so an old project still works with a newer brain".
49. **"anything I will ever need"**: needs a routing layer for task types and a declared list of what is out of scope (for example work the safety classifiers block).
50. **"until completion"**: completion of the brain is not self-evident. The plan needs explicit acceptance criteria and gates, as the sample repo had.
51. **"start building ... once you have a full plan"**: is owner approval of the plan required before building? The words say no; the build follows the plan directly.
52. **"all our previous builds in Claude"**: which builds? Only the sample repo is attached. Other builds are known only if memory or attached files record them.
53. **"super fast"**: wall-clock speed and token efficiency can conflict (parallel subagents are faster and cost more; fast mode is faster and costs 2x). The plan needs a stated priority order.
54. **Brain repo `main` policy**: the sample handbook says the company repo's `main` is updated only on request. The new brain needs its own rule for where learned changes land.

### A4. Items that are impossible as written, or need honest reframing

55. **"quantum logic"** (item 22). There is no quantum computing available to a Claude Code session, and no "quantum" technique reduces LLM token use. Honest reframing: the owner wants the most advanced efficiency methods that exist. Deliver that with real mechanisms: prompt-cache discipline, progressive disclosure (skills, deferred tools), deterministic scripts instead of model calls, model and effort routing, retrieval instead of re-reading, re-run-failures-at-higher-effort, and measurement. If the name is wanted, the nearest truthful analogies are classical: evaluate several candidate approaches in parallel and keep one, or probabilistic routing. Say plainly that these are classical algorithms. Do not label anything "quantum".
56. **"look at all your memory in detail and all our chats"** (items 18 to 19). A Claude Code session has no access to other chats. It can read only: this conversation, the attached repos, loaded memory and instruction files, and anything the owner exports. Honest reframing: mine what is reachable (the sample repo's status logs, decisions, lessons, board minutes, NEEDS_YOU file, ADRs, HR records and git history are a written record of what the owner asked for) and state in the plan that other chats were not readable. Offer a file-based way for the owner to add past requests later.
57. **"only modified by its own machine learning systems"** (item 7). Nothing in this setup trains model weights. The model does not learn between sessions. What can exist is file-based learning: lessons, skills, prompts, routing tables and eval results stored in the brain repo and loaded next time. Honest reframing: "a gated self-improvement pipeline that edits the brain's files from evidence". Also, the first version must be written by the lead in this session, so "only" can hold only after bootstrap.
58. **"everything ... can be successfully processed to completion"** (item 20). No system can guarantee this. Some requests are blocked by safety classifiers or need credentials, money or accounts. Reframe as: a coverage matrix of known request types, each with a route, plus a defined behaviour for unknown and blocked types.
59. **"THE MOST EFFICIENT CLAUDE TOOL EVER"** (item 21). Not provable. Reframe as measured targets against a baseline (the sample repo's pattern), reported with numbers.
60. **"execute to perfection"** / "absolutely highest quality" (items 25, 32). Reframe as explicit acceptance criteria with independent verification. Note the tension recorded in B4: unbounded verification instructions raise cost with no gain on these models.
61. **"work perfectly with it forever"** (item 12). See item 48.
62. **"build anything"** (item 4). Fable 5.2's safeguards block most cybersecurity tasks and most research-biology tasks and limit certain AI-R&D topics (B8). The brain must say so when it applies.

---

## PART B. The models: briefing for the orchestrator design

### B0. Summary table

| | Claude Fable 5.2 | Claude Opus 5.5 | Claude Sonnet 5.5 | Claude Haiku 5.5 |
|---|---|---|---|---|
| Model ID | `claude-fable-5-2` | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` |
| Released | 2026-11-09 | 2026-09-22 | 2026-09-28 | 2026-10-07 |
| Input / output per MTok | $8 / $40 | $4 / $20 | $2 / $10 | $0.10 / $0.50 when the prompt is 100K tokens or fewer; $0.50 / $2.50 above |
| Cache read per MTok | $0.20 (0.025x) | $0.20 (0.05x) | $0.10 (0.05x) | 0.1x input |
| Cache write 5 min / 1 hour | $10 / $16 | $5 / $8 | $2.50 / $4 | 1.25x / 2x input |
| Batch | $4 / $20 | $2 / $10 | 50% off | 50% off |
| Fast mode | $16 / $80 | $8 / $40 | none | none |
| Context / max output | 1M / 128K | 1M / 128K | 1M / 128K | 1M / 128K |
| Thinking | adaptive, always on | adaptive, always on | adaptive, on by default | adaptive, on by default |
| API default effort | `high` | `medium` | `high` | `medium` |
| Claude Code default effort | `medium` | `medium` | `medium` | `medium` |
| Min cacheable prefix | 512 tokens | 512 | 512 | 512 |
| Knowledge cutoff | June 2026 | June 2026 | June 2026 | June 2026 |

Sources: prices, limits, thinking, API effort defaults `[local-doc: models.md, model-migration.md]`, confirmed `[web: https://platform.claude.com/docs/en/models/fable-5-2/overview.md]`. Release dates `[web: https://www.anthropic.com/news]`. Fast mode prices `[web: https://platform.claude.com/docs/en/build-with-claude/fast-mode.md]`. Claude Code effort defaults `[web: https://code.claude.com/docs/en/model-config.md]`. Cache minimum `[local-doc: prompt-caching.md]` (the doc says to check before relying on the value).

### B1. Positioning, pricing and what the owner's subscription changes

- Anthropic's own advice: "Claude Opus 5.5 stays the default for most workloads." Move to Fable 5.2 "when your evals on a Claude Opus model at higher effort still don't meet your requirements." `[local-doc: model-migration.md]` `[web: https://platform.claude.com/docs/en/models/fable-5-2/whats-new-fable-5-2.md]`
- The announcement says Fable and Mythos are best for the most ambitious, open-ended technical work, and recommends Opus 5.5 for most everyday coding and knowledge work. `[web: https://www.anthropic.com/claude/fable]` `[web: https://www.anthropic.com/claude-fable-and-mythos-5-2]`
- Fable 5.2 is cheaper than Fable 5.1 ($10 / $50). Opus 5.5 is cheaper than Opus 5 ($5 / $25). `[local-doc]`
- Fable 5.2 has its own rate limit, with lower token limits at each tier than Opus 5.5. `[local-doc: model-migration.md, "From Claude Opus 5.5"]`
- Neither model supports Priority Tier. `[local-doc]`
- Fable 5.2 requires 30-day data retention. `[local-doc]` `[web: whats-new page]`
- In Claude Code, `default` resolves to Opus 5.5 on Pro, Max, Ultra, Team and Enterprise. No Fable model is the default on any plan. The owner selects Fable with `/model fable`. `[web: https://code.claude.com/docs/en/model-config.md]`
- In Claude Code, "Fable usage may bill to usage credits instead of plan limits"; the model picker then shows "Requires usage credits". `[web: model-config page]`
- The announcement says Fable is included for up to 50% of weekly usage limits on Pro plans and standard Team seats. It does not state the figure for Max. `[web: https://www.anthropic.com/claude-fable-and-mythos-5-2]`
- Subagent requests count toward the same usage limits as the main conversation. `[web: https://code.claude.com/docs/en/sub-agents.md]`
- `[inference]` On a Max subscription the scarce resource is weekly plan usage, not dollars, and Fable draws on a capped share of it. So "token efficient" translates into "more finished work per week before the limit". This makes model and effort routing a first-class design item for the brain, and makes Fable a budgeted resource.

### B2. Effort levels: what each level is for

Effort is the main control for thinking depth, latency and cost on both models. `[local-doc]`

**Fable 5.2** `[local-doc: model-migration.md § Choosing an effort level]`, same text `[web: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2.md]`:

- `low`: quick back-and-forth, well-specified tasks, high-volume work "such as fast, intelligent subagents". Scores at `low` sat close to Fable 5.1 at higher levels.
- `medium`: interactive coding, chat, everyday knowledge work.
- `high` (API default): hard coding, research, agentic work, long unattended runs. Most of the capability gain is present by `high`. Turns take noticeably longer than at `medium`.
- `xhigh`: only the hardest long-running coding and agentic work, where a gain was measured. It "raised scores slightly and used many more tokens".
- `max`: for measuring the ceiling, or rare tasks where time and tokens do not matter (scientific discovery, mathematics). Slow, and many more tokens than `xhigh`.
- Three behaviours tied to level: the model stops early more often at `low` and `medium`; at `high` and above it thinks before almost every reply, including a greeting; effort barely changes reply length, so use the prompt for length and tone.

**Opus 5.5** `[local-doc: model-migration.md § Migrating to Claude Opus 5.5]` `[web: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5.md]`:

- Start at `medium` (the default). At `medium` it matches or exceeds Opus 5 at `high` on coding and knowledge work. On several coding evaluations `low` comes close at much lower cost.
- Reserve `xhigh` and `max` for work with a measured quality gain. At those levels turns run long.
- To get less thinking, lower effort first. This is more reliable than prompt text.

**Sonnet 5.5** `[local-doc]`: start at `medium` for agentic coding and multistep tool use; `low` for chat, content generation, classification, extraction and search. At `low` on long agentic tasks it is more likely to stop and check in, or to skip verifying a change.

**Haiku 5.5** `[local-doc]`: `low` for chat, short tool tasks, simple high-volume requests; `medium` (default) for most work including agentic coding; `high` for knowledge work, longer agent tasks and strict instruction following. At `xhigh` and `max`, compare against Sonnet 5.5 before settling.

**Measured effort curves** (Anthropic-internal, directional) `[web: https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence.md]`:

- Opus 5.5 on a coding subset: `medium` is about 2.5 points below `high` for about 70% of the cost; `low` is about 8 points below for about a third of the cost; `xhigh` is about 1.4 points above for 2.5x the cost.
- Research and knowledge work has nearly flat curves: `medium` matched `high`, and `high` bought nothing measurable. `[local-doc: cost-optimization.md § 2.6]`
- Counter-example: Opus 5.5 at `low` scored 34 points lower than `medium` on an internal defect-search benchmark. Low effort is not safe for every task type.
- "Re-run failures at higher effort": run everything low, re-run only failures at `high`. About 97% solved at about $0.17 per task, against 95.3% at $0.29 for everything at `high`. It needs a reliable failure signal (tests, a checker).

**Effort in Claude Code** `[web: https://code.claude.com/docs/en/model-config.md]`:

- Set by `/effort`, `--effort`, the `effortLevel` setting (accepts `low` to `xhigh`, not `max`), the `CLAUDE_CODE_EFFORT_LEVEL` variable, and `effort:` in skill and subagent frontmatter.
- A subagent with no `effort` of its own runs at the session level only when it uses the main model.
- `ultrathink` in a prompt requests deeper reasoning for that turn only.
- Changing effort mid-session keeps the prompt cache on Fable 5.1 and later, Opus 5.5, Sonnet 5.5 and Haiku 5.5 when signed in with a subscription or API key. `[web: https://code.claude.com/docs/en/prompt-caching.md]`

`[inference]` Recommended starting defaults for the brain, to be confirmed by the brain's own measurements:

| Task type | Model and effort |
|---|---|
| Routine session lead, interactive work with the owner | Opus 5.5 `medium` |
| Hard architecture, ambiguous root cause, long unattended build, plan synthesis | Fable 5.2 `high` (try `medium` first where the task is well specified) |
| Research and document synthesis | Opus 5.5 `medium` (curves are flat; do not pay for `high`) |
| Bounded implementation ticket with tests | Sonnet 5.5 `medium`, re-run failures on Opus 5.5 `medium` or `high` |
| Bulk reading, extraction, classification, file triage | Haiku 5.5 `low` or `medium`, prompt kept at or under 100K tokens |
| Code review and independent verification | Opus 5.5 `medium` or `high`, fresh context |
| Final gate on a high-stakes design | Fable 5.2 `high`, fresh context |
| `xhigh` / `max` | Off by default. Use only for a named hard problem and record the reason |

### B3. Always-on thinking: what it means for prompts and files

- Thinking cannot be disabled on Fable 5.2 or Opus 5.5. `thinking: disabled` and `budget_tokens` return a 400. `[local-doc]` Claude Code also cannot turn it off on these models. `[web: model-config page]`
- Thinking tokens bill as output and count toward `max_tokens`. `[local-doc]`
- **Instructions to think less do not work on Fable 5.2 at `medium` and above.** A line such as "answer directly without deliberating" did not stop it thinking. Remove such lines and lower effort. `[local-doc]` `[web: prompting-claude-fable-5-2]`
- On Opus 5.5 such a line can reduce thinking at `low`, but lowering effort is more reliable; measure quality. `[local-doc]`
- **Do not ask the model to write its reasoning into the response.** It invites a `reasoning_extraction` refusal. Asking for a short explanation of the answer or a summary of actions is still fine. `[local-doc]` `[web: prompting-claude-opus-5-5]`
- In chat prompts, remove "think carefully before answering" lines for Opus 5.5: replies started sooner with no clear quality loss. `[web: prompting-claude-opus-5-5]`
- A token budget written into the prompt changes how much Fable 5.2 spends. Removing a large budget lowered cost at equal performance at `high` and `xhigh`. `[local-doc]` `[web: prompting-claude-fable-5-2]`
- Remaining-context countdowns shown to the model can cause "context anxiety" (suggesting a new session, trimming its own work). Avoid showing them. `[local-doc: Fable 5.1 section, stated to carry over]`
- Text the model writes between tool calls returns as progress-update thinking blocks, empty at the default display. A client that renders only text looks silent. Claude Code manages this itself. `[local-doc]`
- `[inference]` For the brain: no "think step by step", "think hard", "show your reasoning" or "be brief in your thinking" lines anywhere in CLAUDE.md, skills or agent files. Depth is set by `effort:` frontmatter and model choice. No token or context budgets in prompt text.

### B4. Behavioural shifts and the prompting style to use

#### Fable 5.2 (and what carries over from Fable 5.1)

All items `[local-doc: model-migration.md § Migrating to Claude Fable 5.2 -> Behavioral shifts]` and `[web: prompting-claude-fable-5-2]` unless marked.

1. **Over-prescription harms quality.** "Prompts and skills written for prior models are often too prescriptive ... and reduce output quality." Prefer stating the goal and constraints over listing steps. `[local-doc: Fable 5.1 long-running agent recommendations]` Claude Code's own guidance for Fable: outcome-based prompts; "it verifies its own work, so verification reminders are usually unnecessary". `[web: model-config page]`
2. **Give the reason, not just the request.** It performs better when it knows the intent and who the output is for. `[local-doc: Fable 5.1 section]`
3. **Finish the whole task.** It sometimes ends a turn with a list of what remains, an offer to continue, or a stop at an ordinary obstacle, more often at `low` and `medium`. The published "# Finishing work" text halved the number of sessions that ended with doable work left, and raised output tokens by about 30%. It did not remove endings that list what remains and stop. Add it only where the behaviour is seen, and for agentic work at `low` or `medium`.
4. **Approvals are applied literally.** Name the exact actions a rule covers. A rule about "sending messages to people outside this conversation" made it hold back about half of routine requests. Tell it what is approved in a full sentence, not "continue".
5. **Say who owns the code.** With no ownership statement it adds to existing structure, repeats code, and reports nearby problems instead of fixing them. The sentence "This codebase is yours: what it's for and how it's built are your call, and you'll keep building on it." raised merging of repeated code from under a tenth to about half of tries. Costs: about 1.5x output tokens, unrequested changes (often tests and docs), behaviour changes to existing features in one try in six to ten, and closing summaries that omit small changes. "Review the diff, not only the summary." A scope rule elsewhere does not cancel the sentence.
6. **Long turns are quiet.** It may make its first tool call without saying what it will do. It suits long asynchronous work where the user returns for the result. An opening-line-plus-recap instruction raised output tokens about 20%. Use it only where a person watches live.
7. **Subagent use depends on the harness.** With a minimal subagent tool it rarely delegates. Where prompts invite delegation it delegates readily. At `xhigh` and `max` in a coding product it used subagents to review its own work. "Subagents can be a large part of a session's cost, so check which model the harness runs them on by default." Review standing "delegate" lines first. A tool description that puts cost first cut delegation by about a third at equal task success.
8. **Piled-up caution.** Cautious instructions build up in memory, notes, instruction files and messages between agents, and Fable 5.2 follows them closely. Measured effects: one "never retry" note among a dozen cut retries from nearly all tries to about four in ten. A reviewer's "stop at the first error" stopped retries in about a third of tries where Fable 5.1 and Opus 5.5 retried. Under a "never" rule it took an approved step in about one try in ten, against nine in ten when the rule itself said "get a go-ahead first". A general "act more freely" line changed nothing. Fixes: delete notes that are no longer needed; name the steps that need no approval; write the exception into the rule; check what reviewer agents attach; keep a real confirmation step for risky actions.
9. **Hard style rules are followed too closely.** "One instruction per sentence, in 20 words or fewer" makes prose choppy. Remove such rules.
10. **The "treat that answer as done" lines are harmful here.** At `high` they cut thinking on follow-ups but made Fable 5.2 far less likely to point out its own earlier mistakes. Leave them out wherever self-correction matters.
11. **Final reports.** Readers have not seen the tool calls. The published "# Communicating clearly" text (write for an intelligent, low-context reader; key points first; plain words; no invented abbreviations; Simplified Technical English style) made reports less dense.
12. **Ground progress claims.** "Before reporting progress, audit each claim against a tool result from this session." This nearly eliminated fabricated status reports in tests designed to elicit them. `[local-doc: Fable 5.1 section]`
13. **State boundaries.** It sometimes takes adjacent, unrequested actions. When the user describes a problem or asks a question, the deliverable is an assessment; do not apply a fix until asked. `[local-doc: Fable 5.1 section]`
14. **No unrequested tidying.** At higher effort it can refactor beyond the task. The published no-tidying text addresses this. `[local-doc: Fable 5.1 section]`
15. **Whole-file rewrites.** Fable 5.1 tends to rewrite a file where a targeted edit would do. A one-line "surgically edit" instruction restored targeted edits. `[local-doc: Fable 5.1 section; not re-tested for 5.2 in the doc]`
16. **Search at low effort.** At `low`, Fable 5.1 answers from memory more and searches less, most visibly for products and models it half-knows. Raise effort for those turns, or add the "the name itself is the thing to verify" instruction. `[local-doc: Fable 5.1 section]`
17. **Memory surface helps.** It performs notably better when it can write learnings to a file: one lesson per file, a one-line summary at the top, update rather than duplicate, delete wrong notes. `[local-doc: Fable 5.1 section]`
18. **Verification.** Separate fresh-context verifier subagents tend to outperform self-critique. `[local-doc: Fable 5.1 section]` If an existing prompt asks the model to test before reporting, keep it on Fable (marked tentative in the source). `[local-doc]`
19. **Non-blocking subagents.** The lead finishes sooner when it is not forced to wait for each subagent. `[local-doc: Fable 5.1 section]` Claude Code starts subagents in the background by default and delivers results in a later turn. `[web: sub-agents page]`
20. **Tester reports** (anecdotal, from the announcement): it "works until the job is actually complete instead of stopping at a plausible checkpoint", says it does not know instead of guessing, and coordinated very large subagent teams (about 170 reviewer agents in one audit; over 1,000 subagents in one eight-day session). Anthropic's automated audit found lower rates of falsely claiming completion and of failing to disclose weak work, measured on Mythos 5.2. `[web: https://www.anthropic.com/claude-fable-and-mythos-5-2]`

#### Opus 5.5

All items `[local-doc: model-migration.md § Migrating to Claude Opus 5.5]` and `[web: prompting-claude-opus-5-5]`.

1. **Strengths.** Multistep work in a real repository, in fewer steps and about half the tokens of Opus 5 at `high`. Code review: more bugs caught, fewer false alarms. Far less likely to state an unsupported figure or cite the wrong source. Detail-oriented on large inputs without more false flags. Clear plain-language reports. It reads charts and screenshots accurately even at `low`. Output is more than 30% faster than Opus 5.
2. **Unattended runs stop at progress reports.** Some updates end the turn with text. A loop that treats this as "done" stops there. Fixes: keep a checklist the model updates; if a turn ends with open items and no blocker, send a short message naming them; stop after two or three automatic continuations; do not treat the task as done while a background command or subagent is still running. A "standing instruction" paragraph that names the four unwanted stop types reduces early stops, at the cost of somewhat more tool calls and tokens. Leave it out of human-in-the-loop use.
3. **Re-evaluate older verification, verbosity and scope instructions.** On Opus 5, instructions that tell the model to verify caused over-verification, and removing them had no capability cost. `[local-doc: Opus 5 section, line 1105]` In a measured prompt audit, removing "verify twice" cut cost by about a third and removing "be maximally thorough" cut it almost as much; removing contradictory rules and a hand-rolled scratchpad each restored 7 to 11 points of accuracy. `[web: cost page]`
4. **Explore before acting in multi-app work.** It gets to work quickly. On loosely specified tasks, one sentence telling it to look through relevant sources first raised correct completions, for slightly more tool calls.
5. **Time signals.** It is highly responsive to elapsed time. Showing `elapsed 340s / 1200s` or the sentence "Time matters here..." made agent teams finish sooner. On one task set this cut time 47% and cost 60% for a 4.1-point lower score. The budget is advisory. Under time pressure it may verify a little less.
6. **Frontend design defaults.** Without design direction it falls back on a few default styles. "Avoid a generic AI look" only swaps one default for another. Name the specific patterns to avoid, and iterate. This matters for the owner's design bar.
7. **Pasted content.** Marking pasted text with tagged blocks improves resistance to instructions inside it.
8. **Vision scaffolding may no longer be needed.** Re-test it. A crop tool still helps on the densest inputs.

#### Sonnet 5.5 and Haiku 5.5 (worker tiers)

All `[local-doc]`.

- Sonnet 5.5: remove old workarounds ("do not be lazy", tool-call retry shims). It follows "minimize tool calls" literally, so remove such lines. **At `low` it sometimes reports a code change as done without a real check**; the published verification paragraph fixes this. It can call a tool with the wrong letter case; handle that tolerantly. It can read harness text placed right after a tool result as a prompt injection, so do not add per-step text after every tool result, and do not use task budgets on interactive sessions.
- Haiku 5.5: substantially better at instruction following and at running as a subagent. Give it today's date when it has a search tool. With a long system prompt at `low` it sometimes stops early; moving from `low` to `medium` roughly halved early stopping and more than doubled output tokens per attempt. **At `low` and `medium` it sometimes reports work as done without running a check.** At `xhigh` in multi-turn chat it can return an empty reply. It has no server-side fallback for refusals. Prompts over 100K tokens move to a rate card that is five times higher.

#### What to say and what not to say (for both lead models)

Say:

- The goal, the constraints, who the output is for and why.
- Who owns the code (only where restructuring is wanted).
- Exactly which actions are pre-approved and which need a go-ahead, with the exception written inside the rule.
- What "done" means and how it will be checked.
- When user-facing text is wanted and what it should contain.
- Specific patterns to avoid (for design work).

Do not say:

- "Think step by step", "think carefully", "answer without deliberating", "show your reasoning".
- Step-by-step procedures where a goal and constraints would do.
- "Verify twice", "be maximally thorough", "always use a subagent to verify" as blanket rules for Opus 5.5 or Fable. For Sonnet and Haiku workers at low effort, do add the specific run-a-real-check paragraph.
- Blanket "never" rules without scope and reason.
- Standing "always delegate" lines.
- Token budgets or context countdowns in prompt text.
- "Hold all findings for the final response", "don't narrate", "minimize tool calls", "only use tools when strictly necessary".
- Hard sentence-length or style limits.
- "Treat that answer as done" (on Fable 5.2).

`[inference]` Design consequence for the brain: the sample repo's handbook style (many absolute prime directives, 22 standing roles, mandatory reviewer on every ticket, "never" rules) is the pattern these docs warn about for Fable 5.2. The new brain should carry a short core, scoped rules with reasons, and a pruning step in its learning loop that removes cautions whose reason no longer holds. The learning loop itself is the main risk: it is the mechanism by which caution piles up.

### B5. Refusals and fallback

- Both models run safety classifiers. A decline is an HTTP 200 with `stop_reason: "refusal"` and a category: `cyber`, `bio`, `frontier_llm`, `reasoning_extraction`, `general_harms` on Fable 5.2; `cyber`, `bio`, `reasoning_extraction` named for Opus 5.5. `[local-doc]` `[web: prompting-claude-fable-5-2]`
- Fable 5.2's safeguards "will block most cybersecurity-related tasks" (penetration testing, exploit generation, binary-based vulnerability work) and most research biology tasks. Finding vulnerabilities in source code is allowed. Benign security and life-science work can trigger the classifiers. `[web: https://www.anthropic.com/claude-fable-and-mythos-5-2]` `[local-doc]`
- Fable 5.2's permitted API fallback targets are Opus 4.8 and Opus 5. `reasoning_extraction` declines are not retried. `[local-doc]`
- **In Claude Code** `[web: https://code.claude.com/docs/en/model-config.md]`: for Fable and Opus 5.5, a biology flag re-runs on Opus 5 and a cybersecurity flag re-runs on Opus 4.8. **The session then stays on the fallback model until the user runs `/model`.** With "Ask each time" set, a subagent does not pause; it fails instead of switching. `claude --safe-mode` helps find whether CLAUDE.md, skills, MCP or hooks trigger a flag.
- A fallback is a model switch: the next request reads the whole history uncached, and the fallback model runs without the earlier thinking blocks. `[web: https://code.claude.com/docs/en/prompt-caching.md]` `[local-doc]`
- Documented false-positive triggers on Fable 5.1: compile-check phrasing (ask "Are there any bugs in this program?"), lesser-known programming languages without context, and tools that return base64 data into context. The local doc says not to offer these tips for Opus 5.5. `[local-doc]`
- `[inference]` For the brain: (1) keep classifier-adjacent wording out of always-loaded files, since a flag silently downgrades the whole session; (2) tell the owner in plain words when a session has fallen back and how to switch back; (3) route security-flavoured tasks to Opus 5.5 from the start; (4) a subagent that fails on a flag needs a defined retry path.

### B6. Preserved thinking, and why the harness must be append-only

- Each thinking block is valid only against the exact `system` prompt, `tools` and earlier messages that preceded it. On Fable 5.2 this check is enforced for every account. On Opus 5.5 it is enforced by default for accounts created on or after 2026-08-31. A request that replays a thinking block after an edit returns a 400. `[local-doc]` `[web: whats-new page]`
- The same edits also restart the prompt cache. "One discipline serves both: keep `system` and `tools` fixed for the session and treat `messages` as append-only." `[local-doc: cost-optimization.md § 2.1]`
- The `drop_block` escape makes the model think again, which raises output tokens. It is a stopgap. `[local-doc]`
- No model other than Fable 5.2 and Mythos 5.2 reads Fable 5.2's thinking blocks. Moving a conversation from Fable 5.2 to Opus 5.5 loses the reasoning for later turns. Moving from Opus 5.5 up to Fable 5.2 keeps it. `[local-doc]` `[web: whats-new page]`
- "Nothing changes for you if Claude Code, claude.ai, Claude Managed Agents, or the Claude Agent SDK builds your requests." `[web: whats-new page]`
- `[inference]` Because the brain runs inside Claude Code, the 400 error is not the brain's problem. What remains is the cost side. The brain's files decide whether Claude Code's cache holds. The rules that follow from the Claude Code caching page are in B6a.

#### B6a. Cache rules inside Claude Code

All `[web: https://code.claude.com/docs/en/prompt-caching.md]` unless marked.

- Request order is system prompt (with tool definitions), then project context (CLAUDE.md, auto memory, unscoped rules), then the conversation. A change in an earlier layer invalidates everything after it.
- **Invalidates the cache:** switching models (including `opusplan` toggles, safety fallback, and a skill or command whose frontmatter names a different `model`); turning fast mode on or off; connecting or removing an MCP server when tools load up front; removing a tool on purpose; `/compact`; accumulating many images; upgrading Claude Code.
- **Keeps the cache:** editing repo files; invoking skills and commands (they append as messages); plan mode; changing permission mode; changing output style; `/rewind`; spawning a subagent; changing effort on these four models.
- **Editing CLAUDE.md mid-session keeps the cache but does not apply** until `/clear`, `/compact` or a restart. Nested CLAUDE.md files and path-scoped rules load on demand.
- **Subagents do not share the parent's cache.** Each starts its own prefix and warms its own cache. A fork does inherit the parent's prefix and reads its cache. A resumed subagent can read the cache its first run warmed.
- **Cache lifetime on a subscription:** the main conversation gets the 1-hour lifetime within plan usage. Subagents, workflows, compaction and forks get 5 minutes unless `subagentPromptCacheTtl` is set. Once the account is on usage credits, the main conversation drops to 5 minutes.
- The cache is scoped to the machine and directory, and sequential sessions share a prefix only when the git status snapshot at startup matches.
- Healthy agent loops read a median 84% of input from cache; below about 80%, look for a cache-breaker. `[web: cost page]` `/usage` in Claude Code shows the hit ratio, misses and likely cause. `[web: https://code.claude.com/docs/en/costs.md]`
- Cache economics: reads cost 0.025x input on Fable 5.2 and 0.05x on Opus 5.5, so a miss is far more expensive relative to a hit than on older models. `[local-doc: prompt-caching.md]` Without caching, measured agent costs were 3.1x to 7.3x higher. One system-prompt edit in a cached conversation cost up to $1.26; the same text as a mid-conversation message cost up to $0.026. `[web: cost page]`

`[inference]` Design rules for the brain:

1. Choose model and effort at session start and hold them. Do not use `opusplan`. Do not put `model:` in the frontmatter of inline skills; use `context: fork` skills or subagents when another model is wanted.
2. Keep always-loaded files (both CLAUDE.md files, unscoped rules, auto memory) small and stable. Claude Code's guidance is under 200 lines for CLAUDE.md. `[web: costs page]` Put everything else in skills, which load on demand and append.
3. The learning loop must not rewrite always-loaded files during a work session. Batch its edits at session end, so the next session pays one cold start, not many.
4. Put no dates, counters or status text in always-loaded files.
5. Keep the MCP tool list fixed for a session; rely on deferred tool loading.
6. Because every subagent starts cold, a subagent only pays when its work is bulky or parallel. Many small subagent calls are a net loss. Prefer resuming a subagent over starting a new one for related follow-up work.
7. Compact at natural task boundaries, not mid-task.

### B7. Fast mode

- Supported on Fable 5.2 and Opus 5.5 (also Opus 5 and 4.8 in preview). Not on Sonnet or Haiku. `[web: https://platform.claude.com/docs/en/build-with-claude/fast-mode.md]`
- Up to 2.5x higher output tokens per second. The gain is in output speed, not time to first token. Same model, same quality. `[web: fast-mode page]`
- Price is 2x standard: $16 / $80 on Fable 5.2, $8 / $40 on Opus 5.5. Cache multipliers stack on top. Not available with the Batch API. `[web: fast-mode page]`
- Fast and standard speeds keep separate caches. Each toggle re-reads the conversation uncached. Turn it on at the start of a session or not at all. `[web: https://code.claude.com/docs/en/fast-mode.md]`
- **On subscription plans, fast mode is paid from usage credits only, even when plan usage remains.** It requires usage credits to be turned on. `[web: https://code.claude.com/docs/en/fast-mode.md]`
- It works in cloud sessions (`/fast on`, or the model menu at claude.ai/code), for that session only. `[web: Claude Code fast-mode page]`
- Anthropic's own guidance: best for interactive iteration and live debugging; standard speed is better for long autonomous tasks and cost-sensitive work. `[web: Claude Code fast-mode page]`
- `[inference]` For the brain: fast mode off by default. It costs real money beyond the subscription and does nothing for token efficiency. Document it as an owner-controlled switch for a live, time-critical session. The brain's "super fast" requirement should be met by fewer round trips, parallel reads, lower effort where it holds, and scripts instead of model calls.

### B8. Fable 5.2's narrow limits (AI-R&D topics, including accelerator kernel optimisation)

- Anthropic states that during training it deliberately limited gains in the research skills that could most directly speed up AI development. In those areas, **including accelerator kernel optimisation and improving large-language-model architectures, Fable 5.2 and Mythos 5.2 perform at about the level of Opus 5.5.** `[web: https://www.anthropic.com/claude-fable-and-mythos-5-2]`
- The same passage says the changes were designed not to affect nearby skills: agentic coding, hardware development, and traditional AI and machine-learning research including interpretability. `[web: same page]`
- Both models include transparent fallbacks to Opus 5 for a small set of these topics, "such as kernel development on certain nonstandard accelerators". The page points to Section 1.5 of the system card, which I did not read. `[web: same page]`
- The `frontier_llm` refusal category ("could assist the development of competing AI models") is the API-level form of this. `[local-doc]`
- On Anthropic's own evaluations, vulnerability identification is roughly on par with Opus 5.5. `[web: same page]`
- The local reference directory has no mention of kernels or accelerators. `[local-doc: grep found nothing]`
- Secondary sources (blogs, press) describe controversy over similar limits on the original Fable 5. I did not verify them and do not rely on them. `[web: search results only]`
- Other measured weak spots for Fable 5.2 `[web: cost page]`: on a deep-research benchmark it scored 1.9 points below Opus 5.5 at about 3x the cost, and 4.7 to 7.0 points below Fable 5.1; on a coding benchmark at `high` it cost more per solved task than Fable 5.1 ($1.39 against $1.17). `[local-doc: cost-optimization.md § 2.7 says the same in general terms]`
- `[inference]` For the brain: paying the Fable premium buys nothing for GPU or accelerator kernel tuning, LLM architecture or training-pipeline work, and vulnerability finding. Route those to Opus 5.5 from the start. This also avoids a mid-session fallback and its cache loss. For multistep research and document synthesis, Opus 5.5 is the better and cheaper default on current evidence.

### B9. Task budgets

- A task budget tells the model how many tokens it has for a whole agentic loop. The model sees a countdown and paces itself. It is advisory, not a hard cap. Minimum 20,000 tokens. Beta header `task-budgets-2026-03-13`. `[local-doc: model-migration.md § Task Budgets]`
- Set it from the loop's 90th-percentile usage, then tighten. Pass rate fell a few points while cost per task fell by a much larger share. Very tight budgets can produce refusal-like behaviour. A mid-task change invalidates the cache. `[local-doc: cost-optimization.md § 2.6]`
- On Sonnet 5.5 the countdown arrives as a system message after every tool result and can be read as a prompt injection. Do not use task budgets on interactive sessions. `[local-doc]`
- The finding that a prompt-written budget inflates Fable 5.2's spend is about harness text, not the API feature, which that testing did not cover. `[local-doc]` `[web: prompting-claude-fable-5-2]`
- `max_tokens` is a backstop, not a tuning knob. A tight cap cut off many attempts: Fable 5.2 at a 16,384 cap had 85% of attempts capped and solved 20.3%, against 77.4% at 64,000. Set 64,000 for agentic work. `[web: cost page]` `[local-doc: cost-optimization.md § 2.4]` The Opus 5.5 prompting page says 128,000 has worked well for long agentic coding turns. `[web: prompting-claude-opus-5-5]` The two sources differ; both agree a low cap is harmful.
- `[inference]` Task budgets are an API parameter. The brain, running in Claude Code, cannot set them. The usable equivalents in Claude Code are `maxTurns` on subagents, effort level, and an elapsed-time line for Opus 5.5. Do not write token budgets into prompts.

### B10. Which model for which role, with cost-per-task reasoning

Measured data (Anthropic-internal, directional) `[web: https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence.md]`:

| Benchmark | Configuration | Score | Cost |
|---|---|---|---|
| Coding subset, 463 problems | Opus 5.5 `medium` | 93.1% solved | $0.22 per solved task |
| | Opus 5.5 `high` | 95.5% | $0.30 |
| | Opus 5.5 `xhigh` | 96.5% | $0.75 |
| | Fable 5.2 `low` | 94.6% | $0.39 |
| | Fable 5.2 `high` | 96.3% | $1.39 |
| Coding subset (other run) | Sonnet 5.5 `high` | 87.6% | $0.11 |
| | Opus 5.5 `low` | 87.4% | $0.12 |
| Internal agentic coding | Opus 5.5 `medium` | 86.6% | $0.84 per attempt |
| | Fable 5.2 `low` | 88.9% | $1.05 |
| | Fable 5.2 `medium` | 88.9% (single run) | $1.34 |
| | Sonnet 5.5 `high` / `medium` | 77.8% / 62.7% | $0.33 / $0.16 |
| Defect search | Opus 5.5 alone `high` | 0.850 | $236 |
| | Opus 5.5 lead + Sonnet 5.5 subagents | 0.831 | $139 |
| | Fable 5.2 lead + Sonnet 5.5 subagents | 0.833 | $165 |
| | Fable 5.2 alone `low` | 0.866 | $357 |
| Deep research | Fable 5.2 `low` / `medium` / `high` | 54.5 / 55.0 / 57.7 | $1.49 / $2.16 / $4.82 per task |
| Science questions | Haiku 5.5 `medium` | 85% (Opus and Sonnet 91%) | about a twentieth of Opus 5.5's cost per correct answer |
| Agent task set, 79 tasks | Haiku 5.5 `medium` | 93% (single run) | about $0.011 per passed attempt |

Other measured results from the same page:

- Haiku 5.5 subagents on coding cut cost per attempt by 32%, with pass rate down about 4 points.
- An advisor pairing (Opus 5.5 executor, Fable 5.1 advisor) gave 3.5 points for about 3.5x the money. On two other benchmarks the executor never consulted the advisor.
- "When the work is one dependent chain, or fits in a single context without a long cost tail, the orchestrator's model alone at lower effort came out ahead in every case measured." An orchestrator pays only when there is bulk to hand off: many independent pieces, ideally more than one context window. `[local-doc: cost-optimization.md § 2.7 says the same]`
- Claude Code agent teams use about 7x the tokens of a standard session when teammates run in plan mode. `[web: https://code.claude.com/docs/en/costs.md]`

Reading of the data `[inference]`:

- On coding, Fable 5.2 at `high` buys about 3 points over Opus 5.5 `medium` for about 6x the cost per solved task. Opus 5.5 at `high` gets most of that gain for about 1.4x. So the escalation order is Opus `medium`, then Opus `high`, then Fable.
- Fable 5.2 at `low` is a real option: it beats Opus 5.5 `medium` by 1.5 to 4 points at about 1.25x to 1.8x the cost. It is the best "one strong mind" setting when a task is hard but well specified.
- Fable 5.2 as an orchestrator over Sonnet workers scored the same as Opus 5.5 as orchestrator and cost 19% more. The orchestrator seat does not need Fable for routine fan-out. Fable earns the seat when the planning itself is the hard part.
- Sonnet 5.5 is steep between `medium` and `high` (62.7% to 77.8%). Do not run Sonnet workers at `low` on anything agentic.
- Haiku 5.5 is roughly twenty times cheaper per answer with a visible accuracy loss. It fits high-volume work with checkable outputs.

Recommended role map `[inference]`:

| Role | Model and effort | Reason |
|---|---|---|
| **Default lead** (session orchestrator, owner-facing) | Opus 5.5 `medium` | Claude Code's default; best cost per completed task; clear reports; less likely to cite unsupported facts |
| **Deep lead** (new-project architecture, ambiguous root cause, long unattended multi-part builds, plan synthesis from many inputs) | Fable 5.2 `high`; try `low` or `medium` for well-specified hard tasks | Largest measured gains are on long-horizon and ambiguous work; avoid for the B8 topics |
| **Critic / reviewer** | Opus 5.5 `medium` or `high`, fresh context, read-only tools | Opus 5.5 catches more bugs with fewer false alarms; fresh-context verifiers beat self-critique |
| **Final gate on a high-stakes design** | Fable 5.2 `high`, fresh context | Use rarely; one call, bounded input |
| **Implementation worker** | Sonnet 5.5 `medium`, with the run-a-real-check paragraph; failures re-run on Opus 5.5 | Cheapest tier that holds on agentic coding; re-run-failures keeps the pass rate for about 40% less |
| **Bulk reader / extractor / classifier** | Haiku 5.5 `low` or `medium`, prompt at or under 100K tokens, output checked by schema or spot check | About a twentieth of Opus cost; outputs must be checkable |
| **Codebase search** | Claude Code's built-in Explore agent | Read-only and skips CLAUDE.md. Note: on a subscription it may run on Opus, not a cheap model `[web: sub-agents page]` |
| **Deterministic work** (format, lint, count, diff, index, fixture generation) | No model: scripts and hooks | A hook can cut a 10,000-line log to the error lines before the model sees it `[web: costs page]` |

Two cautions on the reviewer role `[local-doc]`: a reviewer's conditions ("stop at the first error") stay in context and suppress routine actions on Fable 5.2; and a review prompt that says "only report high-severity issues" or "be conservative" lowers recall on newer models because they obey it. Keep reviewer output to findings with evidence, and filter severity downstream.

Subagent mechanics the brain must use `[web: https://code.claude.com/docs/en/sub-agents.md]`:

- Model resolution order: per-invocation `model` parameter, then the definition's `model` frontmatter, then `CLAUDE_CODE_SUBAGENT_MODEL`, then the main model. **A subagent with no model set inherits the lead's model**, so on a Fable session every unlabelled subagent runs on Fable.
- Frontmatter supports `model`, `effort`, `tools`, `maxTurns`, `skills`, `memory`, `background`, `isolation`, `omitClaudeMd`.
- A subagent starts with a fresh context. It gets its own prompt, the delegation message, and the full CLAUDE.md hierarchy unless `omitClaudeMd: true`. It does not see the conversation.
- Up to 20 run at once by default; nesting up to three levels.
- Each subagent's final report returns into the lead's context, so many detailed reports still fill it.
- Every agent file's `description` sits in context at startup.

`[inference]` Consequences: set `model` and `effort` explicitly in every brain agent file. Use `omitClaudeMd: true` for bulk readers so they do not pay to load both repos' handbooks. Require short, structured returns from subagents with detail written to files. Keep the agent roster small, because every description is always-loaded context.

### B11. Token-efficiency levers, ranked for a Claude Code based brain

Measured sizes are from `[web: cost page]`; the mapping to the brain is `[inference]`.

| Lever | Measured effect | How the brain applies it |
|---|---|---|
| Prompt cache health | 4.8x to 7.2x cheaper on a research agent; 3.1x to 7.3x costlier without | Rules in B6a; check `/usage` cache line |
| Prompt audit (remove dated instructions) | Old prompts cost 36% more per task on a newer model for no accuracy gain; audited prompts cost 14% less and were more accurate | Short core, no blanket rules, scheduled pruning of learned notes |
| Lower effort where quality holds | `medium` 30% to 52% less than `high` on long coding; `low` about two-thirds less; loss is task-dependent | Effort set per agent and per skill |
| Re-run failures at higher effort | About 40% less than all-at-`high`, same pass rate | Needs a checker; fits tickets with tests |
| Right model per role | Opus `medium` about a sixth of Fable `high` per solved coding task | Role map in B10 |
| Data files through code, not pasted | 92% cheaper and 25 of 25 correct, against 7 of 25 | Scripts read large files; the model reads results |
| Deferred tool loading | 45% with 500 tools; 20% for a GitHub toolset | Default in Claude Code; keep MCP servers few |
| Shorter answers | About 13% less from 39% fewer output tokens | Output shapes for subagent returns |
| Orchestrator with cheaper workers | About a third less, only on work larger than one context | Delegate bulk and parallel work only |
| Skills instead of CLAUDE.md text | Not quantified; CLAUDE.md under 200 lines advised `[web: costs page]` | Progressive disclosure |
| Hooks that pre-filter output | Tens of thousands of tokens down to hundreds in the docs' example `[web: costs page]` | Test and log filters |
| `/clear` between unrelated tasks | Not quantified; free `[web: costs page]` | One task per session; state in files |
| Fast mode | 2x price, no token saving | Off by default |
| Advisor | About 2.1x cost for a gain that may be noise | Do not build |
| Agent teams | About 7x tokens | Off by default |

### B12. Open points and conflicts between sources

1. Effort default: the API default for Fable 5.2 is `high` `[local-doc]`, but Claude Code and the Claude apps default to `medium` `[web: model-config page; announcement]`. The brain runs in Claude Code, so `medium` is the baseline it will see unless it sets effort.
2. `max_tokens`: 64,000 in the cost guidance against 128,000 on the Opus 5.5 prompting page. Not a brain-level setting in Claude Code.
3. Max-plan Fable allowance: not stated on any page I read. Pro and standard Team seats are capped at 50% of weekly limits. The owner should check `/usage` in a Fable session.
4. Whether cloud sessions at claude.ai/code get the same 1-hour main-conversation cache lifetime as local sessions is not stated on the page I read. I assume yes because the rule is keyed to subscription billing. `[inference]`
5. The local doc says "do not offer" Fable 5.1's false-positive tips for Opus 5.5.
6. Several Fable 5.1 prompt snippets (targeted edits, search at low effort, batching tool calls) are stated to carry over to 5.2 only in general terms ("the behavioral guidance ... still applies" appears for 5.1; the 5.2 section "replaces ... the effort and prompting advice"). Treat each as a candidate to test, not a given.
7. All cost figures are API list prices on Anthropic benchmarks. The owner's plan meters usage differently, and none of the numbers were measured on the owner's work. The brain should record its own numbers from its first projects.

### B13. Source list

Local (all under `/tmp/claude-0/bundled-skills/2.1.322/abe77d722f7cc0e8bbf4058a7be92fb3/claude-api/shared/`): `model-migration.md` (sections for Fable 5.1, Fable 5.1 from Fable 5, Opus 5.5, Sonnet 5.5, Haiku 5.5, Fable 5.2, Task Budgets), `models.md`, `cost-optimization.md`, `latency-optimization.md`, `agent-design.md`, `prompt-caching.md`, `live-sources.md`, `platform-availability.md` (grep only). `SKILL.md`: not present.

Web, fetched 2026-11-10:

- https://platform.claude.com/docs/en/models/fable-5-2/whats-new-fable-5-2.md
- https://platform.claude.com/docs/en/models/fable-5-2/overview.md
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2.md
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5.md
- https://platform.claude.com/docs/en/build-with-claude/fast-mode.md
- https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence.md (first 200K of 214K characters)
- https://code.claude.com/docs/en/model-config.md (first 100K of 133K characters)
- https://code.claude.com/docs/en/sub-agents.md (first 100K of 117K characters)
- https://code.claude.com/docs/en/costs.md
- https://code.claude.com/docs/en/prompt-caching.md
- https://code.claude.com/docs/en/fast-mode.md
- https://www.anthropic.com/claude/fable
- https://www.anthropic.com/claude-fable-and-mythos-5-2
- https://www.anthropic.com/news (index only)

Unreachable or not read: https://www.anthropic.com/news/claude-fable-5-2 (HTTP 404); the Fable 5.2 system card (not fetched); the effort page and the preserved-thinking page (not fetched; covered through the local doc and the pages above).
