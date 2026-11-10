# 04 — Algorithms for the Claude Brain (analyst 4 of 10)

Date: 2026-11-10. Scope: Part A, independent extraction of the owner's message 2. Part B, the algorithm lens: what is real, what is not, and what to build as deterministic, zero-model-token Python 3 scripts.

Tags used throughout: **[source]** = a URL in section 9 was read or returned by a search in this session; **[repo]** = read in the sample repo today; **[measured]** = I ran a prototype today (scripts in `/tmp/claude-0/-home-user/ad24da2f-7dc0-51cf-aa28-dee6f5e57a4f/scratchpad/proto04/pack.py` and `/tmp/claude-0/-home-user/ad24da2f-7dc0-51cf-aa28-dee6f5e57a4f/scratchpad/proto04/sched.py`, synthetic instances); **[memory]** = standard result recalled, not re-fetched today; **[inference]** = my reasoning.

---

## 0. The twelve findings that should change the plan

1. **"Quantum logic" cannot be delivered literally.** There is no quantum hardware in a Claude Code container and model inference is classical. What can be delivered is a small set of classical optimisers, one of which (annealing) is legitimately "quantum-inspired" in lineage. Say this to the owner in plain words; do not label greedy or dynamic-programming code "quantum".
2. **Context packing: greedy wins, annealing is a rounding error.** On synthetic instances the lazy cost-benefit greedy reached 99.1% of the true optimum on average; annealing on top added 0.9–1.7% of objective for 12–30x the runtime [measured]. Relevance scores are far noisier than 1–2%. Build greedy; keep the annealer as an optional polish flag.
3. **The brief's premise about MMR is wrong.** MMR is a heuristic with no approximation guarantee. The (1 − 1/e) guarantee belongs to greedy maximisation of a *monotone submodular* function (with partial enumeration under a knapsack budget) [source 1]. Use a monotone coverage objective, not MMR.
4. **Scheduling is the one place annealing earned its keep.** Tickets with dependencies and file-ownership conflicts on N agents: first-come order was 13–15% above the makespan lower bound, critical-path priority 4–7.5%, annealing over the priority order 0–2.3% [measured]. This module may honestly carry the "annealing optimiser" name.
5. **Model/effort assignment under a budget is a multiple-choice knapsack.** Exact dynamic programming solves it in milliseconds. Nothing to anneal.
6. **A cheap-first cascade pays when p > (c_cheap + c_verify) / c_strong** [inference, derived in 2.2]. Published headline savings are large (FrugalGPT up to 98%, RouteLLM 85% on MT Bench, 45% MMLU, 35% GSM8K) [source 3, 4] but they are for single question-answer calls. In an agent loop a model switch forfeits the prompt cache [repo: R-A11], so route at the *subagent boundary*, never mid-conversation.
7. **The sample repo's payroll system never got calibrated.** Its ledger holds 10 seeded rows and its own report says "0 paired runs" for every role [repo]. The algorithms are sound and reusable; the lesson is that metering must be automatic from day one or the estimators run on priors forever.
8. **Review loops plateau at two to three rounds** [source 9, 10]. Stop rule: one round always, a second only to verify fixes of blocking defects, a hard cap of three, plus a capture-recapture estimate of remaining defects when two independent reviewers ran.
9. **The 5-hour window is the binding budget, and its size is unpublished** [repo: R-A11]. Control it with a burn-rate governor on `used_percentage`, not a token count. Parallel agents cut wall-clock time but *raise* token spend; they never save tokens.
10. **Retrieval can start on the standard library alone.** Python 3.13 in this container ships SQLite 3.53.1 with FTS5 [measured]. The sample Library reached recall@5 0.914 and MRR 0.822 on 244 questions, but its evaluation took 599 s and needs fastembed, onnxruntime and numpy [repo]. Build the BM25 tier first, measure it on the same golden-set method, and add dense vectors only if the measured gap justifies the install cost.
11. **Content-addressed caching is the largest zero-token win** [inference]. Hash the inputs of every derived artefact (repo map, summaries, index, context packs); recompute only on a miss. It is exact, deterministic and compounds every session.
12. **Lossy prompt compression of instructions is unsafe; structural compression is safe.** Empirical studies report increased hallucination under prompt compression and sharp drops when the question itself is compressed [source 7, 8]. Compress by structure (IDs, tables, references, diffs, schemas), never by deleting words from instructions.

---

## PART A — Independent extraction of message 2

Each item quotes the owner's exact words. Type: R = requirement, C = constraint, P = preference, I = implied expectation, A = ambiguity, X = impossible or needs honest reframing.

| # | Type | Exact words | What it requires |
|---|---|---|---|
| A1 | R | "I essentially used this repo as a brain to create everything in my travel journal in the best possible way" | The sample repo is the reference pattern. The new repo must reproduce its working parts (handbook, resume loop, Library, agents, hooks, status files) |
| A2 | R | "I want now to create a repo that will act as that" | Deliverable is a repository, not a document or a service |
| A3 | R | "(essentially a mega complex orchestrator)" | The brain orchestrates: planning, delegation, review, budgeting, memory |
| A4 | A | "mega complex" | Describes capability, not a wish for complexity for its own sake. It conflicts with A27 (most efficient). Reframe: complex in capability, minimal in always-loaded context |
| A5 | R | "but to build anything I will ever need from now on" | Domain-general. Nothing may be hard-wired to travel journals, web apps or one stack |
| A6 | X | "anything I will ever need" | Unbounded scope cannot be guaranteed. Reframe: a general core plus an extension mechanism (project-side files, skills, plugins) and an honest list of what it cannot do |
| A7 | C | "When using it I will always use two repos in a chat" | Every session has exactly two repos attached. All paths, hooks and instructions must work in that layout |
| A8 | C | "one of them the Claude brain" | Repo 1 is the brain |
| A9 | C | "which will be only modified by its own machine learning systems" | Humans and project work do not hand-edit the brain. Changes to it go through a defined, automated learning pipeline |
| A10 | X | "machine learning systems" | No model weights are trained here. Honest equivalent: logged outcomes update statistics (bandit counts, estimator histories, retrieval evals) and curated lessons; scripts apply them. Call it "learning from logged outcomes", explain that it is statistics plus curated notes |
| A11 | R | "as it improves by learning with everything I use it for" | Every session must feed the learning loop: capture outcomes, costs, defects, lessons, without the owner doing anything |
| A12 | A | "only modified by its own machine learning systems" | Who writes to the brain during a project session? Needs a rule: project sessions append to an inbox or ledger; a gated promotion step changes the brain proper. Also needs a rule for bootstrapping (the initial build is necessarily written by the lead) |
| A13 | C | "the other repo will be where the project will be built" | Repo 2 holds the product. Product code never lands in the brain |
| A14 | R | "which can also hold files and tools to complement the Claude brain functionality that are specific to that project" | A project-side extension contract: project-specific agents, skills, cards, config, overrides, in a known location the brain discovers |
| A15 | C | "both will always be worked together from now on" | The pairing is permanent. Design the interface (versioned contract) between the two repos |
| A16 | R | "so the project must be built to work perfectly with it forever" | A project scaffold or adoption step makes any repo "brain-compatible"; a compatibility check runs each session |
| A17 | X | "perfectly ... forever" | Cannot be guaranteed across future model and tool changes. Reframe: versioned contract, migration scripts, a self-test at session start, and pinned facts with dates |
| A18 | R | "Now you will create a super long, super detailed plan on how to build this" | Deliverable 1 is a plan, long and detailed |
| A19 | R | "based on very comprehensive research about Claude fable 5.2 and opus 5.5" | The plan must rest on current, cited research into both models |
| A20 | C | "(the main models ai will use it with)" | Target models are Fable 5.2 and Opus 5.5. "ai" is read as "I" (typo). Cheaper tiers may be used for sub-tasks but the design optimises for these two |
| A21 | R | "and also using everything we learned with the sample repo I attached" | Mine the sample repo's lessons, ADRs, research memos, status history and failures |
| A22 | C | "(obviously having present that the current Claude brain's scope for creating stuff is much bigger)" | Generalise; do not copy travel-specific roles, corpora or gates |
| A23 | R | "Also you must look at all your memory in detail and all our chats" | Use every prior-conversation and memory source that is actually accessible |
| A24 | X | "all your memory ... and all our chats" | A cloud session only sees what is attached or stored in reachable memory and repositories. State plainly which sources were readable and which were not; do not imply total recall |
| A25 | R | "consider everything I have ever asked you to build on Claude or any question I have ever asked you can be successfully processed to completion" | Build a requirement corpus of past request types and use it as acceptance tests: each must be executable end to end by the brain |
| A26 | A | "any question I have ever asked you" | Includes non-build tasks (research, explanation, analysis). The brain must handle question-answering, not only software builds |
| A27 | R | "Also VERY IMPORTANT, you MUST MAKE THIS THE MOST EFFICIENT CLAUDE TOOL EVER" | Efficiency is the top-ranked non-functional requirement, in capitals |
| A28 | X | "THE MOST EFFICIENT CLAUDE TOOL EVER" | A superlative cannot be proven. Reframe: publish measured baselines and measured savings per mechanism, so the claim is evidence, not a slogan |
| A29 | R | "it should be much more efficient in tokens" | Token consumption is the primary efficiency metric |
| A30 | R | "through plugins" | Claude Code plugins, skills, hooks, MCP servers are an expected mechanism |
| A31 | R | "and algorithms" | Deterministic algorithms are an expected mechanism (this report) |
| A32 | X | "and quantum logic" | Not literally available. Reframe as quantum-inspired classical optimisation, used only where it measurably helps (sections 1.1–1.5) |
| A33 | R | "and many other thing you must research to see how you can make this super efficient token wise" | Open-ended research mandate: the plan must show the search was wide and report what was rejected |
| A34 | R | "and super fast" | Wall-clock speed is a second efficiency metric. It trades against tokens when parallelism is used; the plan must name the trade |
| A35 | R | "while delivering the absolutely highest quality work" | Quality is not to be traded away for efficiency. Efficiency gains must be quality-neutral, shown by evaluation |
| A36 | R | "with absolute attention to detail" | Verification steps, checklists, review gates |
| A37 | P | "(focus a lot on accuracy, creativity and extreme attention to detail)" | Three named qualities. Accuracy: citations, tests, verification. Creativity: divergent options before convergence. Detail: completeness checks |
| A38 | A | "accuracy, creativity" | These pull in different directions for model settings and review style. The plan needs separate modes (explore vs verify), not one compromise |
| A39 | R | "Create now the super long and super detailed plan" | Repeats A18; "now" means in this session |
| A40 | R | "considering also all our previous builds in Claude" | Repeats A23/A25 for builds specifically |
| A41 | R | "and then start building until completion" | Deliverable 2 is the built repo, in this same run, to completion |
| A42 | C | "once you have a full plan based on extremely extensive research" | Ordering: research, then plan, then build. No building before the plan exists |
| A43 | A | "until completion" | Needs a written definition of done for the brain, or the work has no end. One session may not suffice; checkpointing is required |
| A44 | R | "Make sure you analyze this prompt by 10 independent agents" | Process requirement: ten independent analyses of this prompt (this report is one) |
| A45 | R | "and extract everything I said in full detail" | The extraction must be exhaustive and traceable to his words (this table) |
| A46 | R | "and you can execute to perfection by planning perfectly and researching and analyzing heavily everything" | Heavy research and analysis are explicitly licensed, even though A27 demands efficiency. The efficiency target applies to the brain's future operation, not to this one-off planning effort |
| A47 | I | (from context) owner "prefers clicking/reading files, never shell commands" | Every algorithm below must run from hooks or be invoked by the agent. The owner never runs a script; outputs he needs are Markdown files or pages |
| A48 | I | (from A9 + A11) | The learning data must persist across sessions, so it must be committed to a repository; a cloud container is discarded |
| A49 | I | (from A7 + A27) | Both repos' `CLAUDE.md`, agents, skills and MCP definitions are loaded every session. Always-loaded brain text is a per-session token tax; it must be small and stable (cache-friendly) |
| A50 | I | (from A35 + A27) | An evaluation harness is required: without measured quality, "efficient" degrades into "cheap" |
| A51 | A | "plugins" | May mean Claude Code plugins specifically or extensions in general. Research both; do not assume |
| A52 | A | Whether the brain is private, and whether learning data from one project may inform another | Default: one owner, cross-project learning allowed, no secrets in the ledger |

Tensions the plan must resolve explicitly: A4 vs A27 (complexity vs efficiency); A34 vs A29 (speed via parallelism costs tokens); A46 vs A27 (heavy research now vs frugal operation later); A9 vs A41 (brain "only modified by its own systems" vs the initial build); A37 accuracy vs creativity.

---

## PART B — The algorithms

### B.0 Honesty frame

- **Quantum computing** needs qubits. None are reachable here, and simulating n qubits classically costs memory and time exponential in n. Simulating a quantum algorithm to obtain its speed-up is self-defeating.
- **Quantum-inspired** has two honest meanings. (a) *Simulated quantum annealing* (path-integral Monte Carlo over replicas) and other physics-derived heuristics for QUBO problems. (b) *Dequantised* algorithms, classical sampling methods derived from quantum ones; these help only for very large, low-rank matrices and degrade as rank and condition number grow [source 12]. Meaning (b) has no use at our scale.
- **Simulated annealing** itself is a classical thermal method. It is a sibling of quantum annealing, not a quantum algorithm. I recommend the module name **`anneal`** and the owner-facing description "annealing optimiser (quantum-inspired, runs on ordinary hardware)". The label applies to that module only.
- Published comparisons give no reason to expect quantum-inspired solvers to beat plain simulated annealing on knapsack-type problems: a solver review found "no clear winner" among three quantum-inspired solvers, which were sometimes worse than simulated annealing; D-Wave hardware failed to find optimal knapsack fillings; and the QUBO encoding of the inequality constraint mattered more than the solver [source 2].

Verdict table (details in the numbered sections):

| # | Algorithm | Verdict | Quantum-inspired? |
|---|---|---|---|
| 1.1 | Context packer: lazy cost-benefit greedy on monotone coverage | BUILD NOW | No |
| 1.1b | Annealing polish for the packer | BUILD LATER (flag, off by default) | Yes (annealing) |
| 1.1c | Simulated *quantum* annealing with replicas | SKIP | Yes, no benefit |
| 1.2 | Task-to-(model, effort) assignment: multiple-choice knapsack DP | BUILD NOW | No |
| 1.3 | Ticket scheduler: critical-path list scheduling with file locks | BUILD NOW | No |
| 1.3b | Annealing over schedule priorities | BUILD NOW (small, measured gain) | Yes (annealing) |
| 1.4 | Probability-per-cost search ordering with early stop | BUILD NOW | No (Grover gives nothing classically) |
| 2.1 | Thompson-sampling tier picker with pooled priors | BUILD NOW (advisory) | No |
| 2.2 | Cascade rule at subagent boundary | BUILD NOW | No |
| 2.3 | Review-loop stopping rule and capture-recapture | BUILD NOW | No |
| 2.4 | Value-of-information calculator (research / ask / decide) | BUILD NOW | No |
| 2.5 | WIP limit | BUILD NOW (part of 1.3) | No |
| 2.6 | Burn-rate governor for 5-hour and weekly windows | BUILD NOW | No |
| 2.7 | Reference-class estimator, max-min allocator, enforcer (from payroll) | BUILD NOW (port, simplified) | No |
| 2.8 | Role selection by weighted set cover, role clustering (from orgdesign) | BUILD LATER | No |
| 3.1 | FTS5 BM25 with field weights and id matching | BUILD NOW | No |
| 3.2 | Dense vectors | BUILD LATER (only on measured gap) | No |
| 3.3 | Reciprocal rank fusion | BUILD NOW | No |
| 3.4 | Cross-encoder rerank | BUILD LATER | No |
| 3.5 | Parent-child chunks | BUILD NOW | No |
| 3.6 | SimHash / MinHash deduplication | BUILD NOW | No |
| 3.7 | Content-addressed cache of derived artefacts | BUILD NOW | No |
| 3.8 | Incremental indexing by git diff | BUILD NOW | No |
| 3.9 | PageRank repo map | BUILD NOW | No |
| 3.10 | Regex symbol extraction (no tree-sitter) | BUILD NOW | No |
| 4 | Structural compression | BUILD NOW | No |
| 4b | Lossy compression of instructions | SKIP | No |

---

## 1. Optimisation problems

### 1.1 Context packing

**Problem.** Given candidate chunks i = 1..n, each with token cost c_i, a relevance score r_i for the current task and pairwise similarity s_ij, choose a subset S with total cost at most B tokens that carries the most useful, least repetitive information.

**Two objective functions.**

(Q) Quadratic penalty form, which is a QUBO with one inequality:

    maximise  F_Q(S) = Σ_{i∈S} r_i  −  2λ Σ_{i<j, i,j∈S} s_ij · min(r_i, r_j)     subject to Σ_{i∈S} c_i ≤ B

(C) Monotone coverage form. Each chunk covers "units" u (query terms, entities, ticket acceptance criteria, file paths) with weight w_u, saturating at 1:

    maximise  F_C(S) = Σ_u w_u · min(1, Σ_{i∈S} cov_iu)     subject to Σ_{i∈S} c_i ≤ B

F_C is monotone and submodular; F_Q is submodular but not monotone (adding a redundant chunk can lower it).

**Which is better here.**

- **MMR** (pick argmax θ·r_i − (1−θ)·max_{j∈S} s_ij) is a per-step heuristic. It ignores cost, has no approximation guarantee, and keeps adding chunks until the budget is full even when the additions are redundant. The brief's statement that MMR has a (1 − 1/e) guarantee is incorrect. [memory: Lin and Bilmes 2010 treat MMR as greedy on a non-monotone objective, where the classical guarantee does not apply; the paper is source 11 but I could not open the full text today.]
- **Greedy on a monotone submodular objective under a knapsack budget**: cost-benefit greedy combined with the best single item gives a constant-factor guarantee, ½(1 − 1/e) ≈ 0.316 [memory: Khuller, Moss, Naor 1999; Leskovec et al. 2007]. Greedy started from every seed set of up to three items (two in the refined analysis) reaches (1 − 1/e) ≈ 0.632, which is the best possible in polynomial time in the oracle model [source 1]. Worst-case bounds are loose; in practice greedy is near-optimal.
- **Annealing on the QUBO form** has no guarantee and is slower, but can escape greedy's local choices.

Measured on synthetic instances (clustered similarity, costs 120–600 tokens, λ = 0.5) [measured]:

| Instance | Greedy (best of ratio and gain rules) | Annealing started from greedy | MMR (θ = 0.7), scored on F_Q |
|---|---|---|---|
| n = 16, B = 1500, 30 seeds, vs brute-force optimum | 0.991 mean, 0.946 worst | 0.998 mean, 0.977 worst | 0.971 mean, 0.806 worst |
| n = 60, B = 4000, 20 seeds, vs greedy | 1.000 (1.6 ms) | 1.009 mean, 1.028 best (50 ms) | 0.923 |
| n = 200, B = 8000, 20 seeds, vs greedy | 1.000 (7.3 ms) | 1.017 mean, 1.066 best (86 ms) | negative (fills the budget with redundant chunks) |

Caveats: synthetic data; MMR is being judged on an objective it does not optimise, so the fair reading is "MMR over-fills", not "MMR is useless".

**Conclusion.** Greedy on the coverage objective (C) is the right default: it has a guarantee, is cost-aware, stops when marginal gain reaches zero (so it can return *less* than the budget, which is the actual token saving), and runs in single-digit milliseconds. Annealing buys about 1–2% of an objective whose inputs (relevance scores) are uncertain by far more than that [inference]. It is not worth a default code path.

**Pseudocode (lazy cost-benefit greedy, CELF style).**

```
pack(chunks, B, units):
    covered = {u: 0.0}                         # saturating coverage per unit
    gain(i) = Σ_u w_u * (min(1, covered[u] + cov[i][u]) - covered[u])
    heap = max-heap of (gain(i)/c_i, i, stamp=0) for all i with c_i <= B
    S = []; cost = 0; round = 0
    while heap:
        ratio, i, stamp = pop(heap)
        if cost + c_i > B: continue
        if stamp != round:                      # stale: recompute, push back (lazy evaluation)
            push(heap, (gain(i)/c_i, i, round)); continue
        if gain(i) <= EPS: break                # nothing useful left: stop under budget
        S.append(i); cost += c_i; round += 1
        for u in units(i): covered[u] = min(1, covered[u] + cov[i][u])
    best_single = argmax_i gain_from_empty(i) with c_i <= B
    return better_of(S, [best_single]) ordered by (source path, line)   # stable order for the prompt cache
```

**Complexity.** Worst case O(n² · ū) for n chunks and ū units per chunk; lazy evaluation makes it close to O(n log n · ū) in practice. Memory O(n · ū).

**Design notes that matter more than the optimiser [inference].**
- Output order must be deterministic (sort by path and line, not by score). A stable prefix keeps prompt-cache hits; a reshuffled pack is a cache miss.
- Pack once per task, not per turn. Re-packing mid-conversation edits history and breaks the cache [repo: R-A11 F4; bundled `claude-api` skill, cost-optimization].
- Return parent section pointers, so the agent can expand one chunk on demand instead of receiving all parents up front.
- Units should include the ticket's acceptance criteria and named files, not only query words; that is what makes coverage meaningful.

**Annealing polish (1.1b).** Moves that keep the budget feasible: add, remove, swap. Accept worse moves with probability exp(Δ/T), geometric cooling from T0 to T1, start from the greedy solution, keep the best seen. This avoids slack variables entirely, which matches the finding that formulations without auxiliary variables for the inequality perform best [source 2]. Complexity O(iterations · |S|). Verdict: BUILD LATER, behind a flag, and only keep it if the measurement below shows an end-task difference.

**Simulated quantum annealing (1.1c).** P coupled replicas of the same problem with a transverse-field term, costing P times the work per sweep. No evidence of benefit on instances of tens to hundreds of variables [source 2], and greedy is already within about 1% of optimal. SKIP.

**Expected benefit.** The saving comes from sending fewer tokens for equal answer quality, not from the optimiser's last percent. Typical first-order effect: de-duplicated, budgeted retrieval replaces "top-k of everything" [inference; no number claimed until measured].

**How to measure.** On the golden set: (a) recall@budget, the share of questions whose gold chunk is inside the pack at B = 1500, 3000, 6000 tokens; (b) tokens sent per answered question; (c) redundancy, the mean pairwise Jaccard of packed chunks. Compare top-k, MMR, greedy, greedy plus annealing. Keep the annealer only if (a) improves by at least 2 points at equal B.

### 1.2 Task-to-agent/model assignment under a budget

**Problem.** For tasks t = 1..T choose one arm a from A_t, where an arm is (model tier, effort). Each arm has expected cost c_ta (cache-adjusted tokens or credits) and expected probability of acceptance p_ta. Tasks have value v_t. Total budget B.

**Objective.**

    maximise Σ_t v_t · p_{t,a(t)}     subject to Σ_t c_{t,a(t)} ≤ B,  a(t) ≥ floor(t)

where floor(t) is a policy minimum (security review, design critique and architecture never go below the top tier; the sample repo encodes this as `tier_floor` [repo]).

This is the multiple-choice knapsack problem.

**Pseudocode (exact DP on a discretised budget).**

```
assign(tasks, B, step):
    K = B // step
    best = [-inf] * (K+1); best[0] = 0; choice = []
    for t in tasks:
        new = [-inf] * (K+1); pick = [None] * (K+1)
        for k in 0..K where best[k] > -inf:
            for a in arms(t) with tier(a) >= floor(t):
                k2 = k + ceil(c[t][a] / step)
                if k2 <= K and best[k] + v[t]*p[t][a] > new[k2]:
                    new[k2] = best[k] + v[t]*p[t][a]; pick[k2] = (k, a)
        best = new; choice.append(pick)
    backtrack from argmax(best)
```

**Complexity.** O(T · |A| · B/step). With 200 tasks, 12 arms and 1000 budget steps: 2.4 million updates, well under a second in CPython. An equivalent fast path: start every task on its cheapest allowed arm and repeatedly apply the upgrade with the best Δvalue/Δcost on each task's convex hull; this is optimal for the linear relaxation and within one task of optimal [memory].

**Where quantum adds nothing.** The problem is solved exactly by DP at our sizes. A QUBO encoding would need one-hot penalties per task plus slack bits for the budget, making it larger and harder than the original. SKIP any annealer here.

**Expected benefit.** Bounded by the quality of the inputs p_ta and c_ta, which come from sections 2.1 and 2.7. With cold-start priors the DP mostly reproduces the policy table; it becomes useful once the ledger has data.

**How to measure.** Cost per accepted task and first-pass acceptance rate, per task class, before and after; a hold-out of 10% of tasks routed by the static table.

### 1.3 Scheduling a ticket DAG onto N parallel agents with file-ownership conflicts

**Problem.** Tickets with estimated durations d_i, dependency edges, and the set of files each will write. Two tickets that write the same file must not run at the same time (otherwise parallel agents overwrite each other or produce merge conflicts). N agents. Minimise makespan (wall-clock time to finish all).

**Structure.** The conflict relation is a graph; a set of tickets that can run together is an independent set; partitioning into such sets is graph colouring. With unequal durations and dependencies this becomes resource-constrained project scheduling with one mutual-exclusion resource per file. NP-hard in general; heuristics are standard.

**Lower bound** (for reporting how good a schedule is):

    LB = max( longest dependency path,  ceil(Σ d_i / N),  max over files f of Σ_{i writes f} d_i )

**Pseudocode (event-driven list scheduling).**

```
schedule(tickets, N, priority):
    t = 0; running = min-heap by finish time; locked = {}; done = set(); plan = []
    while pending or running:
        for i in pending sorted by priority desc:
            if len(running) == N: break
            if deps(i) ⊆ done and files(i) ∩ locked == ∅:
                lock files(i); push(running, (t + d_i, i)); plan.append((i, t, agent_slot)); pending.remove(i)
        t, j = pop(running); done.add(j); unlock files(j)      # also pop all others finishing at t
    return plan, t

priority_cp(i) = d_i + max(priority_cp(s) for s in successors(i))   # critical-path tail

anneal_priorities(tickets, N, iters=1500):
    p = priority_cp; cur = best = makespan(schedule(tickets, N, p))
    for it in 0..iters:
        T = T0 * (T1/T0) ** (it/iters)
        swap two priorities; v = makespan(...)
        if v <= cur or random() < exp((cur - v)/T): cur = v; best = min(best, v)
        else: undo swap
```

**Complexity.** One schedule: O(n² ) in the simple form (n tickets), fine for n in the hundreds. Annealing: iters × that; 1500 iterations on 120 tickets ran in a few seconds in CPython [measured].

**Measured** (random DAGs, 25 files, 1–3 files per ticket, durations 1–8, 20 seeds each; ratio of makespan to the lower bound, lower is better) [measured]:

| Tickets, agents | First-come order | Critical-path priority | Annealed priorities | Serial (one agent) |
|---|---|---|---|---|
| 30, 3 | 1.133 | 1.075 | 1.005 | 2.97 |
| 60, 4 | 1.141 | 1.040 | 1.000 | 3.96 |
| 120, 6 | 1.148 | 1.061 | 1.023 | 5.91 |

**Reading.** Parallelism is the large effect (3–6x wall-clock). Critical-path ordering removes about half of the remaining waste. Annealing removes most of the rest, a further 4–7%. That is a small but real gain for a few seconds of CPU and zero tokens, which is why this is the module where the annealer is justified. Duration estimates are uncertain, so re-plan after each ticket completes (the scheduler is cheap enough to rerun every time).

**What it does not do.** It does not reduce tokens. Each parallel agent pays for its own context and cache writes; the sample repo's research cites agent teams at about 7x the tokens of a standard session and multi-agent systems at about 15x chat [repo: R-A11 F5, R-A12 F1]. The scheduler buys speed (A34) at a token price (A29); the WIP limit in 2.5 decides how much to buy.

**Extra value: conflict prevention.** The file-lock model is also a correctness device. The sample repo polices scope with path hooks [repo: `.claude/hooks/protect-paths.sh`]; the scheduler prevents the conflict before it is attempted.

**Verdict.** BUILD NOW: list scheduler with critical-path priority and file locks. BUILD NOW: annealing over priorities (about 30 extra lines). Graph colouring alone (DSATUR waves) is a weaker special case; SKIP as a separate module.

**How to measure.** Makespan / LB per phase plan; number of file conflicts or merge conflicts per phase (target zero); idle agent-minutes.

### 1.4 "Amplitude amplification" intuition vs what classical search gives

Grover's algorithm finds a marked item among N in about √N oracle calls, but only with a quantum computer evaluating the oracle in superposition. A classical simulation performs at least N evaluations. There is no classical speed-up to borrow. [memory; my search today returned nothing citable on this point, so treat it as textbook knowledge, not a fetched source.]

What does help classically, and is exact:

**Problem.** k candidate locations or hypotheses (which file holds the bug, which document answers the question, which fix will work), each with prior probability p_i of being the answer and a cost c_i to check. Minimise expected cost until the answer is found.

**Rule.** Check in descending order of p_i / c_i. This ordering is optimal for a single target with independent checks [memory: classical search theory]. Stop at the first verified hit (early termination).

```
order = sorted(candidates, key=lambda i: p[i]/c[i], reverse=True)
for i in order:
    if verify(i): return i          # early termination
    renormalise remaining p        # Bayes: p_j /= (1 - p_i)
expected_cost = Σ_i c_order[i] * Π_{j<i} (1 - p_order[j]/remaining)
```

**Complexity.** O(k log k). **Benefit.** Depends on how peaked the priors are; with a 50/20/10/... prior and equal costs, expected checks fall from (k+1)/2 to under 2 [inference]. **Where p comes from:** retrieval scores normalised to probabilities, git blame recency, test-failure locality. **Measure:** files read before the first relevant one; tool calls per resolved bug. **Verdict:** BUILD NOW as a helper used by the retrieval tool's result ordering and by debugging checklists. Do not name it after Grover.

### 1.5 Naming

- `pack` (greedy coverage), `assign` (DP), `schedule` (list scheduling): plain names.
- `anneal`: the only module that may be described as quantum-inspired, always with the sentence "runs on ordinary hardware; no quantum computer is involved".
- The owner-facing explanation of "quantum logic" should be one honest paragraph in the brain's README, with the measured numbers from 1.1 and 1.3.

---

## 2. Routing and budgeting

### 2.1 Contextual bandit for model tier and effort

**Problem.** For each task class x (for example code-feature/M, research-memo/S, review, mechanical edit) choose an arm a = (model, effort) to minimise cost while keeping acceptance by the reviewer above a threshold.

**Prior art in the sample repo.** `payroll/payroll/allocator.py: recommend_model()` samples each model's acceptance from Beta(a0 + accepted, b0 + rejected), with an informative Beta(8, 2) prior on the current model and Beta(1, 1) on others, and returns the cheapest model whose sample clears 0.8, requiring at least 5 reviewed trials before switching and never going below the role's tier floor [repo]. This is a sound, conservative design.

**Improvements for a general brain [inference].**
1. Key by task class and size band, not by role name, so it transfers between projects.
2. Hierarchical pooling: each (class, arm) posterior shrinks toward the arm's global posterior, otherwise every new class starts cold. Use pseudo-counts: a0 = 1 + κ·global_accept_rate, b0 = 1 + κ·(1 − rate), κ = 4 (the same shrinkage strength the payroll estimator uses [repo]).
3. Minimise expected cost to acceptance rather than thresholding: pick argmin over eligible arms of (c_a + c_review) / θ_a, where θ_a is the sampled acceptance and retries are assumed independent.
4. Discount old evidence (multiply counts by γ = 0.98 per new observation) and reset on a model version change, because behaviour shifts with each release.
5. Explore on at most 10% of tasks and never on review, security or irreversible tasks [repo: R-A12 item 9].

**Pseudocode.**

```
choose(x, arms, ledger, rng):
    elig = [a for a in arms if tier(a) >= floor(x)]
    for a in elig:
        acc, rej = discounted_counts(ledger, x, a)
        g = global_rate(ledger, a)
        theta[a] = rng.betavariate(1 + 4*g + acc, 1 + 4*(1-g) + rej)
        score[a] = (cost[x][a] + review_cost[x]) / max(theta[a], 0.05)
    return argmin(score)
update(x, a, accepted): append to ledger
```

**Complexity.** O(|arms|) per decision. **Sample size reality.** To tell an 80% arm from a 90% arm needs roughly 50 reviewed outcomes per arm (standard error sqrt(0.85·0.15/50) ≈ 0.05) [inference]. A single owner will take weeks to reach that per class, so the bandit is advisory at first and the static policy table decides. **Published support.** Bandit routers report lower cumulative regret than static routers [repo: R-A12 sources 8, 9; not re-fetched today]. **Measure.** Cost per accepted task by class; regret against the best fixed arm in hindsight. **Verdict.** BUILD NOW, advisory, with the ledger wired automatically.

**A caution specific to the target models.** The bundled `claude-api` skill notes that on Claude Fable 5.2 the size of a token budget written into the prompt changes how much the model spends, and that in Anthropic's testing on coding tasks removing a large one lowered cost at equal performance; it also lists "lines that push delegation" as instructions to re-test on that model [repo-adjacent: `/tmp/claude-0/bundled-skills/2.1.322/abe77d722f7cc0e8bbf4058a7be92fb3/claude-api/shared/prompt-audit.md`]. So the TALE-style lever (state the budget in the prompt, reported as about 67% fewer output tokens with under 3% accuracy loss [repo: R-A12 F1]) must be A/B tested per model, not assumed. Effort level is the dependable lever.

### 2.2 Cascades

**Published numbers.**
- FrugalGPT: matches the best single model with up to 98% cost reduction, or 4% better accuracy at equal cost; the 98% is a best case [source 3].
- RouteLLM: over 85% cost reduction on MT Bench, 45% on MMLU, 35% on GSM8K against always using the strong model, at about 95% of its quality; the paper's own summary is "over 2 times" [source 4].
- Hybrid LLM: up to 40% fewer calls to the large model [repo: R-A12, not re-fetched].

These are for independent question-answer calls between a strong and a much weaker model. They do not transfer directly to agent loops.

**Decision rule (derived).** Try the cheap arm first, verify, escalate on failure. Expected cost = c1 + cv + (1 − p1)·c2. This beats going straight to the strong arm (cost c2) when

    p1 > (c1 + cv) / c2

where p1 is the cheap arm's acceptance probability, c1 its cost, cv the cost of verifying, c2 the strong arm's cost. For a k-stage cascade, order stages by ascending cost and drop any stage that fails the same test against the next one [inference].

**Conditions for it to be valid [inference].**
- Verification must be cheap and trustworthy: tests, type checks, schema validation, a link checker. A model-judged verification has its own cost and error rate and belongs in cv and in p1.
- A failed cheap attempt must do no damage (work in a scratch branch or return a report only).
- Route at the subagent boundary. Switching model inside a conversation discards the prompt cache, and each subagent pays to warm its own cache; cache writes are the largest cost of short subagents [repo: R-A11 F4, F5].
- On a subscription, the weighting of each model against the 5-hour window is unpublished [repo: R-A11 F2], so "cheaper by list price" is an assumption until the calibration experiment in 2.6 is run.

**Pseudocode.**

```
cascade_plan(x, arms):                       # arms sorted by cost ascending
    plan = [arms[-1]]
    for a in reversed(arms[:-1]):
        if p[x][a] > (c[x][a] + cv[x]) / expected_cost(plan): plan.insert(0, a)
    return plan
```

**Verdict.** BUILD NOW as a rule inside the assigner, restricted to task classes with deterministic verification (mechanical edits, fixture generation, codebase search, formatting). **Measure.** Escalation rate, cost per accepted task, and the share of escalations where the cheap attempt's output was reused.

### 2.3 Optimal stopping for review loops

**Problem.** After each critic round, decide whether another round is worth its cost.

**Evidence.** Multi-agent debate accuracy tends to level off or fluctuate across rounds; one benchmark reports that more rounds offer little benefit while more agents help; a 2026 preprint reports the plateau within two to three rounds with reversals in some cohorts; an ICML 2025 paper shows accuracy can fall over rounds [source 9, 10]. Extra rounds help only when they bring new information [source 9].

**Model.** Let d_k be the number of material defects found in round k, V the value of fixing one (expected rework avoided, in credits), C the cost of a round. Defect discovery typically decays geometrically, d_k ≈ d_1·ρ^(k−1) [inference].

**Rule.**

```
continue_review(history, V, C, max_rounds=3):
    k = len(history)
    if k == 0: return True                                   # always one round
    if k >= max_rounds: return False
    if history[-1].blocking > 0: return True                 # verify the fixes once
    rho = estimate_decay(history, class_prior=0.4)           # shrink to the class's logged decay
    expected_next = history[-1].material * rho
    return expected_next * V > C
```

**Capture-recapture** when two reviewers examined the same artefact independently (Lincoln-Petersen; Chapman form avoids division by zero):

    N̂ = (n1 + 1)(n2 + 1)/(m + 1) − 1,    remaining ≈ N̂ − (n1 + n2 − m)

n1, n2 are each reviewer's defect counts and m the overlap. If remaining · V < C, stop. This is a real, deterministic estimate of what is still hidden, and it rewards using two *different* reviewers (different lens or model) over repeating the same one, which agrees with the "new information" finding. Assumption: reviewers are independent and defects equally findable; both are violated in practice, so the estimate is a lower bound [memory: standard in software inspection].

**Complexity.** O(1). **Benefit.** Prevents the fourth and fifth rounds, each costing a full read of the artefact. **Measure.** Defects found per round by class; share of round-3 findings that were material; post-acceptance defect escapes. **Verdict.** BUILD NOW.

### 2.4 Value of information: research, ask, or decide

**Problem.** Before spending tokens on research, or interrupting the owner, decide whether the information is worth it. The sample handbook's rule is "decide and record, don't ask" for everything outside a short list [repo: CLAUDE.md prime directive 6].

**Objective.** Expected value of perfect information:

    EVPI = Σ_s p(s)·max_a U(a, s) − max_a Σ_s p(s)·U(a, s)

Two-action shortcut: with probability q the default choice is wrong, and being wrong costs R in rework:

    research if   q · R · P(research resolves it) > C_research
    ask owner if  the decision is on the owner-only list, or  q · R_irreversible > C_interrupt and it cannot be undone
    otherwise     decide, record as ASSUMED, continue

**Pseudocode.**

```
voi(q, R, c_research, p_resolve, reversible, owner_only, c_interrupt):
    if owner_only: return "ASK (write to NEEDS_YOU, continue with default)"
    if q * R * p_resolve > c_research: return "RESEARCH (budget = min(c_research, 0.5*q*R))"
    if not reversible and q * R > c_interrupt: return "ASK"
    return "DECIDE and record"
```

**Honesty.** q and R are the agent's estimates, so the calculator disciplines the decision more than it optimises it. Its real value is a cap: research spend on a question never exceeds half the expected rework it could prevent [inference]. **Complexity.** O(1). **Measure.** Research tokens per decision; share of ASSUMED decisions later overturned (calibrates q). **Verdict.** BUILD NOW (about 30 lines plus a table of rework costs by decision type).

### 2.5 Critical path and WIP limits

Critical-path computation is inside 1.3. The WIP limit is:

    N = min( width of the ready set,  concurrency cap,  floor(lead review capacity / mean report size),  N allowed by the burn-rate governor in 2.6 )

Reasons: the lead must read every returned report, and those tokens are re-read on every later turn [repo: R-A11 F4]; Anthropic's own rubric quoted in the sample research is one agent for simple work, two to four subagents for comparisons, more than ten only for complex research [repo: R-A12 F1]. Default N = 3 for build phases, re-evaluated from measured idle time and conflict counts. **Verdict.** BUILD NOW as a parameter of the scheduler.

### 2.6 Budget control against the 5-hour and weekly windows

**Facts** [repo: R-A11 F2, F3]. Max has a five-hour session limit, a weekly limit across models and a separate weekly limit for Fable. Absolute sizes and per-model weights are unpublished. Subagent requests count. The status line JSON exposes `rate_limits.five_hour` and `seven_day` with `used_percentage` and `resets_at` for subscribers. Whether a cloud session exposes those fields to hooks is **not verified**; the fallback is the brain's own ledger in cache-adjusted tokens, calibrated to percentage points by experiment.

**Why a classic token bucket is the wrong shape.** A token bucket refills continuously at rate r; the plan window resets in a step. The sample repo's memo proposed a per-role hourly bucket [repo: R-A12 item 7] but it was not implemented in `payroll/` (the modules are meter, pricing, estimator, allocator, enforcer, negotiation, accuracy [repo]). A burn-rate governor matches the real mechanism.

**Objective.** Finish the highest-value work before the reset without hitting the limit; never be caught without a checkpoint.

**Pseudocode.**

```
govern(now, used_pct, resets_at, window_len, ewma_rate, last):
    rate = 0.3 * (used_pct - last.pct)/(now - last.t) + 0.7 * ewma_rate     # pct per minute
    remaining = 100 - used_pct - RESERVE          # RESERVE = 5 pct for checkpoint and wrap-up
    t_exhaust = remaining / max(rate, 1e-9)
    t_left = resets_at - now
    pace = t_exhaust / t_left
    if used_pct >= 95:        return "CHECKPOINT_ONLY"
    if pace < 0.6:            return "DEGRADE_2: WIP=1, defer optional tickets, effort down one notch"
    if pace < 1.0:            return "DEGRADE_1: WIP-=1, no new exploratory subagents"
    if pace > 2.0 and t_left < 45 min: return "SPEND: pull forward parallel work"
    return "NORMAL"
```

The thresholds mirror the sample repo's degradation plan (80% lower effort, 95% checkpoint only, Fable limit falls back to Opus) [repo: R-A11 item 6]. Note that changing effort mid-conversation can invalidate the cache on some models [bundled `claude-api` skill, cost-optimization], so apply effort changes at the next subagent spawn, not on the running conversation.

**Calibration experiment (needed once per model).** Run one scripted subagent task per tier and record the change in `used_percentage` against cache-adjusted tokens. This is experiment E1 that the sample repo listed and never ran [repo: R-A11].

**Complexity.** O(1) per hook call. **Benefit.** Avoids the failure the sample repo observed, a 5-hour limit hit in the middle of research [repo: R-A11 F2]. **Measure.** Limit hits per week (target zero), unused percentage at reset, work lost to un-checkpointed stops (target zero). **Verdict.** BUILD NOW.

### 2.7 What the sample repo already built: `payroll/`

Read today: 1,499 lines of dependency-free Python with tests [repo].

| Module | Algorithm | Generalises? |
|---|---|---|
| `meter.py` | Parses subagent transcript JSONL; de-duplicates records by `message.id` because one API response is written as several records with repeated usage; prices by served model | Yes, essential. The transcript format is undocumented and may change [repo: R-A11 F3], so keep the parser tolerant and tested |
| `pricing.py` | Token vector (input, output, cache write, cache read) × pinned price table; "credits" where 1 credit = USD 0.01 | Yes. Price table must be refreshed from the live pricing page, with a date |
| `estimator.py` | Reference-class forecast in log space. Prior ln-cost ~ N(μ0, 0.5²) anchored so the prior P75 equals the role's anchor; observations normalised by size, effort and class factors; posterior centre = w·median + (1 − w)·μ0 with w = n/(n + 4); scale from 1.4826·MAD with a floor of 0.15; quantiles P25–P90 | Yes. Re-key from role to task class. The size, effort and class factors are marked ASSUMED in `payroll/data/priors.json` and need data |
| `allocator.py` | Reserve fraction (15%) plus weighted max-min fairness by progressive filling when the envelope is short; Thompson-sampling model recommender (2.1) | Yes |
| `enforcer.py` | Run states OK / WARN (70%) / CHECKPOINT (90%) / GRACE / HARD_STOP; control-chart flags: R1 cost above class P90 plus k robust scales, R2 nine consecutive runs on one side of the median | Yes. Claude Code has no per-subagent token cap [repo: R-A11 F3f], so enforcement is `maxTurns`, effort and a pre-spawn gate |
| `negotiation.py` | Top-up state machine: auto-approve the first top-up up to 25% if progress keeps pace with spend; otherwise checkpoint and re-scope or escalate | Partly. Keep the checkpoint-then-rescope rule; drop the salary-review ceremony |
| `accuracy.py` | MAPE of P50, P50/P90 coverage, over-run and under-use rates, cost per accepted ticket; a class is UNCALIBRATED below 5 paired runs | Yes |
| `hooks.py`, `.claude/hooks/payroll-gate.sh`, `payroll-meter.sh` | PreToolUse gate on the Agent tool; SubagentStop metering | Yes, this is the wiring that makes everything else zero-touch |

**Judgement.** The mathematics is careful and reusable. The system did not reach calibration: `payroll/data/ledger.jsonl` has 10 rows, all seeded research-analyst runs, and `docs/hr/payroll/REPORT.md` lists every role as "uncalibrated (0 paired runs ...)" [repo]. For the new brain: (1) port meter, pricing, estimator, enforcer, accuracy nearly as is; (2) key everything by task class; (3) make ledger writes automatic and committed, because A9/A11 depend on it; (4) drop the HR metaphor from code paths (it costs reading tokens and adds nothing computational); (5) one ledger, shared across projects, with a project id column.

### 2.8 What the sample repo already built: `orgdesign/`

Read today: about 2,270 lines [repo].

| Module | Algorithm | Generalises? |
|---|---|---|
| `demand.py` | Demand model: ideas weighted by priority (P0 = 4, P1 = 3, P2 = 1.5, P3 = 0.5) mapped through a theme-to-skill taxonomy; ticket load spread across skills | The formula generalises; the parsers read that project's `IDEA_COVERAGE.md` and phase files, so a project adapter is needed |
| `selection.py` | Weighted set cover: pick the role with the best marginal coverage per cost until a coverage target is met, with governance constraints (required roles, every role has a reviewer selected, sprawl rejection by skill Jaccard, utilisation floor) | Yes. It is the same budgeted-coverage greedy as 1.1, applied to roles |
| `combine.py` | Constrained agglomerative clustering (average linkage) merging roles into multi-role agents; similarity = skill Jaccard + path overlap + bonuses; hard constraints for separation of duties (no agent reviews itself, read-only roles never merge with write roles), size caps; objective = number of agents + balance weight × CV of load | Yes in principle |
| `plan.py`, `pay.py`, `render.py`, `validate.py` | Assemble plan, price it, render Markdown, validate catalogue | Yes |

**Judgement.** Useful only when a project is large enough to need a standing roster. For most future requests (a question, a small tool) a roster is overhead; current guidance cited by the sample repo is to prefer the main loop and spawn subagents only for read-heavy or parallel, discardable work [repo: R-A12 F1]. Keep separation-of-duties checking (cheap, valuable) now; port selection and clustering later, triggered only above a ticket-count threshold. **Verdict.** BUILD LATER, except the separation check, BUILD NOW.

---

## 3. Retrieval

Baseline from the sample repo [repo: `library/config.json`, `library/eval/last_result.json`]: SQLite FTS5 (BM25, heading weight 3.0, path 0.5) plus sqlite-vec with bge-small-en-v1.5 (384 dimensions), reciprocal rank fusion (k = 60), cross-encoder rerank 20 → 5, near-duplicate filter at Jaccard 0.6, maximum three results per source, an authority prior favouring canonical documents. Result: recall@5 0.9139, MRR 0.822 on 244 questions; the evaluation took 598.7 s, about 2.5 s per query on CPU. Dependencies: sqlite-vec, fastembed, onnxruntime, numpy, tokenizers, tiktoken, mcp.

External reference: Anthropic's contextual-retrieval study reports top-20 retrieval failure falling from 5.7% to 3.7% with contextual embeddings (35%), to 2.9% with contextual BM25 added (49%), and to 1.9% with reranking (67%) [source 5].

### 3.1 BM25 on FTS5 — BUILD NOW

- **Problem.** Rank chunks for a text query with exact-term matching (ids, file names, error strings).
- **Objective.** BM25 score, Σ over query terms of IDF(t) · tf·(k1 + 1) / (tf + k1·(1 − b + b·len/avg_len)), with per-column weights.
- **Implementation.** `sqlite3` from the standard library; FTS5 is compiled into this container's Python (SQLite 3.53.1) [measured]. `CREATE VIRTUAL TABLE chunks USING fts5(body, heading, path, tokenize='porter unicode61 remove_diacritics 2')`, query with `bm25(chunks, 1.0, 3.0, 0.5)`. Quote each query token and join with OR; add hyphenated ids as phrases (the sample repo's `fts_query` does this [repo]).
- **Complexity.** Index O(total tokens); query roughly O(postings of the query terms).
- **Contextual prefix.** Prepend a one-line context (document title, heading path, first sentence) to each chunk before indexing; the sample chunker builds this deterministically with no model call [repo: `chunker.py: make_prefix`], which captures much of the contextual-BM25 benefit at zero tokens [inference].
- **Measure.** recall@5 and MRR on a golden set; latency per query.

### 3.2 Dense vectors — BUILD LATER, only on a measured gap

- **Problem.** Match paraphrases that share no words with the target.
- **Cost.** A model download and native wheels at every fresh container unless cached by a setup script; embedding time at ingest.
- **Decision procedure.** Run the golden set with BM25 only. If recall@5 is at or above the gate (0.9), stop. If the misses are paraphrase questions, add dense as an optional tier behind the same interface. I could not run the sample repo's ablation today (no virtual environment present), so the size of the gap on this kind of corpus is **unknown**; do not assume it.
- **Zero-dependency middle step.** A second lexical ranker over character trigrams or over an alias table (synonyms harvested from headings and ids), fused by RRF, recovers some paraphrase misses [inference].

### 3.3 Reciprocal rank fusion — BUILD NOW

- **Objective.** score(d) = Σ over rankers of 1 / (k + rank_r(d)), k = 60 (the constant from Cormack, Clarke and Büttcher 2009 [memory; the sample repo uses 60]).
- **Pseudocode.** `for r in rankings: for pos, d in enumerate(r, 1): s[d] += 1/(60 + pos)`.
- **Complexity.** O(total list length). Needs no score calibration, which is why it is the right fusion for mixed rankers.
- **Use.** Fuse BM25 on body, BM25 on headings and path, and the trigram or alias ranker now; dense later.

### 3.4 Cross-encoder rerank — BUILD LATER

Gains are real (the step from 49% to 67% failure reduction in [source 5]) but it is the reason the sample evaluation takes 2.5 s per query and needs onnxruntime. Deterministic substitutes to try first: the authority prior and per-source cap from the sample repo, plus the coverage-based packer of 1.1, which already performs a diversity-aware second pass.

### 3.5 Parent-child chunks — BUILD NOW

Index small chunks (the sample uses a 380-token target, 300–440 range, 12% overlap, heading path kept, table header repeated in continuation chunks [repo]); return the hit plus a pointer to its parent section; expand on request (`get_section`). Benefit: precise matching with on-demand context, so the default answer is small. Complexity O(1) per expansion. Measure: mean tokens returned per query; expansion rate.

### 3.6 Deduplication with SimHash and MinHash — BUILD NOW

- **Problem.** Near-identical chunks (boilerplate sections, restated rules, copied templates) waste index space and context. The sample repo filters near-duplicates at query time by word-set Jaccard [repo: `search.py: diversify`], which is O(k²) per query and repeats the work on every search.
- **SimHash (64-bit).** For each chunk, hash every 3-word shingle to 64 bits; sum +weight or −weight per bit; the sign vector is the fingerprint. Chunks within Hamming distance 3 are near-duplicates. Candidate lookup by splitting the fingerprint into 4 blocks of 16 bits and indexing each block (any pair within distance 3 shares at least one block).
- **MinHash.** k = 64 hash functions; signature = the minimum hash of the shingle set under each; the fraction of equal positions estimates Jaccard with standard error about sqrt(J(1 − J)/k), roughly 0.06 at k = 64; banding (16 bands of 4 rows) for candidate lookup.
- **Choice.** SimHash for ingest-time near-duplicate marking (one integer per chunk, exact bit operations); MinHash only if graded similarity is needed as the s_ij input to the packer.
- **Pseudocode.**

```
simhash(tokens):
    v = [0]*64
    for sh in shingles(tokens, 3):
        h = int.from_bytes(hashlib.blake2b(sh.encode(), digest_size=8).digest(), "big")
        for b in range(64): v[b] += 1 if (h >> b) & 1 else -1
    return sum(1 << b for b in range(64) if v[b] > 0)
near(a, b) = bin(a ^ b).count("1") <= 3
```

- **Complexity.** O(tokens) per chunk; lookup O(1) expected per block. Use `hashlib`, not Python's `hash()`, which is salted per process and would break determinism.
- **Action on a duplicate.** Keep the canonical copy (authority order), store the others as aliases pointing to it. Measure: share of chunks collapsed; redundancy inside packed contexts.

### 3.7 Content-addressed caching of derived artefacts — BUILD NOW

- **Problem.** Repo maps, file summaries, chunk indexes, context packs, digests are recomputed (often by a model) although their inputs did not change.
- **Rule.** key = SHA-256 of (tool name, tool version, parameters, sorted list of input content hashes). Store the artefact at `cache/<key[:2]>/<key>`. On request: compute the key (cheap), return the stored artefact on a hit.
- **Input hashes for free.** `git ls-files -s` or `git rev-parse HEAD:<path>` already gives a content hash per tracked file; no file needs to be re-read.
- **Pseudocode.**

```
cached(tool, version, params, inputs, compute):
    key = sha256(json.dumps([tool, version, params, sorted(blob_hash(p) for p in inputs)], sort_keys=True))
    path = cache_dir / key[:2] / key
    if path.exists(): return path.read_text()
    out = compute(); atomic_write(path, out); return out
```

- **Complexity.** O(number of inputs) per lookup. **Correctness condition.** The computation must be a pure function of the declared inputs; any model-generated summary is cached with the model id and prompt version in the key.
- **Benefit.** Exact, with no quality risk; the saving is the full cost of each avoided recomputation. For model-written summaries this is the difference between paying once per content change and paying once per session [inference].
- **Where the cache lives.** A cloud container is discarded, so the cache must be committed (small text artefacts) or rebuilt by deterministic scripts at session start. Decide per artefact: commit model-written summaries; rebuild indexes.
- **Measure.** Hit rate; model tokens avoided (logged at each hit as the original cost).

### 3.8 Incremental indexing by git diff — BUILD NOW

The sample ingest already skips files whose SHA-256 is unchanged and removes deleted files [repo: `ingest.py`], but it must walk and hash every file to find out. Faster: store the last indexed commit; run `git diff --name-status -z <last>..HEAD` plus `git status --porcelain -z` for uncommitted changes; re-chunk only A/M/R paths, delete D paths. Complexity O(changed files). Fallback to the full hash walk when the stored commit is unreachable (rebase, shallow clone). Measure: ingest seconds per session start; chunks re-indexed per commit.

### 3.9 PageRank repo map — BUILD NOW

- **Prior art.** Aider's repository map extracts symbol definitions and references with tree-sitter, builds a graph over files, ranks with PageRank weighted toward the files in the chat, and fits the output to a token budget (`--map-tokens`, default 1,024) [source 6, secondary write-ups; the binary-search fitting step is reported by ports and not confirmed from Aider's code].
- **Problem.** Give the agent a small, ranked outline of a repository so it reads the right files first instead of exploring by trial.
- **Objective.** Stationary distribution of a random walk on the reference graph with personalisation:

    PR = (1 − d)·v + d·Mᵀ·PR,    d = 0.85

  Nodes are files. An edge A → B with weight w exists when A references a symbol defined in B; w = count × idf(symbol), so names defined in many files (`get`, `index`) contribute little. v is uniform, or concentrated on the files named in the ticket.
- **Pseudocode.**

```
repo_map(files, focus, budget):
    defs, refs = extract_symbols(files)                  # section 3.10
    for A in files: for s in refs[A]: for B in defs_of[s]: if B != A: W[A][B] += idf[s] / len(defs_of[s])
    pr = v = personalisation(focus)
    repeat 30 times: pr = (1-d)*v + d * (Wnorm^T pr + dangling mass * v)
    rank symbols: score(def in B) = pr[B] * (1 + log(1 + inbound refs to that symbol))
    emit lines "path: kind name(signature)" in score order until budget tokens, then re-sort by path for stable output
```

- **Complexity.** O(iterations × edges); a few thousand files converge in well under a second in pure Python. Cached by 3.7 keyed on the tree hash and the focus set.
- **Benefit.** Replaces exploratory listing and reading. No number claimed; measure it. **Measure.** Files opened before the first edit; tokens spent on exploration tool results per ticket, with and without the map.

### 3.10 Symbol extraction without tree-sitter — BUILD NOW

Tiered, all standard library:
1. Python: the `ast` module gives exact definitions, imports and call names.
2. TypeScript and JavaScript: column-0 regexes for `export`, `function`, `class`, `interface`, `type`, `const X =`, and `import ... from '...'` for edges. The sample chunker already splits TS/JS by top-level declaration with regexes [repo: `chunker.py: _code_units`].
3. Markdown: headings as definitions, relative links and id mentions (`ADR-012`, `TJ-041`) as references. This makes the same PageRank work on the knowledge base, which matters for a brain that is mostly documents.
4. Anything else: a generic regex for `^\s*(def|func|fn|class|struct|interface|enum|type)\s+(\w+)`, and identifier-token overlap for references.
5. If `ctags` happens to be installed, use it; never require it.

Accuracy is lower than a parser (misses nested and dynamically created symbols, confuses same-named symbols), which PageRank tolerates because it aggregates many edges. Measure: precision and recall of definitions against `ast` on Python files as a spot check.

---

## 4. Compression

### 4.1 Safe: structural, lossless or exactly reconstructible — BUILD NOW

| Technique | What it does | Why it is safe |
|---|---|---|
| References instead of repetition | State a rule once in a card with an id; elsewhere cite the id. Delegation messages carry ids plus the two or three facts the task needs | Nothing is removed; the agent can fetch the card. Guard: a delegated agent does not inherit context, so ids must resolve through the retrieval tool [repo: CLAUDE.md §8, context starvation] |
| Tables and key-value blocks for facts | Prices, thresholds, paths, owners as rows | Same information, fewer tokens than prose, and exact matching for BM25 |
| Schema-constrained outputs | Subagents return a fixed structure (verdict, findings list with path and line, evidence, open questions) | Cuts report tokens that the lead re-reads on every later turn [repo: R-A11 F4]; makes outputs machine-checkable. Do not require a reasoning field in the schema: instructing reasoning reproduction can trigger refusals on current models [bundled `claude-api` skill, prompt-audit] |
| Deltas | Send a unified diff or "changed since checkpoint X" rather than whole files; status files as append-only logs with a compact header | Exactly reconstructible |
| Tool-result trimming by rule | Head and tail of long logs, failing tests only, `grep -c` before `grep`, line ranges on reads | Deterministic; the full output stays on disk and can be re-read |
| Stable prefix ordering | Static instructions first, volatile content last; never reorder | Not compression of content but of cost: cached reads are priced at a small fraction of input [repo: R-A11 F1] |
| Deduplication at ingest | 3.6 | Removes copies, keeps the canonical text |
| Progressive disclosure | Short always-loaded core, skills and cards loaded on demand | The sample research cites a system-prompt reduction of more than 80% from folding and deferring [repo: R-A12 F1] |

**Measure.** Always-loaded tokens at session start (both repos); tokens per delegation message; tokens per subagent report; cache-read share of input.

### 4.2 Unsafe: lossy compression of instructions — SKIP

- Token-pruning compressors (LLMLingua family) acknowledge notable drops at high ratios [source 7]. An empirical study across three models found all tested methods appeared to increase hallucination, attributed to information loss [source 7]. Compressing the question itself rather than few-shot examples reduced GSM8K accuracy to roughly 20–35% in one 2026 preprint, and another reports sharp declines on tasks that depend on structural labels [source 8; these are recent preprints returned by search and not independently verified].
- For instructions the failure is silent: a dropped "not", "only" or path changes behaviour without an error. The compressor is also a model that must be installed and run.
- Abbreviated "telegraphic" handbooks written by a model for a model are a milder form of the same risk [inference]; prefer complete sentences in rules and structural economy elsewhere.

### 4.3 Conditionally safe — BUILD LATER, with a test

- Model-written summaries of long reference material (not instructions), cached by content hash, each with a pointer to the source and a spot-check question set. Safe when the reader can always fall back to the source.
- Conversation compaction is a platform feature; treat each compaction as a cache-breaking budget event and write a checkpoint before it [repo: R-A12 F1].

---

## 5. Measurement harness (required by A28, A35, A50)

One deterministic script, run at every gate, writing a Markdown scorecard:

| Metric | Source | Why |
|---|---|---|
| Always-loaded tokens at session start | Count of both repos' loaded instruction files | The fixed tax on every session |
| Cache-adjusted tokens per accepted task, by class | Transcript meter (2.7) | Primary efficiency number |
| First-pass acceptance rate by class and arm | Review verdicts in the ledger | Guards quality while cost falls |
| Retrieval recall@5, MRR, tokens returned per query | Golden set | Retrieval quality and economy |
| Pack recall at budget, redundancy | Golden set through the packer | 1.1 |
| Makespan / lower bound, file conflicts | Scheduler logs | 1.3 |
| Review rounds per artefact, material findings by round | Ledger | 2.3 |
| Window pace, limit hits, unused percentage at reset | Governor log | 2.6 |
| Cache hit rate and tokens avoided | Cache log | 3.7 |
| Estimator MAPE and P50/P90 coverage | `accuracy` port | 2.7 |

Every claimed saving in the brain's documentation should cite a row from this scorecard with a date.

---

## 6. Suggested build order for the algorithm layer [inference]

1. Transcript meter, price table, ledger, session-start and subagent-stop hooks (everything else learns from this).
2. Content-addressed cache and git-diff incremental ingest.
3. FTS5 index with contextual prefix, RRF, parent-child, SimHash dedup; golden set and eval.
4. Context packer (greedy coverage).
5. Symbol extraction and PageRank repo map.
6. Scheduler with file locks, critical-path priority, annealing, WIP limit.
7. Burn-rate governor and enforcer states.
8. Estimator, assigner (DP), cascade rule, Thompson sampler (advisory until calibrated).
9. Review stopping rule and value-of-information calculator.
10. Scorecard.

All of these are standard-library Python; I estimate 2,500–3,500 lines with tests, on the evidence that the sample repo's payroll package is about 1,500 lines and my two prototypes are about 60 lines each [inference].

---

## 7. Things I could not verify

- Fable 5.2 prices, cache multipliers and window weighting. The sample research covers Fable 5.1 [repo: R-A11]; I did not fetch the live pricing page. No dollar figure in this report depends on it.
- Whether cloud sessions expose `rate_limits` to hooks or the status line (2.6).
- The BM25-only versus hybrid gap on a brain-style corpus (3.2). No virtual environment was available to run the sample repo's ablation.
- The exact approximation constants attributed to Khuller-Moss-Naor, Leskovec et al. and Lin-Bilmes are from memory; only the Sviridenko (1 − 1/e) result and its refinement were confirmed by today's search.
- Grover's lack of classical benefit, the p/c search-ordering optimality and the Lincoln-Petersen estimator are textbook results cited from memory.
- Several 2026 preprints on prompt compression and debate rounds came from search summaries, not from reading the papers.
- Prototype results are on synthetic instances, 20–30 seeds each. They show direction and rough size, not a guarantee on real workloads.

---

## 8. Sample-repo files read

- `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose/docs/research/R-A11-token-pricing-and-metering.md`
- `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose/docs/research/R-A12-token-budget-algorithms.md`
- `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose/payroll/payroll/` (estimator, allocator, enforcer, negotiation, accuracy, meter) and `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose/payroll/data/` (priors.json, ledger.jsonl)
- `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose/docs/hr/payroll/REPORT.md`
- `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose/orgdesign/` (selection, combine, demand, plan)
- `/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose/library/config.json`, `library/pipeline/` (search, chunker, ingest), `library/eval/last_result.json`, `library/requirements.txt`
- `/tmp/claude-0/bundled-skills/2.1.322/abe77d722f7cc0e8bbf4058a7be92fb3/claude-api/shared/prompt-audit.md` and `cost-optimization.md` (grep only)

## 9. Web sources (searched 2026-11-10)

1. Kulik, Schwartz, Shachnai, "A Refined Analysis of Submodular Greedy" (Sviridenko's (1 − 1/e) result, pair enumeration, hardness): https://arxiv.org/pdf/2102.12879
2. QUBO and knapsack evidence: "Quantum Computing Techniques for Multi-Knapsack Problems" https://arxiv.org/pdf/2301.05750 ; "Adiabatic Quantum Optimization Fails to Solve the Knapsack Problem" https://ar5iv.arxiv.org/html/2008.07456 ; "Translating Constraints into QUBOs for the Quadratic Knapsack Problem" https://www.iccs-meeting.org/archive/iccs2023/papers/140770086.pdf ; QUBO solver review https://link.springer.com/10.1038/s41598-023-32232-0
3. FrugalGPT: https://arxiv.org/abs/2305.05176v1
4. RouteLLM: https://lmsys.org/blog/2024-07-01-routellm/ ; https://arxiv.org/html/2406.18665v3
5. Anthropic, Contextual Retrieval: https://www.anthropic.com/engineering/contextual-retrieval
6. Aider repository map: https://aider.chat/2023/10/22/repomap.html ; pattern write-up https://www.agentpatterns.ai/context-engineering/repository-map-pattern/
7. LLMLingua: https://arxiv.org/pdf/2310.05736 ; "An Empirical Study on Prompt Compression for Large Language Models": https://arxiv.org/pdf/2505.00019
8. Compression failure cases (preprints, unverified): https://arxiv.org/pdf/2606.24083 ; https://arxiv.org/pdf/2603.23527 ; https://www.emergentmind.com/papers/2604.02985
9. Debate rounds: M3MAD-Bench https://arxiv.org/pdf/2601.02854 ; "A Survey of Scaling in Large Language Model Reasoning" https://arxiv.org/pdf/2504.02181 ; "Detection Without Correction" https://arxiv.org/pdf/2605.27559
10. "Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent Debate" (ICML 2025): https://icml.cc/virtual/2025/49332
11. Lin and Bilmes, "Multi-document Summarization via Budgeted Maximization of Submodular Functions" (NAACL 2010): https://aclanthology.org/N10-1134/
12. Arrazola et al., "Quantum-inspired algorithms in practice": https://ar5iv.arxiv.org/html/1905.10415 ; history of dequantisation: https://arxiv.org/pdf/2412.14703
