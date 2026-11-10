# 02 Context and token efficiency (context-engineer viewpoint)
Date: 2026-11-10. Confidence overall: medium-high on direction, medium on magnitudes (most are from other models/scaffolds, not Claude Code).
Legend: [P] primary source read by me; [S] secondary (blog/aggregator/search snippet); [E] my estimate/inference; [unverified].

## 0. Answer in brief
What reliably cuts tokens without hurting quality, in order of evidence:
1. Mask or truncate OLD tool outputs mechanically (no LLM call). JetBrains: ~40-57% cost cut, solve rate equal or better in 4 of 5 configs [P]. A 2026 "half-life" truncation harness raised pass rates at small windows [S].
2. Keep always-loaded instructions tiny and non-redundant. AGENTS.md study: LLM-generated repo-overview context files did not help and raised cost >20% [P abstract].
3. Progressive disclosure (skills metadata ~100 tokens each, body <5k, scripts run without loading code) [P Anthropic docs].
4. Script the deterministic work, return only a verdict (docs say only script output enters context) [P].
5. Parallel tool calls and bounded sub-agents for read-heavy exploration; avoid for coding that is tightly coupled [P Anthropic + Cognition].
6. Cache-stable prompt prefix; dynamic content last [P abstract of arXiv 2601.06007: 41-80% cost saving across providers].
What hurts: LLM-summarising trajectories as the default, long-context stuffing, compact formats like TOON in tool-call output, auto-generated repo overviews, naive full-context caching, many sub-agents on coupled coding.

## 1. Evidence table (number, conditions, applies in Claude Code?)

| Technique | Measured | Conditions | Source | In Claude Code (we control files/scripts, not API)? |
|---|---|---|---|---|
| Observation masking (keep last M=10 turns' observations, replace older with placeholder) | cost -40..57% vs raw; solve: Qwen3-Coder 480B 53.4->54.8 ($1.29->$0.61); Gemini 2.5 Flash 32.8->35.6 ($0.41->$0.18); but Gemini Flash thinking 40.4->36.4 (drop) | SWE-agent, SWE-bench Verified n=500, 5 models | [P] https://arxiv.org/html/2508.21433v3 | Partly. We cannot rewrite the harness history. We CAN make our scripts emit short outputs and tell agents to re-read rather than recall. |
| Observations share of turn tokens | ~84% of an average SWE-agent turn | SWE-bench Lite-50 preliminary | [P] same | Yes: the lever is tool output size. |
| LLM-Summary | similar cost cut but trajectories 13-15% longer (Qwen3-Coder), 52 vs 44 turns (Gemini Flash); worst solve on Gemini thinking (31.4) | same | [P] same | /compact is the built-in; avoid relying on it, checkpoint to files instead. |
| Hybrid mask+summary | 7% cheaper than masking, 11% than summary (Qwen3-Coder, Verified-50 only) | small sample | [P] same | n/a |
| Half-life tool-output truncation (newest 4 full; older capped, cap halves as age doubles; keep head+tail; active at 50% window) | F2PF 28%->49% (Qwen3.6-35B) at 20,480-token window; converges at 262k window, still ~7% fewer prompt tokens | open-weight models, Yuj harness | [S] https://codex.danielvaughan.com/2026/08/30/same-model-different-harness-tool-output-compression-coding-agent-performance-codex-cli/ (cites arXiv 2608.26218; I did not open the paper) | Pattern is directly implementable in `brain run` output filter (head+tail+marker, size by recency). Big windows reduce the quality gain; expect cost gain only. |
| Learned tool-output pruner (Squeez 2B) | removes 92% input tokens, recall 0.86, F1 0.80 | 11,477 examples, 618 test | [P abstract] https://arxiv.org/abs/2604.04979 | Needs a model; not stdlib. Use task-conditioned grep/regex instead. |
| Action-preserving compressor CoACT | -33.0% total tokens, solve "close to" uncompressed | SWE-bench Verified, 3 models | [P abstract] https://arxiv.org/abs/2607.02911 | Not installable; confirms ~1/3 saving ceiling. |
| ACON guideline-optimised compression | -26..54% peak tokens; AppWorld 56.5% acc @7.33k peak vs 56.0% @9.93k uncompressed | AppWorld, OfficeBench, multi-QA | [S] https://proceedings.mlr.press/v306/kang26b.html (via search) | Idea transfers: compress rules learned from paired success/fail runs, in our learning loop. |
| LLMLingua-2 | 2-5x prompt compression, 1.6-2.9x e2e latency | MeetingBank, LongBench, GSM8K, BBH (prose, not code) | [P abstract] https://arxiv.org/abs/2403.12968 | No: needs a model install and is validated on prose, not code. AVOID for code/tool output. |
| Context rot | all 18 models degrade as input grows even on simple tasks; ~300-token focused vs ~113k-token full prompt on LongMemEval: focused significantly higher; one distractor hurts, four more | Chroma, 194,480 calls; needle position had no notable effect | [P] https://www.trychroma.com/research/context-rot | Yes: argues for small recall packs, short instruction files. Note: position (lost-in-the-middle) was NOT the driver here; length and distractors were. |
| Context editing (clear old tool results) + memory tool | -84% tokens in 100-turn web search; +29% (editing) / +39% (with memory) on internal agentic-search eval | Anthropic internal, baseline unspecified | [P] https://claude.com/blog/context-management | API feature; whether Claude Code applies it to us is [unverified]. We can mimic: write notes to files. |
| Compaction keeps summary + 5 most recent files; sub-agents return 1-2k token summaries | design facts | n/a | [P] https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | Yes: brief sub-agents to return <=2k tokens. |
| Tool search (deferred tool schemas) | ~77K -> ~8.7K tokens overhead; accuracy Opus 4 49%->74%, Opus 4.5 79.5%->88.1% (article also quotes inconsistent 191,300 vs 122,800) | Anthropic internal MCP evals | [P] https://www.anthropic.com/engineering/advanced-tool-use | Claude Code defers MCP schemas by default [S, changelog digests]. Repo .mcp.json does not load in our setting, so n/a. |
| Programmatic tool calling | tokens 43,588 -> 27,297 (-37%); GIA 46.5->51.2% | Anthropic internal | [P] same | The equivalent for us: one `brain` script call replaces N tool calls. |
| Skills progressive disclosure | ~100 tokens/skill metadata; body <5k tokens; <500 lines; refs one level deep | docs | [P] https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices | Yes, core. |
| Agent instruction files | context files "do not generally improve success", cost +20% or more; repo overviews not helpful; agents obey instructions (so extra rules cause extra work) | SWE-bench + CTXBench; Claude Code, Codex, Qwen Code | [P abstract] https://arxiv.org/abs/2602.11988 | Yes: directly about CLAUDE.md. Keep only non-obvious requirements. |
| Parallel tool calls | up to -90% research time on complex queries; effort-scaling rules prevent over-spend | Anthropic research system | [P] https://www.anthropic.com/engineering/multi-agent-research-system | Yes: instruct "batch independent reads in one message". |
| Multi-agent cost | agents ~4x chat tokens, multi-agent ~15x; token use explains 80% of BrowseComp variance; "most coding tasks" have few parallelisable subtasks | Anthropic | [P] same | Yes; supports tiering. Lead + sub-agents beat single Opus 4 by 90.2% on research eval (not coding). |
| Sub-agents sharing context | Cognition: share full traces; parallel sub-agents make conflicting decisions; Claude Code sub-agents ok for narrow questions | essay, no numbers | [P] https://cognition.com/blog/dont-build-multi-agents | Yes: sub-agents for read-only questions; one writer. |
| Prompt cache design | cost saving 41-80%; full-context caching with dynamic tool results can raise latency; put dynamic content at end, exclude dynamic tool results | DeepResearch Bench, 3 providers | [S/P abstract via search] https://arxiv.org/html/2601.06007v2 | Partly: keep CLAUDE.md/skills static (never edit mid-session), put per-run data at the end of briefs. Cache TTL control is API-side [E]. |
| TOON vs JSON | project claim -39.9% tokens, acc 76.4 vs 75.0 on 209 retrieval questions, uniform tabular only; independent: in agent loops TOON up to -18% tokens but ~-9 points accuracy, parallel tool-call output collapses; TRON up to -27% tokens within 14 points | BFCL, MCPToolBench++, MCP-Universe, StableToolBench, 5 open models | [P abstract] https://arxiv.org/abs/2605.29676 ; generation study https://arxiv.org/abs/2603.03306 ; project claim [S] | Only for read-only tabular data that WE print (e.g. brain tables). Never for model-emitted output. |
| Prompt format sensitivity | up to 40% swing on code translation for GPT-3.5, GPT-4 more robust | 2024 models | [P abstract] https://arxiv.org/abs/2411.10541 | Old models; weak evidence for current Claude. |
| Edit formats | Aider unified diff: 20% -> 61% on laziness benchmark (GPT-4 Turbo); hashline: +15 points avg over patch across 16 models, output tokens -24% Sonnet 4.5, but +26% GPT-5.2 Codex and +20% DeepSeek V3.2; third-party 2026: whole-file among most reliable | mixed | aider.chat/docs/unified-diffs.html [S via search], https://stencil.so/blog/the-harness-problem [S] | We do not control Claude Code's Edit tool. We control: tell agents to use Edit with minimal unique old_string, never rewrite whole files > N lines. |
| Plan caching | -46.62% cost, 96.67% of optimal accuracy; overhead 1.04% | 2 apps, not coding | [S] https://arxiv.org/pdf/2506.14852 | Yes in spirit: reuse playbooks keyed by task class (already designed). |
| Agentic search vs embeddings | Claude Code dropped local vector DB for grep/glob (reported by Cherny, May 2025); reasons: staleness, security, reliability; agentic search costs more tokens | secondary reports, no benchmark | [S] https://smartscope.blog/ai-development/practices/rag-debate-agentic-search-code-exploration/ ; I could not confirm wording from Cherny himself | Use grep+file-list "repo map" script; do not build embeddings. |
| Aider repo map | default 1k tokens (`--map-tokens`), grows when no files in chat | docs via third-party | [S] fast.io, openoxide pages from search; verify at aider.chat | Our `brain boot` is the analogue; AGENTS.md paper warns static overviews did not help, so make it on-demand and task-conditioned. |

## 2. Ranked changes for the engine and instruction files

Ranking = (evidence strength x expected saving) / risk. Each: what, wording/pseudocode, effect, risk.

1. **Head+tail+recency tiering in the output-filtered runner** (ADOPT NOW). Evidence: JetBrains 84% observations; half-life policy [S].
   ```
   def filter(out, cmd, budget=None):
       if exit_ok and cmd.kind in {test,build,lint}: return verdict_line + failing_items[:20]
       lines = out.splitlines()
       if len(lines) <= 60: return out
       return "\n".join(lines[:25] + [f"[... {len(lines)-45} lines omitted; full log: .brain/logs/{id}.txt ...]"] + lines[-20:])
   ```
   Always save full output to a file so nothing is lost; the marker gives the path. Effect: [E] 30-60% of observation tokens. Risk: hides the failing line in the middle; mitigate by extracting lines matching /error|FAIL|Traceback|warning:/i into the head.
2. **Shrink CLAUDE.md to non-inferable rules only** (ADOPT NOW). AGENTS.md study. Delete anything the model can infer from code (directory overviews, language style). Wording: "Only rules that a fresh reader could not derive from the repo. Every line must name a failure it prevents." Effect: cost is paid every turn (cache read) and every sub-agent start; study reports +20% cost for context files. Risk: low.
3. **Skills: description <=300 chars (limit is 1,024), body <=150 lines, references one level deep, scripts "run, do not read"** (ADOPT NOW) [P docs]. Ten skills x ~100 tokens = ~1k always-on [E from docs figure].
4. **One scripted call replaces many tool calls** (ADOPT NOW): `brain gate` does lint+test+diffstat and prints one line plus failures. Analogue of programmatic tool calling (-37% tokens, [P]).
5. **Batch independent calls** (ADOPT NOW). Wording in CLAUDE.md: "If two reads/greps do not depend on each other, issue them in the same message." Effect: up to -90% wall time on research tasks [P]; on coding it is smaller [E].
6. **Sub-agent brief template with bounded return** (ADOPT NOW): objective, files to read, output format, "return <=1,500 tokens: findings, file:line, no code dumps", forbidden scope. Anthropic: summaries 1-2k tokens; vague briefs cause duplicate work [P]. Add: "Sub-agents are read-only unless the brief names the one file set they own." (Cognition conflict risk.)
7. **Checkpoint-to-file instead of relying on /compact** (ADOPT NOW). Write `.brain/state.md` (<=40 lines: goal, done, next, decisions). Summarisation lengthens trajectories [P JetBrains]; file notes are Anthropic's recommended structured note-taking [P]. Wording: "After every gate, rewrite state.md in place; never append."
8. **Task-conditioned search before read** (ADOPT NOW): `brain find <symbol|regex> [--ctx 3]` prints path:line + 3 lines; agents read ranges not whole files. Pseudocode: `rg -n --max-count 5 -C2 pat | head -80`. Grep-first matches Claude Code's own choice [S]. Squeez shows task-conditioned pruning can drop 92% of tokens (needs model) [P]; regex ranges give a cheaper approximation [E].
9. **Cache-stable prefix discipline** (ADOPT NOW). Never edit CLAUDE.md/skills mid-session; put volatile data (timestamps, recall results, run ids) in the last part of any brief; do not put a date or git hash at the top of boot output. [P arXiv 2601.06007 abstract advice].
10. **Recall pack cap and no-recall-when-irrelevant** (ADOPT NOW, improvement to existing memory recall). Chroma: focused ~300 tokens beat ~113k full; distractors hurt. Rule: cap pack at 600 tokens; require BM25 score above threshold, else inject nothing; drop items whose helpful/harmful ratio <0.5.
11. **Effort-scaling rule in CLAUDE.md** (ADOPT NOW; matches tiers 0-3): "Tier 0-1: no sub-agents. Tier 2: at most 2 read-only. Tier 3 only with a written reason." Anthropic's embedded scaling rules [P].
12. **Edit discipline wording** (ADOPT NOW): "Use Edit with the smallest unique old_string. For new files use Write. Never re-emit a whole file over 80 lines." Output tokens are ~57% of cost [context file], so reducing re-emission is the biggest lever. Evidence for diff formats is mixed across models (hashline: -24% Sonnet 4.5 but +26% GPT-5.2 Codex) [S], so only apply what the tool already does.
13. **Output-brevity contract for agents** (ADOPT NOW, [E]): "Final report: answer, 3-5 evidence bullets with path:line, open questions. No restating the task, no file listings." Output is the most expensive token class.
14. **Stuck-state detector in `brain run`** (TRY BEHIND A MEASUREMENT): after 3 identical failing commands or 5 reads with no edit, print a fixed redirect line. Reported alongside half-life policy [S]. Measure: median turns to green on benchmark tasks.
15. **Dedup repeated reads** (TRY): `brain read <file>` hashes content; second read in the same session returns "unchanged since turn N, lines x-y already in context" . Risk: model may genuinely have lost the content after compaction; include a `--force`.
16. **Learned compression guidelines (ACON-style)** (TRY): in the learning loop, store compression rules per command class with success/fail evidence; promote only if gate pass-rate does not fall. [S].
17. **TOON/compact tables for brain's own printed tables** (TRY, low priority): only uniform rows, read-only, benchmarked on our own questions. Otherwise plain TSV/Markdown. Not for model output.

## 3. What hurts (with evidence)
1. **Instruction bloat and repo overviews**: +20% cost and no success gain (arXiv 2602.11988 abstract) [P]. Agents follow instructions, so a wrong or needless rule costs real work.
2. **LLM summarisation as the default memory**: no better than masking, longer trajectories (+13-15% Qwen3-Coder; 52 vs 44 turns Gemini Flash), worst result on Gemini thinking (31.4 vs 36.4 masking) [P JetBrains v3].
3. **Long context and distractors**: all 18 models degrade with length; irrelevant but similar content hurts [P Chroma]. Note: needle position had no notable effect in this study, so "lost in the middle" framing is not the main risk; length and distractors are.
4. **Multi-agent for coupled coding**: ~15x tokens; Anthropic says most coding tasks have few parallelisable subtasks; Cognition shows conflicting assumptions [P]. Sub-agents start cold [context file], so every spawn pays brief + tool/skills overhead.
5. **Naive full-context caching**: caching dynamic tool results can raise latency [S/P abstract 2601.06007].
6. **TOON in tool pipelines**: -9 points accuracy, parallel tool-call collapse [P abstract 2605.29676]. Its headline savings hold for uniform tables only.
7. **Prompt compression (LLMLingua) on code/tool output**: evaluated on prose benchmarks [P]; code-specific compressors exist (LongCodeZip, SWE-Pruner, named in a search result) but I did not read them [unverified].
8. **Embedding index for code**: staleness, extra infra; Claude Code abandoned it [S]. No benchmark, so treat as reported practice, not proof.
9. **Over-aggressive truncation**: hides the real error; mitigated by saving the full log and extracting error lines (change 1).

## 4. Six measurable lint rules (scriptable with stdlib; `brain lint`)
Estimated thresholds are my choices [E], justified by cited limits.
1. `claude_md_bytes <= 5120` and `non-blank lines <= 80`. (platform target; AGENTS.md cost finding)
2. For each `SKILL.md`: body lines <= 150 (hard cap 500 per Anthropic), `len(description) <= 300` (hard cap 1,024), description matches `Use when` and has no first-person ("I ", "you can").
3. Skills/agents link depth: every `*.md` reference must be linked directly from SKILL.md (no reference file linking to another reference). Regex check over links.
4. Sum of always-loaded tokens (CLAUDE.md + all skill name+description + agent descriptions), estimated as bytes/4, must be <= 2,500 tokens; report a diff versus last commit and fail on +10%.
5. Every agent file contains a bounded-return clause: regex `(<=|at most|max)\s*\d+\s*(tokens|words|lines)` and a read-only/ownership statement; fail otherwise.
6. Runtime log lint over the token ledger: flag sessions where (a) any single tool result > 4,000 tokens that was not file-saved, (b) the same file read > 2 times without an intervening edit, (c) a sub-agent returned > 2,000 tokens, (d) tier 0-1 sessions that spawned sub-agents. Output counts per session; trend must not rise across releases.
Optional 7: no volatile strings (dates, hashes, run ids) in CLAUDE.md or skill bodies (cache stability): regex `\d{4}-\d{2}-\d{2}|[0-9a-f]{7,40}`.

## 5. How to improve what is already designed
- Output-filtered runner: add recency tiering (newest result full, older results truncated by half-life), error-line extraction, and a full-log file path (change 1).
- Memory recall: add a score threshold and "inject nothing" outcome; cap pack at ~600 tokens (change 10).
- Token ledger: add rules 6a-6d as per-session metrics; use "output tokens per accepted requirement" as the headline since output is ~57% of cost.
- Thompson sampling: include context size bucket as a feature, because masking/truncation benefit is largest when windows are small and trajectories long (half-life results converge at 262k windows [S]).
- `brain boot`: keep it static in format so it sits in the cached prefix; it is a map, and the AGENTS.md study says static overviews did not help, so measure with and without.

## 6. Not reached / unverified
- Primary Aider docs numbers (repo map, unified-diff), Cherny's primary statement, Lost-in-the-Middle (Liu et al. 2023) not re-read; the aider and repo-map figures come from search snippets.
- Half-life paper (arXiv 2608.26218) read only via a secondary blog; the Squeez model card 91%/86% was not opened (abstract says 92%/0.86 recall).
- AttnCompress (2609.08318), SWE-Pruner, LongCodeZip: not read.
- No Reddit, HN, Threads or X threads were retrieved; search returned only blogs/aggregators. The subagent ~5,000-token overhead claim (mindstudio-type blogs) is unverified; measure with our ledger.
- Whether Claude Code applies context editing/tool-result clearing internally: unverified.
- Hugging Face papers pages for these were not fetched individually; arXiv versions used.
