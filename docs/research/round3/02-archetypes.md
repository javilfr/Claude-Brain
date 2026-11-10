# 100 agent archetypes for the Claude Brain HR rack (2026-11-10)

## Answer (confidence: medium on the list, high on the design rules)

The 100 archetypes are in `/tmp/claude-0/-home-user/ad24da2f-7dc0-51cf-aa28-dee6f5e57a4f/scratchpad/research3/archetypes.json` (exactly 100 objects, ten groups of ten, fields as requested). The `id`, `name`, `group`, `base_agent`, `families`, `typical_size` and `risk` columns are tabled below. The `when` and `what_it_adds` sentences are only in the JSON, which is the single source: I had no shell to generate the table from the JSON, and duplicating 200 sentences by hand would invite drift. Counts were checked with Grep: 100 lines starting `{"id":`, one line (the last) with no trailing comma. I could not run a JSON parser (no shell tool), so validity is checked by pattern, not by parse. Run `python3 -I -c "import json;print(len(json.load(open('archetypes.json'))))"` once.

Design rule behind the list (my synthesis of the evidence below): an archetype is a template only if it carries (a) a method with ordered steps, (b) a check that produces evidence, and (c) known pitfalls, for a task class that recurs in this owner's history. A job title ("Senior Backend Engineer", "CEO") is not a template.

## Evidence on role taxonomies and specialisation

Read from sources this session (S = primary or paper; sec = secondary summary):

1. Personas alone do not raise accuracy. Zheng et al., EMNLP Findings 2024 (https://aclanthology.org/2024.findings-emnlp.888/, via search summary): persona in system prompts generally did not improve factual accuracy; choosing the best persona in advance was hard, often no better than random (sec: 162 personas, 2,410 questions, not verified). Wharton Prompting Science Report 4, Dec 2025 (https://arxiv.deeppaper.ai/papers/2512.05858v1, sec) reached the same result; personas still shape tone and audience. Consequence: no template may rely on "You are an expert X". Voice/tone archetypes (voice-matcher, es-original-writer) are the legitimate persona uses.
2. Curated procedural guidance helps, self-written does not. SkillsBench (https://arxiv.org/html/2602.12670v1; figures via search summary): curated skills +16.2 pp average pass rate, range +4.5 pp (software engineering) to +51.9 pp (healthcare), 16 of 84 tasks got worse; self-generated skills no average benefit (about -1.3 pp per one summary). Sources disagree on task count (84 vs 86) and one mirror gave +12.66 pp; verify against the paper. Consequence: templates must be written by research (this round) and kept short and focused; a template that does not change a result should be deleted by `settle` data; the gain for software was the smallest, so software templates must earn their place with checks, not advice.
3. Multi-agent costs. Anthropic (https://www.anthropic.com/engineering/multi-agent-research-system): agents use about 4x chat tokens, multi-agent about 15x; token use explained about 80% of BrowseComp variance; each subagent needs objective, output format, tool guidance and boundaries; vague briefs caused duplicated work; effort rules (1 agent for simple fact-finding, 2-4 for comparisons). Consequence: every archetype's value must exceed its cold-start cost; the `typical_size` field feeds the wage; briefs must carry the five brief elements.
4. Coordination can hurt. Google/MIT, arXiv 2512.08296 (https://arxiv.org/abs/2512.08296v1; figures via https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/): on sequential tasks all multi-agent variants lost 39-70% performance; parallelisable tasks gained (Finance-Agent +81%); independent agents amplified errors 17.2x (search summaries; abstract wording differs between versions). Consequence: archetypes are single-purpose workers for self-contained slices; `ticket-slicer` exists to decide what is genuinely parallel, and sequential chains stay with the lead.
5. Failure taxonomy. MAST, arXiv 2503.13657 (https://arxiv.org/html/2503.13657v3): 14 failure modes in three groups (specification, inter-agent misalignment, task verification), 1,642 annotated traces, seven frameworks; the authors say failures are mostly structural. Role-disobedience (FM-1.2) was only about 1.5% in the latest version (search summary; percentages differ across versions). Consequence: a large role list is not where failures come from; weak briefs and missing verification are. Hence the review/verification group and the fixed brief format.
6. Role value in fixed-pipeline frameworks. MetaGPT (https://arxiv.org/pdf/2308.00352): adding product-manager, architect and project-manager roles beyond the engineer improved executability and revisions at slight cost (search summary of the ablation). ChatDev: removing role profiles gave the biggest drop, 0.3953 to 0.2212 (secondary pages only, https://aiwiki.ai/wiki/ChatDev; not verified in the paper). Both are fixed software pipelines with 5-8 roles and SOP-like structure, which supports method-bearing roles but not a 100-persona company.
7. Community collections. VoltAgent awesome-claude-code-subagents is described as 100+/110+/130+ agents across 10 categories (sources disagree; https://www.sourcepulse.org/projects/11201240 and a DEV post). wshobson/agents: only seen listed; no count or critique found. I found no direct, quotable criticism of these collections; the context-bloat argument is general (sub-agents protect main context, they do not reduce total tokens: https://www.mindstudio.ai/blog/sub-agents-claude-code-context-management, sec). Treat "large catalogues are mostly job titles" as my inference, not a sourced finding.
8. Claude Code's own guidance (https://code.claude.com/docs/en/sub-agents, fetched, last ~17k characters unread): built-ins are Explore (read-only), Plan, general-purpose; use a subagent for verbose output, tool restriction, self-contained work, or repeated worker types; keep descriptions short (warning above 15,000 combined description tokens); one focused job per subagent; route routine work to cheaper models; frontmatter supports tools, model, effort, maxTurns, skills. Consequence: the rack must never load 100 descriptions into the session; only the hired one is rendered, and the two-repo cloud session loads only agents/skills/CLAUDE.md, so the rack stays as JSONL outside `.claude/agents/`.
9. BMAD personas: PM, Architect, Dev, SM, UX, QA, Analyst, Tech Writer, named characters (https://www.mintlify.com/bmad-code-org/BMAD-METHOD/reference/agents/overview, sec). Named characters are exactly the persona style evidence 1 argues against; the project-lifecycle idea (analyst, PM, architect) is retained as method in requirements-extractor and architecture-decider.

Not reached / not done: CrewAI role library, AutoGen/AG2 patterns, OpenHands microagents (one search returned nothing on it), SuperClaude, wshobson/agents contents, Anthropic's example skills repository, and platform.claude.com prompt-engineering pages. Treat any claim about them as absent from this memo. Note the demo repo's evidence: its 500-role catalogue was never used (round context), and its mission sentences are product-specific (e.g. "Score PowerSync, ElectricSQL... on offline durability") (/home/user/Travel-Journal-Work-Repo---RAG-and-Building-Purpose/orgdesign/catalogue/03-research.json). Its 30 agent files mix real work roles (frontend-mobile, qa-lead, security-reviewer, release-manager) with ceremony (five `board-*` seats, chief-of-staff, hr-lead); I read their descriptions only, not bodies. The schema's `cannot_combine_with` (no self-review) and `reviewed_by` ideas are kept as the base-agent split: reviewer/redteam archetypes never share a brief with the builder they check.

## What I took from the demo repo

- Keep: read-only reviewers that do not fix; blind critique (design-critic sees screenshots only); evidence-first research with an "implications" section; least-privilege; one-owner-per-job rule (SCHEMA.md "no two roles may do the same job").
- Drop: boards, standing executives, 20 departments, 25 roles per category. Roles tied to one product's nouns. Fine-grained splits (500 roles) that the hire step could not choose between.
- Merge rule applied: two candidates become one archetype when the method and the check are the same (for example visual critique of an app and of a deck).

## Boundaries between near neighbours (so no two overlap)

- api-live-prober (probes a service before choice) vs api-integration-builder (builds it) vs data-pipeline-builder (batch dataset) vs biodiversity-data-integrator (adds taxonomy/coordinate rules).
- requirements-extractor (parse the request) vs rubric-mapper (match a given rubric to files) vs requirement-verifier (judge completion at the end) vs acceptance-test-designer (write the checks).
- fact-checker (any claim) vs legal-citation-verifier (law-specific existence and in-force check) vs canonical-facts-keeper (keeps one facts file and diffs documents).
- es-en-translator (translate) vs es-original-writer (write natively) vs back-translation-checker (verify) vs legal-terms-translator (legal terms of art).
- deploy-doctor (live site wrong) vs build-failure-diagnoser (build fails) vs release-to-main-engineer (ship) vs rollback-restorer (undo).
- session-handover-writer (writes state) vs git-repo-operator (repo state) vs project-bootstrapper (first pairing).
- Known soft overlap: visual-polish-measurer / phone-first-ui-builder and e2e-test-author on screenshots; copy-editor / voice-matcher. The HR matcher should pick the more specific, and `settle` data should show if either never gets hired.

## Groups

1 discovery-research, 2 planning-requirements, 3 software-building, 4 quality-operations, 5 data-analysis, 6 knowledge-writing, 7 language-localisation, 8 design-media, 9 review-risk, 10 orchestration-owner. Ten each.

## Table (base agents: scout, researcher, builder, writer, reviewer, redteam)

| id | name | group | base | families | size | risk |
|---|---|---|---|---|---|---|
| repo-cartographer | Repo Cartographer | 1 | scout | software, operations | S | trivial |
| docs-snapshotter | Docs Snapshotter | 1 | researcher | software, data | S | standard |
| api-live-prober | API Live Prober | 1 | researcher | data, software | S | standard |
| option-comparer | Option Comparer | 1 | researcher | software, knowledge, data | M | standard |
| deep-researcher | Deep Researcher | 1 | researcher | knowledge | L | standard |
| competitor-teardown | Competitor Teardown | 1 | researcher | knowledge, software | M | trivial |
| history-digger | History Digger | 1 | scout | knowledge, operations | S | trivial |
| claude-product-answerer | Claude Product Answerer | 1 | researcher | operations, knowledge | S | standard |
| dataset-source-finder | Dataset Source Finder | 1 | researcher | data | M | standard |
| source-harvester | Source Harvester | 1 | scout | knowledge, data | M | trivial |
| requirements-extractor | Requirements Extractor | 2 | researcher | all five | M | standard |
| acceptance-test-designer | Acceptance Test Designer | 2 | builder | software, data, knowledge | M | standard |
| ambiguity-resolver | Ambiguity Resolver | 2 | researcher | all five | S | standard |
| architecture-decider | Architecture Decider | 2 | reviewer | software, data | M | high |
| ticket-slicer | Ticket Slicer | 2 | researcher | software, data, knowledge, operations | M | standard |
| rubric-mapper | Rubric Mapper | 2 | researcher | knowledge, software | M | standard |
| blueprint-extractor | Blueprint Extractor | 2 | builder | software, knowledge | L | standard |
| migration-planner | Migration Planner | 2 | researcher | software, data, operations | M | high |
| backlog-prioritiser | Backlog Prioritiser | 2 | researcher | software, knowledge | S | trivial |
| feasibility-reframer | Feasibility Reframer | 2 | researcher | software, data, operations | S | standard |
| web-app-scaffolder | Web App Scaffolder | 3 | builder | software | M | standard |
| phone-first-ui-builder | Phone First UI Builder | 3 | builder | software | L | standard |
| pwa-offline-engineer | PWA Offline Engineer | 3 | builder | software | M | standard |
| api-integration-builder | API Integration Builder | 3 | builder | software, data | M | standard |
| game-builder | Game Builder | 3 | builder | software | L | standard |
| learning-app-builder | Learning App Builder | 3 | builder | software, knowledge | XL | standard |
| cli-script-builder | CLI Script Builder | 3 | builder | software, operations | S | standard |
| content-site-builder | Content Site Builder | 3 | builder | software, knowledge | M | standard |
| minecraft-structure-builder | Minecraft Structure Builder | 3 | builder | software | M | standard |
| refactor-engineer | Refactor Engineer | 3 | builder | software | M | standard |
| build-failure-diagnoser | Build Failure Diagnoser | 4 | builder | software | S | standard |
| deploy-doctor | Deploy Doctor | 4 | builder | software, operations | M | standard |
| release-to-main-engineer | Release To Main Engineer | 4 | builder | software, operations | S | high |
| rollback-restorer | Rollback Restorer | 4 | builder | software, operations | S | one-way-door |
| e2e-test-author | E2E Test Author | 4 | builder | software | M | standard |
| coverage-analyst | Coverage Analyst | 4 | builder | software | M | trivial |
| performance-profiler | Performance Profiler | 4 | builder | software | M | standard |
| accessibility-auditor | Accessibility Auditor | 4 | reviewer | software | M | standard |
| dependency-upgrader | Dependency Upgrader | 4 | builder | software | M | standard |
| bug-reproducer | Bug Reproducer | 4 | builder | software | M | standard |
| data-pipeline-builder | Data Pipeline Builder | 5 | builder | data | L | standard |
| exploratory-analyst | Exploratory Analyst | 5 | builder | data | M | standard |
| statistical-tester | Statistical Tester | 5 | researcher | data, knowledge | M | standard |
| chart-maker | Chart Maker | 5 | builder | data, knowledge | S | trivial |
| spreadsheet-engineer | Spreadsheet Engineer | 5 | builder | data, knowledge | M | standard |
| data-reconciler | Data Reconciler | 5 | builder | data | M | standard |
| schema-migration-engineer | Schema Migration Engineer | 5 | builder | software, data | M | one-way-door |
| biodiversity-data-integrator | Biodiversity Data Integrator | 5 | builder | data, software | L | standard |
| ml-experiment-runner | ML Experiment Runner | 5 | builder | data | L | standard |
| rag-index-builder | RAG Index Builder | 5 | builder | data, knowledge | L | standard |
| long-form-drafter | Long Form Drafter | 6 | writer | knowledge | XL | standard |
| batch-article-rewriter | Batch Article Rewriter | 6 | writer | knowledge | XL | standard |
| knowledge-base-compiler | Knowledge Base Compiler | 6 | writer | knowledge | L | standard |
| canonical-facts-keeper | Canonical Facts Keeper | 6 | reviewer | knowledge | M | high |
| document-producer | Document Producer | 6 | builder | knowledge | M | standard |
| deck-builder | Deck Builder | 6 | builder | knowledge | M | standard |
| strategy-memo-writer | Strategy Memo Writer | 6 | writer | knowledge | M | standard |
| legal-research-analyst | Legal Research Analyst | 6 | researcher | knowledge | L | high |
| case-chronology-builder | Case Chronology Builder | 6 | researcher | knowledge | M | high |
| agent-spec-writer | Agent Spec Writer | 6 | writer | knowledge, software | L | standard |
| es-en-translator | Spanish English Translator | 7 | writer | language | M | standard |
| es-original-writer | Spanish Original Writer | 7 | writer | language, knowledge | M | standard |
| copy-editor | Copy Editor | 7 | writer | language, knowledge | S | trivial |
| glossary-builder | Glossary Builder | 7 | researcher | language | S | standard |
| back-translation-checker | Back Translation Checker | 7 | reviewer | language | S | standard |
| ui-string-localiser | UI String Localiser | 7 | builder | language, software | M | standard |
| bilingual-site-publisher | Bilingual Site Publisher | 7 | builder | language, software | M | standard |
| legal-terms-translator | Legal Terms Translator | 7 | writer | language, knowledge | M | high |
| voice-matcher | Voice Matcher | 7 | writer | language, knowledge | M | standard |
| transcript-cleaner | Transcript Cleaner | 7 | writer | language, knowledge | S | trivial |
| design-brief-author | Design Brief Author | 8 | writer | software | M | standard |
| visual-option-generator | Visual Option Generator | 8 | builder | software | M | trivial |
| visual-polish-measurer | Visual Polish Measurer | 8 | builder | software | S | trivial |
| design-critic | Design Critic | 8 | reviewer | software | S | standard |
| design-system-builder | Design System Builder | 8 | builder | software | L | standard |
| image-pipeline-engineer | Image Pipeline Engineer | 8 | builder | software, data | M | standard |
| motion-builder | Motion Builder | 8 | builder | software | M | standard |
| audio-lesson-producer | Audio Lesson Producer | 8 | builder | software, knowledge | M | standard |
| diagram-maker | Diagram Maker | 8 | builder | software, knowledge | S | trivial |
| name-and-copy-options | Name And Copy Options | 8 | writer | software, knowledge | S | trivial |
| requirement-verifier | Requirement Verifier | 9 | reviewer | all five | M | high |
| fact-checker | Fact Checker | 9 | reviewer | knowledge, language | M | high |
| code-reviewer | Code Reviewer | 9 | reviewer | software | M | standard |
| security-reviewer | Security Reviewer | 9 | reviewer | software | M | high |
| secret-scanner | Secret Scanner | 9 | scout | software, operations | S | high |
| premortem-redteam | Premortem Red Team | 9 | redteam | software, data, knowledge, operations | M | one-way-door |
| injection-auditor | Injection Auditor | 9 | redteam | software, operations | M | high |
| legal-citation-verifier | Legal Citation Verifier | 9 | reviewer | knowledge | M | high |
| privacy-licence-reviewer | Privacy Licence Reviewer | 9 | reviewer | software, data, knowledge | M | high |
| clean-clone-verifier | Clean Clone Verifier | 9 | builder | software, operations | S | standard |
| session-handover-writer | Session Handover Writer | 10 | writer | all five | S | standard |
| needs-you-composer | Needs You Composer | 10 | writer | all five | S | standard |
| owner-computer-guide | Owner Computer Guide | 10 | writer | operations | S | standard |
| git-repo-operator | Git Repo Operator | 10 | builder | software, operations | S | high |
| routine-builder | Routine Builder | 10 | builder | operations | M | standard |
| setup-repairer | Setup Repairer | 10 | builder | operations | M | high |
| token-cost-auditor | Token Cost Auditor | 10 | scout | operations | S | trivial |
| eval-regression-runner | Eval Regression Runner | 10 | builder | software, operations | M | high |
| lesson-distiller | Lesson Distiller | 10 | writer | all five | S | standard |
| project-bootstrapper | Project Bootstrapper | 10 | builder | all five | M | standard |

"all five" = software, data, knowledge, language, operations. Group numbers: 1 discovery-research ... 10 orchestration-owner (names above). The JSON array is the file named in the Answer section; it holds the same 100 objects with the full `when` and `what_it_adds` text.

## Coverage: the eighteen kinds of request (/home/user/Claude-Brain/docs/research/07-past-chats.md, B.4.a)

| # | Kind | Archetype ids |
|---|---|---|
| 1 | Web/PWA build, iPhone first, Vercel | web-app-scaffolder, phone-first-ui-builder, pwa-offline-engineer, deploy-doctor |
| 2 | Design and visual polish | design-brief-author, visual-option-generator, visual-polish-measurer, design-critic, design-system-builder |
| 3 | Handover, repo memory, set up | session-handover-writer, project-bootstrapper |
| 4 | Deployment and release to main | release-to-main-engineer, deploy-doctor, rollback-restorer |
| 5 | Agent team and orchestration design | agent-spec-writer, ticket-slicer, token-cost-auditor |
| 6 | Deep research and retrieval KBs | deep-researcher, knowledge-base-compiler, rag-index-builder |
| 7 | Long-form writing | long-form-drafter, batch-article-rewriter, voice-matcher |
| 8 | Learning apps and blueprints | learning-app-builder, blueprint-extractor, audio-lesson-producer |
| 9 | Rubric deliverables and doc audits | rubric-mapper, requirement-verifier, coverage-analyst |
| 10 | Bilingual Spanish/English | es-en-translator, es-original-writer, ui-string-localiser, bilingual-site-publisher |
| 11 | Data pipelines and external APIs | data-pipeline-builder, api-integration-builder, biodiversity-data-integrator |
| 12 | Games and creative builds | game-builder, minecraft-structure-builder |
| 13 | Help on his own computer | owner-computer-guide, routine-builder |
| 14 | Questions about Claude, repair of setup | claude-product-answerer, setup-repairer |
| 15 | Repo operations | git-repo-operator, rollback-restorer |
| 16 | Legal research (Spanish law) | legal-research-analyst, legal-citation-verifier, case-chronology-builder, legal-terms-translator |
| 17 | Efficiency requests | token-cost-auditor, eval-regression-runner |
| 18 | Downloadable files | document-producer, deck-builder, spreadsheet-engineer |

## Coverage: the 40 acceptance tests (same file, B.4.d)

| Test | Ids | Note |
|---|---|---|
| 1 set up / Start running | project-bootstrapper, repo-cartographer, session-handover-writer | Boot itself is an engine script, not an agent |
| 2 Continue | session-handover-writer | Resume is mostly script |
| 3 get ready for new chat | session-handover-writer, git-repo-operator | |
| 4 near context limit | session-handover-writer | Trigger is engine configuration |
| 5 several chats on same repos | session-handover-writer, git-repo-operator | Lease file is engine |
| 6 Vite app, iPhone, Vercel | web-app-scaffolder, phone-first-ui-builder, e2e-test-author, deploy-doctor | |
| 7 main only on green | release-to-main-engineer | |
| 8 failed Vercel build | build-failure-diagnoser | |
| 9 stale site / 404 | deploy-doctor | |
| 10 go back | rollback-restorer | |
| 11 cancel and revert | rollback-restorer, git-repo-operator | |
| 12 five icons | visual-option-generator | |
| 13 measured visual correction | visual-polish-measurer | |
| 14 redesign, critic score | design-brief-author, design-critic, design-system-builder | |
| 15 hero photos | image-pipeline-engineer | |
| 16 brochure + KB | knowledge-base-compiler, document-producer, rag-index-builder | |
| 17 accurate dates | canonical-facts-keeper, fact-checker | |
| 18 60 articles | batch-article-rewriter | |
| 19 seven agents + workflow | agent-spec-writer, long-form-drafter | |
| 20 Spanish answer | es-original-writer, es-en-translator, back-translation-checker | |
| 21 legal research | legal-research-analyst, legal-citation-verifier | |
| 22 blueprint | blueprint-extractor, learning-app-builder | |
| 23 learning pipeline + regression | lesson-distiller, eval-regression-runner | |
| 24 no brain writes outside pipeline | eval-regression-runner (partial) | Enforced by hook (engine); no archetype fits, gap noted |
| 25 project tools stay in project repo | project-bootstrapper | |
| 26 PlantNet/GBIF/eBird | biodiversity-data-integrator, api-integration-builder, api-live-prober | |
| 27 API key handling | secret-scanner, api-integration-builder | Secure credential form is a lead action |
| 28 one audio sample first | audio-lesson-producer | |
| 29 run on my Mac | owner-computer-guide, clean-clone-verifier | |
| 30 close everything | owner-computer-guide | |
| 31 deliverables table | rubric-mapper, requirement-verifier | |
| 32 test coverage | coverage-analyst | |
| 33 route to cheapest model, ledger | token-cost-auditor | Routing is the engine/learner; HR itself |
| 34 cap parallel agents | ticket-slicer, token-cost-auditor | |
| 35 never write huge file in one step | long-form-drafter, batch-article-rewriter, cli-script-builder | Hook is engine |
| 36 model fallback | none | Engine concern; no template needed |
| 37 noisy performance rerun | performance-profiler | |
| 38 needs-you item | needs-you-composer, ambiguity-resolver | |
| 39 game in waves | game-builder | |
| 40 Minecraft feasibility | minecraft-structure-builder, feasibility-reframer | |

Required areas: Spanish and English writing and translation (es-en-translator, es-original-writer, copy-editor, glossary-builder, back-translation-checker, legal-terms-translator, voice-matcher, ui-string-localiser, bilingual-site-publisher); phone-first web apps deployed from main (web-app-scaffolder, phone-first-ui-builder, pwa-offline-engineer, e2e-test-author, release-to-main-engineer, deploy-doctor, rollback-restorer); research, legal, long-form and learning-app work (deep-researcher, legal-research-analyst, legal-citation-verifier, long-form-drafter, learning-app-builder).

## 15 tempting archetypes rejected

1. Chief of staff / orchestrator: the lead session does this; a helper cannot orchestrate cheaper than its caller (demo repo's chief-of-staff).
2. HR lead / agent hirer: it is `brain hr hire`, a script (no tokens).
3. Five board seats (strategy, risk, craft, product, capital): job titles with opinion; `premortem-redteam` and `strategy-memo-writer` carry the method. Persona evidence above.
4. Product manager: split into requirements-extractor, ticket-slicer, backlog-prioritiser, each with a distinct check.
5. Senior full-stack / backend / frontend engineer: a generic builder does equally well; only stack-specific methods (phone-first-ui-builder, pwa-offline-engineer) earn a template.
6. Software architect as persona: kept only as architecture-decider with a decision-record method and one-way-door flag.
7. Technical writer / docs-writer: generic writer plus the document-producer or session-handover-writer; "write docs" has no distinct check.
8. Project manager / scrum master: no sprints here; ticket-slicer covers the useful part.
9. Prompt engineer: overlaps agent-spec-writer; a standalone one risks "prompt tweaking" that SkillsBench-type evidence says helps only when curated.
10. Data scientist (generic): too broad; split into exploratory-analyst, statistical-tester, ml-experiment-runner.
11. DevOps / SRE engineer: platform-specific tasks are deploy-doctor, release-to-main-engineer and routine-builder; infrastructure-as-code is not in this owner's history.
12. QA tester (generic): e2e-test-author, bug-reproducer, coverage-analyst each have a distinct method.
13. Accessibility fixer: auditor kept, fixer would be the builder.
14. Editor-in-chief / content strategist: no recurring task in the history; strategy-memo-writer covers rare use.
15. Translator for every language (French, Japanese...): the history shows only Spanish and English. The demo repo scaffolded Japanese, but there is no evidence of need. Add a language archetype only after two real tasks (plan 3.5 rule: add a family after two ill-fitting projects).

Also considered and dropped for lack of history: payments/auth builder, mobile native app builder, video editor, database administrator, SEO specialist, social-media writer. Add via `settle` data if requests appear (estimate: the rack should grow by evidence, not by guess).

## Implementation consequences

1. Rack record = the JSON object plus fields the HR build must add: method steps, checks, pitfalls, brief skeleton, tool list, default model/effort (taken from the learner, not from the template), wage by `typical_size`. I wrote only the trigger and differentiator sentences here; full method text is the next job and must come from the researched sources (SkillsBench consequence: curated and short).
2. Retrieval: match the task to `when` trigger words, then break ties by learned success; log when two templates tie (overlap signal).
3. `risk` should raise the reviewer requirement and the effort floor; `one-way-door` should force a premortem-redteam pass or an owner item. This is my design proposal, not sourced.
4. Retire any template unhired or no better than no-template across a stated number of settles (threshold to be set by the lead; none is evidenced here).
5. The 3 gaps (tests 24, 33, 36) are engine behaviours; do not paper over them with templates.

## Unknowns

- Whether 100 is the right count: it was the owner's instruction; the evidence supports few method-bearing templates, so expect many to stay unhired. Estimate, not measured.
- `typical_size` and `risk` values are my estimates from the task descriptions, not measurements; the ledger should replace them.
- Secondary-only figures are marked above (ChatDev ablation, persona study scale, SkillsBench discrepancies).

END OF MEMO
