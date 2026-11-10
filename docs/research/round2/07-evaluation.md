# 07 Evaluation: proving a Brain change helped, with small n and no API key
Date 2026-11-10. Viewpoint: evaluation scientist. Confidence in the overall design: medium-high. Confidence in any single number below: see labels.

Labels: [SRC] = read in a source (URL given). [SEC] = secondary summary of a source. [EST] = my estimate or computation. [UNV] = unverified. All Python below is stdlib only and was NOT executed (no shell in this session); the lead must run it once before trusting it. Hand-computed numbers are marked [EST] and are checkable.

## 0. Answer (first lines)
Prove a change with a three-tier ladder: (1) free deterministic contract tests that must be 100%; (2) free replay tests on recorded artefacts; (3) a paid 10-task live A/B, run as a PAIRED comparison, judged by an exact sign test on tasks that differ plus a Beta posterior, with a pre-registered metric and a stop rule. With n=10 you can only detect large effects: you need 9 of 10 tasks to favour the change [EST, section 3.1]. Smaller improvements cannot be proven at this budget; the honest verdict is "not shown", and the default is to keep the old version. Confidence: high on the method (textbook statistics plus Anthropic guidance), medium on the cost numbers.

## 1. What the sources say (evidence base)
1. Anthropic, Demystifying evals for AI agents (Jan 2026): start with "20-50 simple tasks drawn from real failures"; prefer code graders, LLM graders where needed, humans sparingly; grade the outcome, not the tool-call path; use partial credit; balance positive and negative cases; run several trials, pass@k vs pass^k (75% per-trial gives ~42% pass^3); a 0% pass rate across many trials usually means a broken task; regression evals sit near 100%, capability evals start low; read transcripts; isolate each trial in a clean environment; an eval fixed from 42% to 95% on CORE-Bench by repairing grading bugs. [SRC] https://anthropic.com/engineering/demystifying-evals-for-ai-agents (fetched in full summary).
2. Miller, Adding Error Bars to Evals (Anthropic, Nov 2024): report standard error of the mean, 95% CI = mean +/- 1.96 SEM; cluster questions that share a source; compare models with PAIRED question-level differences ("free" variance reduction); do power analysis. [SRC] https://arxiv.org/pdf/2411.00640 and https://anthropic.com/research/statistical-approach-to-model-evals (via search snippet, paper not fully read).
3. tau-bench (Yao et al. 2024): pass^k = probability all k trials succeed; gpt-4o-class agents pass^8 below 25% on retail. [SEC from search] https://arxiv.org/abs/2406.12045. Caveat from a commentary: stochastic user simulators mix agent and simulator noise. [SEC]
4. Harness matters: Anthropic found resource configuration alone moved Terminal-Bench 2.0 by about 6 points (p<0.01); 1x-3x settings were within noise (p=0.40); about 6% of tasks failed from pod errors. [SEC] https://www.anthropic.com/engineering/infrastructure-noise (primary page only seen as snippets). A fixed model with a changed harness reportedly moved Terminal-Bench 2 pass@1 from 69.7% to 77.0% (arXiv 2605.23950) [SEC, not opened]; Opus 4.6 58.0% in Claude Code vs 74.7% in another harness [SEC blog, vendor-flavoured]. Counterpoint: one analysis puts the average harness effect near 2% (SWE-bench Lite) and 5% (Terminal-Bench 2.0) [SEC]. Implication for Brain: instructions/routing ARE harness changes, so large effects are plausible, but run-to-run infrastructure noise is also large. Control the environment and repeat.
5. SWE-bench Verified was retired by OpenAI in Feb 2026 for contamination and tests that reject correct solutions (138 audited problems) [SEC] https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/. Lesson: public benchmarks saturate and leak; Brain's own tasks must be private, held out, and their graders audited.
6. LLM judges (Zheng et al., NeurIPS 2023): position bias, verbosity bias, self-enhancement bias; GPT-4 agreed with humans >80% on MT-Bench. [SRC via search] https://arxiv.org/html/2306.05685v4. The 80% is for GPT-4, not judges in general.
7. skill-creator now has Create/Eval/Improve/Benchmark modes with executor, grader, comparator (blind A/B) and analyzer sub-agents, and tracks pass rate, tokens and time; one report shows 100% with skill vs 40% without. [SEC only] https://tessl.io/blog/anthropic-brings-evals-to-skill-creator-heres-why-thats-a-big-deal ; I did not find the primary doc. Reuse its blind-comparator pattern; do not depend on it (cloud sessions load skills only from the repo).
8. Not reached or not searched: METR time-horizon primary page (only summaries: 50% horizon, ~7-month doubling in the original work; the "4 months" later figure is [UNV]); GAIA; promptfoo docs; Hugging Face leaderboards; Reddit/HN threads. Statistics (sign test, Beta-Binomial, SPRT, CUSUM) are textbook and written from knowledge, not fetched.

## 2. Tiers

### Tier 0: deterministic contract tests (cost: zero tokens, seconds; run on every edit)
`bin/brain eval contract`. Must be 100%; any failure blocks promote. Examples: CLAUDE.md under 5 KB; each skill has frontmatter name+description under a size cap; every agent file parses; every route in routing table names an existing agent; every memory JSONL row has evidence and counters; `brain boot` output is at most 15 lines; the output-filtered runner truncates a 10k-line fixture to the cap; no skill references a missing file. These are regression evals in Anthropic's sense (near 100%) [SRC 1].

### Tier 1: replay tests on recorded artefacts (cost: zero tokens)
Record transcripts JSONL and `brain` ledger outputs from past sessions into `evals/replay/`. Replay deterministic components against them: token-ledger parser reproduces recorded totals; memory recall returns the recorded-relevant item in top-k for recorded queries (recall@k, MRR); router rule evaluated on recorded task descriptions reproduces the labelled class; Thompson/knapsack scripts given recorded history pick a feasible allocation under budget. Also "transcript lint": scripted checks over a recorded transcript for process violations (edited before reading, claimed done without a gate run, re-read the same file 3+ times, sub-agent spawned for a tier-0 task). These measure whether the instructions were FOLLOWED, which is a necessary precondition for a benefit. Limit: replay cannot show that new instructions change the model's behaviour; only Tier 2 can.

### Tier 2: small live benchmark (cost: subscription tokens; run only for changes that Tier 0/1 pass)
10 tasks (grow toward 20-30 over time, Anthropic's 20-50 [SRC 1]), each with a scripted grader and a clean fixture directory. Arms: A = current main Brain files, B = candidate. Same model, same effort, fresh sub-agent per run, clean workspace copy, fixed time/step cap. Run k=2 trials per task per arm at first (40 runs for 10 tasks) [EST: at the owner-measured 15x multi-agent cost profile this is the expensive step, so budget it explicitly and run it rarely]. Randomise arm order and task order; interleave arms in time so a model update or load spike hits both (infrastructure noise [SEC 4]). Composition of the 10: 3 code, 2 writing, 2 research, 2 routing, 1 negative (a task where the correct behaviour is to do nothing/ask/refuse extra work), per Anthropic's balanced-set advice [SRC 1].

Seeded-defect tests for reviewers (inside Tier 2): take 6 small code snippets, inject one known bug into 4 and none into 2; the reviewer agent must name the line/category for the 4 and report "no defects" for the 2. Metrics: recall on seeded bugs, false-positive rate on clean files. Rotate the seed set; never show the seeds to whoever edits the reviewer prompt (section 5).

## 3. Formats

### 3.1 Task JSON (`evals/tasks/<id>.json`)
```json
{
 "id": "code-001", "version": 1, "split": "dev|heldout", "class": "code|write|research|route",
 "tier": 1, "prompt": "Fix the failing test in fixtures/code-001 without editing tests/.",
 "fixture": "evals/fixtures/code-001", "caps": {"max_tokens": 60000, "max_seconds": 600},
 "graders": [ ... see below ... ],
 "reference_solution": "evals/ref/code-001.patch", "notes": "source: real failure 2026-10-14"
}
```
Grader types (all stdlib, run on the recorded artefact; each returns score 0..1 and a reason):
- `cmd`: run a command in the workspace, pass if exit code 0 (unit tests).
- `file_contains` / `file_absent` / `regex`: string checks.
- `diff_scope`: files changed must be inside an allowed list; line count under N (catches over-engineering).
- `count_max`: transcript metrics (tool calls, tokens, re-reads) must be under a bound.
- `judge`: rubric for the LLM-judge sub-agent (only where nothing scripted works).
Task score = weighted mean of graders; "pass" = all `required` graders pass. Record both; primary metric is pass (binary) to keep the sign test clean, secondary is score and tokens.

Code task:
```json
{"id":"code-001","class":"code","graders":[
 {"type":"cmd","cmd":"python -m unittest discover -s tests","required":true,"weight":3},
 {"type":"diff_scope","allow":["src/**"],"max_lines":40,"required":true,"weight":1},
 {"type":"file_absent","path":"tests/test_*.py.bak","weight":0.5},
 {"type":"count_max","metric":"total_tokens","max":60000,"weight":1}]}
```
Writing task (release notes from a fixed changelog):
```json
{"id":"write-001","class":"write","graders":[
 {"type":"regex","pattern":"(?i)breaking change","required":true,"weight":1},
 {"type":"count_max","metric":"words","max":180,"required":true,"weight":1},
 {"type":"regex_absent","pattern":"(?i)as an ai|delve","weight":0.5},
 {"type":"fact_check","facts":["v2.3.0","drops Python 3.8","fixes #412"],"required":true,"weight":2},
 {"type":"judge","rubric":["Is every claim traceable to the changelog? (yes/no/unknown)","Would a non-technical owner understand the first sentence? (yes/no/unknown)"],"weight":1}]}
```
Research task (answer with sources from a frozen corpus so it is reproducible and offline):
```json
{"id":"res-001","class":"research","fixture":"evals/corpus/res-001/","graders":[
 {"type":"answer_equals","expected_any":["4096","4,096"],"required":true,"weight":3},
 {"type":"cites","must_cite_any":["corpus/res-001/spec.md"],"required":true,"weight":2},
 {"type":"no_uncited_numbers","weight":1},
 {"type":"count_max","metric":"files_read","max":6,"weight":1}]}
```
Routing decision task (no model run needed for the deterministic part; the live part asks a lead to route):
```json
{"id":"route-001","class":"route","prompt":"Rename a variable across 3 files.",
 "expected":{"tier":1,"model_max":"haiku","spawn_agents":0,"effort_max":"low"},
 "graders":[{"type":"route_match","fields":["tier","spawn_agents"],"required":true,"weight":2},
            {"type":"route_cost_le","model_max":"haiku","weight":1}]}
```
Grade routing on cost-feasible AND correct, not on exact path [SRC 1: outcome not path]. Include both over- and under-spend cases so the router is not tuned only to be cheaper.

### 3.2 Result JSON (`evals/runs/<run_id>.jsonl`, one row per trial)
`{"run":"2026-11-10-a","task":"code-001","arm":"A|B","trial":1,"pass":1,"score":0.92,"tokens":41200,"seconds":212,"model":"sonnet-5.5","brain_sha":"abc123","grader_errors":[]}`
Rule: a trial with a nonempty `grader_errors` or an infrastructure failure is rerun, not counted as a failure, and the rerun is logged (flaky-eval handling; Anthropic reports ~6% infra-error rates swamped some results [SEC 4]).

### 3.3 Pre-registration file (`evals/prereg/<change_id>.json`), committed BEFORE any Tier 2 run
```json
{"change":"skill:review v3","hypothesis":"B has higher pass rate than A on review tasks",
 "primary_metric":"pass","secondary":["tokens","seconds"],"tasks":["code-001","..."],"split":"heldout",
 "k_trials":2,"test":"paired sign test one-sided alpha=0.05 on discordant tasks",
 "decision":"ship if exact p<=0.05 AND tokens(B)<=1.10*tokens(A); revert if posterior P(B worse)>=0.80; else keep A",
 "n_max_tasks":10,"stop_rule":"SPRT section 4.3","date":"2026-11-10"}
```

## 4. Statistics (stdlib)

Unit of analysis = the TASK (not the trial). Per task per arm: s = (passes)/k. Pair task i: d_i = sB - sA. Win if d>0, loss if d<0, tie if 0. Trials of one task are not independent samples; averaging them first avoids inflated n (clustering point, [SRC 2]).

### 4.1 Paired exact sign test (primary)
Let b = wins, c = losses, m = b + c (ties dropped). H0: P(win)=0.5. One-sided p = P(X>=b), X~Binomial(m, 0.5) = (sum_{j=b..m} C(m,j)) / 2^m.
```python
from math import comb
def sign_p(b, c):
    m = b + c
    return sum(comb(m, j) for j in range(b, m+1)) / 2**m if m else 1.0
```
Hand-computed critical values at one-sided alpha 0.05 [EST]:
- m=8: need 7 wins (p=9/256=0.035); 6 wins gives 37/256=0.145.
- m=10: need 9 wins (p=11/1024=0.0107); 8 wins gives 56/1024=0.0547, just fails; 10/10 p=0.00098.
- m=20: need 15 wins (p=21700/1048576=0.0207); 14 wins p=0.0577 fails.
- m=30: need 20 wins (p~0.049, standard binomial table value, from memory [UNV-ish]).
Minimum detectable effect (MDE), 80% power-ish [EST]: with m=10 and a true win share among differing tasks of 0.90, P(X>=9)=10(.9^9)(.1)+.9^10=0.736; so even a strong effect has only ~74% power at m=10. At m=30, true share 0.75: normal approximation with continuity gives power ~0.90 [EST, approximate]. Practical reading: n=8-10 detects only "nearly all tasks improve"; n=30 detects "about 3 of 4 differing tasks improve". Ties cost power, so choose tasks that are hard enough to discriminate (not saturated, Anthropic's saturation warning [SRC 1]); a task where both arms always pass or both always fail is wasted.
Two-sided harm check: swap b and c and compute the same p to ask "is B significantly worse".

### 4.2 Beta-Binomial comparison with decision rule
Model theta = P(B wins | the task differs). Prior Beta(1,1) (or Beta(2,2) to be sceptical). Posterior Beta(1+b, 1+c). Exact P(theta>0.5), using the identity I_x(a,b)=P(Bin(a+b-1,x)>=a), gives P(theta>0.5) = P(Bin(b+c+1, 0.5) <= b). No sampling needed:
```python
from math import comb
def p_better(b, c, a0=1, b0=1):          # integer priors only
    n = (b + a0) + (c + b0) - 1           # trials
    k = b + a0                            # need Bin(n,.5) >= k  -> that is P(theta<.5)
    p_worse = sum(comb(n, j) for j in range(k, n+1)) / 2**n   # P(theta<0.5)... see note
    return 1 - p_worse
```
Note: I_0.5(a,b)=P(theta<0.5)=P(Bin(a+b-1,0.5)>=a); the function above returns P(theta>=0.5). Check by hand: b=9,c=1 gives a=10,b=2, n=11, P(Bin(11,.5)>=10)=12/2048 so P(better)=0.9941 [EST]. Test this before use.
For unpaired absolute rates (pass rate of an arm, or routing accuracy) use the Monte Carlo form: draw 20000 `random.betavariate` samples per arm and report the mean of (pB>pA) and the 2.5/97.5 percentiles of pB-pA.
Decision rule (pre-registered; thresholds are my choice [EST], tune only on past data, never on the run in question):
- SHIP if sign-test p<=0.05 AND P(better)>=0.95 AND cost guardrail holds (tokens B <= 1.10 x A, median per-task).
- REVERT/REJECT if P(worse)=1-P(better)>=0.80 (asymmetric on purpose: harm is cheaper to act on than benefit is to prove).
- Otherwise KEEP A ("not shown"). Never "ship because it looks good".
Dependence: a pair is a Brain task, so a wins/losses count only measures tasks of the kinds sampled; say so in the report.

### 4.3 Sequential stopping rule (SPRT on discordant tasks; avoids spending the full budget when the answer is obvious)
Wald SPRT on each differing task: H0 win prob p0=0.5, H1 p1=0.75; alpha=0.05, beta=0.20.
LLR step: win +ln(p1/p0)=+0.405; loss ln((1-p1)/(1-p0))=ln(0.5)=-0.693.
Upper bound A=ln((1-beta)/alpha)=ln(16)=2.773 -> accept B. Lower bound Bd=ln(beta/(1-alpha))=ln(0.2/0.95)=-1.558 -> accept "no benefit" (keep A) [EST arithmetic].
```python
from math import log
def sprt(outcomes, p0=.5, p1=.75, alpha=.05, beta=.2, n_max=30):
    up, lo = log((1-beta)/alpha), log(beta/(1-alpha))
    w, l, S = log(p1/p0), log((1-p1)/(1-p0)), 0.0
    m = 0
    for o in outcomes:               # +1 win, -1 loss; ties skipped
        m += 1; S += w if o > 0 else l
        if S >= up: return "ship", m
        if S <= lo: return "keep_A", m
        if m >= n_max: break
    return "undecided_use_sign_test", m
```
Consequences [EST]: 4 straight wins give S=1.62, 7 straight wins give 2.84 -> ship at 7 differing tasks (cheaper than the fixed m=8-10 test); 3 losses with no wins gives -2.08 -> stop early, keep A. Wald error guarantees hold only if the stream is not otherwise peeked at and the tasks are fixed and ordered by a pre-set shuffle; truncation at n_max slightly changes them, so at truncation fall back to the fixed sign test. Use the SPRT for the step "do I run more tasks", not to override section 4.2 guardrails. mSPRT or Bayesian monitoring give always-valid p-values for continuous production monitoring; at this scale SPRT is simpler and I did not need them [EST].

### 4.4 Drift detector on tokens per task (after a model update, or silently)
Tokens per task depend on class and size tier, so normalise: z_t = (ln(tokens_t) - mu_c) / sigma_c per class-and-tier cell, with mu and sigma from the first 15 runs of that cell (use median and 1.4826*MAD for robustness). Two-sided CUSUM:
```python
def cusum(zs, k=0.5, h=5.0):
    hi = lo = 0.0
    for t, z in enumerate(zs):
        hi = max(0.0, hi + z - k)
        lo = min(0.0, lo + z + k)
        if hi > h: return ("cost_up", t)
        if lo < -h: return ("cost_down", t)
    return None
def page_hinkley(xs, delta=0.05, lam=8.0):   # alternative for raw drift
    mean = 0.0; cum = 0.0; mn = 0.0
    for t, x in enumerate(xs, 1):
        mean += (x - mean)/t
        cum += x - mean - delta
        mn = min(mn, cum)
        if cum - mn > lam: return t
    return None
```
k=0.5, h=5 detects roughly a 1-sigma shift; textbook average run length under no change is about 465 observations for h=5 and 168 for h=4 [UNV, from memory of Montgomery tables; verify by simulating random.gauss 10^4 times, which takes seconds]. Detection delay for a 1-sigma shift is about 10 tasks [EST]. Alarm action: do not auto-revert; open a `drift` ledger entry with brain_sha, model id, date, and run the Tier 2 A/B of "current vs last known-good" if a model change is suspected. Run the same CUSUM on pass rate of a fixed canary of 3 cheap tasks (binary, z computed against the baseline rate) and on first-attempt gate-pass rate. Models are not versioned by the Brain, so record the model id in every ledger row to make drift attributable.

### 4.5 Intervals and judge calibration
- Per-arm pass rate: Wilson 95% interval (stdlib): centre=(p+z^2/2n)/(1+z^2/n), half=z*sqrt(p(1-p)/n+z^2/4n^2)/(1+z^2/n), z=1.96. At n=10 and 8/10 it is roughly 0.49-0.94 [EST]; show it, it teaches the owner humility.
- Paired mean difference of tokens or score: bootstrap the per-task differences (2000 resamples, `random.choices`, percentile 2.5/97.5). With n<10 bootstrap intervals are too narrow; prefer the sign test and report the interval as indicative [EST].
- Reliability: report pass^k as well as pass@k for tasks where consistency matters; unbiased estimator for n trials, c passes: pass^k = C(c,k)/C(n,k) [SEC 3 gives estimator form].
- LLM judge rules: (a) judge each rubric dimension separately with "unknown" allowed [SRC 1]; (b) pairwise comparisons run twice with positions swapped and count only consistent verdicts, ties otherwise (position bias [SRC 6]); (c) strip or length-normalise, and include "shorter is acceptable" in the rubric (verbosity bias); (d) the judge must not be the same agent instance that produced the output; a different model tier is better but self-enhancement may remain [SRC 6]; (e) calibrate once against 10 outputs hand-labelled by the owner or lead, and record agreement; if below ~80% do not use the judge for decisions [EST threshold, from the 80% human-human level in SRC 6]; (f) the blind comparator pattern in skill-creator is the model [SEC 7]. Judges never decide a ship alone; scripted graders carry the primary metric.

## 5. Rules against self-deception
1. Pre-register the metric, tasks, test and decision rule in `evals/prereg/` before the run; the run script refuses to start without a file whose git timestamp precedes the run.
2. Split tasks into `dev` (used while editing) and `heldout` (used once per candidate for the verdict). Heldout tasks are not shown in the editing agent's context; the edit step and the eval step are different sub-agents. If a heldout task has been used to choose between 3+ candidates, retire it and add new ones from fresh real failures [SRC 5 contamination lesson].
3. No tuning on the test set. A candidate that fails may be revised only against `dev`; each revision is a new candidate with a new prereg and its attempts are counted (multiple comparisons: with c candidates tested at alpha 0.05, the chance of one false ship is about 1-(0.95)^c, 23% at c=5 [EST arithmetic]). Use alpha=0.05/c for c rival candidates on the same heldout set, or require replication on fresh tasks.
4. Always report n: tasks, differing tasks, trials per task, arms, model id, date, brain_sha. A result without n is invalid.
5. Report ties, losses, token and time deltas, and pass^k beside the headline; show the failures with transcript links. Read at least 3 failing transcripts per run to confirm failures are fair and not grader bugs [SRC 1]. A 0% task is treated as broken until proven otherwise.
6. Audit graders: each task has a reference solution that must score 1.0, and a null solution (do nothing) that must score 0 for required graders; run this as a Tier 0 test so a broken grader cannot produce a verdict. Make graders cheat-resistant (tests live outside the agent-writable directory, hash the test files before and after) [SRC 1].
7. Same environment both arms: clean copy, same caps, interleaved order, no memory carry-over between trials; if a run hits infra errors rerun it [SEC 4].
8. Compare to the previous version on the same day, not to a stored number: model drift and load move both arms together, and the paired design cancels it.
9. Negative result is a result: log "not shown" in `evals/ledger.jsonl` so the same idea is not retried blindly; count wins and failures like memory items (helpful/harmful).
10. Cost guard on the eval itself: a Tier 2 run must stay under a preset token budget; if the first 4 tasks already exhaust 50% of it, stop and report.
11. Wins that arrive with higher variance or a tie-heavy outcome are not wins. If more than half the tasks tie, the benchmark is saturated; replace tasks, do not lower the bar.

## 6. Two-line owner report
Template: "Change: <what, in plain words>. Result: on <m> of <n> test tasks it did better and on <l> it did worse; cost <+/-x%> tokens; verdict: <adopted | not adopted | not proven yet>."
Example: "The new review checklist found 9 of 10 planted bugs against 6 of 10 before, and used 4% fewer tokens, so it is adopted. With only 10 tasks a small gain can be luck, so we will re-check it on 10 new tasks next week."
Rules: no p-values for the owner; say "not proven yet" instead of "no effect"; put the full numbers in the ledger.

## 7. Implementation sketch
Files: `bin/brain eval {contract,replay,run,report,drift}`; `evals/tasks/*.json`, `evals/fixtures/`, `evals/prereg/`, `evals/runs/*.jsonl`, `evals/ledger.jsonl`; `brain/stats.py` (sign_p, p_better, sprt, cusum, wilson, bootstrap, pass_hat_k). Live runs: the lead dispatches one sub-agent per (task, arm, trial) using the harness's Task tool with the task prompt only, then `brain eval grade` scores the produced workspace. Wire into the promote step of the existing learning pipeline: a delta to CLAUDE.md, a skill or the routing table is promoted only if Tier 0 is 100%, Tier 1 shows no regression, and (for changes claiming a benefit) Tier 2 verdict is ship. Memory-item edits that are low-risk use Tier 0/1 only plus the existing helpful/harmful counters. Improve existing pieces: Thompson sampling per class should log the posterior and be read through the same Beta machinery (a routing change is then an observational A/B); the token ledger becomes the data source for the section 4.4 detector.

## 8. Classification
ADOPT NOW: Tier 0 contract tests; paired sign test with prereg; n reporting; dev/heldout split; grader audit (reference and null solution); transcript lint on replay; two-line owner report; CUSUM on normalised log tokens (cheap, free).
TRY BEHIND A MEASUREMENT: Tier 2 live A/B with k=2 (measure its token cost on the first run and set a cap); SPRT stopping; LLM judge for writing quality (only after the 10-label calibration shows >=80% agreement); seeded-defect reviewer tests; pass^k reporting.
AVOID: public benchmarks (SWE-bench Verified, etc.) as the Brain's yardstick, because of contamination and cost [SEC 5]; judging with the same agent that wrote the output [SRC 6]; absolute baselines from earlier days; ship-on-trend decisions at n<8; auto-reverting on a single drift alarm; scoring the tool-call path instead of the outcome [SRC 1]; mSPRT/always-valid machinery at this scale (more complexity than data).

## 9. Open questions
- Real per-run token cost of a 10-task, 2-arm, k=2 benchmark in this subscription is unmeasured; measure it first. [EST only]
- Whether sub-agent runs inside Claude Code are isolated enough from each other (shared git state, shared memory files) to count as independent: must be tested with a null A/A comparison (same Brain vs itself, expect about 50% wins and no ship) before trusting any A/B. Do this A/A run first; it also measures run-to-run noise.
- CUSUM average run lengths and the m=30 critical value are from memory; verify by simulation.
- METR, GAIA, promptfoo, HF leaderboards and Reddit/HN threads were not fetched this round; only search summaries were seen. HF was not needed for the statistics.
