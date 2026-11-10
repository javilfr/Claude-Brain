# 03 - Routing ML for Claude Brain: small-data online learning of model tier + effort (2026-11-10)

Legend: [FACT] = read in a source (URL given). [DESIGN] = my recommendation (an estimate/inference, not measured). [unverified] = secondary/unchecked.

## 0. Answer (confidence: medium-high on the design shape, low on every numeric constant)

With tens of outcomes, use a hierarchical, discounted, cost-aware Beta-Bernoulli Thompson sampler (global -> task family -> task class), constrained by a "safe set" (explore only cheaper arms, only where a verifying check exists, only below high-risk), with propensity logging for offline IPS evaluation. Add contextual logistic/LinUCB only after roughly 60+ outcomes per arm [DESIGN, rule of thumb]. Nothing published validates any of this on multi-turn agent sessions, so every constant below must be treated as a tunable default and judged by your own ledger.

## 1. Evidence base

### 1.1 Published savings numbers and their conditions
| Source | Claim [FACT] | Conditions / caveat |
|---|---|---|
| RouteLLM, https://lmsys.org/blog/2024-07-01-routellm/ (via search summary) and https://arxiv.org/abs/2406.18665 | ">85% cost reduction on MT-Bench, 45% MMLU, 35% GSM8K"; MF router trained on Arena data reaches 95% of GPT-4 quality with 26% GPT-4 calls (~48% cheaper vs random baseline); 14% with LLM-judge augmentation (~75% cheaper) | Pair GPT-4 Turbo vs Mixtral 8x7B; saving measured against a random-routing baseline; single-turn chat/benchmark prompts. Abstract itself only says "over 2 times in certain cases". I did not read the paper tables. |
| FrugalGPT, https://arxiv.org/abs/2305.05176 | "up to 98% cost reduction" matching best single LLM; or +4% accuracy at equal cost | "Up to"; datasets/cascade config not verifiable from abstract. |
| Hybrid LLM, https://arxiv.org/abs/2404.14618 | "up to 40% fewer calls to the large model, no drop in quality" | "Up to"; benchmarks not in abstract. Counts calls, not tokens/dollars. |
| AutoMix, https://arxiv.org/abs/2310.12963 (NeurIPS 2024) | ">50% compute cost reduction for comparable performance" | Small model self-verifies, POMDP router; beats FrugalGPT and HybridLLM baselines; needs a verification call. |
| RouterBench, https://arxiv.org/abs/2403.12031 | 405,467 samples, 8 datasets, 11 models; no single model dominates; oracle router near-optimal; judge error degrades cascades | Benchmark, not a saving claim. Code https://github.com/withmartian/routerbench |
| ParetoBandit, https://arxiv.org/abs/2604.00136 | Budget compliance within 0.4%; up to +0.071 quality under price/quality shift; new model integrated in about 142 steps; geometric forgetting on sufficient statistics | 1,824 benchmark prompts, 3-model portfolio, preprint. Stats here are for 100s of steps, not tens. |
| OrcaRouter, https://arxiv.org/abs/2605.30736 | LinUCB, one ridge regressor per arm, offline warm start from full-information rewards; RouterArena #2: 75.54% acc at USD 1.00 / 1000 queries | 6-page tech report; needs an offline curated prompt set; hyperparameters not in abstract. |
| Poon et al., https://arxiv.org/abs/2506.17670 (AAAI-26) | Greedy LinUCB per step for multi-step LLM selection with budget-aware variant, sublinear myopic regret | Theory plus benchmarks; myopic (does not model cache/context carry-over). |

Hub assets (reachable, via https://huggingface.co/api/datasets?search=routellm and /api/models?search=router): datasets routellm/gpt4_dataset, routellm/arena_battles_embeddings, routellm/mmlu_battles, routellm/lmsys-arena-human-preference-55k-thresholds (hundreds of downloads each); models katanemo/Arch-Router-1.5B (arxiv 2506.16655), switchboardllm/switchboard-router-0.5b. All are chat-preference routers that need an embedding/LLM model. Not useful for us: our arms are Claude tiers on repository tasks, and we cannot run a 0.5B-1.5B model at session start (no installs).

### 1.2 Practitioner evidence
Searches returned NO Reddit/HN/Threads threads on this topic; only blogs and vendor pages (all secondary, commercial stake):
- https://dev.to/lynkr/your-llm-bill-is-a-misallocation-problem-not-a-model-problem-18dg : claims ex-ante difficulty prediction fails to beat trivial baselines on agentic coding traffic and the gain in cascades comes from the verifier [unverified, vendor].
- Same search: a vendor blog said four learned routers fell from 46-47% to 8.9-21.4% solve rate on unseen agentic repo work [unverified, secondhand].
- Stanford review https://web.stanford.edu/~shuhuiq/blog/review-routing-cascades.html : cascades need a signal from the cheap model's answer flagging probable error.
- Guides suggest starting with 5-10 hand rules and shadow-routing for a validation set [unverified blog advice].
Inference [DESIGN]: our verifying checks (tests, gates, requirements ledger) are exactly the cascade verifier; this is the strongest lever and it is already built.

### 1.3 Non-stationary / safe / offline theory
- Discounted TS (Raj and Kalyani 2017, only analysed for 2 arms) and sliding-window Beta-SWTS (Trovo et al. 2020; analysis corrected by Fiandri, Metelli, Trovo 2024, https://arxiv.org/abs/2409.05181); Qi, Guo, Zhu 2025 analyse discounted and sliding-window TS for abrupt change (https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11765042/ , listed in search; I did not open it). Source: search summary.
- Conservative bandits, Wu et al. ICML 2016, https://proceedings.mlr.press/v48/wu16.html : play the baseline arm unless the learner's choice keeps cumulative reward above (1-alpha) x baseline. Basis for section 4.
- Replay, Li et al. https://arxiv.org/abs/1003.5956 : unbiased only if logging was uniformly random; keeps ~T/K records, high variance as arms grow. Basis for section 6.

## 2. Specification

Notation: arm a = (model_id, effort) e.g. (haiku-5.5, low). Class c in family f. Baseline arm b(c) = what the owner's current rules assign (the safe default).

### 2.1 Reward (1): two separate quantities, no mixed scalar for the posterior
Success score s in [0,1] [DESIGN]:
- s = 1.0 if the verifying check passed on first attempt and no rework turn was needed;
- s = 0.5 if passed after exactly 1 rework/repair round (or escalation);
- s = 0.0 if failed, required >=2 rework rounds, owner rejected/reverted, or no check and owner flagged.
- No check and no owner feedback: DO NOT update (missing, not success).
Cost c = total tokens-weighted cost of the attempt including any escalated retry, normalised by the baseline arm's running median cost for that class: c_norm = c / median_cost(b(c)) (so 1.0 means "same as baseline"). Weight tokens by price (output ~57% of spend per context file; weight output tokens ~5x input is plan-price dependent, read prices from config, do not hardcode).
Posterior update uses s only (fractional update, a heuristic; the exact version is to draw Bernoulli(s)):
  alpha += s ; beta += 1 - s
Selection uses utility with an owner-set exchange rate V (how many "baseline-task costs" a verified success is worth; default V = 3 [DESIGN]):
  expected_cost(a) = c_a + (1 - p_a) * c_escalate(a)      # failure costs a retry on the next tier
  score(a) = p_a * V - expected_cost(a)
Thompson step: draw p_a ~ Beta(alpha_a, beta_a), pick argmax score(a) over the allowed set (section 2.4). c_a is an exponentially weighted mean of observed c_norm (decay 0.9), initialised from price ratios.
Why not one scalar reward: a Beta needs [0,1]; mixing tokens into it hides pass-rate uncertainty, and cost is much less noisy than pass/fail.

### 2.2 Hierarchical priors (2): shrinkage chain with capped pseudo-counts
Per arm a, keep discounted counts (S, N) at three levels: global g, family f, class c.
  p_g = (S_g + 1) / (N_g + 2)                      # or an informed seed from price tiers: stronger model => higher
  p_f = (S_f + K_G * p_g) / (N_f + K_G)           K_G = 4
  p_c = (S_c + K_F * p_f) / (N_c + K_F)           K_F = 6
  Posterior for class c: Beta(alpha, beta) = (S_c + K_F*p_f,  (N_c - S_c) + K_F*(1 - p_f))
A brand-new class has N_c=0, so it equals Beta(K_F p_f, K_F(1-p_f)): effective prior weight 6 outcomes (wide on purpose). Cold family falls to global. K values [DESIGN]; if you have >=200 ledger rows, fit K_F by maximising the beta-binomial marginal likelihood over classes (empirical Bayes; pure-Python grid search over K in {2,4,8,16}).
Ordering prior (inference): impose monotonic seeds p(opus) >= p(sonnet) >= p(haiku), p(effort high) >= p(low) so early draws are not absurd; seed with weak strength 2.

### 2.3 Non-stationarity (3)
Key all counts by model_id (exact version string from transcript). Rules [DESIGN]:
1. Discounting at every update of an (arm, level): S = gamma*S + s; N = gamma*N + 1, gamma = 0.97 (memory about 33 outcomes). Also cap N <= 40 (Qi-style bounded memory, ParetoBandit uses geometric forgetting). Discount only on updates of that arm (not wall-clock), so idle arms do not decay to prior.
2. On model_id change for a tier: shrink the old statistics rather than delete them: scale (S,N) by min(1, 4/N) at all levels (keeps prior mean, ESS = 4), set arm.probation = 5 verified trials during which exploration eligibility is boosted (section 2.4) but only inside the safe set. Ledger rows keep their model_id so offline replay can restrict to the current id.
3. Drift alarm (optional, cheap): if the mean s of the last 8 outcomes of an arm is below its discounted posterior mean by more than 2 posterior SDs, apply the shrink in rule 2 and flag "needs review" to the owner.
4. Sliding window alternative (Trovo): keep last W=30 outcomes per arm; equivalent in effect, but needs a list; discounting is simpler and O(1).

### 2.4 Safe exploration (4)
Allowed set A(task) [DESIGN, in the spirit of conservative bandits, Wu 2016]:
- A = {b(c)} always includes the baseline.
- Arms cheaper than baseline are ELIGIBLE only if ALL: task has a verifying check that runs before the work is accepted; risk tier is not high (never for release, security, migrations, data deletion, owner-flagged); size tier <= 2; escalation path to baseline exists (on check failure rerun on baseline, cost of the experiment = the wasted cheap attempt, bounded).
- Arms more expensive than baseline: allowed as exploitation only (when the baseline's lower bound is below the required quality), never to "explore".
- Exploration budget: cumulative wasted spend on failed cheap attempts <= 5% of rolling 50-task spend, and at most 1 in 4 eligible tasks explores [DESIGN constants]. If exceeded, play baseline (conservative-bandit fallback).
- A cheaper arm is exploited (not just explored) only when its 10th-percentile posterior quantile q10(p_a) >= p_baseline_mean - 0.05 AND n_eff >= 5.
- Thompson sampling itself does the exploring inside the eligible set; do not add epsilon-greedy on top.
- No-check tasks: always baseline. Owner-visible log line shows when an experiment ran.

### 2.5 Contextual upgrade (5)
Features x (d=7) [DESIGN]: bias, size_tier/3, log1p(files_touched)/3, has_check, plus family one-hot (hash to <=3 dims) or class prior p_c from section 2.2 as a single feature (cleaner: logit(p_c)). Per arm: online logistic regression, L2 lambda=1, SGD step 0.1/sqrt(t), or LinUCB with Sherman-Morrison inverse update (d<=8, pure Python lists). Choose arm by Thompson-style perturbation: sample theta from N(mean, A^-1 * v^2) needs Cholesky; cheaper: LinUCB score = x.theta + alpha*sqrt(x A^-1 x), alpha=0.5, then same constraint/utility as 2.1.
When NOT worth it [DESIGN estimates; the first is the standard events-per-variable heuristic from regression literature, I did not source it here]:
- fewer than about 10 minority-class events per feature: with d=7 that is roughly 70 failures-or-successes per arm; tens of total outcomes will not support it;
- class one-hot already explains it (leave-one-out log-loss of contextual model not better than hierarchical Beta by >= 0.01);
- check absent on most tasks (labels too sparse);
- model_id changed recently (parameters stale; ParetoBandit needed ~142 steps to integrate a new arm even with 100s-per-run data, so tens of outcomes is far below).
Decision rule: run both in shadow; promote contextual only if leave-one-out log-loss beats the Beta chain over at least 100 rows AND the improvement CI excludes 0. Otherwise keep Beta. Published learned routers also degrade out of distribution (secondary, unverified), a further reason for caution.

### 2.6 Offline evaluation (6)
Log per decision (ledger JSONL): task_id, class, family, features, model_id for all arms, eligible set, chosen arm, propensity pi_log(a|x) (the probability Thompson assigned, estimate by 200 repeated draws; 1.0 if forced baseline), s, c_norm, rework count, timestamp.
Estimators:
- Simple replay (Li 2011) is valid only on uniformly random logs; ours are not, so use it only for a small randomised audit slice (e.g. 10% of eligible tasks chosen uniformly among eligible arms). It keeps only ~1/K of rows.
- IPS: V_hat(pi) = (1/n) sum w_i * r_i, w_i = pi(a_i|x_i)/pi_log(a_i|x_i); use self-normalised version (sum w r / sum w) and clip w <= 10.
- Direct method: evaluate the hierarchical posterior's predicted p on held-out rows (leave-one-out log-loss, Brier).
- Report ESS = (sum w)^2 / sum w^2.
Minimum before trusting [DESIGN, estimates]: per (family, arm) pair compared, ESS >= 30 and >= 10 logged runs of each arm; bootstrap 1000 resamples for a 90% interval; act only if the interval for "cheaper-vs-baseline success difference" lies above -0.10 (or whatever owner tolerance). Below that, the log is for display only. Caveat: since production mostly plays the baseline, cheap-arm propensities are small and ESS grows slowly; the randomised audit slice is what buys valid offline evaluation.

### 2.7 Confidence reporting to the owner (7)
Compute quantiles by sampling 2000 betavariate draws. Per class and recommendation, print one line, e.g.:
  "Small docs edits: the cheaper model passed its checks 8 of 9 times. We are 90% sure it succeeds at least 62% of the time. Confidence: MEDIUM. Estimated saving vs always using the stronger model: 30-45% on these tasks (estimate)."
Labels [DESIGN]: n_eff < 5 -> "Too early, using the safe default"; 5-14 -> LOW; 15-29 with q10 within 0.1 of baseline -> MEDIUM; >=30 and offline ESS >= 30 -> HIGH. Always state the sample count, the date range, whether the model version changed since, and what was NOT tested (no-check or high-risk tasks are never experimented on). Report savings as range from bootstrap, labelled "estimate", never as a point figure.

## 3. Pseudocode (stdlib only)

```python
import random, math

K_G, K_F, GAMMA, NCAP = 4.0, 6.0, 0.97, 40.0

def upd(st, s):                      # st = [S, N]
    st[0] = GAMMA*st[0] + s; st[1] = GAMMA*st[1] + 1.0
    if st[1] > NCAP: k = NCAP/st[1]; st[0] *= k; st[1] = NCAP

def posterior(arm, cls, fam, T):     # T[level][arm] -> [S,N]
    Sg, Ng = T['g'][arm]; pg = (Sg + 1)/(Ng + 2)
    Sf, Nf = T['f'][fam][arm]; pf = (Sf + K_G*pg)/(Nf + K_G)
    Sc, Nc = T['c'][cls][arm]
    return Sc + K_F*pf, (Nc - Sc) + K_F*(1 - pf)

def choose(task, arms, T, cost, V=3.0):
    allowed = [task.baseline] + [a for a in arms if cheaper(a, task.baseline) and safe(task)]
    if not budget_ok(): allowed = [task.baseline]
    best, bs = None, -1e9
    for a in allowed:
        al, be = posterior(a, task.cls, task.fam, T)
        p = random.betavariate(max(al, 1e-3), max(be, 1e-3))
        score = p*V - (cost[a] + (1-p)*cost[escalate(a)])
        if score > bs: best, bs = a, score
    if cheaper(best, task.baseline) and not exploit_ok(best, task, T):
        if not explore_slot(): best = task.baseline        # 1-in-4 cap
    return best          # log propensity via repeated draws

def on_model_change(arm, T, n0=4.0):
    for lvl in all_stat_cells(T, arm):
        if lvl[1] > n0: k = n0/lvl[1]; lvl[0] *= k; lvl[1] *= k
    probation[arm] = 5

def q(al, be, qt=0.10, n=2000):
    xs = sorted(random.betavariate(al, be) for _ in range(n)); return xs[int(qt*n)]
```

## 4. What does not transfer to multi-turn agent sessions
- Published routers pick a model per single query with a judged answer; agent sessions are sequences where cache writes (36% of cost) and cached reads depend on keeping the same model/context; switching mid-session likely forfeits cache [inference from the cost profile in context; not measured]. Route per task/sub-agent boundary, not per turn.
- Reward is delayed and noisy (rework, owner revert), and attribution to the routing choice vs the prompt/plan is confounded.
- Savings figures are vs random or always-strong baselines on benchmark prompts; ours is vs the current rules.
- Learned difficulty predictors reportedly fail on agentic coding (secondary, unverified); verifier-based cascades are the safer analogue.
- Sub-agents start cold (context file), so tier cost for helpers includes context rebuilding that single-query papers ignore.
- Judge/verifier error degrades cascades (RouterBench); our checks must be trusted tests, not model self-assessment.

## 5. Classification
ADOPT NOW: hierarchical discounted Beta TS with cost-aware score; two-quantity reward; model_id keyed stats with shrink-on-change; safe set + exploration budget; propensity logging; Beta-quantile confidence lines.
TRY BEHIND A MEASUREMENT: contextual LinUCB/logistic in shadow (gate in 2.5); 10% randomised audit slice for valid replay; drift alarm; empirical-Bayes K fitting.
AVOID: HF pretrained routers (RouteLLM, Arch-Router) as runtime components (no installs, chat-preference training, OOD risk); exploring on high-risk or no-check tasks; mixing tokens into the Bernoulli reward; plain replay on non-uniform logs; reporting RouteLLM/FrugalGPT headline savings to the owner as expected savings.

## 6. Unknowns and what I could not reach
- Did not read full paper tables (RouteLLM, Hybrid LLM, FrugalGPT, ParetoBandit, OrcaRouter, Poon): only abstracts/search summaries. No Reddit/HN/Threads/X threads located; practitioner claims are vendor blogs.
- All constants (gamma 0.97, K_G 4, K_F 6, V 3, 5% budget, ESS 30, EPV rule) are untested defaults; tune on the ledger.
- Fractional Beta update is a heuristic without guarantee.
- Whether switching model forfeits cache within a session is inferred, not tested.
