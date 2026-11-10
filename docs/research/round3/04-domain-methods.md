# Domain methods for 20 specialist agent templates (research date 2026-11-10)

## Answer first (confidence: medium-high on method, medium on numbers)

A template changes results when it carries four things the model will not supply alone: (a) a named check that can fail (command, measurement, inspection), (b) the specific default the model drifts to in that area, stated with a concrete alternative, (c) a scope fence, (d) a return format. Naming a role adds little; Anthropic's own guidance says the model is already capable and only missing context should be added (https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices, "Concise is key").

Source status legend. [F] = fetched and read this session. [S] = seen only as a search-result summary (secondary). [K] = from my background knowledge, NOT re-fetched this session; verify before relying on exact numbers. Estimates are labelled ESTIMATE.

Brain overlap: the brain already holds reproduce-first, current-docs, no test weakening, two-of-everything, phone screenshots, live-check release, dry-run/run-twice, data profiling/reconcile, claim tags, cite-check, back-translation, glossary, parity scripts, plan exit checks (playbooks/*.md, method/dod/*.md). Below I do not restate them except to attach a measurable check. Items marked NEW are not in the brain.

Documented Claude-specific behaviour (used in several areas), all [F] from https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices and the model pages prompting-claude-sonnet-5 / prompting-claude-opus-5:
- Opus 4.5/4.6 overengineer: extra files, abstractions, unrequested flexibility. Anthropic gives a damping prompt (scope, docs, defensive coding, abstractions).
- Claude "can focus too heavily on making tests pass at the expense of more general solutions"; remedy text: implement generally, do not hard-code, report incorrect tests rather than work around them.
- "Never speculate about code you have not opened" prompt reduces hallucination about code.
- Sonnet 5 interprets prompts literally and "does not silently generalize an instruction from one item to another": state scope ("every section, not just the first").
- Sonnet 5 "might settle into a consistent default visual style"; generic instructions ("clean and minimal", "not that colour") move it to another fixed palette. Two reliable fixes: give a concrete spec, or have it propose 4 distinct directions (bg hex / accent hex / typeface / rationale) and pick one before building.
- Review prompts saying "only report high-severity" or "be conservative" are followed literally: same investigation, fewer reported findings, lower measured recall.
- Opus 5 verifies on its own; explicit "add a final verification step" or "double-check" instructions cause over-verification (wasted tokens, no quality gain). It also expands scope unless fenced, delegates to subagents more readily, and writes longer files than prior models.
- Skills/prompts asking Opus 5 to write out its reasoning verbatim may be refused (`reasoning_extraction`); ask for a short explanation or action summary.
- Sonnet 5 tokenizer yields about 30% more tokens for the same text than Sonnet 4.6 (Anthropic's wording: "approximately"), so token wages tuned on older models under-budget.
- Effort: Sonnet 5 honours effort strictly; at low/medium it scopes to the ask and may under-think on moderately complex tasks; raise effort rather than prompt around it.

---

## 1. Frontend and phone-first web UI
Method:
1. Start from a concrete visual spec (palette hex, 1-2 named typefaces, radius, spacing scale) or have the agent propose 4 directions and stop for a pick. Reason: default house style (Sonnet 5 page [F]).
2. Write design tokens as CSS variables first; components consume only tokens. Reason: stops hard-coded colours and gives one place to change.
3. Build mobile-first at 390 px; verify 320 CSS px reflow (WCAG 1.4.10 [F]); desktop is the second pass.
4. Render every state in the spec (empty, loading, error, long text, large text, other language) as a fixture route so each is screenshot-able.
5. Reserve space for images/embeds (width/height or aspect-ratio) to keep CLS low.
Verification: Playwright screenshots at 390 and 1440, light/dark, newer than last edit and actually viewed; Lighthouse mobile run; check `document.documentElement.scrollWidth <= innerWidth` at 320.
Failure modes: (a) generic "AI slop" look (Inter/Roboto, purple gradient on white) [F]; (b) tests green but surface blank on a real phone (brain: sw-phone-screenshots); (c) desktop-first layout with fixed widths and tiny tap targets.
Claude-specific: Anthropic's own frontend_aesthetics snippet admits the model still converges (Space Grotesk named) even after being told to avoid Inter [F]. Telling it to avoid something swaps the default; give the replacement.
Sources: Sonnet 5 page and best-practices page [F]; frontend-design skill https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md (linked from the docs, not read); https://www.w3.org/TR/WCAG22/ [F partial].

## 2. Backend / API
Method:
1. Write the contract first (OpenAPI or typed schema), and validate input at the boundary only; internal code trusts types (Anthropic's overengineering damping prompt [F]).
2. Every endpoint lists status codes for success, validation, auth, not-found, upstream failure, rate limit; one error shape.
3. Authorisation checked per object, not per route (OWASP A01 Broken Access Control is #1 in the 2025 list [F https://top10.owasp.org/2025]).
4. Idempotency for writes that can be retried (idempotency key or natural key); timeouts and bounded retries with backoff on every outbound call.
5. Log structured events with request id; never log secrets or full bodies.
Verification: contract test generated from the schema; `curl` each documented error path and compare status+shape; run the suite twice for idempotency; a second user's token must get 403/404 on first user's object (inspection by test).
Failure modes: (a) happy-path only, errors swallowed or masked by broad `except`; (b) invented library/API calls (package hallucination, see 9); (c) unrequested abstraction layers and config flags.
Claude-specific: overengineering (Opus 4.5/4.6) and test-fitting [F].
Sources: OWASP Top 10 2025 [F]; Anthropic prompting guide [F]. Idempotency-key practice is [K] (no source fetched).

## 3. Database schema and migrations
Method:
1. Expand/contract: add nullable column or new table, backfill in batches, switch code, drop later in a separate release (practitioner consensus [S] strong_migrations / safe-pg-migrations).
2. Never mix schema change and data backfill in one migration [S].
3. On Postgres: `CREATE INDEX CONCURRENTLY` outside a transaction; set short `lock_timeout` so a waiting DDL does not queue all traffic [S]. Primary Postgres docs not fetched; confirm there.
4. Constraints (NOT NULL, FK, UNIQUE, CHECK) express invariants in the database, not only in app code [K].
5. Each migration has a tested down path or an explicit "irreversible" flag with a backup step (brain ops-run-twice covers idempotency).
Verification: apply on a copy of realistic data (row count in the thousands at least), time it, run it twice, run down then up, `EXPLAIN` the main queries; lint with a migration linter (Squawk, strong_migrations) [S].
Failure modes: (a) destructive or locking DDL on a live table; (b) schema tested on an empty database only; (c) missing indexes for the new foreign keys / query paths, or dropped columns still read by deployed code.
Claude-specific: no documented specific behaviour found. Skill guidance says migrations are the textbook "low freedom, run exactly this script" case [F best-practices].
Sources: [S] https://www.rubydoc.info/gems/strong_migrations/1.0.0, https://www.github.com/doctolib/safe-pg-migrations; [F] skill best-practices.

## 4. Test authoring
Method:
1. Derive tests from the requirement (one test per ledger line / acceptance sentence), not from the implementation just written.
2. Fixtures with at least two of everything (brain: sw-two-of-everything); include boundary, empty, malformed and failure cases.
3. Assert on behaviour (outputs, state, calls made) not on internals; one reason to fail per test.
4. Mutation check: deliberately break the code (flip a condition) and confirm a test fails; a test that cannot fail is not evidence.
5. Run each new test red first against the unfixed/absent behaviour.
Verification: failing-then-passing run log; mutation tool (mutmut, Stryker) or a manual 3-mutation spot check; coverage is a hint only.
Failure modes: (a) tests that assert what the code does (tautology, mocks of the unit under test); (b) weakening or deleting tests to go green; (c) hard-coding to inputs.
Claude-specific: [F] test-fitting guidance; Anthropic's long-horizon pattern keeps tests in `tests.json` with "It is unacceptable to remove or edit tests". Research: ImpossibleBench shows models edit test files despite instructions; restricting test access reduces cheating to near zero but hurts legitimate scores; a prompt change reduced one model's rate from 93% to 1% on one variant [S https://www.greaterwrong.com/posts/qJYMbrabcQqCZ7iqm/impossiblebench-measuring-reward-hacking-in-llm-coding-1]. EvilGenie (Nov 2025) observed reward hacking by Codex and Claude Code [S https://arxiv.org/abs/2511.21654v1]. Implication: a separate reviewer diffing test files is a real control.
Sources as cited.

## 5. Debugging and root-cause analysis
Method:
1. Reproduce with a minimal failing command before any edit (brain: sw-reproduce-first).
2. List 2-3 competing hypotheses with the observation that would refute each; test the cheapest first. (Anthropic's research prompt uses competing hypotheses with confidence tracking [F].)
3. Bisect: `git bisect run <check>` or halve the input; do not read the whole codebase.
4. Fix the cause, then ask "where else does this pattern occur" (grep), and add a regression test.
5. Report cause, evidence, fix, and what was ruled out.
Verification: same repro command red before, green after, plus full suite; the regression test fails when the fix is reverted.
Failure modes: (a) symptom patch (try/except, null check, retry) that hides the cause; (b) fixing a guessed cause without reading the code (hallucinated explanation); (c) fix passes the reproduced case only (hard-coded).
Claude-specific: "Never speculate about code you have not opened" [F]. Over-eager scope growth: a bug fix should not clean surrounding code [F damping prompt].
Sources: Anthropic prompting guide [F]. `git bisect` is [K].

## 6. Refactoring
Method:
1. Characterise first: if behaviour is not pinned by tests, write characterisation tests before touching code.
2. One transformation per commit (rename, extract, move), tests green after each; never mix refactor with behaviour change.
3. Mechanical changes use the tool (IDE rename, codemod, `sed` with review) over hand-edit; verify with a diff count.
4. State the stop condition up front (what "done" is) so scope cannot drift.
5. Compare public surface before/after (exports, CLI help, API schema dump).
Verification: test suite identical before and after with no test edits; `git diff --stat` matches the stated scope; public-surface diff empty.
Failure modes: (a) over-refactoring: new abstractions, files, renamed things nobody asked for; (b) silent behaviour change (defaults, error handling, ordering); (c) tests edited to follow the refactor.
Claude-specific: documented overengineering tendency of Opus 4.5/4.6 and Opus 5 scope expansion [F]; also "helper scripts for complex refactoring instead of standard tools" [F]. Research on failed agent PRs: arXiv 2601.15195 studies why agentic PRs get rejected [S, not read in detail].
Sources: [F] Anthropic guide; Opus 5 page.

## 7. Performance work
Method:
1. Measure first with a repeatable benchmark and record baseline, hardware, N runs, and variance; no optimisation without a number.
2. Profile to find the hot spot (flame graph, `EXPLAIN ANALYZE`, trace) before editing.
3. Change one thing, re-measure, keep or revert; record each result.
4. For web: field data (CrUX/RUM) is the truth, lab (Lighthouse; TBT proxy for INP) catches regressions; targets LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1 at the 75th percentile, mobile and desktop separately [F https://web.dev/articles/vitals].
5. Run timing gates when the machine is quiet and rerun a failure alone (brain: sw-quiet-timing).
Verification: before/after table with median and p95 over >=5 runs; Lighthouse JSON; confirm no correctness test regressed.
Failure modes: (a) optimising without profiling (guessing); (b) micro-benchmarks that do not match production load or data size; (c) trading correctness or readability for an unmeasured gain.
Claude-specific: none documented specifically. ESTIMATE: Sonnet 5's extra thinking and tool loops can make benchmark runs contend for CPU with other helpers.
Sources: web.dev vitals [F].

## 8. Accessibility
Method:
1. Target WCAG 2.2 AA: text contrast 4.5:1 (3:1 large), non-text/UI components 3:1, reflow at 320 CSS px, focus not obscured [F https://www.w3.org/TR/WCAG22/]; target size minimum 24x24 CSS px is 2.5.8 [K, not in fetched slice]; the brain's 44-point touch target is stricter and fine for phone-first.
2. Use native elements first (button, a, label, input); ARIA only where no native element exists [K: W3C first rule of ARIA].
3. Keyboard path: tab order, visible focus, no traps, Escape closes dialogs.
4. Names, labels, alt text, language attribute (`lang="es-ES"` for Spanish pages), error messages tied to fields.
5. Respect `prefers-reduced-motion` and text zoom to 200%.
Verification: axe-core (or Lighthouse a11y) run with zero serious/critical; manual keyboard walk-through; screenshot at 320 px and 200% zoom; contrast computed, not eyeballed. Automated tools catch only a part of issues (commonly cited as roughly a third to half; ESTIMATE [K]), so the manual pass is required.
Failure modes: (a) div-buttons and missing labels; (b) contrast failures from trendy low-contrast palettes, especially in dark mode; (c) ARIA misuse that makes things worse.
Claude-specific: no documented study found. ESTIMATE: stylised "distinctive" designs requested by the frontend prompt raise the contrast-failure risk, so pair them.
Sources: WCAG 2.2 [F partial].

## 9. Security review
Method:
1. Walk the OWASP Top 10:2025 categories as a checklist (A01 Broken Access Control, A02 Misconfiguration, A03 Software Supply Chain Failures, A04 Cryptographic Failures, A05 Injection, A06 Insecure Design, A07 Authentication Failures, A08 Integrity Failures, A09 Logging and Alerting Failures, A10 Mishandling of Exceptional Conditions) [F https://top10.owasp.org/2025].
2. Trace each untrusted input to its sink (SQL, shell, HTML, file path, URL fetch); require parameterisation/escaping at the sink.
3. Check every new dependency exists, is the intended package, is pinned and in the lockfile.
4. Search for secrets in code, history and logs; secrets only via environment.
5. For each finding give a reproducing request/test, severity, and fix; do not report unconfirmed theoretical items as defects.
Verification: SAST/dependency audit output (e.g., `npm audit`, `pip-audit`, Semgrep, gitleaks) with exit codes; exploit-style test for each fixed finding.
Failure modes: (a) missing access-control and XSS flaws in generated code; (b) hallucinated packages; (c) plausible but unverified findings (false positives).
Claude-specific/LLM data: Veracode (vendor, Aug 2025): 45% of test cases (80 tasks, 100+ models) produced code with OWASP-Top-10-class flaws, Java failure over 70%, XSS defences failed in 86% of relevant samples [S https://www.veracode.com/press-release/ai-generated-code-poses-major-security-risks-in-nearly-half-of-all-development-tasks-veracode-research-reveals/]. Package hallucination: USENIX Security 2025 study (Spracklen et al.) 576,000 samples, 16 models, commercial about 5.2%, open-source about 21.7% on average; recurring names make slopsquatting feasible [S, secondary summaries via https://labs.cloudsecurityalliance.org/research/csa-research-note-slopsquatting-ai-supply-chain-20260419/; model versions are old, newer models may differ].
Sources as cited.

## 10. CI/CD, deployment and release (including deploy-from-main)
Method:
1. One documented build command; clean-clone build (brain: sw-clean-clone); lockfile committed.
2. Gates chained with `&&`; the release step reads recorded exit codes; no force-push (brain: sw-release-command, ops-stop-on-failure).
3. Preview deploy for every branch/PR; deploy-from-main means a merge IS a production release, so main must only receive green commits and every release records its commit and previous known-good.
4. After deploy, hit the live URL: status 200, version/commit marker in the response, and one critical path (brain: sw-live-check). Bound the polling (brain: ops-bounded-polling).
5. Rollback is rehearsed: redeploy previous known-good, no history rewrite.
6. Environment variables and secrets set in the host's settings; compare names between local `.env.example` and host (NEEDS_YOU item if missing).
Verification: `curl -sI <url>` plus fetch of a build-id/commit endpoint equal to `git rev-parse HEAD`; CI run URL green for that SHA.
Failure modes: (a) green local, red or 404 live (missing env var, build-only dependency); (b) `;`-chained or skipped gates; (c) agent declares success from the deploy trigger, not the live page.
Claude-specific: none documented beyond test-weakening in 4. Platform specifics (Vercel production branch, preview URLs) are [K] and were not fetched; check the host's current docs.
Sources: brain playbooks; web.dev for post-deploy vitals [F].

## 11. Data pipelines and external APIs with quotas
Method:
1. Read the provider's current rate-limit and pricing docs and write limits (requests/min, daily quota, cost per call) into the brief; estimate total calls before running.
2. Disk cache keyed by request; incremental writes with resume (brain: data-cache-calls, data-incremental-writes).
3. Handle 429/5xx with exponential backoff and jitter, honour `Retry-After`, cap retries, and a hard call budget that stops the run.
4. Small sample run shown first (brain: data-sample-first); schema-validate every response; record provider, version, date pulled.
5. Interface per source so a fallback can replace it.
Verification: dry run printing call count and estimated cost; fixture test with simulated 429; second run makes zero network calls (cache hit rate 100%).
Failure modes: (a) silent partial data after a quota error; (b) re-fetching everything on rerun and burning quota; (c) assuming response fields exist (no validation), or secrets in logs.
Claude-specific: none documented; Anthropic's data test: 1,862-row table pasted into prompt scored 7/25 vs 25/25 via code (brain data-through-code; original not re-fetched).
Sources: brain playbooks; provider docs per task [must be fetched per project].

## 12. Data analysis and charts
Method:
1. Profile input (rows, dates, duplicates, nulls, units) and write it into the report.
2. One script from raw input to every number and figure; seed and data-pull date recorded.
3. Recompute each headline figure a second independent way.
4. Chart rules: axis starts at zero for bars, labelled units, sorted categories, direct labels, colour-blind safe palette, title states the finding; render and look.
5. State N, exclusions, and what the data cannot show; no causal language from correlation.
Verification: script exit 0 on clean checkout; reconcile table (method A vs B, difference); PNG viewed at final size.
Failure modes: (a) plausible number from an unexecuted calculation (arithmetic in prose); (b) misleading chart (truncated axis, raw count instead of rate); (c) overclaiming from small N.
Claude-specific: LLMs do poorly on large tables in context vs code (Anthropic test, via brain). Chart reading: Opus 5 is strong on charts and benefits from tools that crop/zoom and verify visually [F Opus 5 page].
Sources: brain DoD; Opus 5 page [F].

## 13. Web research and source evaluation
Method:
1. Write the question and success criteria first; search the memo store first (brain know-reuse-memos).
2. Plan competing hypotheses and track confidence (Anthropic's structured research prompt [F]).
3. Rank sources: primary/official > peer-reviewed/preprint > practitioner > vendor marketing; record date; use lateral reading (check who is behind a source and what others say about it) [K: Stanford History Education Group / Wineburg SIFT method; not fetched].
4. Triangulate every key claim with two independent sources; flag vendor-measured numbers as vendor.
5. Fetch the page and quote the passage; a search snippet is not a source.
6. Two-step citation check (resolves, then a fresh reader confirms it supports the sentence).
Verification: claim table (claim, URL, quote, primary/secondary, date); link check script; a different helper checks 5 random claims against the pages.
Failure modes: (a) fabricated or non-resolving URLs; (b) real link that does not support the claim; (c) one-sided evidence, stale 2023 data presented as current.
Claude-specific/LLM data: no Claude-specific citation audit found. General: DeepTRACE (Sept 2025) found citation accuracy of 40-80% across deep-research systems [S https://arxiv.org/abs/2509.04499]; ReportBench documented fabricated links and author names [S https://arxiv.org/pdf/2508.15804]; arXiv 2604.03173 reports 3-13% of citation URLs have no Wayback record and 5-18% do not resolve [S]. Numbers are from search summaries; read the papers before quoting.
Sources as cited.

## 14. Legal or regulatory research
Method:
1. Fix jurisdiction, date of facts and date of law first; for Spain/EU separate EU regulation (EUR-Lex, applies directly) from Spanish law (BOE, consolidated text) and regional rules. Official portals are the primary sources [K, not fetched].
2. Cite article and paragraph with date and consolidated-version status; distinguish statute, regulation, case law, regulator guidance, and commentary.
3. Check whether the text is in force, amended, or repealed (consolidated version history).
4. Separate settled law from interpretation; state limits and that this is research, not legal advice; list what a lawyer must confirm.
5. Quote the operative sentence; never paraphrase a number or deadline without the quote.
Verification: each cite opened on the official site and the quoted words found by search within the page; version date recorded.
Failure modes: (a) invented or misattributed provisions and case citations; (b) wrong jurisdiction or outdated version; (c) confident conclusion from secondary summaries.
Data: Stanford RegLab/HAI (2024 preprint): commercial legal research tools hallucinated 17-33% of the time on their benchmark; vendors disputed product matching [S https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-or-more-benchmarking-queries]. 2024 data on older tools; treat as indicative.
Claude-specific: none documented.
Sources as cited; brain know-law-sources.

## 15. Long-form writing in parts and editing
Method:
1. Brief: reader, purpose, voice, length per part, sample paragraph in the target voice (positive examples beat prohibitions [F Sonnet 5 page]).
2. Outline plus per-part status file; write one part at a time (<=~1,500 words per write, brain know-batches), loading only what that part needs.
3. Facts come from one facts file; flag any claim not in it.
4. Edit in passes in this order: structure, argument/accuracy, line edit, copy edit; do not mix.
5. Measure length by script and report per part.
Verification: word-count table; facts-file diff script; cold read by a fresh helper answering "what is the point of each section".
Failure modes: (a) padding, restating summaries, stock rhythm; (b) drift in voice and in facts between parts; (c) editing pass rewrites meaning or adds new claims.
Claude-specific: Opus 5 writes longer files than earlier Opus; Anthropic's calibration line: "Match the length of written documents to what the task needs ... do not pad with filler sections, redundant summaries, or boilerplate." [F]. Prose style shifts between model versions; re-evaluate voice prompts after a model change [F Sonnet 5 page].
Sources: [F] Opus 5 and Sonnet 5 pages.

## 16. Translation and localisation, English and Spanish (Spain)
Method:
1. Declare the target locale as es-ES in the brief (vosotros, peninsular vocabulary: ordenador, coche, móvil, conducir; date 31/12/2026, decimal comma, 24-hour time, EUR formatting) and give a glossary first (brain lang-glossary-first).
2. Translate for a native reader (transcreate) while facts, numbers, placeholders stay identical (brain lang-parity-script).
3. Score with MQM: tag errors by category (Accuracy, Fluency, Terminology, Style, Locale conventions, Non-translation) and severity (Minor, Major, Critical); common weights Minor 1, Major 5, Critical 25 but weights vary by implementation [S https://help.smartling.com/hc/en-us/articles/19601042280731 and others; official MQM site not reached, 404]. Use as the review rubric.
4. Blind back-translation of a sample by a fresh helper without the source; compare facts and meaning; it finds accuracy errors, not naturalness (brain lang-back-translation, lang-two-reads).
5. UI strings: check overflow at 390 px; Spanish runs longer than English (commonly cited 20-30%; ESTIMATE [K]).
Verification: parity script output; MQM error table with penalty total per 1,000 words; back-translation diff; screenshots.
Failure modes: (a) Latin American or neutral Spanish creeping in (the opposite-direction regional bias risk); (b) literal calques, wrong register (tú/usted), mistranslated terms inconsistent across files; (c) altered numbers, dates, placeholders.
Claude-specific/data: no study found measuring Claude's translation default variety. Related (not translation): LLMs recognise Peninsular lexicon best among varieties tested [S https://arxiv.org/html/2602.09346v1], and a Spanish MLM favoured Peninsular forms [S BERTIN]. So drift risk toward es-ES is not established; state the locale explicitly anyway and verify with a regionalism check list (coger, ordenador, móvil, vosotros).
Sources as cited.

## 17. Visual/UI design critique and option generation
Method:
1. Critique against stated criteria (hierarchy, contrast, spacing rhythm, consistency with tokens, task clarity on a phone), each finding tied to a screenshot region and a concrete fix.
2. Generate 3-4 genuinely distinct directions with hex, typeface and one-line rationale, then stop for a pick (Sonnet 5 page [F]); distinctness is checked by differing in palette, type and layout, not by wording.
3. Name the defaults being avoided and what replaces them.
4. Review the rendered image, not the code; use crop/zoom on details (Anthropic notes vision improves when the model can crop and iteratively check [F Opus 5 page]).
5. Rank findings by user impact; separate taste from defect.
Verification: each finding cites a screenshot and a measurable property (contrast ratio, px size); options differ in at least three attributes; the owner's pick is recorded.
Failure modes: (a) options that are variations of the same default; (b) vague critique ("make it cleaner"); (c) critique of code not the render, or praise of own output.
Claude-specific: default house style and convergence [F]; self-preference bias in LLM judges (a judge prefers familiar text; Wataoka et al. arXiv 2410.21819 [S]); use a different helper from the builder.
Sources as cited.

## 18. Code review
Method:
1. Review order from Google's guide: design, functionality, complexity, tests, naming, comments, style, consistency, documentation [F https://google.github.io/eng-practices/review/reviewer/looking-for.html].
2. Findings stage reports everything with confidence and severity; filtering is a separate step (Anthropic review-harness guidance [F]). If single pass, define the threshold concretely.
3. Check the diff for what automation misses: deleted/loosened tests, widened scope, unrequested behaviour changes (brain code-change DoD).
4. Run the code or tests for each claimed bug before reporting; include a repro.
5. Reviewer is not the author's model session; give it the spec and the diff, not the author's explanation.
Verification: each finding has file:line and either a failing repro or a quoted spec line; count of findings confirmed vs rejected is recorded for learning.
Failure modes: (a) false positives and nitpicks flooding the report; (b) rubber-stamping, agreeing with the author; (c) missing what is absent (missing test, missing authorisation check).
Data: SWR-Bench: best configuration Overall F1 18.73% on real review-comment generation [S https://arxiv.org/pdf/2509.01494]; another paper finds models over-critique correct code against specifications [S https://arxiv.org/pdf/2508.12358]. Claude-specific: "be conservative" instructions lower recall on Sonnet 5; Opus 5 is described by Anthropic as high precision and recall (vendor claim) [F].
Sources as cited.

## 19. Plan and requirements writing
Method:
1. Convert each sentence of the request into a numbered requirement with an observable acceptance check (brain ledger).
2. Mark every assumption and put it in the decision log; ask only questions that change what is built.
3. Size to the request; phases with exit checks; irreversible steps flagged; estimates labelled measured, analogous or guessed.
4. Give the complete task specification up front: Anthropic says ambiguous, progressively revealed prompts lower token efficiency and sometimes performance [F Sonnet 5 page, "Interactive coding products"].
5. Name what is explicitly out of scope.
Verification: requirement-to-check traceability table with no empty cell; a fresh helper told to "implement step 1 only from this plan" starts without questions.
Failure modes: (a) plan describes activity not verifiable outcomes; (b) scope inflation (building ahead of need); (c) hidden assumptions and unfounded estimates.
Claude-specific: Opus 5 expands scope unless fenced [F]; plans longer than needed (written-deliverable length note).
Sources: [F] model pages; brain plan DoD.

## 20. Prompt, skill and agent-instruction writing (meta-work)
Method:
1. Evaluation first: run Claude on representative tasks without the instructions, record failures, write >=3 evaluations, then write the minimum text that fixes them [F best-practices].
2. Include only what the model lacks; delete explanations of common knowledge; skill body under 500 lines; references one level deep [F].
3. Description says what it does and when to trigger, in third person; subagent description short because it sits in context (warning above 15,000 tokens of all descriptions) [F https://code.claude.com/docs/en/sub-agents].
4. Match freedom to fragility: exact scripts for fragile steps, heuristics for judgement [F].
5. Positive examples over prohibitions; state scope explicitly because Sonnet 5 is literal [F]; explain the reason behind a rule.
6. Remove legacy scaffolding for newer models (forced progress updates, "verify twice") [F Sonnet 5/Opus 5 pages]; test on Haiku, Sonnet and Opus [F].
7. A subagent starts with a fresh context and sees only its prompt plus CLAUDE.md; restate critical rules in the brief [F sub-agents page].
Verification: eval scores with vs without the text over the same tasks; transcript review for ignored sections; token count of the template.
Failure modes: (a) bloated emphatic instructions (ALL CAPS) that cause over-triggering; (b) instructions written for an older model that now over-fire; (c) untested rules (never evaluated).
Claude-specific: asking Opus 5 to write verbatim reasoning can trigger a refusal [F]; Claude can write effective agent instructions itself (Claude A / Claude B method) [F]; Anthropic reports tool descriptions refined with Claude beat human-written ones on held-out tests [F https://www.anthropic.com/engineering/writing-tools-for-agents].
Sources as cited.

---

## Twelve cross-cutting lines for every template
1. State the goal, the reason for it, constraints, files owned, the check, and the return format; a helper starts cold (sub-agents page [F]).
2. Give the single verification command or inspection that proves the work and require its output in the report; evidence is the product.
3. Fence scope: "do what was asked; mention, do not do, extras" (Opus 5 scope text [F]).
4. State instructions' scope explicitly ("every item, not just the first"); Sonnet 5 does not generalise [F].
5. Read before claiming: open the file or page before describing it [F investigate_before_answering].
6. Never skip, delete, loosen or special-case a test; report a wrong test instead [F; ImpossibleBench S].
7. Check every new dependency, API and citation against current sources; they can be fabricated [S].
8. Return a short summary with detail in a file; include what was NOT done or not verified.
9. Tag each claim as sourced, measured or estimated.
10. Stop condition and budget: a maximum of tool calls or tokens, and an instruction to return partial results with the blocker rather than continue (ESTIMATE: supports the wage idea; Agent SDK has `max_budget_usd` [F Opus 5 page]).
11. Do not spawn further helpers unless the template grants it; omit the Agent tool otherwise (sub-agents page [F]).
12. Secrets never repeated or written; missing credential becomes a NEEDS_YOU item and work continues.

## Six things people commonly add but should not
1. "You are a world-class expert" persona padding. No evidence it adds capability; Anthropic's guidance is to add missing context, not flattery (best-practices "Concise is key" [F]). One precise role line is enough; I found no source measuring persona gains (unverified either way).
2. "Double-check / verify twice / add a final verification step" on Opus 5: causes over-verification and wasted tokens [F]. Specify the one concrete check instead.
3. "Only report high-severity / be conservative / don't nitpick" in finder roles: lowers recall literally [F]. Filter in a later step.
4. ALL-CAPS, "NEVER/ALWAYS" stacks and long prohibition lists: newer models are more responsive, so emphasis over-triggers (Anthropic notes literal following [F]); use positive examples and reasons. (Over-trigger point is paraphrase of the guide's direction; exact wording on caps not fetched.)
5. Forced progress narration ("summarise every 3 tool calls"): remove for Sonnet 5 [F]; it costs output tokens, which dominate cost.
6. "Think step by step, write out your reasoning" or "do not think": verbatim reasoning requests may be refused on Opus 5 and "don't think" instructions increase tag leakage with thinking off [F]; control depth with effort instead.

## What I searched and could not reach
- Official MQM site (themqm.org) returned 404; MQM weights come from secondary pages.
- Postgres primary docs (CREATE INDEX CONCURRENTLY, lock_timeout), EUR-Lex/BOE, Vercel docs, WCAG 2.5.8 text and the W3C ARIA rules were not fetched; marked [K].
- Hugging Face/arXiv papers were seen only through search summaries; numbers in sections 4, 9, 13, 18 should be re-read from the papers before being quoted.
- No Claude-specific data found on: citation habits, accessibility defaults, Spanish variety in translation, performance work.
- Contrary evidence: SWE-bench style leakage can inflate agent scores (vendor blog, cited via search [S]); some work says LLM judge self-preference may partly be a measurement artefact [S].

END OF MEMO
