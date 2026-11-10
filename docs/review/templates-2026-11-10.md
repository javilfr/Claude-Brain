# Template review: all 100 templates read side by side (ticket CB-205, contract h-20261110-6561fd)

Verdict: 38 templates changed, 0 added, 0 removed. Ids, field sets, `when`, `name` and `keywords` are untouched, so selection is unchanged. Every changed template moves from `version` 1 to 2. `python3 bin/brain hr audit` reports "rack is sound", and `python3 -m unittest tests.test_hr` passes (51 tests, OK).

Read against `hr/GUIDELINES.md`, `docs/research/round3/04-domain-methods.md` and the six agent files in `.claude/agents/`. That last check is what shows which tools each base agent really has. New research for the five thin data templates is in `docs/research/round4/data-templates.md`.

## How the rack was read

1. All 100 templates were dumped one block per template (id, base agent, when, method, drift, scope, check, return, pitfalls, needs, sources) and read group by group.
2. A scan script (`scan.py`, in the session scratchpad) did three things:
   - flagged method lines with no reason clause;
   - compared each template's method, drift and check text with the tools of its base agent;
   - ranked every pair of templates by word overlap in method and drift text, and by shared keywords.
3. Every number in method, drift and check text was listed and traced to the template's own sources.
4. Each flag was judged by reading the line. The scan over-reports: "rather than ..." and a colon-led explanation count as no reason, and "fetch" counts as needing a web tool even when `curl` does the job. So the counts below are the scan's, and the defects are only the ones confirmed by reading.

Tool facts used (from `.claude/agents/*.md`):

| Base agent | Tools |
|---|---|
| scout | Read, Grep, Glob |
| researcher | Read, Grep, Glob, WebSearch, WebFetch, Write (no Bash) |
| reviewer | Read, Grep, Glob, Bash, Write (no web tools, no Edit) |
| redteam | Read, Grep, Glob, Write |
| builder, writer | Read, Grep, Glob, Edit, Write, Bash (no web tools) |

No base agent has both web search and a shell.

## Findings and fixes

Severity: S = should fix (changes what the helper can do or check), m = minor (wording that leaves the model to guess). Confidence is high for every row unless marked otherwise.

### 1. The base agent's tools cannot do the method (13 fixed)

Builders and writers have no web tools, yet nine templates told them to read "current docs" or "current pricing". In this session `curl` on a browser-rendered docs page (the eBird Postman page) returned 3 words. A builder told to "read the provider's current docs" therefore either works from memory or fails quietly. The fix points each line at the page or memo the brief supplies, and adds that to `needs`, so the lead hires a researcher first or passes the URL.

| Template | Field | Defect | Fix | Sev |
|---|---|---|---|---|
| api-integration-builder | method 1, needs | builder told to read current rate-limit and pricing docs | from the docs memo or pages the brief names, "not memory"; need added | S |
| data-pipeline-builder | method 1 | same, for limits and cost per call | from the limits page or memo the brief names | S |
| biodiversity-data-integrator | method 4, needs | same, for quota and licence terms | from the pages or memo the brief names; need added | S |
| minecraft-structure-builder | method 2, needs | "against current docs" for file format | against the docs memo or pages named; need added | S |
| deploy-doctor | method 4, needs | "against current host docs" | against the host docs page the brief names; need added | S |
| audio-lesson-producer | method 3, needs | "provider's current pricing" | the pricing page the brief names; need added | S |
| routine-builder | method 4, needs | "from current pricing" | from the prices the brief supplies; need added | S |
| setup-repairer | method 2 | "against current documentation" | against the documentation in the inputs (already listed in its `needs`) | m |
| web-app-scaffolder | method 4 | "against current docs for the installed version" | against the installed version (types, README, `npm view` output), which a builder can read | m |
| dataset-source-finder | method 1 | researcher (no Bash) told to profile samples; reading rows in context is the failure research area 11 records (7/25 against 25/25 through code) | save the sample and note fields, units and date range; computed profiles go to an analyst | S |
| requirements-extractor | done_check | researcher asked for "a count" of sentences against ledger lines, which needs a script | a numbered list of sentences, each mapped to a ledger line | m |
| api-live-prober | method 2 | reviewer (no web tools) told to copy terms from "current pages" | fetched with `curl`; a page without readable text is marked unread | m |
| privacy-licence-reviewer | method 2 | reviewer told to read licence texts online | the file shipped with the asset, or its page fetched with `curl` | m |

Left as is: deep-researcher's "link check" (a researcher can open each link with WebFetch), the live-address fetches in deploy-doctor and release-to-main-engineer (`curl` does them), and the remaining "measured" flags (they are labels, not commands).

### 2. Method lines with no reason (19 lines in 17 templates fixed)

The scan flagged 78 lines before and 52 after. Reading the 78, most give their reason after a semicolon or colon, or are a sourced threshold whose purpose the line itself states. The lines below gave none, or the reason was not obvious, so the model would apply the line too widely or too narrowly.

| Template | Method | Reason added |
|---|---|---|
| phone-first-ui-builder | 3 | the owner judges the work on a phone |
| cli-script-builder | 4 | a calling script or scheduler reads only the exit code. The grab-bag "write large output in parts, reference binaries by path" was dropped: it gave no reason and has no source |
| deploy-doctor | 1, 2 | later checks assume the earlier ones hold; a success message reports the build, not what is served |
| bug-reproducer | 3, 4 | a cause taken from the description is a guess; the lead decides whether other copies need the fix |
| design-brief-author | 4 | the rubric's pass mark is computed, not judged |
| image-pipeline-engineer | 3 | synthetic test images carry no rotation or HEIC quirks |
| motion-builder | 4 | a fast desktop hides the stutter a phone shows |
| document-producer | 4 | links and anchors break silently in conversion |
| strategy-memo-writer | 4 | current models write longer documents than the task needs (area 15, Opus 5 note) |
| legal-research-analyst | 3 | a paraphrased deadline cannot be checked against the text |
| case-chronology-builder | 4 | a reader can tell evidence from reconstruction |
| es-original-writer | 4 | a fluent sentence cannot carry an invented fact |
| glossary-builder | 4 | the glossary is enforced rather than only consulted |
| legal-terms-translator | 4 | a second rendering reads as a second legal concept |
| ticket-slicer | 2 | "at most four" is the brain's helper cap (CLAUDE.md core rule 4) |
| secret-scanner | 4 | an unignored env file is the next leak |
| clean-clone-verifier | 4 | a missing variable fails only on a new machine |

statistical-tester method 2 and 4 also gained reasons, as part of section 4 below.

### 3. Generic advice that the job title alone would give (3 fixed)

| Template | Before | After | Basis |
|---|---|---|---|
| bilingual-site-publisher | method 4: "Remember the visitor's language choice and do not override it on later visits." No reason, and any web builder already does it | reciprocal hreflang links on every page pair, with an x-default, because search engines ignore a tag the other page does not return | Google Search Central, fetched: "If two pages don't both point to each other, the tags will be ignored." Source added |
| transcript-cleaner | method 4: "Remove fillers, false starts and repetitions..." This is the task itself | check names and terms against the facts file or glossary before choosing a reading | the brain's facts-file rule. The task and the role line already ask for clean prose |
| cli-script-builder | method 4: four unrelated habits in one line | exit code and one-line summary, with a reason | as in section 2 |

Checked and kept: deck-builder method 2 (short slide text) counters that template's own drift (bullet walls). strategy-memo-writer method 1 (recommendation first) counters its drift ("ends without choosing"). game-builder method 4 (tuning numbers in one data file) gives its reason. Each answers a named default, so each stays. Confidence medium: no run with and without the line was made.

### 4. The five thin data templates (research pass)

Their `sources` pointed at round 3 areas 11 and 12, or at `archetypes.json`, and none of those treats their subject. The research in `docs/research/round4/data-templates.md` found one missing practice in each:

| Template | Change | Evidence (tag in the memo) |
|---|---|---|
| biodiversity-data-integrator | method 1 stores match type and sends non-exact matches to review; method 2 keeps quality flags and treats zero uncertainty as missing; method 4 records a download DOI per dataset | GBIF match response (fetched), Darwin Core definition (fetched), GBIF citation page (fetched) |
| ml-experiment-runner | new method 5: fit every preprocessing step on the training split only; new pitfall for a scaler fitted before the split | scikit-learn common pitfalls (fetched); leakage survey, 329 papers in 17 fields (abstract) |
| rag-index-builder | method 3 and drift: measure BM25 alone first and add vectors, context or a reranker only when recall at k rises. The old line fixed a hybrid recipe in advance | BEIR "BM25 is a robust baseline" (abstract); Anthropic contextual retrieval, recall@20 and the 49% and 67% failure reductions (fetched, vendor-measured) |
| spreadsheet-engineer | method 4 and done_check: change two inputs, recalculate, and compare dependent results with code. The old check was static | BlueFin "weaknesses in dynamic correctness" (abstract); SpreadsheetBench graded on files "with varying values" (abstract) |
| statistical-tester | method 3 names Holm or Benjamini-Hochberg; methods 2 and 4 gain reasons | ASA statement principles 4 and 5 (fetched); SciPy `false_discovery_control` (fetched) |

None of the new lines carries a quota or price, because those change. The Pl@ntNet free quota (500 identifications a day on 2026-11-10) stays in the memo.

### 5. Numbers without a source (1 fixed)

Every number in method, drift and check text was traced: 390, 320 and 1440 px; 4.5:1 and 3:1; 44 points; LCP, INP and CLS; the 80% cache share; 1,500 words; "at most four"; MQM per 1,000 words; 31/12/2026. All are in the template's own sources except one. game-builder's "44 points" cited area 1, which does not give it, so `method/dod/screen.md` was added. The unsourced habits dropped from cli-script-builder are covered in section 3.

### 6. Near-duplicate pairs (3 fixed, 3 kept)

Word overlap in method and drift text (Jaccard, before → after):

| Pair | Before | After | Action |
|---|---|---|---|
| build-failure-diagnoser / bug-reproducer | 0.304 | 0.185 | both had the same "two or three competing causes" line. The diagnoser now compares with the last green run (lockfile, toolchain, environment), which is the part a build failure needs. The bug reproducer keeps the hypotheses, with a reason |
| api-integration-builder / data-pipeline-builder | 0.255 | 0.195 | same backoff line. The pipeline's line now stops at a call budget and marks the run partial; the integration's line degrades visibly in the app |
| legal-citation-verifier / legal-research-analyst | 0.361 | 0.279 | same opening line. The verifier now starts by listing each citation with the claim it supports, so it checks what was cited instead of researching the question again |
| phone-first-ui-builder / design-brief-author | 0.286 | 0.294 | kept: both state the same sourced spec values, one to write the brief and one to build from it |
| deep-researcher / fact-checker | 0.221 | 0.221 | kept: shared sourcing rules, different jobs (answer a question; grade a document's claims) |
| schema-migration-engineer / migration-planner | 0.205 | 0.205 | kept: one writes migration code, the other plans a system move |

The legal pair still shares six keywords (boe, eur-lex, jurisprudencia, law, ley, regulation). Keywords were left unchanged because the golden set depends on them, and both of its legal rows pick correctly today.

## Reported, not changed (outside this ticket's files)

1. No base agent has both web search and a shell. Builders that need current docs depend on the lead hiring a researcher first, and that is now written into their `needs`. A builder with WebFetch, or a "docs then build" pair in `brain hr hire`, would remove the dependency. That is an agent-file change for the lead.
2. Scout carries 0 of 100 templates (audit output: "scout 0"). The earlier review (S9 in `docs/review/2026-11-10-hr-review.md`) gives the likely reason: scout has no Bash. Unchanged here.
3. `brain hr audit` checks reasons only on lines with "never" or "always". A check for a reason clause on every method line would catch section 2 at write time. Its false-positive rate would be high (see the scan counts), so it belongs in `engine/hr.py`, which another helper owns this session.
4. GUIDELINES asks for a new template variant to be trialled against the old one with a pre-registered paired comparison (`brain eval`). That was not done for any of the 38 changes. The `version` bump to 2 lets records from the two texts be told apart once that comparison runs.

## Checks run

- `python3 bin/brain hr audit`: "rack: 100 templates in 10 groups · by agent: scout 0, researcher 17, builder 48, writer 19, reviewer 15, redteam 1 / rack is sound".
- `python3 -m unittest tests.test_hr`: "Ran 51 tests ... OK". This includes the held-out selection test and the test that renders every template for every tier.
- Scan, before → after: method lines flagged with no reason 78 → 52 (the rest read as reasoned); possible tool mismatches 30 → 22 (the rest are `curl` fetches or labels, listed in section 1).
- Rendered briefs (sonnet, medium, a one-line task) for the five data templates, before → after, in words: statistical-tester 353 → 361, spreadsheet-engineer 345 → 360, biodiversity-data-integrator 348 → 368, ml-experiment-runner 344 → 371, rag-index-builder 338 → 364. `lint_brief` reported no error for any of them. The largest changed brief is 378 words, which is above the 350-word note and below the 500-word refusal.

## Not checked

- No helper was run on a task with the old and the new text, so no line has a measured effect on output. Each fix rests on the tool table, the research memo or the reading above.
- The [S] items in the memo were read as abstracts only.
- The scan's similarity measure is word overlap. Pairs that overlap in meaning but not in words could be missed.
