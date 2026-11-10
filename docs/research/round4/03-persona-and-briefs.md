# Round 4 / 03: Persona lines and file-pointer briefs (CB-207)

Date of research: 2026-11-10. Contract h-20261110-e33bbd.

## Question and stop condition
Q1: Does a role line ("You are an expert X") change task accuracy for current frontier models, Claude especially, versus plain task instructions?
Q2: Does passing a sub-agent brief as a file pointer save tokens versus an inline brief?
An answer = measured results with source, date, models tested; opinion kept apart; Claude-specific evidence flagged present or absent. Existing memo checked first: docs/research/round3/01-briefs-and-templates.md (section 1.3 and line 199 cover the same ground; its persona figures were abstract-only; this memo adds the Dec 2025 and Mar 2026 papers' model lists and numbers).

## Answer
Q1 (confidence: medium-high for "no reliable accuracy gain"; low for Claude specifically). Measured studies find expert personas do not reliably raise factual accuracy and sometimes lower it; they change tone, depth and style. NO study found tested a Claude model as the model under test. Anthropic's own docs claim a role "focuses behavior and tone", which is a vendor claim about tone, not an accuracy measurement.
Q2 (confidence: low-medium). No controlled measurement of file-pointer brief versus inline brief for sub-agents was found. Closest measured evidence on reference-passing says it does NOT beat summarising on tokens but preserves more facts. Whether a pointer saves tokens for a brief is ESTIMATE: depends on whether the brief would otherwise be written once inline (no saving; the helper adds a Read turn) or reused across helpers (saving).

## Hypotheses
- H1 persona lines give no accuracy benefit, only style effects: SUPPORTED (0.7).
- H2 persona lines help, especially for Claude/modern models: no measured support found (0.1); only vendor assertion.
- H3 persona lines hurt accuracy on knowledge tasks: supported for small open models, mixed for others (0.4).
- P1 pointer saves tokens: unproven (0.3). P2 pointer is neutral or costs a turn for single-use briefs: plausible (0.5). P3 pointer helps fidelity/parent-context size: partly supported (0.4).

## Claim table
| # | Claim | URL | Quoted passage | Tier | Date | Conf. |
|---|---|---|---|---|---|---|
| 1 | Expert personas did not improve accuracy on GPQA Diamond / MMLU-Pro across six models (no Claude) | https://arxiv.org/abs/2512.05858 | "Across both benchmarks, persona prompts generally did not improve accuracy relative to a no-persona baseline." | primary (preprint) | 2025-12-05 | high |
| 2 | Models were GPT-4o, GPT-4o-mini, o3-mini, o4-mini, Gemini 2.0 Flash, Gemini 2.5 Flash; one significant gain (Young Child persona, Gemini 2.5 Flash, RD 0.098); 9 significant negatives on MMLU-Pro; Gemini 2.0 Flash expert personas gained | https://gail.wharton.upenn.edu/research-and-insights/playing-pretend-expert-personas/ | "Expert AI personas don't improve factual accuracy, but low-knowledge ones hurt performance." | primary-adjacent (authors' site) | 2025-12-07 | high |
| 3 | Low-knowledge and mismatched personas can lower accuracy or cause refusals | same arXiv abs | "Low-knowledge personas often reduced accuracy." / "Domain-mismatched expert personas sometimes degraded performance." | primary | 2025-12-05 | high |
| 4 | Expert persona prefixes lowered MMLU accuracy 71.6% to 68.0% on six small open models (Qwen2.5-7B, Llama-3.1-8B, Mistral-7B, Mixtral-8x7B, two DeepSeek-R1 distills); no Claude tested; helped alignment-style tasks (Extraction +0.65, STEM +0.60 on MT-Bench-style score); Coding -0.65; longer personas (~150 tokens) hurt knowledge tasks more than ~5-token ones | https://arxiv.org/html/2603.18507 | "overall accuracy: 68.0% vs. 71.6% base model" (section 3.1a); "coding knowledge (Coding, -0.65)" | primary (preprint, USC) | 2026-03-19 | high on numbers; Table 1 shows 67.3 for Qwen so figures are not fully self-consistent |
| 5 | Role prompting changes style not capability: raises depth, lowers clarity, small aggregate differences (1,140 open-ended questions, 38 roles; models not identifiable from the page I could read) | https://arxiv.org/abs/2605.29420 | "role prompting systematically increases expertise depth while reducing clarity" | primary (preprint; abstract only read; PDF unreadable) | 2026-05-28 | medium |
| 6 | Older evidence, same direction: 162 personas, 4 model families, 2,410 questions; personas no improvement, effects largely random | https://arxiv.org/abs/2311.10054 | "adding personas in system prompts does not improve model performance" | primary, peer-reviewed (Findings of EMNLP 2024) | 2023-11 (rev. 2024-10) | high; outside 2025-26 window and models are older |
| 7 | Anthropic docs recommend a role line, claiming a tone/behaviour effect, not an accuracy effect | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices | "Setting a role in the system prompt focuses Claude's behavior and tone for your use case. Even a single sentence makes a difference:" | vendor | fetched 2026-11-10 (page lists Claude Sonnet 5.5, Fable 5.2) | high that the text says this; no data given |
| 8 | Anthropic's newest model guide (Fable 5.2) gives testing-based advice on sub-agent briefing, ownership statements and cost, and contains no role-line advice (searched for role/persona terms in the fetched text: none) | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2 | "Claude Fable 5.2 responds closely to what the prompt says about who owns the code"; one ownership sentence gave merges "in about half of the tries ... and in under a tenth of the tries without it" | vendor, measured by vendor (small tasks) | fetched 2026-11-10 | medium. Relevant as an example that one framing sentence can move Claude behaviour; it is an ownership statement, not an expert-persona line |
| 9 | Sub-agent briefs: a non-fork subagent starts with fresh context; Claude writes the delegation message; subagent also loads CLAUDE.md unless omitClaudeMd | https://code.claude.com/docs/en/sub-agents | "Each subagent starts with a fresh, isolated context window. ... Claude composes a delegation message that summarizes the task, and the subagent works from there." | vendor docs | fetched 2026-11-10 | high |
| 10 | Brief content matters more than channel: each subagent needs objective, output format, tool guidance, task boundaries; vague briefs caused duplicated work | https://www.anthropic.com/engineering/multi-agent-research-system | "Each subagent needs an objective, an output format, guidance on the tools and sources to use, and clear task boundaries." | vendor engineering blog | fetched 2026-11-10 (original post 2025) | high |
| 11 | Anthropic's pass-by-reference is for subagent OUTPUTS, to cut token copying | same | "Subagents call tools to store their work in external systems, then pass lightweight references back to the coordinator." | vendor | as above | high; not about briefs going down |
| 12 | Measured: reference-passing did not beat a summarising orchestrator on tokens (~1.9x vs ~2.5x saving over naive) but kept more facts (8/8 vs 6/8; n=3 per arm; cross-vendor n=10 on Qwen2.5-7B, Mistral-7B same direction); writer experiment n=33 over Haiku/Sonnet/Opus, 4/4 both | https://zenodo.org/records/20671083 | "Summarizing baseline saves more tokens than TOAP (~2.5x vs ~1.9x over naive baseline, Table 2)." | single-author preprint, not peer reviewed | 2026-06-12 | low-medium (small n) |
| 13 | Practitioner illustration: file path ~50 tokens versus ~5,000 for inline findings | https://www.zivtech.com/blog/economics-of-claude-code-part-2-agent-tradeoff | "Fifty tokens for a file path versus five thousand for the findings." | practitioner blog, no method given (illustrative) | 2026-04-22 | low; about outputs returned to parent, not briefs |

## Findings (what the evidence supports)
1. Measured: no reliable accuracy benefit from expert persona lines on multiple-choice knowledge benchmarks, across GPT, Gemini (claim 1-2) and small open models (claim 4), consistent with 2024 evidence (claim 6). Independent of each other, three groups, same direction.
2. Measured: personas shift style (depth, tone, instruction-following alignment) and can cost clarity (claims 4-5). Where the task is tone or format, a role line can matter.
3. Gap: no Claude model appears as the model under test in any study found. Applying these results to Claude is an inference [ESTIMATE]. Anthropic recommends role lines but cites tone, not accuracy (claim 7).
4. Pointer versus inline: no direct measurement. The one controlled reference-vs-summary study finds no token win over summarising (claim 12). A pointer to a brief adds one Read turn per helper (claim 9 mechanics; the Read cost itself is my inference [ESTIMATE]). The reliably documented saving of reference-passing is for outputs and repeated shared content (claims 11, 13).
5. Brief quality, not channel, is the evidenced lever (claim 10).

## Opinion / inference, labelled
- [ESTIMATE] For brain delegation, keep role lines to one short functional label (tone and scope); drop seniority adjectives. Consistent with round3 NO_PERSONA rule; a cost-benefit judgement, not a measured result.
- [ESTIMATE] File pointer pays only when the same brief is reused by several helpers or exceeds what the lead would otherwise re-type; for a single-use brief, inline text avoids an extra turn. Should be measured with the ledger (one A/B: same task, pointer vs inline, count input+output tokens).

## Contrary evidence
- Wharton found some positive cells (Gemini 2.0 Flash expert personas on MMLU-Pro; Young Child on Gemini 2.5 Flash GPQA), so effects are model-specific.
- Role prompting did better on advisory questions, medicine and psychology (claim 5, abstract-level).
- Anthropic docs say a role helps (claim 7), no data supplied.
- Pointer: fidelity advantage of references (claim 12) favours pointers when a summary would drop facts.

## Unknowns / not checked
- Any Claude-model persona accuracy study: none found; absence of evidence, search limited to a handful of queries.
- Effect sizes in 2605.29420 and which models it used: PDF not readable; abstract only.
- USC paper last ~6,000 characters unread; Table 1 vs text figure mismatch (67.3 vs 68.0) not resolved.
- Wharton arXiv PDF tables not read; figures from the authors' summary page.
- Practitioner threads (HN, Reddit) not searched; press coverage (Register, SEJ) seen only in search snippets, not cited as sources.
- Claude Code's actual input-token accounting for a Read turn versus inline text: not measured.
- Anthropic docs pages "Prompting Claude Opus 5" etc. not fetched.

## Link check
All URLs in the claim table were fetched in this session (arxiv abs 2512.05858, 2605.29420 [abs content; PDF unreadable], 2311.10054, html 2603.18507, Wharton page, Anthropic docs x2, code.claude.com sub-agents, Anthropic engineering blog, Zenodo, Zivtech). Passages above are copied from the fetch results, which came via a summarising fetch tool; treat quotes as tool-relayed, not read from raw HTML.

END OF MEMO
