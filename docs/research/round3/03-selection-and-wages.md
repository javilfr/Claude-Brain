# HR department: template selection, hire-or-not, token wage, payroll, settlement, reviews

Date: 2026-11-10. Author: research subagent. Scope: algorithms in pure Python standard library for `engine/hr.py` of Claude Brain.

## 0. Answer in brief (confidence in brackets)

1. **Recommended design, in one paragraph.** Pick a template by BM25 retrieval over `when`/`keywords` giving a fit in [0,1], multiplied by a lower confidence bound of a hierarchical Beta pass-rate (class baseline -> group -> template -> template x class), the same shrinkage shape `mlearn.posterior` already uses. A novelty guard allows an unproven template (fewer than 5 checked uses) only on low-risk, checked, tier <= 2 work, inside the existing exploration cap, and never in the same hire as a model/effort exploration. "No template fits" is decided by two thresholds (fit and vocabulary coverage), and then the plain base agent is used. [medium: structure follows existing code and standard methods; the threshold values are untested starting points]
2. **Hire or not.** Delegate only when `p * C_self > H_p80 + B*pi_out + R*a + V` (section 3), where the main saving is that material read by the lead is re-read from cache on every later turn, and the main cost is the helper's measured spend. At Opus-lead prices and default constants the break-even is roughly 60k tokens of material for a Sonnet helper and roughly 10k for a Haiku helper (my arithmetic, section 3.4; estimates, not measurements). [medium-low: the inequality is first-principles; every constant is an assumption until the ledger supplies it]
3. **Wage.** Use a pooled log-ratio model: median from a size-band x effort prior, class shift by exponentially weighted mean of log(actual/prior) with shrinkage (this is what `mlearn._ew` and `calibrate` already do), spread from a pooled conformal quantile blended with a prior sigma of 0.6. Budget at the 0.80 quantile, not 0.90. [medium]
4. **A wage cannot be enforced inside Claude Code.** Task budgets are not supported on Claude Code (official docs), `maxTurns` is the only hard per-subagent limit and it counts turns, not tokens, and Anthropic's own testing found that a large written token budget made Fable 5.2 spend more. So the wage is (a) a go/no-go and model/effort selection input, (b) a turn-count and reply-length instruction, (c) the yardstick for an after-the-fact overrun flag. [high on the facts, sources in section 4.2]
5. **Why the demo ledger stayed empty** (section 8): the demo's metering depended on a human-filed "grant" per ticket, its gate allowed everything without a grant, its hook wrote `outcome: "unknown"`, and nothing ever set the outcome. The new design must put hire, brief, usage match and settlement in one scripted path with no lead action beyond running `brain close`. [high on the code reading; the claim that no grants were ever filed comes from the brief, not verified by me]

What I could not do: run any code (no execution tool in this session). All formulas and pseudocode below are unexecuted; the arithmetic that appears was done by hand and is labelled.

---

## 1. What exists and what the new module plugs into (facts read from the code)

| Fact | Where |
|---|---|
| `fold(state, records, cfg)` is pure, canonical order (`at`, kind, id), idempotent per record id | `/home/user/Claude-Brain/engine/mlearn.py:842-862` |
| Hierarchical Beta shrinkage global -> family -> class with K_G=4, K_F=6; discounted updates (gamma 0.97, n_cap 40) | `mlearn.py:208-218`, `:181-188`; constants in `memory/ml_config.json` bandit block |
| Score y: 1 first-pass green, 0.5 green after one rework, 0 otherwise, None without a verifying check (no learning then) | `mlearn.py:546-557` |
| `suggest_arm`: Thompson draws over safe arms, 200 seeded draws give a logged propensity; cheaper arms only with check, risk in {trivial, standard}, tier <= 2; exploration cap 25 % of eligible, wasted spend <= 5 % | `mlearn.py:152-167`, `:239-248`, `:260-315`; `ml_config.json` explore block |
| `calibrate(state, cls, family, est_tokens, est_minutes)` returns p50/p80 from EW mean of log ratio actual/estimate, conformal rank quantile from the last 30 ratios, pooled class -> family -> all with K=5, prior p80 factor 1.5 | `mlearn.py:369-425`, `ml_config.json` calibration block |
| Drift charts (EWMA, Page-Hinkley, CUSUM) per class; an alarm forgets 10 % of class bandit mass and caps calibration n at 5 | `mlearn.py:434-505` |
| `item_score` already uses an LCB of a Beta (z=1.28) for recall ranking; credit = advantage over class baseline split among followed items | `mlearn.py:528-583` |
| `route.assign(tasks, budget)`: exact multiple-choice knapsack on integer cost and float quality, Pareto-front DP, returns `feasible: false` with the cheapest assignment when the budget cannot be met | `/home/user/Claude-Brain/engine/route.py:364-425` |
| `route.cheap_first(p, c_cheap, c_verify, c_strong)`: cascade rule `p > (c_cheap + c_verify)/c_strong` | `route.py:354-360` |
| `route._tokens`, `_fold`, `_close` (accent folding; one-edit fuzzy match for words of 5+ letters) usable for Spanish/English dictation | `route.py:32-61` |
| Ledger reads each helper transcript separately in `read_transcript` (unique assistant messages with model and usage; first message is first in dict order) but `summarise` merges helpers into `helpers_total`; **per-helper usage is therefore available but not exposed** | `/home/user/Claude-Brain/engine/ledger.py:67-98`, `:145-190` |
| `_outcomes` in `capture` gives each outcome `model` = the **main** conversation's model and `tokens` = `s["totals"]` (main plus helpers) divided by class count. With helpers this credits the lead's arm with the helpers' tokens. | `ledger.py:288, 293` |
| `memory/models.json`: prices per model, roles -> (model, effort), `limits.max_parallel_helpers 4`, `helper_reply_tokens 2000`, escalation ladder | `/home/user/Claude-Brain/memory/models.json` |

Defect to fix before HR goes live (inference from the lines above): `ledger._outcomes` attributes helper tokens to the lead's arm. HR must write its own helper-level outcome and the main-session outcome must subtract settled helper tokens (or use `s["main"]`).

---

## 2. Template selection (question 1)

### 2.1 Rack record (data, one JSON object per line)

```
{"id":"T-bugfix-tracer","ver":3,"group":"debug","base_agent":"builder",
 "when":"reproduce a failing behaviour, find the root cause, fix it, add a regression test",
 "keywords":["bug","fix","regression","stack trace","failing test","crash","arreglar","fallo"],
 "not_for":["new feature","design"],
 "classes":["software.bugfix"], "min_tier":1, "max_risk":"standard",
 "needs_check":true, "default_effort":"medium", "status":"active|probation|retired|new",
 "size_bands":["S","M","L"]}
```
Group = about 10 groups of about 10 templates (assumption: the owner asked for 100 templates; a group level gives the middle shrinkage layer).

### 2.2 Lexical retrieval: BM25 with a normalised fit

Per document (template) build a term-frequency map from its text with field weights: keywords x3, `when` x1, id/group words x2, `classes` tokens x3 (written as pseudo-terms like `cls_software_bugfix`). Query terms: `route._tokens(task)` minus stop words, plus the pseudo-term of `route.classify(...)["task_class"]` and the family. For each query token not in the rack vocabulary V, map it to the nearest vocabulary token with `route._close` (one edit, length >= 5); otherwise it is out of vocabulary (OOV).

Okapi BM25 with non-negative idf (the Lucene variant):

```
idf(t)   = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))              N = 100 live + probation templates
bm25(q,d)= sum_{t in q ∩ V} idf(t) * tf(t,d)*(k1+1) / (tf(t,d) + k1*(1 - b + b*|d|/avgdl))
fit(q,d) = min(1, bm25(q,d) / sum_{t in q ∩ V} idf(t))            # 1.0 = every query term present once in an average-length doc
cov(q,d) = sum_{t in q ∩ d} idf(t) / sum_{t in q ∩ V} idf(t)       # share of query information the template covers
```
Defaults k1 = 1.2, b = 0.75 (standard textbook values from Robertson and Zaragoza; I did not re-fetch the source this session). With 100 short documents, idf is noisy; the "+1" inside the log keeps it positive, and `b` matters little because documents are about the same length. The normalisation by the query's own idf mass is my construction (engineering judgement): it makes `fit` comparable across queries so one threshold can be used.

Cost: 100 documents x about 60 terms; building the index at each call is microseconds. No cache file is needed.

### 2.3 Learned prior: hierarchical Beta on "passed its check first time"

Per template t in group g, class c, with y from `mlearn._y` (1, 0.5, 0; only when `has_check`). Cells hold `[S, N]` and are updated with `mlearn._upd(cell, y, gamma=0.97, n_cap=40)`:

```
cells:  G[g], T[t], TC[t,c]                 (class baseline b_c comes from mlearn state["baseline"][c], default credit.baseline_prior 0.6)
m0   = b_c
m_g  = (S_g  + K_G * m0 ) / (N_g  + K_G)            K_G = 4   (same as mlearn)
m_t  = (S_t  + K_F * m_g) / (N_t  + K_F)            K_F = 6   (same as mlearn)
alpha = S_tc + K_C * m_t ;  beta = (N_tc - S_tc) + K_C * (1 - m_t)        K_C = 4
q_lcb(t,c) = mean - z*sd of Beta(alpha,beta), z = 1.2816     (use mlearn._beta_q)
```
Why the class baseline as the top prior: it removes most of the "this template got hard tasks" confound at zero cost. Why pooled `T[t]` across classes: with tens of data points the (t,c) cell is almost always empty, so most of the information comes from the template pooled and the group. All of K_G, K_F, K_C reuse the mlearn values except K_C (new, judgement).

Evidence status: hierarchical shrinkage with capped pseudo-counts is the mlearn design, which cites its own round-2 memos (not re-read by me). There is no study of template selection for coding agents that I found; this is engineering judgement.

### 2.4 Choice rule (LCB by default, Thompson only to explore)

```
def choose_template(task, cls, fam, risk, tier, has_check, state, cfg, rng):
    q = tokens(task) + [pseudo(cls), pseudo(fam)]
    ranked = bm25_rank(q)                                  # list of (t, fit, cov), live+probation only
    cand = [r for r in ranked[:5] if r.fit >= TAU_FIT and r.cov >= TAU_COV
            and tier >= t.min_tier and risk_ok(risk, t.max_risk)]
    if not cand: return NONE("no template fits: fit %.2f < %.2f or coverage %.2f < %.2f", ...)
    for r in cand:
        a, b = post(r.t, cls)                              # section 2.3
        r.lcb  = max(0, mean(a,b) - z*sd(a,b))
        r.n    = raw uses of t (undiscounted count of checked outcomes)
        r.novel = r.n < N_NOVEL                            # 5
    exploit = max((r for r in cand if not r.novel and r.t.status == "active"), key=lambda r: r.fit * r.lcb, default=None)
    explore_ok = has_check and risk in SAFE_RISKS and tier <= 2 and budget_ok(state.hr_window) and not arm_exploring
    if explore_ok:
        # Thompson over the (novel or non-novel) candidates; 200 seeded draws -> propensity, like mlearn.suggest_arm
        pick = thompson(cand, fit*theta, rng); propensity = share of draws
        if pick.novel or pick.t.status == "probation": explored = True
    else:
        pick = exploit            # a novel template is never chosen here
    if pick is None: return NONE("only unproven templates fit and this work is not low-risk")
    # must beat the plain base agent: base_q is the lcb of the base agent on this class (mlearn raw/posterior)
    if pick.lcb + MARGIN < base_q and not explored: return NONE("base agent has a better record on this class")
    return pick (+ fit, cov, lcb, n, propensity, explored, basis string)
```
Parameters (all **assumed**, to go to `memory/hr_config.json`): TAU_FIT 0.35, TAU_COV 0.30, N_NOVEL 5, MARGIN 0.05, SAFE_RISKS = ml_config explore.safe_risks, exploration cap = a copy of `mlearn._budget_ok` over a separate `hr_window` (max_rate 0.25, max_waste 0.05).

Product `fit * lcb` has no formal justification. Interpretation offered as an estimate: fit stands for the probability the template is the right archetype, lcb for the pass probability if it is. It ranks sensibly; I did not test it.

**Calibrating TAU_FIT and TAU_COV.** Before launch write 30 to 40 labelled queries (including 10 with no right template, and some in Spanish), compute fit/cov of the best template, and choose the thresholds that maximise the F1 of "a template is right". This is a few minutes of owner or lead labelling; without it the defaults are guesses. After launch every lead override ("I used the base agent") is a label.

**Detecting "no template fits".** Any of: (i) best fit < TAU_FIT; (ii) best cov < TAU_COV; (iii) fewer than 2 informative tokens after stop-word removal; (iv) more than 70 % of content tokens OOV; (v) the best templates all fail `min_tier`/`max_risk`. The answer is then `base_agent = role default` from `mlearn.baseline`, recorded as `template_id = null` so the null case also accumulates outcomes (this gives the base-agent record that the template must beat).

**Confounding rule.** Never explore a template and a model/effort arm in the same hire (one factor at a time). The two propensities are logged separately; without this rule the outcome cannot be credited to either.

---

## 3. Hire or not (question 2)

### 3.1 Where the money goes (facts)

- A subagent runs in its own context window and returns a summary; use subagents for work that "produces verbose output you don't need in your main context", is "self-contained and can return a summary"; use the main conversation for quick targeted changes, iterative work, shared context, and when latency matters because a fresh subagent "may need time to gather context" (https://code.claude.com/docs/en/sub-agents).
- Claude Code sends the full conversation with every request; history is re-read at the cached rate, so a long session keeps paying for everything already in context (https://code.claude.com/docs/en/costs, "Why usage climbs in a long session"). Material the lead reads is therefore paid again on every later request.
- Subagent requests "still draw on your usage" (same page); agent teams use about 7x tokens (same page, official).
- Anthropic's multi-agent research system: agents use about 4x the tokens of chat, multi-agent about 15x; token usage alone explained 80 % of BrowseComp performance variance; most coding tasks have "fewer truly parallelizable tasks than research" (https://www.anthropic.com/engineering/multi-agent-research-system, fetched today).
- Kim et al., "Towards a Science of Scaling Agent Systems" (arXiv 2512.08296): multi-agent change versus single agent ranged from +80.8 % on decomposable financial reasoning to -70.0 % on sequential planning; centralised verification limited error propagation (https://arxiv.org/abs/2512.08296; abstract only).
- Measured helper size (demo repo, the only measured data in reach): ten research-memo helpers from one session, each 6 to 13 turns; ledger tokens (input + cache write + cache read + output) 437k to 2.07M, median 594k by my computation from `payroll/data/ledger.jsonl` lines 1-10; output tokens 15.4k to 40.3k, median 19.5k; cache write 93k to 281k per helper. Conditions: one session, one task class, same model (`claude-fable-5-1`, medium effort), outcome field "accepted" on all. Cold-start size is not separable from these totals.
- Anthropic's guidance for newer models: Opus 5 "delegates to subagents more readily"; delegation "multiplies cost and time when applied to small tasks"; the damping prompt is "Do not delegate work you can finish yourself in a handful of tool calls" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5). Fable 5.2: "subagents can account for a large part of what a session costs" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2).

### 3.2 The inequality

Prices per token for the lead: `pi_w` (cache write), `pi_r` (cache read), `pi_o` (output); `a = pi_w + T*pi_r` is the lead's carrying cost per token that enters its context, where `T` is the number of lead requests remaining after the material enters the context.

```
C_self  = X*a + O*pi_o                         lead does it: X tokens enter its context (material + tool results + its own output), O output tokens
C_help  = H + B*pi_o + R*a + V + (1-p)*C_self  helper does it
delegate  <=>  C_self - C_help >= theta
         <=>  p * C_self  >=  H_p80 + B*pi_o + R*a + V + theta
```
- `H`: the helper's own predicted cost from the wage model (section 5), at the p80 quantile so the decision is conservative. It already contains the cold start (system prompt, tools, agent file, brief, material).
- `B`: tokens of the brief the lead writes (output price). With `brain hr hire` writing the brief to a file, the lead only writes "follow the brief at <path>", so `B` is about 40 tokens, not 800. This is a real saving of the scheme.
- `R`: helper's report tokens that the lead reads (`limits.helper_reply_tokens` = 2000 at most).
- `V`: lead's cost of verifying. With a check: the check output summary, about 1k to 2k tokens. Without a check: `V = rho * X * pi_w` with rho = 0.3 (assumed).
- `p`: probability the helper passes first time: the Beta mean from section 2.3, or the class-level value for the null template. Failure costs the helper's whole spend plus the lead redoing the work (`(1-p) C_self` is the redo, `H` is sunk).
- `theta`: risk margin, default 0.
- **No check**: the brief's rule says helpers need a check. If none exists, delegate only if `X >= 3 * X_star` where `X_star` is the break-even material size computed with the check-free `V` (the 3x is judgement), and mark the settlement `has_check=false` so nothing is learned from it (I-07).

**Parallelism** adds no token saving; it removes wall-clock time. Add `lambda * minutes_saved` to the left side only when the owner has stated a deadline (default `lambda = 0`). Parallel helpers are allowed only if the sub-tasks are file-disjoint and independent, at most `limits.max_parallel_helpers = 4`; the Kim et al. result (-70 % on sequential work) and Anthropic's "most coding tasks" remark are the reasons to require independence, not a formula.

### 3.3 Default constants and how each is learned from the ledger

| Constant | Default (assumed) | Learned from | Method |
|---|---|---|---|
| `T`, lead requests after the material enters | 20 for tier 2, 10 for tier 1, 40 for tier 3 | Number of unique assistant messages in the main transcript after the delegation point, per tier | Median of the last 20 sessions; `ledger.read_transcript(main)` already gives the message list |
| `pi_*` | `memory/models.json` | none | read |
| `H` | wage model p80 | settlement records | section 5 |
| Cold start `S` (diagnostic, not in the formula) | 15k tokens | first assistant message of each helper transcript: `in + cache_write + cache_read` | median per base agent; this is the only direct measurement of cold-start cost and it is available today in `read_transcript(...)["messages"][0]` |
| `B` | 40 tokens | length of the one-line prompt the lead sent (from the hire record) | median |
| `R` | 1500 tokens | helper's last message `out` | median |
| `V` with check | 1500 tokens | cannot be measured separately; keep the default | none |
| `rho` | 0.3 | cannot be measured | none |
| `p` | Beta mean | settlement | section 2.3 |
| `C_self` | structural `X*a + O*pi_o` | **cannot be observed for delegated work** (counterfactual). Cross-check against `mlearn.expected_cost` for the lead arm in that class | log the structural estimate with every hire so it can be compared with later non-delegated work of the same class |

State plainly: the rule's central quantity `C_self` is a counterfactual, so the rule itself cannot be validated from delegated runs. Only its inputs can be calibrated. Fortnightly, compare the structural `C_self` with the realised main-session cost of non-delegated tasks of the same class and size band; if they differ by more than 2x, fix `T` or `X`.

### 3.4 Worked example (my arithmetic, assumptions stated)

Lead Opus 5.5 at `models.json` prices: `pi_w = 5`, `pi_r = 0.2`, `pi_o = 20` dollars per million tokens; `T = 20` gives `a = 5 + 20*0.2 = 9` dollars per million, i.e. $0.90 for 100k tokens of material kept in the lead's context. Overheads: `B = 40` ($0.0008), `R = 2000` ($0.018), `V = 1500` tokens at `pi_o` ($0.03), total about $0.05. Helper Sonnet: demo-observed cost of similar helpers at Sonnet rates was reported as about $0.42 to $1.32 per research helper (R-A11 F5, an observed-but-secondary figure from the demo repo's memo), so take `H_p80 = $0.80`. With `p = 0.8`: `C_self >= (0.80 + 0.05)/0.8 = $1.06`, i.e. `X >= 1.06 / 9e-6 = 118k` tokens. With `H_p80 = $0.40` (cheap end): `X >= 56k`. For a Haiku scout (`H` about $0.05): `X >= 0.1/0.8/9e-6 = 14k`. These say: material under roughly 15k tokens is read by the lead itself, 15k-60k only for Haiku-class scouting, and delegation to Sonnet pays only from about 50k-120k tokens of material. These are estimates driven by assumed `T` and `H`; `T` is the most sensitive constant (double it and the thresholds halve).

---

## 4. Wage setting (question 3)

### 4.1 What is being predicted

Unit: ledger tokens (`in + cache_write + cache_read + out`, the same quantity `ledger._tokens` and mlearn's `tokens` use), plus two companions: `out` (output tokens, which dominate price and are what the helper "writes") and `turns` (unique assistant messages). Dollar cost is derived through `ledger.price`. Tokens in cache reads grow with turns squared-ish (context re-sent every turn), so turns are the cleaner control quantity.

Evidence that prediction is hard, and why a quantile is the right target:
- Bai et al., arXiv 2604.22750 (v3, 2 Oct 2026): SWE-bench Verified, eight frontier models; same-task runs differ by up to 30x in total tokens; input tokens dominate cost; models predict their own token use with correlation up to 0.39 and underestimate; higher spend does not mean higher accuracy (https://arxiv.org/abs/2604.22750, abstract).
- Smekal, arXiv 2608.25399 (26 Aug 2026): 2,700 runs on one model; stripping a spec to a bare user story raised spend by 29.7 %; prompt sensitivity 13 % to 115 % by task; run-to-run variance unaffected by prompt; a predictor fit from one cheap probe run on an unseen task estimated spend within 36 % (https://arxiv.org/abs/2608.25399, abstract only; the probe-count details were not in the abstract).
- Implication: the lead's own estimate is not a good input (do not use `est_tokens` from the lead); use a size-band prior and learn the class shift. A "probe run" is not affordable here.

### 4.2 What the wage controls in practice inside Claude Code (verified facts)

| Mechanism | Hard or soft | Facts | Source |
|---|---|---|---|
| API `task_budget` | advisory; **not supported on Claude Code** | "Task budgets are not supported on Claude Code or Cowork surfaces"; minimum 20,000; "a soft hint, not a hard cap"; "a budget that is too small for the task can cause refusal-like behavior"; countdown visible only to the model | https://platform.claude.com/docs/en/build-with-claude/task-budgets (fetched 2026-11-10) |
| `max_tokens` | hard, **per request** | "In a tool-use loop, each request in the turn has its own `max_tokens`, so it doesn't bound the whole turn's spend" | https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost |
| `effort` | soft but calibrated; the main cost lever | "a behavioral signal, not a strict token budget"; lowering it is "usually the better first lever"; it controls thinking, not visible reply length (Opus 5: "prompt for length") | https://platform.claude.com/docs/en/build-with-claude/effort ; thinking-steering-and-cost ; prompting-claude-opus-5 |
| Subagent `maxTurns` (frontmatter) | **hard**, counts turns | "When the subagent reaches the limit, Claude Code returns its output marked as partial, and Claude can resume it" (marking needs v2.1.246+). It is a frontmatter field, i.e. fixed per agent file; I found no per-invocation `maxTurns` (UNVERIFIED either way; the demo memo R-A11 E4 lists the same open question for `effort`) | https://code.claude.com/docs/en/sub-agents |
| Per-subagent token cap | **does not exist** | the sub-agents page describes only `autoCompactWindow` (100k-1M), `maxTurns`, concurrency | same page |
| `--max-budget-usd`, `maxBudgetUsd` | hard, whole query, print/SDK mode | Opus 5 guide names the SDK option and `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` / `..._SPAWN_DEPTH` as the deterministic caps | prompting-claude-opus-5 "Controlling subagent spawning"; demo R-A11 F3 |
| Hooks (`PreToolUse` on Agent could deny a spawn) | hard, but **not available in a two-repo cloud session** where only CLAUDE.md, skills, agents and scripts load (ROUND3_CONTEXT) | | context file |

**The documented caveat about written token budgets.** The Fable 5.2 prompting guide, section "Review instructions written for earlier models": "A token budget that your harness writes into the prompt: ... The size of that budget changes how much Claude Fable 5.2 spends. In Anthropic's testing on coding tasks at `high` and `xhigh` effort, removing a large budget lowered cost, with equivalent performance. Test your tasks without the budget. This finding is about text in the prompt, not the API's task budgets" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2). Related: the Sonnet 5.5 guide warns that a token countdown a harness appends after every tool result can make the model treat genuine user messages as possible prompt injection (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5, "Mid-turn user messages"); and "asking Claude Sonnet 5.5 in the system prompt to think less doesn't reliably reduce its thinking" (thinking-steering-and-cost). The TALE paper (arXiv 2412.18547) reported that a budget far below what a task needs can be ignored and even raise output; I know this only from the demo memo R-A12 F1, not re-fetched, so treat as secondary.

**Implementation consequences (decisions):**
1. The wage is **never written as a large token number** in the brief, and never as a running countdown. A helper cannot see its own token count in Claude Code anyway.
2. The brief carries only quantities the helper can observe: `Work in at most about {turns_p80} tool-call rounds; if the check is not green by then, stop and report what is done and what remains`, and `Report in at most {reply_tokens} tokens; put detail in the file named in the brief` (the second is the existing `helper_reply_tokens` rule and is supported by Anthropic's "prompt for length" guidance). Both are soft.
3. The hard controls are the choice of `model`/`effort` (agent file) and, if the rack needs it, one agent-file variant per turn limit (for example `builder` with `maxTurns: 12` and `builder-long` with 30). Whether the Agent tool accepts a per-call `maxTurns` is unverified; check once before building variants.
4. The wage's largest practical use is the **go/no-go and payroll step** (sections 3 and 6), where it is a decision input, and the **settlement** where it is the yardstick.
5. **Overrun policy** (measured only after the helper ends, because a foreground helper blocks the lead): overrun ratio `rho_o = total_tokens / wage_tokens`. `rho_o > 1`: flag in the settlement and count in the overrun rate. `rho_o > 1.5`, or output marked partial by `maxTurns`: "runaway": record, do not kill, do not auto-raise the wage; the lead decides one of (a) accept the partial output and resume once if acceptance criteria remain, (b) escalate one step on `models.json.escalation` if the check failed, (c) do the remainder itself. A partial run is a right-censored observation: record it with `partial=true`, fold its value times 1.25 into the wage model (judgement; it is at least that large) and count it as `passed=false`. Never delete or hide it.
6. Target overrun rate: 15 % to 30 % (R-A12 F6 target, itself a synthesis); 0 % indicates padding. If the rate over the last 15 settlements is outside 10 %-40 %, report it; do not auto-retune beyond the normal learning.

### 4.3 Four methods compared (little data: tens of points in total, 0-5 per cell)

| Method | Data needed | Strength | Weakness at small n | Existing code |
|---|---|---|---|---|
| (a) Per-class log-normal, conjugate normal-inverse-gamma updates | works from n = 0 via the prior; quantile = mu_n + t * s_n * sqrt(1 + 1/kappa_n) | smooth, interpretable, uses the prior | stdlib has `statistics.NormalDist().inv_cdf` but no Student-t quantile (a Cornish-Fisher approximation is needed); log-normal tail is too light for agent spend. Check on the only data I have: for the ten demo helpers, mean log tokens 6.6085 and sd 0.516 (my hand computation) give a fitted p90 of about 1.43M, but 2 of 10 observations (1.58M, 2.07M) exceed it. n = 10, one class: suggestive only | none |
| (b) Empirical quantiles with pooling | the rank `ceil((n+1)q)` must be <= n: n >= 4 for q = 0.80, n >= 9 for 0.90, n >= 19 for 0.95 | no distribution assumption | below those n the "quantile" is the sample maximum; per-class cells rarely reach 9 | `mlearn._conformal` |
| (c) Split conformal on log residuals | same rank rule; guarantees marginal coverage >= q for exchangeable data (Angelopoulos and Bates, arXiv 2107.07511: distribution-free, non-asymptotic guarantees) | pooled across classes if residuals are made relative (log of actual over predicted) | needs a point predictor and a calibration set; exchangeability breaks under drift (Gibbs and Candes, arXiv 2106.00170, adaptive conformal inference, addresses shift with an online rule); wasteful for n < 10 | `mlearn.calibrate` is a pooled EW + conformal hybrid on log ratios |
| (d) Quantile tracking by stochastic approximation of the pinball loss | n = 0 (starts at the prior) | online, tiny state, tracks drift: `theta <- theta + eta * (1[y > theta] - (1 - q))` | noisy: with eta = 0.2 in log units, the estimate jitters ±20 %; needs ~20+ points to settle; no pooling unless done on offsets; the quantile is at the mercy of the last few points | none (6 lines) |

**Recommendation: (c)-with-prior, i.e. extend what `mlearn.calibrate` already does**, because it needs no new statistical machinery, pools across class, family and all, and degrades to the prior. Concretely:

```
band  in {S,M,L,XL}   from material size X (tokens): S < 15k, M < 60k, L < 200k, XL otherwise   (assumed; same cut-offs as in section 3's break-even region)
P50(band, effort) = P50_M * size_factor[band] * effort_factor[effort]
        P50_M  = 600_000 ledger tokens   (observed: median 594k for 10 helpers, one class, one session, Fable 5.1 medium; NOT a general constant)
        size_factor  = {S: 0.4, M: 1, L: 2.5, XL: 6}      (ASSUMED in the demo's priors.json; no source)
        effort_factor= {low: 0.6, medium: 1, high: 1.5, xhigh: 2.2, max: 3.0}  (ASSUMED in the demo; Anthropic publishes no per-level multiplier)
        model tier multiplier = 1.0 for all tiers (no evidence either way; Bai et al. show large model differences on SWE-bench, so the learned shift below must absorb it)
sigma0 = 0.6   (demo prior 0.5; observed log sd of 10 same-class helpers 0.52; widened because cells mix tasks)
r_i    = ln(total_tokens_i / P50_at_hire_i)        # per settled helper; partial runs multiplied by 1.25 first
mu_c   = EW mean of r over class c with half-life 20 settlements (mlearn._ew), pooled to family then all with K = 5 pseudo-tasks
e_i    = r_i - mu_c(before this record)            # centred residual, kept in a pooled list, last 30
Qhat_q = (n * conformal(e, q) + K_s * z_q * sigma0) / (n + K_s)       n = len(pooled e); K_s = 5; z_0.8 = 0.8416
WAGE_tokens = P50 * exp(mu_c + Qhat_0.80)
```
Cold start (n = 0, mu = 0): `WAGE = P50 * exp(0.8416 * 0.6) = 1.657 * P50` (hand computation). For M at medium effort: 994k ledger tokens. `WAGE_out` and `WAGE_turns` use the same machinery on the `out` and `turns` series with their own priors (M: out 19.5k observed median, turns 8 observed median; both from the same ten helpers; sigma0 for turns 0.35, an assumption).

Priors table (ledger tokens at medium effort; bands S/M/L/XL): 240k / 600k / 1.5M / 3.6M. Only the M cell has any observation behind it. The per-model-tier column is deliberately identical across Haiku, Sonnet, Opus and Fable until each tier has at least 5 settlements, after which `mu` for the "tier" pseudo-class (family level) takes over. If the owner wants differing cold-start priors per tier, the first 5 settlements per tier should be run on S/M tasks to measure it; a one-off calibration batch costs about 5 x 0.3-0.6M tokens per tier.

Why 0.80 and not 0.90: the wage is a flag threshold and a soft instruction, not a cap, so the cost of overshoot is a flag, while a generous number invites expansion to fill it (Parkinson's law as invoked in the demo's R-A12, and the Fable 5.2 finding above). Conformal rank at q = 0.80 exists from n = 4; at 0.90 only from n = 9.

Optional later (n >= 20 in the pooled list): add the adaptive offset of method (d) as a coverage monitor, `delta <- clip(delta + 0.1 * (miss - 0.2), -0.4, 0.4)` and add `delta` to `Qhat`; it follows drift faster than the EW mean. Not recommended for v1: two correcting mechanisms on a few dozen points will fight each other.

Drift: reuse `mlearn._drift_step` on the helper stream (class key `h:<class>`); after an alarm cap pooled n at `calibration.drift_cap` (5). Tokenizer or model change (model id differs from the last seen for that tier): shrink the class cells to n = 4 (mlearn does this for bandit cells with `model_change_n`; same idea). Official note: models from 4.7 on produce about 30 % more tokens for the same text than Sonnet 4.6 (demo R-A11 F1 citing the pricing page; secondary).

---

## 5. Hire pipeline summary (what `brain hr hire` does)

```
1. cls = route.classify(task)            # tier 0 -> return {"hire": false, "why": "answer directly"}
2. X, O = estimate_material(task, project_files_hint)    # given by the caller or by file sizes (bytes/3.6 ~ tokens: assumed)
3. base = quick arm (mlearn.suggest_arm role = tmpl default)   # for the EV only
4. ev = delegation_ev(...)  (section 3)  -> if not delegate: write nothing, tell the lead "do it yourself"
5. tmpl = choose_template(...) (section 2) ; arm = mlearn.suggest_arm(h:<cls>, base_agent role, risk, tier, has_check, rng) unless tmpl.explored
6. wage = wage(...) (section 4.3) ; turns, reply cap
7. write brief file: goal, why, constraints, files owned, check, return format, turn limit, reply cap, the template's guidelines, HR ticket line "hr-<id>"
8. write hire record  .brain/log/hr-<id>.json  (hash of project id, I-05)
9. print one line: "Spawn <base_agent> with: 'HR ticket hr-<id>. Follow the brief at <path>.'"
```
Everything the lead types is one short prompt; settlement finds the helper by the `hr-<id>` string in the first user message of the helper transcript (design; the transcript format is documented as internal, so test on a real transcript first: UNVERIFIED).

---

## 6. Payroll under a budget (question 4)

Goal: across a plan of tickets maximise expected completed value within the session token budget and the usage-window limit.

**Currency.** Use micro-dollars at list price (integers) as the single cost currency: the plan limits' per-model weights are unpublished (demo R-A11 F2: only Fable has its own weekly bucket; no token-to-percent conversion), so token counts across models are not comparable and dollars are the least-bad common unit. Convert each token vector with `ledger.price`. `assign` needs integer cost and float quality; both are satisfied.

**Options per ticket i** (limit to about 8 per ticket to keep the Pareto DP small): for the top-2 templates (including the base-agent null) x safe arms from `mlearn.safe_arms` (max 3) = at most 6, plus `self` (lead does it), plus `defer` (cost 0, quality 0, so `assign` is always feasible and the answer "defer ticket 7" is explicit).

```
for option j = (template t, arm a):
    p_j   = pass probability: Beta mean of cell (t,c) (section 2.3) combined with the arm's mlearn posterior:
            use the template cell if n_t >= 5, else mlearn.posterior(arm) (do not multiply the two: they are not independent)
    c_j   = E[helper cost] = exp(mu + sigma_hat^2/2) * P50 converted to dollars at arm prices     # mean, not the wage quantile
            + hire overhead (B*pi_o + R*a + V)
    esc   = next arm on models.json.escalation; p_esc = its mlearn posterior mean
    cost_j    = round(1e6 * (c_j + (1-p_j) * c_esc_attempt))        # cascade, as route.cheap_first
    quality_j = V_i * (p_j + (1-p_j) * p_esc)                       # V_i = ticket value (owner priority: must 3, should 2, could 1; assumed)
option self : cost = round(1e6 * C_self), quality = V_i * p_lead   # p_lead from mlearn raw_g/posterior for the lead role and class
option defer: cost 0, quality 0
budget_eff = session_budget_usd*1e6 - reserve
reserve    = z_0.9 * sqrt(sum_i Var_i)          # Var_i of lognormal: (exp(s^2)-1)*exp(2*mu_i + s^2) per chosen ticket cost; normal approximation, assumed independent
```
Using means for the knapsack and a reserve from the aggregated variance, instead of summing per-ticket wages, avoids over-reserving: ten tickets at q80 each summed are far above the q80 of the sum. (The sqrt-sum formula is the standard independent-variance result; independence is an assumption, and session-level shocks such as a model change violate it.)

**Constraints outside `assign`.**
- Fable weekly bucket: before building options remove Fable arms if the owner-declared remaining Fable share is below a threshold (`assign` has one constraint only; a Lagrangian penalty would need tuning I cannot justify).
- 5-hour and 7-day windows: the budget passed in should be `min(session_budget, window_remaining_share * usd_per_window_percent)`. The factor `usd_per_window_percent` is unknown; to measure it record `rate_limits.five_hour.used_percentage` deltas at hire and settle if the cloud session exposes them to scripts (UNVERIFIED), and run the E1 experiment in R-A11.
- Concurrency: after `assign`, schedule helpers in waves of <= 4 with file-disjoint ownership; this does not change cost.
- If `feasible` is false, drop the lowest `V_i / cost` ticket to `defer` and re-run (loop at most `len(tickets)` times).

**"Lead does it itself"** is always an option: its cost is the carrying cost `X*a + O*pi_o` (not just the output), and its quality uses the lead's own pass rate. This is what stops the payroll from hiring for small tickets; with the example thresholds of section 3.4, `self` wins below roughly 15k-120k tokens of material depending on the helper.

Evidence: exact multiple-choice knapsack is already coded in `route.assign` (read). The bipartite Hungarian assignment is not needed because there is no unique-capacity constraint on templates; MCKP with one budget is the right model. Contract-Net-style bidding (Smith 1980, cited in the demo's R-A12 F5) is not recommended: it needs bids from agents, and agents' self-estimates are unreliable (Bai et al. above).

---

## 7. Settlement and learning (question 5)

### 7.1 When and how it runs

`brain close` (rule 9, already run at session end) calls `hr.settle_session(sid)`: for each `.brain/log/hr-<id>.json` of that session without a settlement, find the helper transcript whose first user message contains `hr-<id>`, read it with `ledger.read_transcript`, read the gate/check result from the gate log, write the settlement, and emit records into the learning inbox through the existing `learn` pipeline (rule 8: no hand edits). A hire with no matching transcript is settled as `helper_ran=false` and counted (a clear count of "briefs written but never used" is the direct detector for the demo's failure mode). The lead performs no extra step.

### 7.2 Settlement record (exact fields)

```
kind              "settlement"
id                "hrs-" + sha256(hire_id + "settle")[:16]            # fold idempotency
hire_id           "hr-<8 hex>"
session           session id
at                ISO time of settlement
ticket_hash       sha256 of project ticket id (I-05: no project identifiers)
task_class, family, tier, risk, size_band, has_check, check_id
template_id (null = base agent), template_ver, template_group, template_basis ("retrieval"|"explore"|"none")
fit, cov, template_lcb, template_n_before, template_propensity, template_explored
base_agent, model, effort, model_id (served id from message.model), arm_explored, arm_propensity
hire: {"delegate": true, "C_self": usd, "H_p80": usd, "overheads": usd, "p": float, "margin": usd}
wage: {"tokens": int, "out": int, "turns": int, "quantile": 0.8, "pred_p50_tokens": int, "basis": "prior|class n=..|family|all", "n": int}
usage: {"in":int,"cache_write_5m":int,"cache_write_1h":int,"cache_read":int,"out":int,"thinking":int,
        "total_tokens": int, "turns": int, "first_request_tokens": int, "last_out": int, "minutes": float, "cost_usd": float}
brief_tokens, reply_tokens
passed (bool|null), first_pass (bool|null), rework (int), escalated_to (arm|null), partial (bool), helper_ran (bool)
overrun_ratio      total_tokens / wage.tokens
out_overrun_ratio  out / wage.out
turn_overrun_ratio turns / wage.turns
outcome_source     "gate" | "lead_declared" | "none"      # only "gate" teaches pass rates (I-07)
```
Plus one derived `kind: "outcome"` record for `mlearn` with the fields it already reads (`task_class: "h:"+cls`, `family: "h:"+fam`, `tier, risk, model, effort, model_id, has_check, passed, first_pass, rework, tokens, cost, minutes, est_tokens = wage.pred_p50_tokens, explored = arm_explored, propensity = arm_propensity`). The `h:` prefix keeps helper cells apart from lead cells in the bandit, the calibration and the drift charts, since cells are keyed by class string (`mlearn.py:758-760`, `:779`); family pooling would still mix lead and helper unless the family is prefixed too, which is why the family is prefixed. This prefix is my design choice: the alternative of adding a `role` dimension to mlearn is cleaner but touches existing tested code (open question for the lead).

### 7.3 Who learns what

| Learner | Update | Input fields |
|---|---|---|
| Template cells G[g], T[t], TC[t,c] | `mlearn._upd(cell, y, 0.97, 40)`, y from `mlearn._y` (only if `outcome_source == "gate"`) | template_id, class, passed, first_pass, rework |
| Arm bandit (model, effort) | existing `mlearn._fold_outcome` on the derived outcome | model, effort, passed, tokens, cost, propensity |
| Wage model | r = ln(total/pred_p50) into `_ew` (class, family, all), pooled residual list, turns and out series | usage, wage.pred_p50_tokens |
| Hire-EV constants | medians of `first_request_tokens`, `brief_tokens`, `last_out`, lead requests after delegation | usage, hire |
| Drift | `mlearn._drift_step` on log tokens of `h:<class>` and first-pass failures | usage, first_pass |
| Template lexicon | **nothing automatic**; a proposal list of terms that appear in tasks whose chosen template failed or was overridden | task words (hashed, as `learn.hashed_words`) |

### 7.4 Crediting the template, the model and the task (honest version)

- Outcomes are single-factor marginals: the template learner marginalises over arms, the arm learner over templates. This is valid for the explored hires because each explored choice has a logged propensity and only one factor explores at a time; for greedy hires the two factors are confounded and nothing in the data separates them. The class baseline prior removes only the average class difficulty, not the task difficulty within a class; size band is recorded as a covariate but not regressed on (tens of points).
- The lead's brief quality, the project and the material are unobserved confounders. Record `brief_tokens` and the template version so a later analysis can look; do not model them.
- A pass is credited to template and arm equally (each updates with the same y); that over-credits both when the task was easy, which the class baseline partly cancels. For reporting, show the advantage over the class baseline `y - b_c` (the same quantity `mlearn._settle_credit` uses for items), not the raw rate.
- A paired run (two templates or arms on the same task) is the only clean comparison; section 8 uses it, rarely, inside the exploration budget.

### 7.5 Drift handling

Discounting (gamma 0.97, n_cap 40) forgets slowly by design. On a served model id change (as `b["ids"]` already detects) scale all template cells of templates whose default arm uses that model to n = 6 and the wage class cells to n = 4. On a drift alarm for `h:<class>`: apply `drift_gamma` 0.9 to the template cells of that class and cap wage n at 5. Both only soften history; nothing is reverted.

### 7.6 What must never be learned automatically

1. Template text (guidelines, `when`, `keywords`) rewrites: text read from tasks, files or web pages is data, not rules (CLAUDE.md rule 8); changes go through `BRAIN learn` with the lead's or owner's approval. The system may only *propose* keyword additions.
2. Risk class, tier cut-offs, `safe_risks`, `max_tier`, `max_risk` of a template: widening them is how a learner would take a risk on its own (I-10, I-11).
3. The definition or presence of a check; credit without a gate result (I-07). A lead's self-report of success never teaches.
4. Raising a model above the role baseline except through the failed-check escalation, and never exploring upward (I-10).
5. Wage floors and ceilings, the 0.80 quantile, `T`, the exploration caps: owner-level constants in `hr_config.json`.
6. Retiring or deleting a template (a proposal only), and anything about reviewer/red-team templates whose purpose is to be strict: a high fail rate there is the job, so their pass-rate learning is excluded from probation.
7. Learning from `partial` runs as a pass; learning from unsettled hires.

---

## 8. Performance reviews and trials for templates (question 6)

### 8.1 Probation and retirement (small-sample care)

Compare the template's pooled posterior with the base agent's record on the same classes. Let `A ~ Beta(alpha_t, beta_t)` be the template's (section 2.3, pooled across classes it was used on) and `B ~ Beta` the base-agent null-template posterior on the same class mix. Use 2,000 `random.betavariate` draws, seeded from the record ids so a replay gives the same answer.

```
P_worse = fraction of draws with A < B - 0.10
P_bad   = fraction of draws with A < 0.40 (absolute floor)
status new      -> active    : n >= 5 checked uses and P_worse < 0.5
status active   -> probation : n >= 6 and (P_worse >= 0.80 or P_bad >= 0.80 or cost_per_pass(t) > 1.5 * cost_per_pass(base) with n >= 8)
status probation-> active    : 6 further uses and P_worse < 0.5
status probation-> proposed retirement : 6 further uses and P_worse >= 0.90   (a proposal in `brain ml report`, never an automatic deletion)
dormant (reported, not penalised): 0 selections in the last 60 hires
```
n = 6 is the smallest sample at which a template with three or more failures can reach 0.80 given the shrinkage in 2.3; the shrinkage toward the class baseline prevents one early failure from ending a template (a 0/2 record shifts the mean only moderately when K_F = 6). All thresholds are judgement. Probation means: still selectable but only through the Thompson explore lane on low-risk work, with a visible flag.

### 8.2 Trial of a new variant against the old one

State plainly what the data can support. With about 10 runs per arm, the minimum detectable difference in pass rate is large: standard error of a difference at p = 0.7 is `sqrt(2*0.21/10) = 0.205`, so 80 % power at one-sided 5 % needs a true difference of about `(1.645+0.84)*0.205 = 0.51` (my arithmetic, normal approximation). With 30 per arm: se 0.118, detectable about 0.29. Small improvements cannot be demonstrated in this environment; only large effects, regressions that matter, or a clear cost drop.

Protocol (pre-registered, written to `stats/hr-trials/<id>.json` through the learn pipeline *before* the first run; later edits invalid):

```
hypothesis   "variant V of T-xxx lowers tokens per first-pass success without lowering pass rate by more than 0.15"
population   classes C, tiers <= 2, has_check, risk in safe_risks   (only low-risk work enters a trial)
assignment   within each class, alternate V/old by a seeded coin (block of 2) ; one factor changed (template text only: same base agent, model, effort)
primary      (i) non-inferiority: P(p_V > p_old - 0.15) >= 0.80 under Beta(1+S, 1+N-S) posteriors, MC 4000 draws
             (ii) cost: median log tokens per helper lower for V by >= 0.10 (Mann-Whitney U p < 0.10 or bootstrap CI excluding 0)
n_min        8 settled runs per arm (sequential stop allowed only at 8, 12, 16; stop after 16 regardless)
decision     adopt V if (i) and (ii); keep old if neither; if only (i), keep both active and let the bandit decide; if neither (i), retire V.
paired mode  for rare high-value changes: run both on the SAME task (2x cost; counts against exploration waste cap 5 %); analyse discordant pairs with the exact sign test (6 discordant pairs all one way gives one-sided p = 0.0156 (1/64); 5-0 gives 0.031).
```
Why alternation within a class rather than random assignment: with tens of runs, simple randomisation can leave classes unbalanced; blocks of 2 within a class are the cheapest control. Why a 0.15 margin: a tolerance chosen so n = 8 per arm can show it; it is a business judgement, not statistics. No evidence on prompt-variant testing in agent templates was found beyond Anthropic's repeated advice to "test your tasks without the budget"/"measure on your own evals" (Fable 5.2, thinking-steering pages cited above).

---

## 9. Evidence summary, with gaps

| Topic | What exists | Source |
|---|---|---|
| Token cost prediction for agents | variance up to 30x on the same task; self-prediction correlation <= 0.39 and underestimates; one cheap probe reaches within 36 % | arXiv 2604.22750; arXiv 2608.25399 (abstracts fetched 2026-11-10) |
| Budget-aware agents | giving a larger tool-call budget alone does not help; a Budget Tracker plus budget-aware planning (BATS) improves results (Gemini-2.5-Pro on BrowseComp: 24.6 %) | arXiv 2511.17006 (search snippet only, not fetched; secondary) |
| Task budgets (Claude API) | advisory, beta header `task-budgets-2026-03-13`, min 20,000, not on Claude Code | https://platform.claude.com/docs/en/build-with-claude/task-budgets |
| Written budgets in prompts | large written budget raised Fable 5.2 spend with equivalent performance when removed (testing at high/xhigh, coding) | Fable 5.2 prompting guide (above) |
| Effort | the calibrated lever; Opus 5 guide: `low`/`medium` "liberally as your primary control for token cost"; effort sweeps must be re-run per model | prompting-claude-opus-5; effort page |
| Delegation cost | 4x / 15x token multiples; subagent calls draw on usage; fresh subagents need time to gather context; Opus 5 and Fable 5.2 delegate readily and need damping | multi-agent research system post; costs page; sub-agents page; prompting guides |
| When delegation hurts | -70 % on sequential tasks, +80.8 % on decomposable ones (one benchmark suite) | arXiv 2512.08296 |
| Conformal / quantile tracking | finite-sample distribution-free coverage; adaptive version for shifting data | arXiv 2107.07511; arXiv 2106.00170 (abstracts) |
| BM25, Thompson sampling, Beta-Bernoulli shrinkage, McNemar/sign test, MCKP | standard methods; I used background knowledge and the repo's own code and did not re-fetch primary papers this session | n/a: **unverified in this session** |
| Template-level performance learning for agent archetypes, hire-or-not EV rules, wage-as-prompt-budget calibration | **no evidence found**. The EV inequality, the fit x LCB combination, the turns-based wage hint and all constants are engineering judgement | n/a |

Contrary evidence and unknowns: (1) a written budget may help smaller models or non-coding work; the Fable 5.2 finding is for one model on coding at high effort. (2) The demo's TALE result (budgets help reasoning length) conflicts in spirit with the Fable 5.2 finding; both are about different things (chain-of-thought length versus agentic spend). (3) `T`, `H` and the cold-start priors rest on one session's ten helpers of one class. (4) Whether `maxTurns` can be set per call, whether scripts can see `rate_limits`, and whether the helper transcript's first user message reliably contains the HR ticket string are all unverified.

Searches done: Claude Code costs docs, sub-agents docs, task-budgets, thinking-steering-and-cost, effort, prompting best practices, Opus 5 / Fable 5.2 / Sonnet 5.5 prompting pages, Anthropic multi-agent research post, arXiv abstracts 2604.22750, 2608.25399, 2512.08296, 2106.00170, 2107.07511; one search for BATS (2511.17006), snippet only. Not reached or not attempted: TALE and s1 primary text, the Anthropic "when to fold subagents" article (cited only through the demo memo R-A12), the Max-plan limit articles, any paper on template/skill selection learning.

---

## 10. Why the demo's ledger stayed empty (what it specified, and what to avoid)

What it specified (R-A11, R-A12): hook-metered ledger by `SubagentStop`, grants per (ticket, role), PreToolUse gate on the Agent tool that denies spawns when a grant is spent, a renegotiation state machine (+25 % once at 80 % spend if 60 % of acceptance criteria are met), P75 allowances from a reference-class forecast with priors, EWMA/Nelson control charts, PI correction, token buckets, a Thompson picker. It was a very large design for a system with no data.

What the code shows (read, `payroll/payroll/hooks.py`):
- `on_subagent_stop` takes `task_class` and `ticket_size` only from an existing grant, defaulting to `"unknown"` and `"M"`; it hard-codes `"outcome": "unknown"` (lines 46-50). Nothing in the files I read ever sets an outcome later.
- `on_pre_agent` allows any spawn that has no grant (lines 62-67: "no grant: unmetered, allow"), so the gate does nothing unless the lead first files a grant by a separate CLI command.
- All hooks fail open (module docstring).
- The 10 ledger rows have `task_class`, `ticket_size` and `outcome: "accepted"` and share one `ts`, and they lack the `source: "SubagentStop"` key the hook writes (compare `ledger.jsonl` rows with `hooks.py:49`). So they were batch-written outside the hook; I cannot say by whom. The brief says no grants were ever filed; I did not verify that.
- Hooks (`.claude/settings.json`) do not load in the two-repo cloud session (ROUND3_CONTEXT), so even a correctly wired hook would not run there.

Consequences for `engine/hr.py` (design decisions): (1) one scripted path creates the hire record, so class and size are known without a human-filed grant; (2) settlement runs inside `brain close`, which already runs every session; (3) outcomes come from the gate log, not from a lead-typed word; (4) "briefs written but no helper ran" and "helper ran with no hire record" are counted and shown in `brain ml report`, so silence is visible; (5) no gate that depends on state the lead must file; (6) start with four learners only (template cells, wage, arm via mlearn, hire-EV constants) and no control charts or token buckets until there are at least 30 settlements.

---

## 11. Interface proposal for `engine/hr.py`

All learning pure and deterministic like `mlearn`: state in `stats/hr.json`, changed only by `fold`; the rack in `memory/templates/rack.jsonl`; constants in `memory/hr_config.json`. Writing files is the job of `learn apply`.

```python
# --- data
load_rack(root) -> list[dict]                           # rack records, status filtered by caller
config(root) -> dict                                    # memory/hr_config.json + models.json (as mlearn.config)
load(root) -> dict                                      # stats/hr.json or empty skeleton
empty_state() -> dict

# --- retrieval and selection
bm25_rank(query_tokens: list[str], rack: list[dict]) -> list[dict]          # [{id, fit, cov, matched, oov_share}]
posterior_template(state, cfg, template: dict, task_class: str) -> tuple[float,float]   # (alpha, beta)
choose_template(task: str, ctx: dict, rack, state, cfg, rng) -> dict
    # ctx = {task_class, family, tier, risk, has_check}
    # -> {template_id|None, fit, cov, lcb, n, explored, propensity, basis, base_agent}

# --- hire or not
delegation_ev(ctx: dict, material_tokens: int, out_tokens: int, wage_p80_usd: float, p: float,
              state, cfg, parallel_k: int = 1) -> dict
    # -> {delegate: bool, c_self, c_help, margin, break_even_material, why}

# --- wage
predict_tokens(state, cfg, size_band: str, effort: str, task_class: str, family: str) -> dict
    # -> {p50, wage, q, out_wage, turns_wage, n, level("prior"|"class"|"family"|"all"), basis}
wage_turns(...)    # inside predict_tokens
size_band(material_tokens: int, cfg) -> str

# --- payroll
plan_payroll(tickets: list[dict], budget_usd: float, state, cfg, rng) -> dict
    # tickets: [{id, task, ctx, material_tokens, value}] ->
    # {choice: {id: option}, cost_usd, quality, reserve_usd, feasible, deferred: [ids]}   # builds options, calls route.assign

# --- the brief
render_brief(hire: dict, template: dict, task: str, wage: dict, out_path) -> str          # writes the file, returns its path
hire(task: str, *, project=None, risk=None, tier=None, has_check=None, material_tokens=None,
     parallel_k=1, seed=None) -> dict
    # one call does section 5: {delegate, why, template, arm, wage, brief_path, hire_id, spawn_line}

# --- settlement
find_helper_transcript(hire_id: str, sub_paths) -> Path | None
helper_usage(path) -> dict                               # per-helper usage from ledger.read_transcript (new in ledger.py)
settle(hire: dict, usage: dict|None, gate_result: dict|None, now: str) -> list[dict]       # [settlement record, derived mlearn outcome]
settle_session(sid, brain_root=None) -> list[dict]       # called by ledger.capture / `brain close`

# --- learning and review (pure)
fold(state, records, cfg) -> dict                        # kinds: settlement, hr_review, hr_trial
review(state, cfg, rack) -> list[dict]                   # proposals: probation / reinstate / retire / dormant, with n and probabilities
trial_open(spec: dict) -> dict ; trial_assign(trial, class, rng) -> "V"|"old" ; trial_decide(trial, records, cfg) -> dict
report(state, cfg) -> list[str]                          # owner wording, n for every claim, <= max_lines, same style as mlearn.report
```
CLI: `brain hr hire "<task>" [--risk] [--check] [--material N]`, `brain hr plan --budget USD tickets.json`, `brain hr settle` (normally via `close`), `brain hr review`, `brain hr report`.

Config file `memory/hr_config.json` holds (all **assumed**, to be tuned): `tau_fit 0.35, tau_cov 0.30, n_novel 5, margin 0.05, K_C 4, bm25 {k1 1.2, b 0.75}, quantile 0.80, sigma0 0.6, K_s 5, size_cuts [15000, 60000, 200000], prior_p50_M 600000, size_factor, effort_factor, rho 0.3, T_by_tier {1:10, 2:20, 3:40}, nocheck_multiplier 3, overrun_runaway 1.5, censored_uplift 1.25, probation {n 6, p_worse 0.8, margin 0.10, p_floor 0.40, cost_ratio 1.5}, trial {n_min 8, n_max 16, noninferiority 0.15}`.

Minimum viable build order: (1) `ledger.helper_usage` and the fix to `_outcomes` double counting; (2) rack + BM25 + `hire` writing brief and hire record, base agent and role-default arms only (no learning needed to be useful: it already saves the lead's output tokens on briefs); (3) `settle_session` hooked into `close`; (4) wage prior and fold; (5) template cells; (6) payroll and trials after 30 settlements exist.

END OF MEMO
