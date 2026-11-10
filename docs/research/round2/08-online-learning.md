# 08 Online learning inside the brain's scripts (applied-statistics viewpoint)

Date: 2026-11-10. Author: research agent 08.

## 0. Answer and confidence

Short answer: yes, put a small set of classical online estimators in `engine/` (stdlib only). Ranked by value/complexity (section 12), build in this order: (4) estimate calibration, (5) drift/anomaly charts, (2) memory credit + lower-confidence-bound ranking, (10f) gate-flakiness score, (10c) hierarchical + discounted Thompson, (9) usage-based forgetting, (7) capture-recapture review stopping. Then, only behind a shadow-mode measurement: (1) learned sizing, (3) learned retrieval weights, (6) window pacing. (8) is mostly already built.

Confidence: HIGH that the estimators below are statistically sound (standard references, from my own knowledge, not re-fetched). MEDIUM-LOW on their payoff for this brain, because the data volume is small (my estimate: tens of sessions per month, not thousands; so every method needs shrinkage to a prior and a minimum-data gate). I found NO published evidence that these methods work on the specific signals of a Claude Code harness (tokens per task, first-pass rate); the transfer is by analogy.

## 1. Evidence status (what I read vs. what is from memory)

Read via search results only (snippets, pages not opened; treat as SECONDARY):
- Real-Time Detection and Repair of LLM Agent Failures, uses CUSUM over per-channel surprise: https://arxiv.org/pdf/2608.02464
- One-sided Page CUSUM on token entropy: https://arxiv.org/pdf/2605.19966
- Search found NO source validating Page-Hinkley/CUSUM on token cost or pass-rate of coding agents. The caveat found: PH has no alert state, both need tuning; in a wireless benchmark they were not top performers (https://arxiv.org/pdf/2508.00042).
- MeridianDB retrieval docs apply Wilson score to memory success/failure counts and note the shared-outcome (zero-sum) problem without solving it: https://araldhafeeri.github.io/MeridianDB/retrieval
- Wilson lower bound for ranking few observations: https://docs.rs/crate/smelt-memory/0.1.0/source/src/utility/wilson.rs
- Forgetting curves in agent memory: FSFM https://arxiv.org/pdf/2604.20300 (exponential R=e^(-lambda t); authors report value-based retention beats passive Ebbinghaus decay for high-value memories), FadeMem https://arxiv.org/html/2601.18642v1 (reports 45% storage reduction on its benchmarks), engramai code doc (R=e^(-t/S), S grows on successful retrieval) https://docs.rs/crate/engramai/latest/source/src/models/ebbinghaus.rs
- Not searched / not reached: Hugging Face papers and blog specifically, Reddit/HN/X threads. I did not search them in this pass; nothing here should be read as HF-validated.

From memory, standard references (not fetched, mark [from memory]): Wilson 1927 interval; Page 1954 CUSUM; Hinkley 1971 / Page-Hinkley; Roberts 1959 EWMA chart; Lincoln-Petersen / Chapman 1951 / Chao 1984 estimators; McCallum & Nigam 1998 multinomial NB for text; Thompson 1933 sampling and discounted variants (Garivier & Moulines 2011); Vovk conformal prediction; Ebbinghaus 1885.

Local code facts (read):
- `engine/items.py:35-40` `confidence()` is the Beta MEAN with trust-dependent prior; it is not a lower bound, and it is not used with exposure-conditioning.
- `engine/recall.py:127-132` recency is linear decay from 1.0 (30 d) to a floor of 0.7 (365 d): effectively a fixed schedule, no usage-based stability.
- `engine/learn.py:176-186` already has word-set Jaccard and a polarity regex (`negative`) for duplicate/conflict detection.
- `engine/route.py:407` `cheap_first(p_cheap,...)` and Thompson stats in `stats/` exist.
- Counters in items are validated as non-negative ints (`items.py:73-75`), so fractional credit must live in a separate stats file (see 3).

## 2. Cross-cutting design rules (apply to every learner)

1. Advice, not authority: every learner outputs a number or a hint consumed by a script or shown on `brain boot`; none edits CLAUDE.md, rules, or owner files. Rule 8 of CLAUDE.md holds: parameters are written only by `BRAIN close` / `BRAIN learn` into `stats/*.json`.
2. Shadow first: a learner logs what it WOULD have decided next to what the rule decided, for N sessions. It goes active only when its prequential score beats the rule baseline (test-then-train, section 13).
3. Prior = current behaviour. Every learner starts as the existing rule/hand-set value and moves away only with evidence (Bayesian shrinkage). Parameter moves are clipped (e.g. weight within 0.5x..2x of the hand value).
4. Minimum data gates, per learner, below. Below the gate: output equals prior.
5. Deterministic and reproducible: stats files carry `n`, `version`, `updated`; seeds fixed for any sampling; one `stats/learner_state.json` per learner with an `enabled` flag as kill switch; `BRAIN doctor` verifies it parses.
6. Update from ledger rows only (tokens, gates, rework, corrections), never from text the model produced about itself or from web content (prompt-injection and self-grading risk).
7. Drift (5) can reset or down-weight any learner's history: it is the safety net.

## 3. (2) Memory item credit assignment + lower-confidence ranking

Data: per session, set R of recalled items, F subset followed (flag per item), outcome signals: gates passed first time (g), rework count, owner corrections (c), class baseline.
Outcome y in [0,1]: y = 1 if first-pass green and no owner correction, 0 if gate failed after the item was followed or owner corrected; partial (0.5) for green after rework. Define baseline b_class = EW mean of y in that task class (from all sessions).

Key rule (statistical): update ONLY followed items (exposure-conditioned). A recalled-but-ignored item cannot have caused the outcome; it only gets an `ignored` count (used in (3) and (9)). This removes the biggest bias in MeridianDB-style counting.

Shared credit with baseline adjustment (the core, cheap):
```
adv = y - b_class                      # advantage over class baseline, in [-1,1]
w   = 1/|F|                            # equal share; use 1/sqrt|F| to be less dilutive
for i in F:
    if adv > 0: a_i += w*adv           # fractional "helpful"
    else:       b_i += w*(-adv)        # fractional "harmful"
    n_i += 1
```
Store floats in `stats/credit.json` {id: [a, b, n, ignored]}; the pipeline turns them into integer `helpful`/`harmful` deltas only when a whole unit has accrued (delta ops only, per existing pipeline).

Score for recall ranking (lower confidence bound on Beta(a0+a, b0+b), a0,b0 from the trust prior at `items.py` PRIOR):
```
A=a0+a; B=b0+b; m=A/(A+B); v=A*B/((A+B)**2*(A+B+1))
lcb = m - 1.28*sqrt(v)                 # ~10th percentile (normal approx; no scipy needed)
```
Recall multiplies relevance by a factor f = clip(0.7 + 0.6*lcb, 0.7, 1.15) so evidence moves rank by at most about +-30%. Exploration: reserve one of k slots for a Thompson draw `random.betavariate(A,B)` among probation or low-n items so new lessons get tested (cold-start fix).

Alternatives considered:
- Leave-one-out via regression: y ~ intercept_class + sum_i beta_i * followed_i, online ridge SGD: `beta_i += eta*(y - yhat)*followed_i - eta*lam*beta_i`. It handles co-occurrence confounding (two items always recalled together) properly but needs roughly 10x the sessions; ESTIMATE: not before ~150 labelled sessions. Put behind a measurement.
- Shapley-lite: with |F| <= 6 exact Shapley needs the counterfactual y for subsets that never occurred; you only observe one subset per session, so it cannot be estimated from logs. REJECT; equal share is the practical Shapley under additivity.

Cold start: trust prior (owner-stated strong, derived weak). Minimum data: rank factor stays 1.0 until n_i >= 3 followed sessions; a demotion PROPOSAL (not action) when upper bound of harm share < 0.5 fails, i.e. n >= 5 and mean(b/(a+b)) - 1.28*sd > 0.5. Proposal goes through validate/promote.
Test: simulate sessions in `tests/` with known true item effects (e.g. 20 items, 2 harmful, random sets of 4 recalled, 70% followed); assert the harmful ones are ranked bottom by 60 sessions; and a confounded pair test showing the limit. Replay on real ledger: Spearman between lcb at time t and followed-success rate afterwards.
Failure modes: confounding by task difficulty (mitigated by class baseline, not removed); Goodhart (a trivially followed item looks good); "followed" detection noise (unknown how it's logged: OPEN QUESTION); a sticky pair; owner-stated items must never be demoted by this (excluded, see section 14).

## 4. (4) Estimate calibration (tokens and minutes)

Data: per finished task: estimated tokens/minutes e, actual x, class k, model, role.
Work in logs: r = ln(x/e). Heavy-tailed ratios are lognormal-ish [estimate; check on data].

Update (EW mean/variance, half-life H=20 tasks, alpha = 1-2^(-1/H)):
```
d = r - mu;  mu += alpha*d;  var = (1-alpha)*(var + alpha*d*d)
```
Partial pooling to avoid per-class starvation:
```
mu_k_hat = (n_k*mu_k + K*mu_global)/(n_k+K),  K=5   # same for var
```
Quantiles: conformal, distribution-free. Keep last 50 ratios per class sorted; for coverage 1-a take the ceil((n+1)(1-a))-th smallest as q. Median for the schedule, q80 for budgets/stop-loss. Estimate to use: e_cal = e*exp(q).
Decision driven: `schedule.py` durations (median), `budget` caps and "ask before exceeding" (q80), knapsack costs in `route.assign`.
Cold start: ratio 1.0 with a wide prior (q80 = 1.5x, a deliberately pessimistic factor [my estimate]). Minimum data: act (use class estimate) at n_k >= 5; otherwise pooled global at n >= 5; otherwise prior.
Test: prequential coverage: the fraction of tasks with actual <= q80 estimate must be 0.80 +- 0.10 once n>=30; pinball loss vs uncalibrated. Unit test with synthetic lognormal and a regime shift.
Failure: anchoring (agents lower their effort to hit the estimate; the estimate becomes self-fulfilling) so also track the correlation of e with x; regime change (model update) handled by (5) reset of n_k to min(n_k,5); outliers from aborted sessions (exclude rows with `aborted`); estimated tokens measured by cost-weighted units, not raw, since output is ~57% of cost (context file).

## 5. (5) Anomaly and drift detection

Streams: ln(tokens per task) per class (and output tokens alone), first-pass indicator, rework count, minutes. Reference: first 15 observations after a reset, robust mu0 = median, sigma0 = 1.4826*MAD.

EWMA (continuous): `z = lam*x + (1-lam)*z`, lam=0.2; alarm if |z-mu0| > L*sigma0*sqrt(lam/(2-lam)), L=3 (in-control average run length about 370 for normal data [from memory]).
CUSUM (binary first-pass failure, p0 baseline, detect rise to p1 = p0+0.2): 
```
k = (p1-p0)/(2*ln? ) -> use simple form: s = max(0, s + (fail - (p0 + 0.1)));  alarm if s > h, h=2.5
```
Page-Hinkley (mean shift in tokens): 
```
mbar += (x-mbar)/t;  m += x - mbar - delta;  M = min(M,m);  alarm if m - M > lambda
delta = 0.5*sigma0, lambda = 5*sigma0   # tune on replay
```
Decision driven: alarms never change code or memory; they (a) print one line in `brain boot` ("drift: tokens/task, class X, +34% since session N, model id changed at N" when the transcript model string changed: this attribution is deterministic), (b) discount old posterior mass in Thompson stats (gamma 0.9 on that model/class cell once), (c) cap n_k in calibration, (d) bad-lesson check: compare first-pass rate in the 10 tasks before vs after each promotion (sign test on windows) and propose demotion of the item promoted just before the shift. Require two consecutive alarms or alarm + a second chart to reduce false positives given about 20 classes x 3 charts (multiplicity: expect a false alarm about every 370/60 ~ 6 observations if uncorrected [my arithmetic]; so use the confirmation rule and only chart classes with n>=15).
Cold start: no charts until 15 observations of a class. Test: replay with injected +40% shift at a known index: detection delay under 8 tasks and zero alarms in 200 null draws at 3 seeds. Failure: seasonality by project type mixed in one class; slow drift evades CUSUM (use PH + EWMA); self-poisoning if the baseline updates during the shift (freeze the baseline while in alarm). Evidence base: only analogical (arXiv 2608.02464 uses CUSUM on agent surprise; no coding-agent token study found).

## 6. (1) Learned request sizing (behind a measurement)

Data: first user sentence text (owner request only), rule output (tier, family), labels: the final tier actually needed. Strong labels: an escalation (rule said 1, work needed 2), an owner correction ("just answer", "do the whole thing"). Weak label: no escalation/correction (weight 0.3, to avoid learning the rules' own mistakes as truth).

Model: online multinomial NB with Laplace smoothing alpha=0.5 over word unigrams (+ bigrams for negations), counts n[c][w], N[c], class counts. Posterior with rules as an informative prior and damped likelihood:
```
log P(c|x) = log pi_c + (1/ sqrt(T)) * sum_t log((n[c][w_t]+a)/(N[c]+a*V))      # T = #tokens, damping stops long texts overpowering the prior
pi_c = 0.7 if c == rule_tier else 0.1      # rules as prior
```
Decision (hint only): if argmax != rule_tier AND P >= 0.85 AND labelled strong n >= 30 AND |argmax - rule| == 1, show "sizing hint". Guards (hard, in code): a learned hint can NEVER move a tier-0 request (question) to tier >= 2; recommended stricter: it can never raise tier-0 at all; a downgrade from 2/3 is allowed only as a hint "consider tier 1" since over-process is the main waste. Rules remain the authority; the learner gets promoted to auto only after shadow evidence.
Cold start: pi is 0.7/0.1 and counts empty, so output equals the rules. Minimum data: 30 strong labels, with at least 5 in each class involved in the change [my numbers, tunable].
Test: prequential accuracy and an asymmetric cost (under-size costs 3, oversize costs 1 [my assumption]) vs rule-only; ship only if cost is lower on the last 40% of data by a paired sign test p<0.1. Also unit tests of the guard with adversarial inputs.
Failure: label noise from owner mood; owner uses dictation/typos (use the existing `_fold`/stem from route.py); tiny data (ESTIMATE: 30 strong labels may take months), so expect it to stay dormant; vocabulary drift when projects change; memorising project-specific words (keep per-family counts or hash features). Logistic regression is not better here: NB converges with far fewer samples (Ng & Jordan 2001 [from memory]).

## 7. (3) Retrieval learning from usage (behind a measurement)

Data: per recall impression: candidate features f (BM25 per field text/tags/class, scope match, importance, recency, lcb), shown/not shown, followed/not followed. Labels only for SHOWN items (y=1 followed, 0 shown-not-followed). Not-shown items are unlabelled (selection bias).
Update: online logistic regression with L2 pull toward the hand weights w0 (the prior):
```
p = sigmoid(w.f);  w -= eta*((p - y)*f*ipw + lam*(w - w0));   eta=0.05, lam=1.0
ipw = 1/pi_i   # propensity of being shown: 1 for greedy slots, 1/p_explore for the exploration slot; clip at 5
w = clip(w, 0.5*w0, 2*w0)
```
Decision: the relevance combination weights in `recall.pack`. Cold start: w0. Minimum: 100 labelled impressions and >= 20 exploration impressions. Test: time-split replay; compare followed@k and NDCG@k of new weights vs w0 on the held-out final 20% (counterfactual via IPW); require improvement and non-regression in token cost per recall. Failure: feedback loop (popular items shown, so followed, so more popular) mitigated by the exploration slot and clipping; "followed" is a noisy label (a model may follow a lesson without being credited, or the reverse); small value when the corpus is small (BM25 over a few hundred items is already near-saturated [estimate]). Prefer the per-item prior from (2) first: it captures most of this signal for a fraction of the complexity.

## 8. (6) Usage-window pacing

Facts: the limit is unpublished (context file). I did not verify window length or the unit (tokens vs cost-weighted) [unverified]. Also other usage (the owner's claude.ai chat, other tools) may count against the same pool and is invisible to the ledger: the biggest threat to validity.
Data: per window, cumulative cost-equivalent units U(t) from ledger; stop events (rate-limit message) with U at stop.
Estimator (censored data): each stop gives an observation L_i ~ U_stop (approximately the limit). Non-stop windows give lower bounds. 
```
L_hat = median(U_stop_i) if n_stops >= 2 else max(U seen in any window) * 1.0   # latter is only a lower bound
rate  = EWMA of units/min over the last 30 min (halflife 15 min)
t_exh = (L_hat - U)/rate
```
Decision: if t_exh < time left in the window, advise shed: lower effort, fewer parallel helpers, defer low-priority streams (schedule to the next window, written to `NEEDS_YOU`-style notes). Cold start: no advice until 1 observed stop; show only "observed max so far". Test: backtest: predicted stop time vs actual stop time error; not testable before several stops exist. Failure: limit changes with server load/plan [unverified, plausible]; sessions in parallel; false advice reduces throughput. Keep it informational with a clear label until it has at least 3 stops.

## 9. (7) Review stopping by capture-recapture

Data: defect sets found by two independent review passes (A,B; different model/prompt/lens), deduplicated by a defect key (file+line range+category). n1=|A|, n2=|B|, m=|A∩B|.
Chapman estimator: `N_hat = (n1+1)(n2+1)/(m+1) - 1`; remaining = N_hat - |A∪B|. For k>=3 rounds use Chao lower bound on unseen: `f1*(f1-1)/(2*(f2+1))` where f1,f2 are the number of defects found in exactly 1 and 2 rounds.
Rule: do another round if remaining >= 1 AND expected defect cost*remaining > round cost (tokens from (4)); stop when the last round found zero new defects and remaining < 0.5; hard cap at 3 rounds. If m = 0 the estimate is unbounded: treat as "keep reviewing" (cap applies).
Cold start: fixed rule "two rounds for tier >= 2". Minimum: m >= 2 for the estimator to be used; below that, apply the fixed rule.
Test: simulation with known defect counts and heterogeneous detection probabilities; check the bias; apply on past reviews by hiding round 3 and checking whether the estimate predicted its yield.
Failure: reviewers from one model family are positively correlated, so the estimator UNDERestimates N (a known bias of capture-recapture with heterogeneous catchability, Chao 1984 [from memory]); treat as a lower bound, not a guarantee; diversify lenses. Inspections literature (e.g. Eick et al. 1992; Briand et al.) [from memory, not checked] reports the same estimators for human inspections; not validated for LLM reviewers.

## 10. (8) Duplicate and conflict detection

Already built (`learn.py:176-186`). Improvements, in order of value:
1. Add a containment score `|A∩B|/min(|A|,|B|)` alongside Jaccard (short lesson inside a long one). Duplicate if Jaccard >= 0.6 or containment >= 0.8 on content words (stopwords and polarity words removed).
2. Conflict candidate: same scope/class, shared-core >= 0.5, opposite polarity (existing regex) -> never auto-resolve; route to curate with both items' evidence and (2)'s credit (the one with higher lcb and more recent evidence supersedes) as a suggested winner.
3. MinHash/LSH: NOT needed below about 5000 items (pairwise Jaccard on sets of 10-30 words is trivial); only add if the corpus grows. Value of MinHash here is low.
Test: labelled pairs from the existing items; precision >= 0.9 at the chosen threshold. Failure: negation-heavy phrasing ("never X unless Y") breaks polarity; false merges delete nuance, so merges are proposals.

## 11. (9) Forgetting curves and usage-based decay

Replace fixed 90 days / the linear recency floor. Model: retention `R = exp(-t/S)` with t = days since last FOLLOWED use (not last recall), stability S per item:
```
S0 by type (days): lesson 45, fact 120, playbook line 90      # priors [my estimate]; standing/owner-stated: infinite
on followed use after gap g:   S = S * (1 + 0.8*(1 - R_before))  # spaced-repetition effect: bigger gain when it was about to be forgotten; cap 365
on harmful outcome: S = S * 0.5
```
Fit S0 from data: per type, take the gaps between successive followed uses; set S0 such that R(q80 gap)=0.5, i.e. S0 = q80_gap/ln2, needing >= 10 gaps per type; before that use the priors.
Decisions: (a) recall multiplier = 0.7 + 0.3*R (so old items are demoted, not hidden); (b) archive PROPOSAL when R < 0.15 and ignored >= 3 and lcb below the median, through the existing decay delta (`build_decay`); never delete.
Evidence: FSFM https://arxiv.org/pdf/2604.20300 (secondary; exponential retention, with value-based retention reported to beat passive decay for high-value memories), engramai docs.rs (S grows on retrieval). No measurement found for coding agents. Test: replay: archived items must not have been followed within the next 60 days (false-archive rate < 5%). Failure: rare-but-critical items (release procedures used quarterly) look dead: protect by importance=3 and by type, and by `S` growth on each use; seasonal tasks.

## 12. (10) Other learners with real expected value, and the ranking

10a. Gate flakiness (high value, trivial). Per gate command: Beta counts of "failed then passed on rerun with no code change" (flaky) vs "failed and stayed failed". Flaky score = mean of Beta(1+f, 1+s). Decision: rerun once automatically if score >= 0.2 instead of spending a rework cycle; flag gates with score >= 0.5 in boot as "flaky, investigate". Needs the runner to log code hash per run. Failure: masking real intermittent bugs, so the flag is reported not silenced. Source: standard flaky-test practice [from memory].
10b. Hierarchical and discounted Thompson (improves the existing bandit). Cell prior = the parent posterior (class prior = family posterior = global), `Beta(a0,b0)=Beta(K*p_parent+1, K*(1-p_parent)+1)`, K=4: fixes cold start for new task classes. Discount `a,b *= 0.98` per observation (Garivier & Moulines [from memory]) so a model update washes out. Reward = pass-first-time minus lambda*normalised cost, or a constrained form (pass probability per unit cost), consistent with `cheap_first`. Test: simulated non-stationary bandit regret vs the plain version.
10c. File co-change prior for orientation (medium). From transcripts, count files read/edited per task class and co-edited pairs; boot lists the three most likely files. Saves exploratory reads (read tokens). Needs measurement: bytes read before first edit with/without.
10d. Verbosity monitor (medium): per role output tokens quantiles by class, since output is about 57% of cost (context file); a task above q90 flagged post hoc to `learn note` as a candidate lesson ("this class over-produces"). Pure (4)+(5) reuse.
10e. Source yield for online searching (low): Beta of "search produced an accepted item" per source domain to order sources. Only worthwhile once the search routine exists.

Ranking (value/complexity; value = expected saved tokens/rework, complexity = code + data need):
1. (4) Calibration: high / low
2. (5) Drift charts + bad-lesson check: high / low; also protects the rest
3. (2) Credit assignment + LCB + exploration slot: high / low-medium
4. (10a) Gate flakiness: medium-high / trivial
5. (10b) Hierarchical + discounted Thompson: medium-high / low
6. (9) Usage-based forgetting: medium / low
7. (7) Capture-recapture: medium / low (only for tier >= 2)
8. (10d) Verbosity monitor: medium / trivial after (4)(5)
9. (1) Learned sizing: medium / medium; data-starved, guard-heavy
10. (10c) File co-change: medium / medium
11. (3) Learned retrieval weights: low-medium / medium-high; do (2) first
12. (6) Window pacing: medium if limits bind, but unverifiable inputs / medium
13. (8) MinHash: low; containment+polarity tweak only
14. (10e) source yield: low

## 13. Testing protocol common to all

- Prequential (test-then-train) evaluation on the ledger replay: for each session in time order, predict with the current state, score, then update. Report vs the rule baseline.
- Synthetic ground-truth simulators in `tests/test_learners.py` (known effects, known shifts) with fixed seeds; pass/fail thresholds written above.
- Shadow log `stats/shadow.jsonl`: learner suggestion vs rule decision; promotion to active requires the improvement criterion in each section and is itself a `BRAIN learn` delta.
- `BRAIN doctor` checks: files parse, n monotone, parameters within clips, kill switches readable.

## 14. What must NOT be learned automatically, and why

1. Owner-stated standing rules and preferences: owner words are the ground truth; a statistical score may only surface a conflict, never demote or edit them (the credit signal is confounded and Goodhart-prone).
2. The tier guard, gate definitions, release-on-green rule, secrets handling, path guards: safety invariants. A learner that can relax them can be gamed by noise or by injected text. They change only by human-reviewed commits.
3. Pass/fail criteria and thresholds of gates and the definition of done: learning "what counts as passing" from outcomes turns the metric into a target (it would learn to pass, not to be right).
4. Anything labelled by the model's own self-assessment, or derived from web or project text: unverified, injection-prone. Labels come only from ledger facts (gate results, rework, owner correction).
5. Model weights for tier-0 requests (questions): never promote a question to a project; the cost of over-processing is the largest waste.
6. Automatic deletion of memory: archive proposals only; deletion is irreversible and the data is too sparse to be sure.
7. The routing choice for safety-critical or irreversible actions (deploys, deleting data): keep the strongest model by rule; do not let the bandit explore there.
8. Pacing as a hard cutoff: the limit is unverified and shared with other usage; the learner advises, it does not stop work.
9. Cross-project transfer of project-specific lessons into global scope without evidence from >= 2 projects (the existing `projects` counter); otherwise overfitting to one codebase.

## 15. Open questions

- How is "followed" detected per recalled item today? If it is a model-reported flag, (2) and (3) inherit its bias; a text/diff-based check is better. Not determined from my reading.
- Real session volume: needed to calibrate all minimum-data gates; my gates are estimates.
- Is the rate-limit unit tokens or cost-weighted, and is the window length 5 hours? [unverified; not fetched]
- No HF papers/blog or threads were searched in this pass; a follow-up could look for published evaluations of memory-utility scoring in coding agents.
