# HR rack template review (contract h-20261110-1e042a, ticket CB-205)

The folder is not empty: `hr/rack/` holds 100 templates (10 files of 10). `python3 bin/brain hr audit` says "rack is sound" (researcher 17, builder 48, writer 19, reviewer 15, redteam 1). Checked against hr/GUIDELINES.md (39 rows) and docs/research/round3/04-domain-methods.md (143 rows).

**Counts: present 142, wrong 30, missing 9, not checked 1 (182 rows).** Findings by severity: blocking 2, should-fix 12, minor 14.

Method: a script (scratchpad `checks.py`, `T.json`) counted words, list sizes, drift format, return-contract parts, scope parts, method lines without a reason clause, absolutes, banned wording, pronouns and paths, source paths, and pairwise similarity (Jaccard on method+drift+role+done words; difflib on method lines). Every method line, drift and done check was also read by hand. Locations are `hr/rack/<file>.jsonl:<line>`, and `M2` means method item 2. Ambiguous rubric lines get the strictest plausible reading, as the scope asked; those cases are marked "strict".

---

## 1. Missing and wrong rows (evidence)

### hr/GUIDELINES.md

| Row | Verdict | Evidence |
|---|---|---|
| G:9 `done_check`: a check that can fail | wrong | All 100 done checks contain `{check}`, but 17 researcher templates (no Bash in `.claude/agents/researcher.md:4`) and the redteam template (`premortem-redteam`, review.jsonl:6; no Bash in redteam.md:4) cannot run a command. See §3. |
| G:11 `scope_rule`: owns, does not touch, at the edge | wrong | No "does not touch" clause: build.jsonl:1, :2, :4, :9. No edge action: discovery.jsonl:8, quality-ops.jsonl:9, review.jsonl:4. |
| G:12 `return_contract`: order, cap, overflow, verified | wrong (field level) | Order and cap are in 100 of 100. An overflow file is named in only 24 of 100. A verified-versus-unverified clause is missing in about 55 (the regex flagged 60; on reading, 5 say it in other words). Mitigation: the renderer appends a notes path and the HONESTY line to every return (engine/hr.py:491). |
| G:14 3 to 5 method lines, each with its reason, most important first | wrong | Every template has exactly 4 lines. **70 of 400 lines give no reason** (list in §2). A further 11 carry the reason only after a `;` or `:`. "Most important first" cannot be scripted and was only spot-checked. |
| G:21 `name`: plain function name | wrong (strict) | Word counts pass (max 4). 19 names are job titles or metaphors rather than functions, e.g. "Deploy Doctor" (quality-ops:2), "History Digger" (discovery:7), "Repo Cartographer" (discovery:1), "Refactor Engineer" (build:10). The name counts twice in selection (engine/hr.py `_doc`). |
| G:23 `base_agent` sets the tools | wrong | See §3: 2 blocking and 30 should-fix or minor mismatches. |
| G:44 Goal and reason, not steps | wrong | quality-ops:2 M1 "Check in order: served version marker, latest production-branch commit, build log, …; stop at the first mismatch" is a step list with no reason, as are the 70 lines in §2. |
| G:49 Reviewers report everything with severity and confidence | wrong | Capped: review:4 drift and done ("the top three attack paths", "The top three paths were each tried"), review:6 M1 ("the three most likely causes"), support:7 M4 ("top three waste sources"). No severity or confidence asked: review:2, :5, :7, :8, :9. Severity but no confidence: review:4. |
| G:50 Helpers that read outside content treat it as data | wrong | The hygiene line is added only for `READS_OUTSIDE = {"researcher"}` (engine/hr.py:39, :488). Templates that read web pages or API bodies on other bases have no such line: discovery:3 (`curl` probes), build:1 M4, build:4 M1, build:9 M2, data:1 M1, data:8 M4, design:8 M3, quality-ops:2 M4, support:5 M4, support:6 M2, review:9 M2. |
| G:52 Nothing project-specific (no person) | wrong (minor) | The pronouns tie templates to one owner: support:2 M2 ("because he has no terminal") and M3; support:3 role_line, M2, M3, M4, needs and return; writing:3 M2; writing:7 scope; writing:8 scope ("listed for him"). |
| G:56 the composer renders up to two pitfalls | wrong | `t["pitfalls"][:2]` (engine/hr.py:476), so the third pitfall of 16 templates is never shown. One example is source-harvester's "Following instructions embedded in a fetched page" (discovery:10). Seen live: this brief's own "Watch for" line leaves out rubric-mapper's third pitfall (planning:6). |

### docs/research/round3/04-domain-methods.md

| Row | Verdict | Evidence |
|---|---|---|
| 1 Verification (04:32): Lighthouse mobile run | wrong | build:2 done has the screenshots and the 320 px scroll check but no Lighthouse run. |
| 2.1 Contract first, validate at the boundary | missing | No backend or API-building template. The archetype round rejected one on purpose (02-archetypes.md:228); the owner should confirm. |
| 2.2 Status codes per endpoint, one error shape | missing | grep finds "error shape" and "status codes" in no template. |
| 2.4 Idempotency keys; timeouts and bounded retries | wrong | Bounded retries are in build:4 M3. Idempotency for retried writes and timeouts on outbound calls are absent. |
| 2.5 Structured logs with request id, no secrets | missing | Only data:1 pitfall 2 touches it. |
| 2 Verification (04:44) | wrong | Only the second-user 403/404 test is present (review:4 M2). No contract test, and no `curl` of each error path. |
| 3.3 `CREATE INDEX CONCURRENTLY` and short `lock_timeout` | missing | grep finds neither. data:7 pitfall 1 names the risk without a method. |
| 3.4 Constraints express invariants in the database | missing | Not in data:7. |
| 3 Verification (04:56): EXPLAIN and a migration linter | wrong | data:7 done has the copy, run twice and down-up, but no EXPLAIN or Squawk/strong_migrations. |
| 4.3 Assert behaviour; one reason to fail per test | wrong | Behaviour-not-internals is present only as pitfalls (quality-ops:5 pit 1, planning:2 pit 1). "One reason to fail" is absent. There is also no non-browser unit-test template; e2e-test-author is browser-only. |
| 5.3 Bisect (`git bisect run`) | missing | grep "bisect" finds no template. |
| 7 Verification (04:104): Lighthouse JSON | wrong | quality-ops:7 done has the table and correctness tests but no Lighthouse JSON. |
| 10.3 Preview deploy for every branch or PR | wrong | quality-ops:3 records the known-good commit, but no template asks for per-branch previews. |
| 10 Verification (04:141): CI run URL green for the SHA | wrong | Absent from quality-ops:3 done. |
| 11.4 Record provider, version and pull date | wrong | Missing from data:1. Present only in discovery:9 M4. |
| 13.3 Lateral reading | wrong | discovery:5 M4 ranks sources but has no lateral-reading step. |
| 13 Verification (04:178): a *different* helper checks 5 claims | wrong | review:2 done: "five supported claims were reopened" by the same helper. |
| 15.1 Brief includes a sample paragraph in the target voice | wrong | writing:1 needs "reader, purpose and voice"; no sample is asked for. |
| 15 Verification (04:203): cold read by a fresh helper | wrong | Absent from writing:1 and writing:2. |
| 18 Verification (04:239): count of confirmed versus rejected findings recorded | wrong | Absent from review:3. |
| 19.5 Name what is out of scope | missing | No planning template asks for it. |
| 19 Verification (04:251): a fresh helper starts step 1 without questions | wrong | Absent. planning:2 done has the traceability table only. |
| 20.4 Match freedom to fragility | missing | Not in writing:10. |
| 20.6 Test on Haiku, Sonnet and Opus | wrong | writing:10 drift removes legacy scaffolding, but there is no cross-model test. |
| Cross-cutting 2 (04:274): a check whose output is required | wrong | The same 18 templates as G:9. |
| Cross-cutting 9 (04:281): tag each claim sourced, measured or estimated | wrong | Present in roughly 15 templates (e.g. discovery:4, :5, planning:4, quality-ops:7, writing:7), absent in most builders and writers. |
| Cross-cutting 10 (04:282): stop condition and budget | missing (rubric conflict) | No template states a stop condition or budget. GUIDELINES:48 forbids token numbers in template text, and the wage lives in the contract. Owner to rule. |
| Don't 3 (04:289): "only report high severity" in finder roles | wrong | The same caps as G:49 (review:4, review:6, support:7). |

---

## 2. Findings by category (severity, confidence, proposed fix)

### 2a. Method lines with no reason (should-fix as a set; each line minor; confidence high)
Fix for every line: add a "because" or "so" clause naming the failure it prevents, or drop the line.

- build: :2 M3, :4 M3, :7 M4
- data: :3 M2, :4 M4, :8 M3
- design: :1 M4, :3 M3, :4 M3, :5 M3, :5 M4, :6 M3, :7 M4, :8 M3, :9 M3
- discovery: :5 M4, :8 M4
- language: :1 M2, :2 M3, :2 M4, :4 M2, :4 M4, :7 M4, :8 M3, :8 M4
- planning: :4 M3, :5 M2, :5 M4, :6 M4, :8 M3, :9 M4, :10 M3
- quality-ops: :1 M3, :2 M1, :2 M2, :5 M4, :6 M4, :8 M1, :8 M4, :10 M3, :10 M4
- review: :1 M2, :2 M3, :3 M3, :4 M4, :5 M3, :5 M4, :6 M2, :6 M4, :7 M1, :7 M3, :8 M3, :8 M4, :9 M3, :9 M4, :10 M3, :10 M4
- support: :3 M3, :5 M3, :5 M4, :6 M4, :7 M4, :8 M3, :9 M4
- writing: :3 M4, :4 M3, :5 M4, :7 M4, :8 M3, :9 M4

That is 70 lines. The reason is implicit, after `;` or `:`, in 11 more (minor): build:3 M4, build:10 M4, data:1 M3, data:2 M2, data:3 M4, language:3 M4, language:5 M4, language:9 M3, planning:4 M4, quality-ops:7 M4, support:7 M3. The audit does not check method reasons; it checks only absolutes (engine/hr.py validate_template).

### 2b. Base agents whose tools cannot do the method
Tool sets: researcher has Read, Grep, Glob, WebSearch, WebFetch, Write (no Bash). Reviewer and builder have Bash but no web tools. Redteam has neither Bash nor web. **No base agent has both web and Bash.**

- **BLOCKING** planning:8 migration-planner (researcher). M2 builds the parity checklist "from the running system", and pitfall 1 warns against "A parity list built from docs instead of the running system". A researcher can only read docs and pages. Fix: `base_agent: reviewer`, `role: researcher`. Confidence high.
- **BLOCKING** discovery:9 dataset-source-finder (researcher). M1 and done require a fetched sample with "fields, units, date range and missing values". WebFetch returns model-processed text, and there is no Bash to profile it. Fix: reviewer with role researcher, sampling with `curl` and a profiling script. Confidence medium-high.
- should-fix: 17 researcher templates put `{check} passes`, `result recorded` or `is met` in done, and none can run a command: discovery:2, :4, :5, :6, :8, :9, :10; planning:1, :3, :5, :8, :9, :10; review:2, :8; writing:8, :9. Fix: replace `{check}` with an inspection or quote check in these templates, or have the composer render "the lead runs `{check}`". Confidence high.
- should-fix: review:6 premortem-redteam done "{check} result recorded", but redteam has no Bash. Fix: drop `{check}`. Confidence high.
- should-fix: discovery:5 done "a link check over the memo passes", with no Bash to run one. Fix: "each URL re-fetched with WebFetch". Confidence medium.
- should-fix: builders told to read current web docs or pricing, with no web tool and only `curl` through Bash: build:1 M4, build:4 M1, build:9 M2, data:1 M1, data:8 M4, design:8 M3, quality-ops:2 M4, support:5 M4, support:6 M2. Fix: add `needs: research memo path` (support:6 already does this) or fetch through a docs-snapshotter hire first. Confidence medium, since `curl` may suffice.
- should-fix: writing:10 done "evaluations ran with and without the file". A writer has no Agent tool to run a model on the tasks. Fix: make the evaluations a separate eval-regression-runner hire. Confidence medium-low (`claude -p` through Bash was not tested).
- minor: language:9 M4 and design:10 M4 assume a "fresh reader" or a supplied search result. They are hedged with "where possible" and "unless supplied". Fix: keep the hedge and add "else mark unchecked".
- minor: review:9 M2 reads licence texts that are usually online, and review:4 M3 checks registries; the reviewer has no web tool. Fix: name `curl` or ask for a licences input.
- minor: planning:1 done "count of request sentences" and planning:9 "recomputing the formula reproduces the order" must be done by hand without Bash. Fix: reword to "counted" without "by script".

### 2c. Unsourced or mis-sourced numbers and claims
- should-fix: language:1 drift asserts the default is "neutral or Latin American vocabulary". The source says the opposite is unproven: 04:217 "drift risk toward es-ES is not established", and LLMs favour Peninsular forms. Fix: reword as a risk to check, not an observed default. Confidence medium-high.
- should-fix: review:6 "three most likely causes" contradicts its own cited source `.claude/agents/redteam.md:12` ("about five concrete failure modes"). Fix: use "about five" or cite the archetype. Confidence high.
- minor: design:2 M1 "three to five options", but the source says "3-4" (04:223) and design:1 drift says "three or four". Fix: "three or four".
- minor: review:4, review:6 and support:7 caps of "three" trace only to archetypes.json `what_it_adds`, which cites no evidence. Fix: as in G:49.
- minor: discovery:10 done "three sampled passages" has no source. Fix: cite or say "a sample".
- minor, unsourced factual claims: build:3 M4 (iOS storage eviction, archetypes.json only); design:7 M2 ("animating width, top or margin forces layout every frame", in no 04 area); design:6 M2 (EXIF rotation and GPS). Fix: add an MDN, WebKit or web.dev source.
- minor: drift lines asserting a model default in areas where 04 records "Claude-specific: none documented" (areas 3, 7, 10, 11, 14 and 16; 04:58, :106, :143, :155, :193, :217): data:7, quality-ops:7, quality-ops:3, data:1, writing:8, language:2. Fix: label these as observed agent failure modes or estimates. Confidence medium.
- Sourced and checked, no action: 390/320/1440 px, 4.5:1 and 3:1, 44-point (04 areas 1 and 8); LCP/INP/CLS (04:102); ≥5 runs (04:104); about 1,500 words (playbooks/knowledge.md:19); about 80% cache (method/efficiency.md:9); at most four helpers and three questions (CLAUDE.md:23, :25); five re-checked claims (04:178).

### 2d. Thin-sourced data templates (requested list)
Each cites only 04 area 11 or 12, playbooks/data.md and archetypes.json. archetypes.json has no citations, and none of these areas covers the claims below. Severity should-fix, confidence high that no source in the repo supports them.

- **statistical-tester (data:3).** Needs a source for: pre-registering the test from the design (M1); checking assumptions and switching to an assumption-free method (M2); effect size with interval beside p, and multiple-comparison correction (M3); and the drift "run several tests and report the one that came out significant" as a model default. Candidates: ASA statement on p-values (2016); a p-hacking or forking-paths reference.
- **spreadsheet-engineer (data:5).** Needs a source for: "formulas written by a script carry no computed result until then" (M3; this is library behaviour, e.g. openpyxl docs); check cells that must equal zero (M2); and the drift "computing in code and pasting values" as a model default.
- **biodiversity-data-integrator (data:8).** Needs a source for: taxonomic backbone resolution and "synonyms otherwise split one species in two" (M1, GBIF backbone docs); coordinate uncertainty and basis of record (M2, Darwin Core terms); an identification score as a candidate to check against occurrences (M3, PlantNet or eBird docs); "attribution duties travel with the data" (M4, GBIF licence docs); and the drift "trusting the top identification result" as a model default.
- **ml-experiment-runner (data:9).** Needs a source for: a split grouped by entity or time to prevent leakage (M1, e.g. Kapoor and Narayanan on leakage); "a high score can still lose to doing nothing" with a trivial baseline (M2); touching the test set once (M4); and the drift "best of many runs … scored on data used for tuning" as a model default.
- **rag-index-builder (data:10).** It cites no 04 area at all. Needs a source for: a golden set written first and gating on recall@k (M1, M4); structural chunking with parent pointers (M2); "exact names and codes are missed by embeddings alone" for hybrid search (M3, e.g. Anthropic's contextual-retrieval post); and the drift "fixed-size chunks, vector search only" as a model default.

### 2e. Near-duplicate pairs (minor unless noted; selection checked with `hr.select(..., near=True)`)
- should-fix: legal-citation-verifier (review:8) and legal-research-analyst (writing:8). Body Jaccard 0.315, keyword Jaccard 0.32, M1 nearly identical (difflib 0.77). For "is it legal to sublet my flat under Spanish law" the scores were 0.80 against 0.65. Fix: drop the shared keywords (BOE, EUR-Lex, jurisprudencia) from one, or merge them.
- build-failure-diagnoser (quality-ops:1) and bug-reproducer (quality-ops:10): body 0.30, M3 at 0.80. Selection separated them (1.0 against 0.22). Fix: keep both and reword the shared M3 once.
- api-integration-builder (build:4) and data-pipeline-builder (data:1): body 0.28, M3 at 0.60. The API probe query scored 0.63 for both data-pipeline and api-live-prober. Fix: move the backoff line into one template and refer to it.
- phone-first-ui-builder (build:2) M2 and design-system-builder (design:5) M1 (0.66), and build:2 with design-brief-author (body 0.25). Fix: build:2 should take its tokens from the design system, not restate them.
- design-critic (design:4) M4 and code-reviewer (review:3) M4 (0.67); document-producer (writing:5) M2 and deck-builder (writing:6) M3 (0.62); es-original-writer M4 and long-form-drafter M3 (0.70). Shared wording only; no action needed.
- schema-migration-engineer (data:7) and migration-planner (planning:8): body 0.20. "migrate the database to Postgres" picks the builder (1.0 against 0.62), so the plan step is skipped for a one-way-door task. Fix: add "plan" or "rehearse" keywords to the planner, or have data:7 ask for the plan.

### 2f. Job titles with generic advice (minor; confidence low-medium)
- writing:7 strategy-memo-writer: M1 "Open with the recommendation" and M4 "Match length to the decision" are advice the model already follows. Fix: replace M4 with a measurable check (e.g. a one-page decision section by word count).
- planning:9 backlog-prioritiser: M1 to M4 are standard prioritisation advice, with no drift backed by a source (cites plan DoD and area 19 only). Fix: ground the drift in an observed failure or retire the template.
- language:3 copy-editor M1 to M3 and language:10 transcript-cleaner M4 ("Remove fillers, false starts and repetitions") are generic. Fix: keep the number-parity done checks and cut the generic lines.
- writing:6 deck-builder M1 and M2 (claim titles, speaker notes) are standard advice; its M3 and M4 render checks earn the template. Fix: replace M2 with a measurable text limit per slide.
- Names (G:21): "Deploy Doctor", "History Digger", "Repo Cartographer", "Premortem Red Team", and the "Engineer" and "Analyst" titles. Fix: function names such as "Diagnose stale deploy" or "Find earlier work".

### 2g. Other defects
- should-fix: when the lead gives no `--check`, the whole template `done_check` is replaced by a generic line (engine/hr.py:477-483). The template-specific evidence (e.g. design:1 contrast computation, review:2 claim reopening) is lost exactly in the research and review hires that usually have no command. Fix: render the done check with `{check}` removed. Confidence high.
- should-fix: the third pitfall is never rendered in 16 templates (G:56). Fix: trim to two, or render three. Confidence high.
- minor: discovery:7 M2 and support:1, :8, :9, :10 name brain internals ("brain recall", "brain's validate command"). This is arguably allowed for the brain's own work; owner to rule.
- minor: the audit does not enforce method reasons, the return-contract parts, the scope parts or the drift format. That is why G:11, G:12 and G:14 pass the audit and fail here.
- minor: GUIDELINES:7 cites "three or fewer modules doing best". The templates render 4 method lines, a drift and 2 pitfalls. Owner to confirm whether "module" means a method line. Confidence low.

---

## 3. Full table

### hr/GUIDELINES.md (order of the file)
| # | Rubric line | Verdict | Evidence |
|---|---|---|---|
| 1 | :3 audit enforces limits | present | `brain hr audit` reports "rack is sound" |
| 2 | :7 earns its place; no persona; curated guidance | present | persona regex finds 0 hits |
| 3 | :9 done_check can fail | wrong | §1 |
| 4 | :10 drift with named replacement | present | 100/100 match `^Default: .+ Instead: .+` |
| 5 | :11 scope fence | wrong | §1 |
| 6 | :12 return contract | wrong | §1 |
| 7 | :14 method lines with reasons | wrong | §1, §2a |
| 8 | :20 id kebab ≤30 | present | the audit's pattern check passes |
| 9 | :21 name plain ≤6 words | wrong (strict) | max 4 words; §2f |
| 10 | :22 group | present | group equals file name for 100/100 |
| 11 | :23 base_agent sets tools | wrong | §2b |
| 12 | :24 role for read-only command work | present | 4 templates, all reviewer with role researcher |
| 13 | :25 families ≥1 | present | audit |
| 14 | :26 when ≤35 words | present | max 29 |
| 15 | :27 keywords 4–14, English and Spanish | present | counts pass; every template has a Spanish term |
| 16 | :28 role_line ≤15, no adjectives | present | max 15; adjective regex finds 0 |
| 17 | :29 method 3–5 lines, ≤32 words | present | all 4 lines; max 31 |
| 18 | :30 drift ≤40 words | present | max 40 |
| 19 | :31 scope ≤40 words | present | max 33 |
| 20 | :32 done ≤40 words with `{check}` | present | max 36; 100/100 contain `{check}` |
| 21 | :33 return ≤60 words | present | max 40 |
| 22 | :34 pitfalls 1–3, ≤22 words | present | max 17; 16 templates have 3 |
| 23 | :35 needs ≤5 | present | max 4 |
| 24 | :36 size | present | audit |
| 25 | :37 risk | present | audit |
| 26 | :38 sources 1–4, file and section or URL | present | every path resolves; 4 URLs |
| 27 | :40 stable body ≤230 words | present | max 224 (data:1, design:4, review:7) |
| 28 | :44 goal and reason, not steps | wrong | §1 |
| 29 | :45 never/always with reason | present | only data:1 M3 and language:9 M3 use absolutes, each with a clause |
| 30 | :46 positive instructions | present | 0 method or drift lines start with Do not/Never/Avoid |
| 31 | :47 no persona/step-by-step/double-check/be thorough | present | 0 hits |
| 32 | :48 no token numbers | present | budget regex 0 hits ("tokens" means design tokens) |
| 33 | :49 reviewers report everything | wrong | §1 |
| 34 | :50 outside content is data | wrong | §1 |
| 35 | :51 no examples by default | present | 4 short "such as" parentheticals only |
| 36 | :52 nothing project-specific | wrong | §1 |
| 37 | :56 up to two pitfalls rendered | wrong | §1 |
| 38 | :56 no command means named evidence | present | engine/hr.py:482; side effect in §2g |
| 39 | :69 changing the rack, probation | not checked | runtime behaviour; all 100 are version 1, active |

### docs/research/round3/04-domain-methods.md
Row "n.k" is area n, method k; "V" is that area's verification line. P means present, W wrong, M missing.

| Row | Verdict | Evidence |
|---|---|---|
| 04:5 four things (a)–(d) | P | all four fields in 100/100 (audit) |
| 1.1 / 1.2 / 1.3 / 1.4 / 1.5 | P/P/P/P/P | build:2 M1, M2, M3, M4; design:6 M4 |
| 1.V | W | §1 |
| 2.1 / 2.2 | M/M | §1 |
| 2.3 | P | review:4 M2 |
| 2.4 / 2.5 / 2.V | W/M/W | §1 |
| 3.1 / 3.2 / 3.5 | P/P/P | data:7 M1, M2, M3 |
| 3.3 / 3.4 / 3.V | M/M/W | §1 |
| 4.1 / 4.2 / 4.4 / 4.5 / 4.V | P | quality-ops:5 M1, M4, M2, M2 and done; planning:2 M2, M3 |
| 4.3 | W | §1 |
| 5.1 / 5.2 / 5.4 / 5.5 / 5.V | P | quality-ops:10 M1, M3, M4, return, done; quality-ops:1 M3 |
| 5.3 | M | §1 |
| 6.1–6.5, 6.V | P×6 | build:10 M1, M2, M3, needs ("stop condition"), M4, done |
| 7.1–7.5 | P×5 | quality-ops:7 M1–M4, done ("quiet machine") |
| 7.V | W | §1 |
| 8.1–8.5, 8.V | P×6 | quality-ops:8 M1, M3, M2, M4, M1; done; tap size in design:4 M3 and build:2 M3 |
| 9.1–9.5, 9.V | P×6 | review:4 M3, M1, M3; review:5 M1; review:4 M4 and done |
| 10.1 / 10.2 / 10.4 / 10.5 / 10.6 | P | build:1 M1, M3; quality-ops:3 M1, M2, M4; quality-ops:4 M2; quality-ops:2 M3 |
| 10.3 / 10.V | W/W | §1 |
| 11.1 / 11.2 / 11.3 / 11.5 / 11.V | P | data:1 M1, M2, M3; build:4 M2; data:1 done |
| 11.4 | W | §1 |
| 12.1–12.5, 12.V | P×6 | data:2 M1, M2, M3; data:4 M2; data:2 M4 and done; data:4 done |
| 13.1 / 13.2 / 13.4 / 13.5 / 13.6 | P | discovery:5 M1, M2, M4, M3, done; review:2 |
| 13.3 / 13.V | W/W | §1 |
| 14.1–14.5, 14.V | P×6 | writing:8 M1, M2, M2, M4, M3, done; review:8 M3 |
| 15.2 / 15.3 / 15.4 / 15.5 | P | writing:1 M1/M2, M3; language:3 M1; writing:1 done |
| 15.1 / 15.V | W/W | §1 |
| 16.1–16.5, 16.V | P×6 | language:1 M1, M2; language:5 M4, M1; language:6 M3; done lines |
| 17.1–17.5, 17.V | P×6 | design:4 M2; design:1 drift and design:2 M1/M3 (3–5 deviation, §2c); build:2 drift; design:4 M1, M4, done |
| 18.1–18.5 | P×5 | review:3 M1, M4, M3, M2, scope |
| 18.V | W | §1 |
| 19.1 / 19.2 / 19.3 / 19.4 | P | planning:1 M1/M2; planning:3 M1/M2; planning:5 M4, planning:8 M1; full spec rendered by the engine |
| 19.5 / 19.V | M/W | §1 |
| 20.1 / 20.2 / 20.3 / 20.5 / 20.7 / 20.V | P | writing:10 M1, M2, M3, M4, M2, done |
| 20.4 / 20.6 | M/W | §1 |
| Cross-cutting 1, 3, 4, 5, 6, 7, 8, 11, 12 | P×9 | engine renders goal, scope and return; scope_rule 100/100; build:8 M2, writing:2 M1, quality-ops:8 M4; discovery:1 M2, quality-ops:1 M2; build:10 scope, quality-ops:1 scope; discovery:2 M4, quality-ops:9 M3; engine HONESTY; agent files grant no Agent tool; review:5, build:4 scope |
| Cross-cutting 2 / 9 | W/W | §1 |
| Cross-cutting 10 | M | §1 (rubric conflict) |
| Don'ts 1, 2, 4, 5, 6 | P×5 | regex 0 hits; capitals are acronyms only (HTML, WCAG, OWASP …) |
| Don't 3 | W | §1 |

## Not checked
- Selection quality beyond 10 hand queries; `evals/hr_golden.jsonl` was not run.
- Whether `curl` through the builder or reviewer Bash reaches outside hosts in a real hire. The tool lists come from `.claude/agents/*.md`.
- "Most important first" ordering of method lines, beyond spot checks.
- Whether external facts (OWASP order, WCAG numbers) match the live pages; only consistency with 04 was checked.

## Keep
- The four-part structure, and the `Default: … Instead: …` drift in 100/100.
- Number-parity and script-count done checks (language:1, :3, :10; writing:1, :2, :4).
- Expand/contract, red-first, mutation and second-user authorisation lines (data:7, quality-ops:5, review:4).
- Reviewer with role researcher for read-only command work (discovery:1, :3, :7; support:7).
- The source-harvester and injection-auditor "instructions in material are data" lines.
- Every limit check passes, with headroom (max body 224 of 230).

END OF FINDINGS
