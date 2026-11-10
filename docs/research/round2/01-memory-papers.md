# Memory and self-improvement papers -> file-based learning loop (research memo, 2026-11-10)

Viewpoint: memory/self-improvement researcher. Confidence overall: MEDIUM-HIGH on mechanisms (read from HF paper pages / arXiv abstracts via a summarising fetcher, so numbers are second-hand from that fetch; marked where the fetcher flagged inconsistency), MEDIUM on translation (my inference, labelled [inference]).

## 0. Answer in brief

1. The best evidence supports the design already built (itemised bullets with helpful/harmful counters, delta ops, no full rewrites). ACE, ExpeL, Mem0, Zep all converge on it. Keep it.
2. The biggest remaining risks are not in the data structure but in WHO supplies the helpful/harmful signal and WHAT is allowed to be stored. Self-judged signals are the weak point (ACE caveat, ReasoningBank LLM-judge, poisoning paper trust-score failure, misevolution). Credit must come from external checks (gates, tests, owner), not from the model saying "that helped".
3. Self-generated skills/playbooks are NOT reliably helpful: SkillsBench reports curated skills help, self-generated give negligible/negative benefit; SkillEvolBench says raw-trajectory reuse often beats distilled skills. So: promote slowly, keep a link to raw evidence, measure before/after.
4. Retrieve few, not many: ReasoningBank k=1 best (49.7) vs k=4 (44.4); poisoning exposure rises with k. Current 400-token budget is directionally right.
5. Distilled memory from failures helps if labelled as failure/guardrail (ReasoningBank 46.5 -> 49.7 with failures; ReMem robust to failed trajectories while baselines degrade).

## 1. Paper-by-paper (mechanism / gain / what fails / translation)

Sources fetched: HF paper pages via WebFetch, arXiv abstracts; secondary = search snippets.

### ACE - Agentic Context Engineering (HF https://huggingface.co/papers/2510.04618)
- Mechanism: Generator -> Reflector -> Curator; curator emits delta bullets merged by deterministic non-LLM code; each bullet has ID + helpful/harmful counters; grow-and-refine = append, bump counters, dedupe by embedding, lazily or per delta.
- Gain: AppWorld ReAct+ACE 59.4 offline (+17.0 over 42.4 base), 59.5 online; without ground-truth labels 57.2 (+14.8). Ablation: no Reflector + no multi-epoch 55.1; Reflector only 56.8; full 59.4. vs GEPA: -82.3% latency, -75.1% rollouts (AppWorld offline); vs Dynamic Cheatsheet: -91.5% latency, -83.6% token cost (FiNER online).
- Fails: brevity bias (optimizers drop domain heuristics); context collapse: an ~18,000-token context at 66.7 accuracy rewritten to 122 tokens at 57.1, below the 63.7 no-adaptation baseline. Needs a strong Reflector; without reliable feedback (labels/execution outcome) financial tasks degraded and context was polluted.
- Already matched by our pipeline (delta-only, counters). Gaps: dedupe uses Jaccard 0.6 (engine/learn.py:33) not semantic; Reflector quality gate; multi-epoch reflection.

### GEPA (https://huggingface.co/papers/2507.19457)
- Mechanism: reflect on traces in natural language, propose new prompt for one module, accept only if minibatch improves, score on held-out Pareto set, parents sampled proportional to number of instances they win; optional Merge.
- Gain: beats GRPO by ~10% avg (up to 19-20%) with up to 35x fewer rollouts (678 on IFBench); beats MIPROv2 up to ~11%. Always choosing the top candidate trailed by up to 8.17% (avg ~6.4%).
- Fails: instructions only; Merge hurt Qwen3 8B; most rollouts spent on validation scoring.
- Translation: for playbook/CLAUDE.md-line changes, use accept-only-if-improves on a small held-out replay set and keep a Pareto set of variants per task class (not one global best).

### Dynamic Cheatsheet (https://huggingface.co/papers/2504.07952)
- Mechanism: curator rewrites a persistent memory with no ground-truth labels; DC-RS retrieves top-3 similar past pairs.
- Gain: Claude 3.5 Sonnet AIME 2024 23.3 -> 50.0 (DC-Cu); AIME 2025 6.7 -> 36.7; GPQA-Diamond 59.6 -> 68.7. Full-history appending was worse than curated (26.7 vs 50.0). Token cost rose: 370 -> 1,035 (RS) / 1,831 (Cu) per AIME query.
- Fails: weak generators fill memory with flawed strategies; retrieval noise; error amplification in embedding neighbourhoods; lossy rewrites (model abbreviates memory); memory from stronger model can degrade weaker one; order sensitive; GPT-4o-mini fell below baseline on AIME 2024.
- Translation: confirms "never let an LLM rewrite the whole store"; confirms model-tier tagging of items (Haiku/Sonnet-authored notes should not auto-bind Opus and vice versa) [inference].

### ExpeL (https://huggingface.co/papers/2308.10144)
- Mechanism: insight list edited by ADD (importance 2) / EDIT (+1) / UPVOTE (+1) / DOWNVOTE (-1); removed at 0. Insights from success/failure PAIRS on same task.
- Gain/ablation: learned insights beat hand-written; insights extracted from few-shot examples only gave no gain over ReAct; Reflexion-gathered experience beat ReAct-only; adding raw reflections to extraction input HURT (hallucinated reflections); task-similarity retrieval best, random dropped sharply. HotpotQA insights-only 36% vs retrieval-only 31%; ALFWorld 50% vs 55%.
- Translation: our INC_HELPFUL/INC_HARMFUL with demote at x>=3 and x>h (engine/learn.py:480) is ExpeL voting. Add: pair-based extraction (failure + later success on same task class) as the strongest evidence type; do not feed unverified reflections to the extractor.

### Agent Workflow Memory (https://huggingface.co/papers/2409.07429)
- Mechanism: induce reusable workflows (description + steps) from successful trajectories, abstract example-specific values to placeholders.
- Gain: WebArena +12.0 points (51.1% relative), ~2.0 fewer steps/task; most gain in first ~40 queries. Online induction keeps only trajectories an evaluator judged successful.
- Fails: wrong induced workflows hurt; over-reliance (agent follows workflow when a step does not fit); offline + online combined was NOT additive; workflows exposed as callable actions used in only 18.5% of tasks; AWM fell below no-memory on hardest subset (ReasoningBank report: 3.4 vs 10.3).
- Translation: playbook lines need an explicit "applies when / stop and deviate when" field; templates with placeholders.

### ReasoningBank (https://huggingface.co/papers/2509.25140)
- Mechanism: per trajectory, LLM-judge success/failure; up to 3 items (title, one-line description, content); k=1 retrieval; MaTTS (parallel/sequential extra rollouts).
- Gain: WebArena +8.3 (Gemini-2.5-flash 40.5->48.8), +7.2 (pro), +4.6 (Claude-3.7-sonnet 41.7->46.3); SWE-Bench-Verified 34.2->38.8 (Flash), 54.0->57.4 (Pro); failures included 46.5 -> 49.7; steps -1.4.
- Fails: more memories hurt (k=4: 44.4); noisy judge; AWM + failures dropped 44.4 -> 42.2; no pruning.
- Translation: item = {title, one-line description, body}; description is what gets BM25-indexed and shown first; body loads on demand (token saving) [inference].

### Evo-Memory / ExpRAG / ReMem (https://arxiv.org/abs/2511.20857; results from html v2)
- Gain: Claude 3.7 Sonnet multi-turn: baseline 0.24, History 0.49, ExpRAG 0.63, ReMem 0.78 success; ALFWorld steps 22.6 -> 11.5. Gain correlates with within-dataset task similarity (Pearson r=0.717 Gemini, 0.563 Claude). Single-turn gains modest; AIME-24 ReMem 0.13 vs baseline 0.17 (worse).
- Fails: gains small where transferable experience is limited (science reasoning, tool use); "memory remains fragile in stability and procedural reuse". Paper text contains misquoted numbers (fetcher flagged).
- Translation: gate memory use by task-class similarity; for novel task classes inject nothing.

### Experience-following study (https://arxiv.org/abs/2505.16067, ACL 2026; secondary summary only)
- High input similarity -> high output similarity; errors propagate; "misaligned experience replay" (similar input, useless as demonstration). Recommends selective addition (quality-check before storing) and deletion; reported ~10% absolute avg gain over naive growth [from summary, not verified in paper].
- Translation: store-time quality check + delete-on-low-utility; track per-item output-similarity-to-outcome (see #5).

### Mem0 (https://huggingface.co/papers/2504.19413)
- Mechanism: extract candidate facts; retrieve top-10 similar; LLM picks ADD/UPDATE/DELETE/NOOP.
- Gain (self-reported, LLM judge): LOCOMO J 66.88 vs full-context 72.90, OpenAI 52.90, A-Mem 48.38; ~1,764 memory tokens/query vs ~26,000; p95 total latency 1.44s vs 17.1s.
- Translation: NOOP must be a first-class op (we have INC_HELPFUL on near-duplicate, which is similar); add UPDATE-with-supersede, not delete.

### A-MEM (https://huggingface.co/papers/2502.12110)
- Zettelkasten notes: keywords, tags, description, links to top-k neighbours; neighbours' context updated on write ("evolution"). ~1,200 tokens per memory op vs ~16,900 (LoCoMo/MemGPT). Removing links+evolution lowers scores; no error bars; depends on model quality; each write costs several LLM calls.
- Translation: our LINK op exists. Do NOT adopt "evolve neighbours' text on write" (silent rewrites = collapse/poison route) [inference]; only add links and tags.

### Zep/Graphiti (https://huggingface.co/papers/2501.13956)
- Bi-temporal facts: t_valid, t_invalid, t'_created, t'_expired; contradiction invalidates old edge (kept, not deleted). DMR 94.8 vs MemGPT 93.4; LongMemEval +15.2% (4o-mini) / +18.5% (4o), latency -~90% (not like-for-like); single-session-assistant regressed 17.7% (4o).
- Translation: facts (versions, API behaviours, model facts) get valid_from/valid_to/verified_at; supersede instead of delete. Fits "constantly searching for new info about models".

### MemGPT/Letta (secondary: letta.com, search snippets; not fetched)
- Letta claims filesystem storage 74.0% on LoCoMo beating specialised memory tools (vendor claim); sleep-time compute: ~5x less test-time compute at matched accuracy, up to +13%/+18% on modified benchmarks (third-party summary). Direction: git-backed files + bash tools.
- Translation: validates file/git memory; sleep-time = `brain learn` run at session close/idle off the critical path.

### Voyager lineage (https://huggingface.co/papers/2305.16291)
- Skill added only after self-verification; keyed by description embedding; top-5 retrieval; composition. Self-verification removal -73% items; random curriculum -93%; no skill library plateaus.
- Translation: verification-before-store is the most important ingredient. Our "gate/outcome evidence" requirement (EVIDENCE_RE in learn.py:40) is the right shape.

### Skills-specific 2026 evidence
- SkillsBench https://arxiv.org/abs/2602.12670: curated skills 33.9% -> 50.5% pass (+16.6 pp), range +4.1 to +25.7 over 18 configs; <=3 skill modules better than exhaustive bundles. The "self-generated negligible/negative" claim is from a search-snippet summary [secondary; the abstract fetch did not show it].
- SkillEvolBench https://arxiv.org/abs/2605.24117: agents rarely form robust reusable skills; raw-trajectory reuse often beats distilled skills; more skill updates add drift and clutter.
- CoEvoSkills https://arxiv.org/abs/2604.01687: skill generator + co-evolving surrogate verifier beats five baselines on SkillsBench (no effect sizes in abstract). MUSE (2605.27366) reports +15.21 pp with human skills and self-generated exceeding human ceiling on 35 tasks [secondary, preprint].
- Translation: skill/playbook count cap (<=3 loaded per task); verifier must be independent (tests, gates).

### Safety evidence
- MINJA https://arxiv.org/abs/2503.03704: 98.2% injection success, 76.8% attack success via queries alone. EHR follow-up https://arxiv.org/html/2601.05504v1: with 6 prior benign memories ASR dropped to 6.67% (GPT-4o-mini), 0% Llama; retrieving 10 instead of 3 raised ASR 6% -> 38%; model-assigned trust was a confidence filter not a security filter (54 poisoned entries accepted at trust 1.0); pure append-time strictness blocked benign too. Authors suggest external ground-truth checks.
- AgentPoison >80% ASR at <0.1% poison rate: vendor blog only [unverified].
- Misevolution / TAME https://arxiv.org/html/2602.03224: benign task evolution lowered trustworthiness; items carry utility Q (init 0.5, Q <- Q + 0.2*c*(r-Q)) plus trust note; TAME 0.733 vs ReasoningBank 0.587 on GPT-5.2 AIME but lost on Qwen3 Task-Bench (0.606 vs 0.624/0.662).
- "Honest Lying" https://arxiv.org/pdf/2605.29463 [secondary]: with binary pass/fail the reflection can be causally wrong; false "approach X always fails" lessons are self-sealing because the agent never retries X.

### Newest HF items seen (11/2026 daily_papers)
"FlyHash for LLM Agent Memory" (2611.05791, 1 upvote), "Sage-Taiyi metacognitive architecture" (2611.12762, 20 upvotes), EvoMemBench 2605.18421, EvoAgentBench 2607.05202, ContinualSkillBench 2608.03874, Metis 2606.24151 (+20.6% AppWorld, -22.8% cost, text+code dual memory). Only titles/abstract-level seen; not evaluated. The daily_papers query parameter did not filter (returned unfiltered recent list).

## 2. Mapping to the existing code (read from repo)
- Beta-posterior confidence with trust priors: engine/items.py:35-40; priors engine/items.py:24.
- Promotion: candidate -> probation at h>=1 or owner-stated; probation -> active at h>=3 and sessions>=2; demote at harmful>=3 and >helpful: engine/learn.py:480-487.
- Dedup: Jaccard>=0.6 (learn.py:33,515) -> vote instead of ADD; conflicting polarity -> LINK conflicts.
- "used" records with `helped` boolean become INC_HELPFUL/INC_HARMFUL (learn.py:558-562): the source of `helped` is the weak point (see #1).
- Decay 90/270 days (learn.py:34-35) time-only.

## 3. Ranked improvements (expected value high -> low)

Labels: ADOPT = adopt now; TRY = behind a measurement.

### 1. ADOPT: credit only from external outcomes, never self-report
Evidence: poisoning paper (trust score is confidence not security); ACE caveat; Voyager self-verification ablation -73%; misevolution. Effect: no token cost; prevents the highest-impact corruption.
```
def credit(session):
    for item in session.items_injected:           # recorded by `brain recall`
        gate = session.gate_result_after(item.use_ts)   # tests/lint/req check
        if gate in (PASS_FIRST_TRY): op INC_HELPFUL(item, weight=1, evidence="gate:"+id)
        elif gate == FAIL_AFTER_FOLLOWING(item): op INC_HARMFUL(item, weight=1)
        else: no op                                 # model opinion never counts
    owner_correction naming item -> INC_HARMFUL weight=3 evidence "owner:"
```
Risk: sparse signal; fine (slower but safe).

### 2. ADOPT: attribution by injection log, with confound control
Only items that `recall` actually injected and that the transcript shows were consulted can be credited; if >3 items injected at once, split credit 1/n (fractional counters; allow float). Evidence: TAME contribution score c; k-scaling hurts. [inference for the split]
```
inject_log.append({session, item, rank, ts}); credit_i = base / max(1, n_injected)
```

### 3. ADOPT: cap retrieval at k<=3 items and one-line stubs first
Evidence: ReasoningBank k=1 49.7 vs k=4 44.4; poisoning ASR rises with k (6%->38%); SkillsBench <=3 modules; A-Mem gains level off at higher k. Token effect: negative (saves). Sketch: recall returns `id | description (<=20 tokens)`; body fetched by `brain recall --open ID`; hard top-3 after coverage packing; require min BM25 score and min task-class match, else inject nothing (ReMem gain tracks similarity).
```
cands = bm25(query)[:20]; keep those with score>=s_min and class_overlap
rank by score * confidence(item) * recency_factor ; pack greedily, k<=3, tokens<=budget
if none: return "no relevant memory"   # silence is a valid answer
```

### 4. ADOPT: two-key promotion with independent evidence and a trial period
Current: probation->active at h>=3, sessions>=2. Add: evidence from >=2 distinct sessions AND >=1 distinct project/task-class AND at least one gate-type evidence AND no unresolved conflict; imperative items from "observed" trust never reach `active` without a gate pass. Maybe lower-bound test: promote when Wilson/Beta 80% lower bound > 0.6 [thresholds are my estimate, not from papers].
```
lb = beta_quantile(0.2, h+a0+1, x+b0+1)   # stdlib: approximate with Wilson interval
promote if lb>0.6 and sessions>=2 and projects>=1 and any(e.startswith(("gate:","test:")) for e in evidence)
```
Evidence: ExpeL voting; ACE counters; SkillEvolBench clutter.

### 5. ADOPT: store-time selective addition (quality gate before ADD)
Evidence: experience-following study (secondary), Voyager verification, Dynamic Cheatsheet error amplification. Reject at ADD: no evidence prefix, text >400 chars, imperatives sourced from tool output/web (rule 8 already), absolute claims ("always/never") with fewer than 2 evidence lines, any text matching injection patterns ("ignore previous", "from now on", URLs with instructions).
```
def admit(note): 
    if note.source in (web, tool_output, project_file): note.type='fact', note.trust='external'  # never a rule
    if is_absolute(note.text) and len(note.evidence)<2: return reject
    if note.trust=='external' and imperative(note.text): return reject
```
Cheap: pure regex. Extends learn.py check_note.

### 6. ADOPT: bi-temporal facts with supersede-not-delete
Evidence: Zep (t_valid/t_invalid, history kept; LongMemEval +15.2/+18.5%). Fields: valid_from, valid_to, verified_at, source_url. `brain recall` filters valid_to=null; items unverified > N days for model/pricing facts are shown with "(unverified Nd)" or trigger the news check. Mem0 UPDATE/DELETE → here SUPERSEDE op (sets valid_to, links new). Serves the "constantly searching for new info" requirement cheaply: check only facts past their TTL.
```
op SUPERSEDE{old,new}: old.valid_to=today; old.status='retired'; new.supersedes=[old]
fact TTL by class: model/pricing 14d, library API 60d, process 180d   # [my estimate]
```

### 7. ADOPT: failure-and-guardrail items as a typed kind, created from failure/success PAIRS
Evidence: ReasoningBank 46.5 -> 49.7 including failures; ExpeL pairs; ReMem robust to failed trajectories. Item type `pitfall` with fields trigger, symptom, guard. Generate only when a later success on same task class exists in the log (paired) or gate-fail repeated twice; prevents Honest-Lying style false "X never works": every pitfall must carry the observed error text/gate id and an expiry/retest date (retest 1 in N times, e.g. via Thompson-style exploration flag).
```
if gate_failed(sig) and later_pass(same_task_class): note(type='pitfall', trigger=sig, guard=diff_summary, evidence=[gate:fail_id, gate:pass_id])
pitfall.retest_after = now+60d  # lets recall flag "re-verify" rather than forbid
```

### 8. ADOPT: change-control for text edits (anti-collapse invariants)
Evidence: ACE collapse 18k -> 122 tokens, 66.7 -> 57.1; Dynamic Cheatsheet lossy rewrites. Invariants in apply_delta: EDIT_TEXT may change <=30% of characters per op (my threshold), may not shrink an item below 50%; total store token count may not fall >10% in one delta; retired items go to archive (exists: memory/archive.jsonl). Add a checksum check that unreferenced items were not touched.
```
def validate_edit(old,new): assert edit_ratio(old,new)<=0.3 and len(new)>=0.5*len(old)
def validate_delta(before,after): assert tokens(after)>=0.9*tokens(before) or delta.is_decay
```

### 9. TRY: held-out replay test for playbook/prompt line changes (GEPA-style accept-if-better)
Evidence: GEPA accept-only-if-improves, Pareto selection (top-only trails 6.4% avg). Keep `learning/replay/*.jsonl` of 10-20 past task briefs with a deterministic check (gate outcome, token count). A candidate playbook edit is promoted only if on the replay set pass-rate not lower and tokens not higher. Cost is real model runs; do it only for playbook/CLAUDE.md changes (rare), not items. Pareto: keep per-task-class best variant rather than one global best. [implementation cost high; measure first on 1 playbook]

### 10. TRY: Thompson-style item exploration with decayed counters
TAME's Q-update Q <- Q + a*c*(r-Q), a=0.2 gives recency-weighted utility. Add `q` alongside Beta counts; sample q from Beta for ranking so new items occasionally get tried (bandit), mirroring the routing Thompson sampler.
```
score(item) = bm25_norm * beta_sample(h+a0+1, x+b0+1) * (0.5**(age_days/half_life[class]))
update after gate: q += 0.2*c*(r-q)
```
Risk: exploring harmful items; cap exploration to probation items and to 1 of 3 slots.

### 11. TRY: keep raw-trajectory pointers beside distilled items
Evidence: SkillEvolBench (raw reuse often beats distilled); AWM over-reliance. Item gets `episode` pointer (path to a compact 5-line trace in stats/ or project). Recall can show the one best matching episode for a new class instead of a rule. Token cost: only when opened.

### 12. TRY: semantic-near-dup detection beyond Jaccard
ACE dedupes with embeddings; ours is Jaccard 0.6. Without installs, use stemmed token-set + character 4-gram Jaccard, and a polarity check (exists). Measure false merge/false split on the existing items first. Opposite-polarity near-duplicates already LINK conflicts, good.

### 13. TRY: sleep-time consolidation window
Letta sleep-time (secondary figures). `brain close` only appends notes; consolidation runs as a separate step at next session start only if inbox size >N or >24h, to keep close fast. Mostly already designed; make it explicitly off the critical path.

### 14. ADOPT (small): task-class stratified counters
ReMem gain correlates with similarity; AIME-24 got worse with memory. Store `helpful/harmful` per task_class in addition to global; an item harmful in one class is excluded there, not retired globally.
```
item.by_class = {"web-ui": [h,x], "data-etl": [h,x]}; rank uses by_class[cls] if n>=3 else global
```

### 15. ADOPT (small): model-tier provenance on items
Dynamic Cheatsheet: memory from stronger model can degrade weaker. Record `author_model` and `applies_to_tier`; helper agents (Haiku/Sonnet) only get items that passed gates when used by that tier [inference; DC evidence is about cross-model transfer].

## 4. The five most dangerous practices to avoid
1. Letting the model judge its own memory (self-assessed helpfulness/trust/"verified"). Poisoning paper: poisoned entries got trust 1.0; ACE and ReasoningBank warn of judge noise.
2. Full LLM rewrites of memory/playbooks ("tidy up", "summarise lessons"). ACE context collapse (18k->122 tokens, 66.7->57.1, below baseline); DC lossy rewrites.
3. Promoting or injecting many items / big skill bundles ("more memory is better"). ReasoningBank k=4 < k=1; SkillsBench <=3 modules; SkillEvolBench clutter; poisoning ASR rises with k.
4. Storing text read from the web, tool output or project files as rules, or auto-generating skills without an independent verifier. MINJA 98.2% injection; no strong defence known; SkillsBench self-generated skills negligible/negative (secondary).
5. Storing absolute negative lessons ("X never works") from single binary failures, with no expiry or retest. Honest-Lying (secondary): self-sealing; Reflexion WebShop 43%->35% after four rounds (secondary summary).

## 5. Contrary evidence and unknowns
- Mem0 below full context on LOCOMO (66.88 vs 72.90): memory compression loses accuracy; gains are mostly cost/latency. Zep regressed on single-session-assistant (-17.7% with 4o).
- DC/ACE/ReasoningBank were tested on AppWorld/WebArena/AIME-style tasks and older models; none tested on Claude Code software building with Opus/Fable-class models. Transfer is [unverified]. Thresholds in section 3 (0.3 edit ratio, 0.6 lower bound, TTLs) are my estimates, to be tuned on our own logs.
- The fetcher summarised pages; some numbers were flagged inconsistent by it (AWM 24.6% abstract vs body; Evo-Memory text vs tables). I used body/table numbers where flagged.
- Not reached/not read in full: Reflexion original, MemGPT paper, Voyager tail, Letta primary pages, AgentPoison primary, HF discussion threads and Reddit/HN/X threads (not searched in this pass; time-boxed). A self-evolving-agents survey was not located in this pass.
- Experience-following paper numbers are from search summaries only.

## 6. Searches run
HF paper pages (ACE, GEPA, DC, AWM, ExpeL, Zep, Mem0, A-MEM, ReasoningBank, Voyager); arXiv abs (Evo-Memory, SkillsBench, CoEvoSkills, SkillEvolBench); arXiv html (2601.05504, 2602.03224, 2511.20857v2); WebSearch on memory poisoning, self-evolving memory benchmarks, experience-following, Letta, Claude skills evolution, Reflexion limits; HF daily_papers API (unfiltered output).
