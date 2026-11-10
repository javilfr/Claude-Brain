# 05 Practitioner view: what heavy Claude Code users report (2026)

Date: 2026-11-10. Author: research sub-agent (practitioner viewpoint).

## Answer first (confidence: medium)
Practitioners converge on one theme: context and quota are the scarce resources, so keep the always-loaded file short, offload bulk to files and scripts, use helpers sparingly, and gate "done" on an objective check. Our current design agrees with most of this. Three points need action: (1) effort changes may invalidate the prompt cache, which contradicts rule 5; (2) repo hooks do not load in two-repo cloud sessions, so every behaviour that practitioners say needs a hook must be a script or a rule; (3) Opus 5.x has specific unattended-run behaviour (text-only turn ends) that rule 9 and the loop must handle.

## Limits of this research (read before relying on counts)
- I could NOT read Reddit, X or Threads threads directly. Reddit appeared only as snippets in search summaries via a third-party mirror (reddit.sentinel-team.org), which I did not open. Threads (threads.com) and X returned nothing usable. HN: one search hit (brianlovin.com/hn/47581701), not opened.
- Most evidence is blog posts (dev.to, Medium, personal sites). Many are SEO-style and may repeat one another. "Sources" below means distinct pages that I saw in search results or fetched; they are not proven independent people. Only the rows marked PRIMARY are official docs.
- Search summaries were produced by a tool; where I did not open the page I mark it (S = snippet only). Numbers are as quoted by the page, unverified by me.
- Rating rule: corroborated = 3+ distinct pages agree, or official doc; single report = 1 or 2; contested = pages disagree.

## Claims (34)

### CLAUDE.md
1. Keep CLAUDE.md under roughly 200-250 lines; move detail to linked files. Rating: corroborated (5+ pages: dev.to/davekurian/your-claudemd-is-too-long-the-200-line-ceiling-that-actually-works-1fb0, dev.to/0xmariowu/claudemd-best-practices-2026-1i5a, dev.to/builtbyzac/how-i-structure-claudemd-for-real-projects-5cam, thepromptshelf.dev blog, adipod.pages.dev; all S).
2. A Reddit user reported Claude ignoring rules near the bottom at about 400 lines (S, via search summary of reddit mirror). Single report.
3. Budget heuristic: about 2% of context window (about 4k tokens of 200k). Source: igorganapolsky.github.io/trading/lessons/ll-017-claude-md-bloat-antipattern-dec12 (S). Single report. Our ~5 KB (about 1.3k tokens) is inside it.
4. Rules should be testable ("all async functions must have a timeout"), not vague ("write good code"). Corroborated (3 pages in the same search; S).
5. Put hard rules first, then context, then background. 2 reports (Reddit post S; one blog). Single/weak.
6. Auto-generated boilerplate instruction files did not help in a benchmark study; hand-written lessons/workflow rules are the counterpoint. Contested (one author argues the study was over-generalised; I did not open the study). S.
7. Editing the top of CLAUDE.md or system prompt invalidates the prompt cache for the session. 1 page in cache search (dsebastien / reddit mirror S). Single report; consistent with Anthropic cache semantics but not verified here.

### Skills, commands, agents
8. Commands now merge into skills: a file in .claude/commands and one in .claude/skills both create /name; skills are the forward path. Corroborated (4 pages: buttondown.com/redpen/archive/slash-commands-vs-skills-vs-subagents-three/, vivekhaldar.com/articles/claude-code-subagents-commands-skills-converging/, second-brain-nuxt.vercel.app, pub.towardsai.net). Secondary.
9. Skill descriptions share a listing budget; overflow silently hides descriptions so the skill cannot auto-invoke (names stay; /name still works). Corroborated (4 pages: dev.to/rulestack/too-many-claude-code-skills-how-the-listing-budget-decides-which-descriptions-claude-sees-4a6m, claudefa.st/blog/guide/mechanics/skill-listing-budget, engineered.at/articles/claude-code-skills-not-triggering-it-might-not-see-them, hackernoon). BUT exact numbers are contested (per-skill cap 250 / 1,024 / 1,536 chars; total 1%, 2% of window, 15,000 chars). Mechanism corroborated, numbers contested.
10. Put the trigger phrase first in a description because truncation keeps the start. 2 pages. Single/weak.
11. A "forced eval" pre-prompt hook to make skills fire cut activation by 30 points in one tester's setup. Single report (besthub.dev article, S).
12. Skills, commands and subagents all depend on model compliance; for guaranteed behaviour use hooks. Corroborated (3 pages), but hooks do not load for us (see platform facts).

### Sub-agents and tokens
13. Parallel sub-agents drain quota faster per minute; one refactor of 300+ files hit the Pro limit in about 15 min parallel vs about 30 min sequential, and the $100 Max window in about 75 min. Source: dev.to/onlineeric/claude-code-sub-agents-burn-out-your-tokens-4cd8 (fetched, July 2025, one anecdotal test, no control). Single report; older than six months.
14. Research that would cost 75,000+ tokens in the main context cost about 500 tokens as a sub-agent summary. Source: blakecrosley.com/en/blog/context-window-management (fetched, Feb 2026, self-reported). Single report. Contrasts with claim 13: the winning case is bulky read-only research that returns a summary.
15. Sub-agents resend project context each call, adding cost and latency (same dev.to page). Single report; matches our "cold start" fact.
16. A Reddit thread (Feb 2026) guessed usage "skyrocketed" after the 4.6 models because models spawn more sub-agents. Speculation, not confirmed by Anthropic (S). Single report.
17. PRIMARY: Opus 5 delegates to sub-agents more readily than earlier models; Anthropic suggests capping delegation for cost-sensitive work, via CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH, CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS (Claude Code 2.1.217 or later) (Opus 5 prompting guide, found via search S; Opus 5.5 guide fetched: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5). Corroborated: the Opus 5 guide plus 2 third-party posts (apidog, aident.ai).
18. Practitioner guardrails seen: depth 2, max 5 children (blakecrosley, single); "use at most two subagents unless I request more" (aident.ai, single).

### Usage limits and cache
19. PRIMARY: cloud sessions, terminal, IDE and chat share one rate-limit pool; parallel cloud tasks consume it proportionally (code.claude.com/docs/en/claude-code-on-the-web.md, Limitations). Corroborated.
20. Plan token quotas are not published; multipliers are relative to Pro. 2 pages (fast.io, morphllm). Single/weak.
21. Anthropic's own usage tips: /clear between tasks; Sonnet for routine work and Opus only when stuck. 1 summarising page citing Anthropic's guide (S). Single report; I did not open the Anthropic page.
22. Anthropic raised Claude Code limits in May 2026 (reports: doubled 5-hour limits on May 6, and peak-hour reductions removed). Contested/unverified: different dates and wording across 2 pages (S).
23. Prompt-cache TTL: 5 min vs 1 hour. Reports conflict on when and whether the default dropped from 1h to 5m (dev.to/whoffagents..., recca0120.github.io/en/2026/04/14/claude-code-cache-ttl-audit/, devclass.com 2026/04/14: Anthropic said it should not raise cost). Contested. Writes cost 1.25x (5m) or 2x (1h) base input; reads 0.1x (one page, S). Posters say sub-agents use 5m even on subscription (Reddit S). Implication (my inference): idle gaps over 5 minutes make the next turn a cache rewrite.

### Context hygiene
24. Quality degrades well before the hard limit: one author measured about 60% utilisation over 50 sessions (blakecrosley, Feb 2026). Single measured report; autocompact thresholds quoted elsewhere vary (64-75%, 83.5%, 95%). Contested numbers.
25. Compact or clear at task boundaries, not when forced (blakecrosley, thepromptshelf.dev, claudify.tech, hackernoon, morphllm). Corroborated (5 pages).
26. Auto-compaction is lossy: Claude remembers editing a file but not its text (morphllm.com/claude-code-auto-compact, S). Corroborated (3 pages). Compaction can thrash when the agent re-reads big outputs (single).
27. Write a hand-made handoff before compacting or ending; status/files/decision/blocked/next structure; under 500 tokens to load (blakecrosley: 49 handoff docs; mejba.me; HN commenter via brianlovin.com/hn/47581701 S). Corroborated (4).
28. Hook-based "read SESSION.md after compaction" is unreliable: Claude does not reliably re-read before answering. anthropics/claude-code issue #43733 (fetched; opened 2026-04-05; closed not planned 2026-05-16; no human comments, so one reporter). Single report. Duplicates #36749, #32881, #17237 exist, so the need is repeated.
29. PRIMARY: in cloud sessions, CLAUDE_AUTOCOMPACT_PCT_OVERRIDE is set by the platform and your env var does not change it; /compact, /context, /clear work; /plugin and /resume do not (code.claude.com/docs/en/claude-code-on-the-web.md, "Manage context"). Corroborated (official).

### MCP
30. MCP Tool Search (lazy tool schemas) shipped in Claude Code 2.1.7 and defers tools when definitions exceed about 10% of context. Reported before/after: about 77K to 8.7K tokens (2.1.69 write-up), 7 servers = 36,000 tokens (18%), 7+ servers = 67,000+ tokens. Corroborated that eager loading costs tens of thousands of tokens (5+ pages: claudefa.st, atcyrus.com, dev.to/gentic_news, besthub.dev, mcp.directory); the percentages (85/90/95%) are not controlled, so treat as contested. Not directly relevant to us: .mcp.json does not load in two-repo sessions.

### Hooks
31. Best-value hooks: formatter on PostToolUse (Edit|Write); heavy test/lint on Stop with a stop_hook_active loop guard; PreToolUse guards for .env and dangerous commands, kept fast. Corroborated (4+ pages: dev.to/ohugonnot..., dev.to/noxcraftdev..., azukiazusa.dev, eseospace.com). A Stop hook that blocks eight times in a row with no tool call is overridden (one page; S).

### Plan, spec, tests
32. Write tests first and review them before implementation; a test that passes before any code exists checks nothing; agent-written tests mostly agree with agent-written code. Corroborated (5 pages: buildermethods.com, dev.to/whoffagents, cc.bruniaux.com, capitalandcompute.net, S).
33. The agent may weaken or edit the test to get green; tell it not to modify the test file. Corroborated (3 pages). Matches our rule 6.
34. Plan mode only gates when implementation starts; spec-driven development adds persistent requirements and review gates (datacamp.com/tutorial/spec-driven-development-with-claude-code, analyticsvidhya 2026/08, others). Corroborated (4). No outcome data comparing spec-first with plain TDD found.

### Cloud, phone
35. PRIMARY: a cloud session clones the GitHub remote at your branch, not your checkout; unpushed commits are invisible; "Branch is not on GitHub" falls back to a pushed ancestor or default branch silently-ish; untracked files are not bundled; bundle under 100 MB; `--cloud` works with one repository at a time from the CLI. Environment expires after inactivity and background shell commands, sub-agents and /loop do not survive it (code.claude.com/docs/en/claude-code-on-the-web.md). Corroborated (official).
36. PRIMARY: cloud-session diffs omit changes made by commands (formatters) until committed and pushed (same page). Single (official).
37. Phone is best for steering, not composing; pre-approving safe commands cut approvals to 2-3 per run (nxcode.io, buildermethods.com/library/claude-code-on-mobile, mejba.me; S). Corroborated (3 pages, all blogs). Phones can start sessions since August 2026 (one page, S).

### Long-running runs
38. PRIMARY: Opus 5.5 can end a turn with text-only progress updates; an unattended loop that treats end_turn as done stops early. Fix: keep a checklist file or todo, re-prompt naming open items, stop after 2-3 automatic continuations, and use a system-prompt paragraph naming the early-stop patterns (prompting-claude-opus-5-5, "Unattended agentic runs"). Single source but official.
39. Loops fail by: never exiting, optimising for test-pass or issue-close, docs drifting from code, cost. Mitigations: verification-gated exit, append-only progress file, capped iterations, circuit breaker (dev.to/intelligenttools_tomic_85..., h0bb3.github.io/log/.../ralph-wiggum-loops-downsides.html, tomwojcik-com.pages.dev/posts/2026-01-15/ralph-claude-code, dev.to/thebasedcapital...). Corroborated (4). No page I saw documented reward hacking with data.

### Opus 5.x prompts (PRIMARY unless noted)
40. Opus 5.5 default effort is `medium`; `medium` matched Opus 5 `high` on coding evals; xhigh/max only where a quality gain is measured; lowering effort cuts thinking more reliably than prompt text. Changing top-level effort between requests invalidates the prompt cache; per-message effort change (beta) keeps it (platform.claude.com .../prompting-claude-opus-5-5, "Calibrate effort").
41. Do not write "double-check your answer" style instructions; they compound with built-in self-correction (Opus 5 guide, S via search; apidog.com/blog/prompting-claude-opus-5/ agrees). 2 sources.
42. Opus 5.5 responds to elapsed-time signals (`elapsed 340s / 1200s`) and finishes sooner in multiagent teams; budget is advisory. Single (official).
43. Opus 5.x may add unrequested steps on narrow tasks; constrain scope explicitly (apidog, noqta.tn S). 2 reports.
44. Existing Opus 5 prompts "should perform well without changes"; trim redundant instructions rather than rewrite (official). I found no practitioner thread on Fable 5.x prompt changes: unknown.

### Self-deception about productivity
45. METR 2025 RCT: experienced developers took 19% longer with AI while believing they were about 20% faster (dev.to/zyvop..., getcoai.com; secondary; tools were Cursor with Claude 3.x, not Claude Code). Corroborated as to the original study (4+ pages). 2026 follow-up numbers (about 4% slowdown after correction; 18% speedup among 10 returnees; developers refusing to work without AI) are contested and observational. I did not open METR's own pages.

(Count: 45 numbered claims, of which 38+ distinct and not duplicate of platform facts. Corroborated: 1, 4, 8, 9 (mechanism), 12, 17, 19, 25, 26, 27, 29, 30 (cost), 31, 32, 33, 34, 35, 37, 39, 45 (original). Contested: 6, 9 (numbers), 22, 23, 24, 30 (percent), 45 (2026). Single: the rest.)

## 12 practices to adopt (with mechanism)
1. Keep CLAUDE.md as is (about 55 lines, testable rules). Lint: line count under 120 and byte size under 6 KB in `BRAIN doctor`. Supports claims 1, 3, 4.
2. Skill descriptions: put trigger phrases in the first 100 characters, keep each under 300 characters, add a total-length check to `BRAIN doctor` (10 skills). Because numbers are contested, test live: ask for each skill by situation and record whether it fires. Claims 9, 10.
3. Handoff file format: Status / Files / Decision / Blocked / Next, under 500 tokens, written by `BRAIN checkpoint` before long work (already designed; add the five fixed headings). Claim 27. Because hook-based re-read is unreliable (28), make `brain boot` the single re-entry point and make the first line of CLAUDE.md work for it ("on Continue, run boot").
4. Compact or clear at task boundaries, never mid-task: add to `brain-build` "after each finished ledger item: checkpoint, then /compact with focus text". Claims 24, 25.
5. Bound helpers by rule and by number: keep "at most four"; add "two unless the task is a read-only fan-out"; make helpers return a summary under 300 words with detail in a file. Claims 13-15, 17-18.
6. Use helpers for bulky read-only research (summary returns about 500 tokens vs 75k in main). Do not use them for edits that need the parent's context. Claim 14.
7. Tests first, reviewed by a different agent (reviewer) before implementation; forbid editing existing tests to pass; record the red run as evidence. `BRAIN run` should capture the failing run as proof that the test failed first. Claims 32, 33.
8. Unattended-loop contract for Opus 5.x: ledger/checklist file is the loop state; if a turn ends with open ledger items and no stated blocker, `BRAIN` prints the one-line continue message (use the guide's wording: "Your task list still has open items: ... Continue with them. If one is blocked, say what is blocking it."); stop after 3 continuations and write NEEDS_YOU. Claims 38, 39.
9. Add the guide's early-stop paragraph (names four early-stop patterns) to the autonomous skill text, not to CLAUDE.md, so it costs nothing in sized-0/1 work. Claim 38. Test behind a measurement: tool calls and output tokens rise "somewhat" per the guide.
10. Idle-gap rule: if more than 5 minutes will pass (waiting on user), checkpoint first; resuming cold costs a cache rewrite. Claim 23 (contested; label as inference).
11. Phone flow: pre-state in the first message the plan, then let the session run; ask for decisions as a numbered menu with defaults (already in rule 2 and Working with the owner); push the branch before any hand-off; end each session with the branch name and one line "what to look at". Claims 35, 37.
12. Effort first, not model switch, and set effort explicitly by task class (medium default on Opus 5.5). Keep `memory/models.json` as the single source. Claim 40. But see contradiction A.

## 12 anti-patterns to lint for
1. CLAUDE.md or a skill over the size caps (claim 1, 3).
2. Skill description over 300 chars or total listing large; trigger phrase not first (9, 10).
3. A rule that only a hook could enforce, placed in repo hooks (hooks do not load in two-repo sessions; 12).
4. Helper briefs without a check or return format; more than four concurrent helpers (13-15).
5. Helpers launched for work smaller than their cold-start cost (15).
6. "Double-check your answer", "think carefully", "be thorough" in prompts or skills (41, 40).
7. Reading whole large files or full test output into the main context; use `BRAIN run` and offset reads (blakecrosley numbers: 2,000-line file about 15-20k tokens).
8. Editing or deleting tests to get green; a new test that passes before the code (33, 32).
9. Declaring done on a text-only turn with open ledger items (38).
10. Handoff or progress file overwritten instead of appended (39 mentions append-only progress file).
11. Changing model or top-level effort mid-session without need (cache; 40, contradiction A).
12. Asking the user to restate things the repo already holds; and self-report of speed gains without a measured number (45). Lint for report lines that claim "faster" or "saved N tokens" without a ledger figure.

## Contradictions with, or risks for, our current design
A. Rule 5 says "Switching model discards the cache. Adjust effort ... instead." The Opus 5.5 guide says changing the top-level `effort` between requests also invalidates the prompt cache; only the beta per-message effort change keeps it. I could not confirm how Claude Code's `/effort` is sent. Action: measure cache read vs write tokens across an `/effort` change from the transcript JSONL before keeping this advice; until then reword rule 5 as "Avoid changing model or effort mid-task; set both at the start of a task."
B. CLAUDE.md rule 9 and the hooks in `.claude/hooks/` (guard_paths.py, session_end.py) and `.claude/settings.json`: per the fixed platform facts, repo hooks do not load in two-repo sessions, and practitioners say instructions are advisory (claims 12, 28). `BRAIN close` therefore depends on compliance. Mitigation: have `brain boot` print an "unclosed previous session" warning, and let the ledger check refuse "done" until close has run.
C. Rule 4 "at most four helpers" is a prose cap; Anthropic's hard caps are env vars (claim 17) which cannot be set from the brain repo in cloud sessions [unverified for cloud environment variables; the docs say environment variables can be set on the cloud environment, which the owner would have to do]. Keep the prose cap and add the owner step to NEEDS_YOU only if measurement shows overspawn.
D. Multi-hour autonomous work under Opus 5.5 can stop at a progress report (claim 38); nothing in the CLAUDE.md addresses this. Add to the autonomous skill, not CLAUDE.md.
E. Cloud-session facts: unpushed work is invisible, environments expire, background tasks and /loop die (claim 35). Rule 7 "checkpoint" must include `git push` of the project branch, otherwise a checkpoint lives only on a VM that can be reclaimed. [My inference from the docs; check whether `BRAIN checkpoint` pushes.]
F. Compaction in cloud sessions is triggered by a platform-set threshold you cannot change via env var (claim 29), so "compact at task boundaries" has to be manual `/compact` or `/clear`.
G. No practitioner source supports our "one cheap model assigned by Thompson sampling" idea or contradicts it; absence of evidence, not support.

## Not found / unknowns
- Fable 5.x prompt-behaviour reports from practitioners: none found. Only Anthropic's Opus 5/5.5 guides.
- Threads (threads.com) and X: no accessible results.
- Direct measurement of sub-agent token waste versus single session: none beyond the anecdote in claim 13.
- Real outcome data for spec-first versus TDD: none.
- Whether `CLAUDE_CODE_*` subagent env vars can be set in a two-repo cloud session: unverified.

## Search log
Searches run (WebSearch): CLAUDE.md length; sub-agents tokens and Max plan; HN long-run compaction handover; cloud sessions multi-repo/phone; MCP tool search; hooks that pay off; Opus 5 prompting; METR productivity; skills vs commands vs agents; plan mode/TDD; usage-limit tips; overnight loops; cache TTL; phone workflow; skill listing budget. Fetched: blakecrosley.com context post; dev.to onlineeric sub-agents post; platform.claude.com Opus 5.5 guide; code.claude.com cloud docs; anthropics/claude-code issue 43733. Not fetched (snippets only): all other URLs above.
