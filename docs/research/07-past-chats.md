# 07 — Past chats, memory and "everything I have ever asked" (analyst 7 of 10)

Date: 2026-11-10. Read-only work. No repository, session, routine or environment was changed.

## 0. What I could and could not access

| Source | Result |
|---|---|
| Persistent Claude memory directory | **None exists** in this session. `/root/.claude` holds only this session's transcript, synced skills (docs, docx, pdf, pptx, xlsx, google-workspace, import-memory, morning, skill-creator), one built-in plugin record and empty `backups/`. |
| Chats in the consumer claude.ai app | **Not reachable.** Nothing here can list or read them. |
| Claude Code cloud session history | **Reachable.** 120 sessions listed (two pages, the second ended with no further cursor). Dates run 2026-04-16 to 2026-11-10. |
| Session transcripts | **Sampled, not complete.** See coverage below. |
| Scheduled routines | Reachable. First page read (30 entries, all disabled or already fired). More pages exist and were not read. |
| Sample repo owner documents | Read: `docs/owner-brief.md`, `docs/DECISIONS.md`, headings of `docs/NEEDS_YOU.md`, headings of `docs/owner/persona-2026-11-05.md`. |

### Transcript coverage, stated exactly

The events tool returns the newest 100 raw events per call, and most events are tool output, so one page usually holds zero to six human messages. There is no way to jump to the start of a session. Full coverage of long sessions would need thousands of calls.

- **55 sessions were started by the owner** (53 from the iOS app, 2 from the web). **65 were started by Claude** as child sessions (gate shards, team sessions, release sessions).
- **Newest page read for 52 of the 55 owner sessions.** This count includes the current session, whose two messages come from `OWNER_PROMPT.md`.
- **Second-newest page read for 32 of them.**
- **Reached the first message** in 13 sessions (short sessions, or sessions where the second page hit the start).
- **One full list of user messages** recovered from a context-compaction summary (the Costa Rica brochure session).
- **Not read at all:** `01GagRJ…` "Expand wiki pages to 800-1000 words" and `01D9s9…` "Enable experimental agent teams feature". Both returned pages over 16 MB. Only their titles are used.
- **Second page not read:** the eight "Start running / Keep running / Plan continuation" Travel Journal sessions. Owner directions for those come from the sample repo's `DECISIONS.md` rows 13 to 17 instead.
- **The 65 child sessions were skipped on purpose.** Their prompts were written by Claude, not the owner. Their titles are used as evidence of how work was split.

Consequence: the first request of most long sessions is known only through the session title (generated from the first prompt), the last assistant message, and routine prompts. Every quote below was read directly. Nothing is reconstructed.

Three secrets were found pasted into chats (a storage token and two API keys). They are not copied here. One appears in section 5 as a failure pattern.

---

## PART A — Extraction from the owner's message 2

Numbered. Each item quotes the words it comes from. Type: R requirement, C constraint, P preference, I implied expectation, A ambiguity, X impossible or needs honest reframing.

### A.1 What the thing is

1. **R** — A new repository that plays the role the sample repo played. "I essentially used this repo as a brain to create everything in my travel journal in the best possible way. I want now to create a repo that will act as that"
2. **R** — It is an orchestrator, and a large one. "(essentially a mega complex orchestrator)"
3. **R** — Scope is unlimited by domain. "to build anything I will ever need from now on"
4. **I** — The scope is far wider than one web app. "(obviously having present that the current Claude brain's scope for creating stuff is much bigger)". Past sessions confirm this: apps, games, documents, research, a Minecraft world, a legal analysis system, a car project.
5. **I** — The sample repo's strengths must carry over. "using everything we learned with the sample repo I attached". That means its lessons as well as its structure: what worked, what cost too much, what broke.

### A.2 The two-repo operating model

6. **C** — Two repos in every chat. "When using it I will always use two repos in a chat, one of them the Claude brain"
7. **C** — The brain is not edited by hand or by project work. "which will be only modified by its own machine learning systems as it improves by learning with everything I use it for"
8. **R** — The brain learns from every use. "as it improves by learning with everything I use it for"
9. **R** — The second repo is where the product is built. "the other repo will be where the project will be built"
10. **R** — The project repo may hold project-specific extensions. "which can also hold files and tools to complement the Claude brain functionality that are specific to that project"
11. **C** — The pairing is permanent. "both will always be worked together from now on"
12. **R** — The project side must be shaped to fit the brain. "so the project must be built to work perfectly with it forever"
13. **A** — "the project must be built to work perfectly with it" could mean (a) every project repo gets a standard brain-compatible scaffold, or (b) the brain itself is the "project" that must work with the pairing. Reading (a) fits the sentence. The plan should include a project-repo bootstrap and a compatibility contract with versions.
14. **A** — "only modified by its own machine learning systems" conflicts with the first build, which must be written by Claude in a session. Reframe: after the initial build, changes to the brain go only through a defined learning pipeline with its own gate, never as a side effect of project work.
15. **X** — "machine learning systems". Claude cannot retrain its weights from inside a repo. What can be built honestly: a file-based learning loop (capture what happened, distill lessons, update skills, cards, routing tables and evals, gate the change with a regression suite). The plan should say this in plain words and not call it model training.
16. **I** — "forever" implies durability across model versions, Claude Code changes and renamed tools. The brain needs versioned contracts, a self-check at session start and a way to degrade when a feature is missing.

### A.3 Deliverable one: the plan

17. **R** — A plan first. "Now you will create a super long, super detailed plan on how to build this"
18. **P** — Length and detail are wanted in the plan. "super long, super detailed" (said twice: "Create now the super long and super detailed plan")
19. **R** — Research on the two named models. "based on very comprehensive research about Claude fable 5.2 and opus 5.5 (the main models ai will use it with)"
20. **A** — "the main models ai will use it with" most likely means "the main models I will use it with". Sonnet 5.5 and Haiku 5.5 exist and matter for cost, so the plan should cover routing to them even though they are not "main".
21. **R** — The plan must use lessons from the sample repo. "also using everything we learned with the sample repo I attached"
22. **R** — The plan must account for earlier builds. "Create now the super long and super detailed plan considering also all our previous builds in Claude"

### A.4 History and memory

23. **R** — Review memory and all chats. "Also you must look at all your memory in detail and all our chats"
24. **R** — Everything asked before must be completable by the brain. "consider everything I have ever asked you to build on Claude or any question I have ever asked you can be successfully processed to completion"
25. **X** — "all your memory" and "all our chats": there is no memory store, and consumer-app chats cannot be read. Cloud session history can be read, and only by sampling. Say so plainly. Part B is the honest version.
26. **I** — Item 24 is an acceptance criterion, not background. The brain needs a coverage checklist built from past requests (section B.4.d).

### A.5 Efficiency and speed

27. **R, top priority** — "Also VERY IMPORTANT, you MUST MAKE THIS THE MOST EFFICIENT CLAUDE TOOL EVER"
28. **R** — Token efficiency by named means. "it should be much more efficient in tokens through plugins and algorithms and quantum logic and many other thing you must research"
29. **X** — "quantum logic". No quantum computing is available to a Claude Code session, and none would cut tokens. Honest reframing: research and name what does exist (prompt caching, model routing, context budgeting, retrieval that returns small exact chunks, deterministic scripts doing work a model would otherwise do, scheduling and search algorithms). If a quantum-inspired classical method helps, name it as that and measure it. Do not label anything "quantum" for effect.
30. **X** — "THE MOST EFFICIENT CLAUDE TOOL EVER" cannot be proven. Reframe as measured targets against a baseline: tokens and cost per delivered ticket compared with the Travel Journal build, with the numbers published in the brain.
31. **R** — Research is required to find the methods. "you must research to see how you can make this super efficient token wise and super fast"
32. **R** — Speed. "super fast"
33. **A** — "plugins" may mean Claude Code plugins, MCP servers, skills, or tools in general. The plan should evaluate all four and choose by measured cost. Note that each loaded tool definition and skill description costs context in every session.

### A.6 Quality

34. **R** — "while delivering the absolutely highest quality work with absolute attention to detail"
35. **R** — Three named qualities. "(focus a lot on accuracy, creativity and extreme attention to detail)"
36. **A / tension** — Highest quality and lowest tokens pull against each other. The owner asks for both and ranks neither. The plan needs an explicit rule: quality gates are fixed, and efficiency is found in how the gate is reached (routing, caching, less re-reading, fewer redundant agents), never by lowering the gate.

### A.7 Process for this job

37. **R** — Build after planning, to the end. "then start building until completion once you have a full plan based on extremely extensive research"
38. **R** — Ten independent analyses of the prompt. "Make sure you analyze this prompt by 10 independent agents and extract everything I said in full detail"
39. **R** — Execution quality. "and you can execute to perfection by planning perfectly and researching and analyzing heavily everything"
40. **I** — No stopping to ask. The phrase "until completion" matches a pattern in at least six earlier sessions ("Do not stop and do not ask me anything else until everything is fully done").
41. **A** — "until completion" has no stated definition of done. The plan must define it: files that exist, checks that pass, a demonstration on a sample project.
42. **X / tension** — "super long" plans and "analyze heavily everything" cost tokens, which conflicts with item 27. Resolve by spending heavily once on the build of the brain and making every later session cheap.

### A.8 Carried over from message 1 and context

43. **C** — The sample repo is read-only in this chat. "we will not modify or touch this repo at all in this chat, just read it"
44. **I** — The owner does not use a terminal. Everything he must do is a file to read or a button to tap (from the sample repo's owner brief, and confirmed in section B.4.b).
45. **I** — He works from an iPhone. 53 of 55 owner sessions started in the iOS app. Reports and prompts must read well on a phone.

---

## PART B — What the owner has asked Claude for

### B.1 Session table

Omitted from the repository copy: the table listed 120 session ids and titles, which are private history. Counts and findings drawn from it are kept below.

### B.2 Projects seen, oldest to newest

| Project (repo) | Sessions | What it is | Evidence |
|---|---|---|---|
| Japan 2026 travel app (`japan-2026`) | 9 | Vite + React PWA for a 15-day Japan trip: itinerary, history essays, places, wiki, tools, palettes, icon. Five-agent team (CEO, front end, back end, content, journalist). | Titles; agent files read inside transcript; owner messages |
| Spanish legal counsel system (`New-CC`) | 3 | Corpus of 12,249 legal texts, 35 knowledge files, 13 agents, five-phase case pipeline, PDF reports, bilingual. Started with "set up". | Transcript content |
| DevTool (`DevTool`) | 2 | A developer or deployment tool that shows Vercel build results. | Owner messages |
| Audiobooks (`Audiobooks`) | 1 | Not identified beyond the name. | Title only |
| Org (`Org`) | 2 | A personal app ("command center" appears in a related prompt). Icon redesign. | Owner message |
| Minecraft world editing (`mncrft`, `Server`) | 3 | Python tools that write Bedrock structure files; later a local server run on a Mac with Docker. | Owner messages |
| Plant identification (`plant`) | 1 | PlantNet recognition plus GBIF taxonomy lookup module. | First message |
| Delivery game (`game`, and one attempt inside `japan-2026`) | 2 | Browser game built in waves, auto-shipped to `main`. | Last assistant message |
| Course projects (`Projectx`, `projectnew`, `project-3`, `project-4`, `project-5`, `project-8`) | 8 | Rubric-driven assignments: an outfit-recommendation agent, a fine-tuned classifier with a demo video script, a bug-fix exercise, an issue from a public repo. | Owner messages |
| Aperture / camera learning app (`camerapp`) | 5 | A learning app with lessons, flash cards, generated audio. | Owner messages |
| Communication skills app (`betteryou`) | 1 | Learning app built from a book: 17 stages, 163 lessons. | Last assistant message |
| Photography course app (`PhotoEd`) | 1 | Book-centred learning dashboard. | Owner messages |
| Birding trip app (`birding-SAL-GUA`) | 2 | Trip research and web app with eBird data harvest. | Owner messages |
| Dream car (`car-build`) | 1 | Research plus a web app, run as a non-stop improvement loop with hourly check-ins. | Routine prompts |
| Costa Rica trip (`costa-Rica-3`) | 2 | A 2,052-file knowledge base with BM25 search, 10 agents, 10 skills, a 189-page brochure, then an iPhone web app. | Compaction summary |
| Travel Journal (`Travel-Journal` + company repo) | 13 owner sessions + 65 child sessions | The sample repo and its product. | Sample repo; transcripts |
| Claude Brain (`Claude-Brain`) | 1 (this one) | The current request. | Owner prompt |

### B.3 Standing instructions found in memory-like stores

From the sample repo (already binding there, and strong signals for the brain):

- `owner-brief.md`: prefers visual interfaces to the command line; "Everything he must do is a file to read or a button to click." Max subscription. Bird photography with a long telephoto, astrophotography with a star tracker.
- `DECISIONS.md` rows 13 to 17, marked as owner direction and not assumed: the journal covers the whole experience and is not food-first; build all software and prove it on a sample before any real trip; the app is read-only and trips are added only in the Claude chat; a light theme "that does not hurt the eyes and looks stunning".
- `CLAUDE.md` section 11 (owner instruction of 2026-11-05): the product's `main` is always the latest deployable app, pushed only on a green gate, never force-pushed.
- `NEEDS_YOU.md`: twelve numbered items, each written as click-only steps.

From routines (all created by Claude on the owner's behalf, all finished):

- Car project: 20 or more one-shot "continue improvement loop" check-ins, about one per hour for two days. Prompt text: "user asked for non-stop work until they say stop".
- Travel Journal: an hourly "teams check-in (keep ≥10 running)" routine. Prompt text: "owner: always at least 10 teams running". Several one-shot release and CI checks.

### B.4 Synthesis

#### (a) Catalogue of task classes

Counts are owner sessions in which the class clearly appears. A session can count in more than one class. Counts are a floor, because of sampling.

| # | Task class | Sessions | Example quotes (read directly) |
|---|---|---|---|
| 1 | Web or PWA app build, iPhone first, deployed on Vercel | 30+ | "turn it into a Vite web app to be deployed in vercel and that I will be able to use perfectly in my iPhone 17 pro" · "The app should be totally changed to give the books a much more central part" |
| 2 | Design and visual polish | 12+ | "I want a brand new design for the app icon, propose 5 ones in 2026 IOS style so it looks great, I will choose from the 5 you provide" · "Make the Tori gate in the icon larger and exactly in the center of the icon" · "add some text with the top image like travel journal with perfect typography and a color that looks great with the background images" |
| 3 | Session handover, repo memory and "set up" protocols | 12+ | "research online how to create a true memory in the repo for Claude code for when I create a new chat soon you know exactly everything we have done in detail and everything I've told you" · "When I just put setup at the start of the chat, set up these two words will be the key to start initializing the chat" · "Get everything ready to continue in a new chat with renewed context" |
| 4 | Deployment and release to `main` | 10+ | "Please push to main and fix the deployment so the new version is actually visible when using the vercel link and make sure you always do this for any update after this" · "Does it know to always merge into main so vercel deploys with extreme detail?" |
| 5 | Agent team and orchestration design | 8+ | "Recommend a team of 7 different agents … extremely detailed with at least 600 words each … I want this team to also have a brain agent as a keystone that will take all the needed decisions that otherwise it would ask me" · "I need you to deploy plenty of agents and help me craft at 60000 word document" |
| 6 | Deep research and knowledge bases with retrieval | 7+ | "creating extremely detailed files about everything we will do on our trip … all organized with a rag system and with agent teams" · "go research for a long time hundreds of websites and prepare the whole new report" |
| 7 | Long-form writing and content production | 6+ | "every daily article of the history section being rewritten to 800-1000 words through very comprehensive research … in total will amount close to 60000 words" |
| 8 | Learning apps generated from books or topics, and reusable blueprints | 5 | "create an extremely long and detailed json document for Claude code to build from scratch (with a very long multi-session plan) something similar but for the topic of my choice" · "Remember you should not add any of the quick check and questions and answers just the actual lesson part" |
| 9 | Rubric-driven course deliverables and documentation audits | 8 | "Make sure we have all of this and if we don't then explain what we don't have" · "Analyze step by step and make sure everything is done fully correctly" · "Prepare a script for a video in the shorter most simple end" |
| 10 | Bilingual output, Spanish and English | 4+ | "Hey team I'm with my grandparents who only speak Spanish, one by one tell them a little about what you do in this team" · a "set up" request written in Spanish · a Spanish-language update report on a legal case · the final report of one app session delivered in Spanish |
| 11 | Data pipelines and external APIs | 5+ | Plant identification via PlantNet and GBIF; eBird harvest for birding; routes, climate and species pipelines for Costa Rica; text-to-speech for lessons ("Can we start with just one lesson for me to try and see if I like the voice") |
| 12 | Games and creative builds | 4 | "Continue improving" (game built in waves) · Minecraft: "help me edit a Minecraft world creating buildings and other structures that I tell you" |
| 13 | Help running things on his own computer | 4 | "How can i run this locally on my macbook pro give me all code boxes to copy and paste in my terminal" · "So how do I run it? Can't I launch in my browser?" · "im done playing, close everything" |
| 14 | Questions about Claude itself and repair of the working setup | 5+ | "check your memory and create a report of my main ideas for everything and what you should do when editing the web app" · "I have a bunch of chats running on the same repos probably causing problems, how can we fix it, stop everything into one and organize everything without losing any of the work" · title "Enable experimental agent teams feature" |
| 15 | Repo operations | 5+ | "Clone it into this repo" · "Relocate the book pdf to a perfect location within the repo" · "revert all you did if you made any changes" |
| 16 | Legal research and case analysis (Spanish law) | 3 | A corpus-backed counsel system with a five-phase pipeline and PDF reports; a request for a refreshed Spanish report after new facts emerged |
| 17 | Efficiency requests | 2 | "Prepare a quick low token very effectively built base for the whole build as well" · the current message 2 |
| 18 | Downloadable files and documents | 3+ | "I want to download these two, make the downloadable from here" · brochure delivered as PDF |

#### (b) Recurring instruction patterns and standing preferences

1. **Run without stopping and decide for him.** "Do not stop and do not ask me anything else until everything is fully done, take the best possible choices based on research for any questions you might have". Repeated in the car project, the Costa Rica project, the Minecraft agent brief ("a brain agent as a keystone that will take all the needed decisions that otherwise it would ask me") and message 2.
2. **Short trigger words that start a whole protocol.** "set up" (legal system, birding, Costa Rica), "Start running" (Travel Journal), "Continue" as a complete message (seen eight or more times). The brain needs one-word entry points that are safe to send from a phone.
3. **A fresh chat when context is high, with a perfect handover.** "we are using too much context" · "start it in a new chat with renewed context" · "prepare everything and give me the prompt I should give to start it". Seen in at least seven sessions. Handover is a first-class deliverable.
4. **`main` must always be the deployable app and Vercel must show it.** Asked in DevTool (May), the communication app (June), Aperture (June), birding (July), Travel Journal (November, three times in one hour). This is the single most repeated standing instruction.
5. **Research first, heavily.** "comprehensive research", "research heavily", "hundreds of websites", "research all AI and anthropic info online that might be useful".
6. **Emphasis vocabulary.** "extremely detailed", "super long", "perfect/perfectly", "fully", "everything", "absolutely", capital letters for priorities. He equates length with thoroughness for plans and agent briefs ("at least 600 words each", "at least 1000 words").
7. **Agent teams as the default shape of work.** Asked for by name in the Japan app, Minecraft, legal system, Costa Rica, Travel Journal ("always at least 10 teams running").
8. **Options, then he picks.** "propose 5 ones … I will choose from the 5 you provide" · "I really like option number one but…". Design decisions go well when offered as a short numbered menu with images.
9. **Try a small sample before the full run.** "Can we start with just one lesson for me to try and see if I like the voice" · "prove it on a SAMPLE before any real trip".
10. **Phone-first, no terminal.** 53 of 55 sessions from iOS. When a terminal is unavoidable he asks for "all code boxes to copy and paste". He pastes raw terminal output back and expects diagnosis.
11. **Accuracy about his own facts.** "It is very important you're fully accurate in mapping my trip chronologically" · "today (20th) should be day one, not day 2 … we have 15 days not 16" · "don't focus at all in the number of species … the number is misrepresenting". He corrects wrong facts quickly and expects no invented numbers.
12. **Build for growth.** "it must made with the knowledge that it is to display dozens of trips, so make sure you figure out how to implement this dynamic heavily".
13. **Reuse what worked.** "I love it and I want to create something similar in a different repo for a different topic". The blueprint request in June is an early version of the Claude Brain idea.
14. **Spanish when the audience is Spanish-speaking.** He writes in either language and expects the reply to match.
15. **Dictated, fast, typo-tolerant messages.** "memore", "A new chart", "ai" for "I". The brain must read intent, not spelling.

#### (c) Recurring failure and complaint patterns

| # | Pattern | Evidence | What the brain must do about it |
|---|---|---|---|
| 1 | **Context exhaustion forces chat changes.** | "we are using too much context"; seven or more handover requests; car session at 610,677 of 1,000,000 tokens; one session continued from a compaction summary | Budget context per session, checkpoint to files, hand over before the limit, keep the start-up read small |
| 2 | **Timeouts on large single edits.** | "Continue always dividing in many steps, do not time out" · "this is a simple task why are you timing out"; 27 timeout strings in that one page | Never write or rewrite a very large file in one step; chunk by rule |
| 3 | **Huge pastes kill sessions.** | A 2.58 MB source file with inlined images pasted as a message; that session ended as failed. Two other sessions return pages over 16 MB | Never inline large binaries; detect and move big content to files; tell the owner to attach instead of paste |
| 4 | **Vercel shows nothing because work sat on a branch.** | "My Vercel deploy reads from main, which might be why I don't see any changes at all"; car project ended with "site still 404; awaiting Vercel promote" after a day and a half of idle check-ins | A release rule in the brain from day one, plus a check that production actually serves the new commit |
| 5 | **Rate limits from too many parallel agents.** | Costa Rica summary: "20 parallel agents hit the session rate limit (429) and produced nothing"; 429 strings in five sessions | Cap parallel agents, write incrementally, prefer scripts for bulk data work |
| 6 | **Many chats on the same repos at once.** | "I have a bunch of chats running on the same repos probably causing problems"; background agents still running when he wanted to leave: "Seems like there are still two tasks running are you sure I can start a new chat" | One lead per repo pair, a visible list of what is running, a clean stop procedure |
| 7 | **Quality regressions after long iteration.** | "It's the worst and most incomplete it's ever been" followed by a request to go back and restart from scratch | Tagged known-good versions, easy rollback, regression checks before replacing a working feature |
| 8 | **Requests cancelled after work started.** | "Just cancel doing anything about this in the Japan app, revert all you did" | Work on a branch, keep reverts cheap, confirm the target repo before a large build |
| 9 | **Repo assumed to hold work that was not there.** | Three sessions opened on empty repos; Claude reported "There is no code or tests to analyze" | Check the repo state first and say what is missing in the first reply |
| 10 | **Secrets pasted into chat.** | Three occurrences (a storage token, two API keys) | Never echo or commit them; use the credential form; write a warning into the owner guide |
| 11 | **Infrastructure and model availability failures.** | One session never started ("executable file not found"); one ended with "Claude Fable 5 is currently unavailable"; "Overloaded" strings in four sessions | A fallback model plan and a start-up self-check |
| 12 | **Quota or account limits on third-party services.** | Text-to-speech calls returned "exceeded quota"; a free weather quota ran out | Stand-ins and a clear "needs you" note instead of silent failure |
| 13 | **Tight performance budgets blocking releases on a busy machine.** | "The one failure was the iPhone day-page load time: 2,652 ms against the 2,600 ms budget. That run shared the CPU with other agents." | Run gates on a quiet machine or in a dedicated session; separate noisy measurements from hard failures |
| 14 | **High cost of the orchestration style.** | Reported session cost at list price, last value seen per session: Costa Rica app 626.51 USD; one Travel Journal session 495.77; another 377.90; car 285.23. About 3,200 USD across the 39 owner sessions with a readable figure, of which about 1,780 in 12 Travel Journal parent sessions. Child sessions are not included. The car session shows 525,899,094 cache-read tokens | This is the baseline that "most efficient" must beat. Record cost per ticket and publish it |

Caveat on row 14: the figure is the `total_cost_usd` of the last result event on the newest page. One cross-check against the session record matched (285.23 against 282.75 for the car session), so it is treated as cumulative. The owner is on a Max subscription, so this is list-price equivalent, not money paid.

#### (d) Capability coverage checklist (acceptance tests for the brain)

Each line is a test the finished brain should pass on a sample project.

**Start, resume, handover**

1. Given the single message "set up" or "Start running" in a new chat with both repos attached, the brain orients, reads only a small fixed set of files, states where the project stands in under ten lines, and starts the next task without a question. Proof: a start-up token count under a published budget.
2. Given "Continue" with no other text, the brain resumes the exact ticket recorded in the progress file. Proof: the next commit carries that ticket id.
3. Given "get everything ready to continue in a new chat", the brain stops background work, commits and pushes both repos, writes a handover file and returns the one-line prompt to paste. Proof: a list of running tasks that is empty, and a clean tree in both repos.
4. Given a session nearing its context limit, the brain proposes the handover itself before quality drops. Proof: a threshold in configuration and a logged trigger.
5. Given several chats on the same repos, the brain detects it and names which one should continue. Proof: a lock or lease file and a plain-language warning.

**Build and release**

6. Given "build a Vite web app for iPhone and deploy on Vercel", the brain scaffolds, builds, tests at iPhone viewport sizes, and leaves `main` deployable. Proof: build log, phone-size screenshots, and a check that the production URL serves the new commit.
7. Given any completed change in a project whose owner deploys from `main`, the brain fast-forwards `main` only on a green gate and never force-pushes. Proof: gate output stored with the release line.
8. Given a failed Vercel build, the brain reports the real failing step in plain words. Proof: the quoted error line.
9. Given a production site that still shows the old version or a 404, the brain says so in the first line and gives click-only steps, and does not keep polling for a day. Proof: a bounded number of checks.
10. Given "it's the worst it's ever been, go back", the brain restores the last tagged good version within one turn. Proof: tag list and a diff against the restored state.
11. Given "cancel and revert everything", the brain reverts cleanly and shows the repo matches its state before the work. Proof: an empty diff.

**Design**

12. Given "propose 5 app icons, I will choose", the brain returns five rendered options as images with one-line descriptions, then applies the chosen one everywhere it is used. Proof: image files and a list of replaced assets.
13. Given a visual correction such as "make the gate larger and exactly centred", the brain measures the result. Proof: before and after images and the measured offset.
14. Given "redesign the app to be book-centric" or similar, the brain produces a design brief, gets a critic score at or above the bar, and ships it. Proof: critic score and screenshots.
15. Given five hero photos, the brain stores them at full quality, serves sized derivatives and rotates them as asked. Proof: file sizes and a test of the rotation.

**Research, knowledge, writing**

16. Given a pasted conversation and "create a huge detailed brochure and a knowledge base any AI can use", the brain builds a searchable file set with sources and assumptions listed, then a PDF. Proof: file count, search test results, the assumptions list.
17. Given "be fully accurate about my dates and facts", the brain keeps one canonical facts file, and every derived file is checked against it. Proof: a fact-check report with zero mismatches.
18. Given "rewrite 60 articles to 800 to 1,000 words each", the brain plans batches, writes in chunks that cannot time out, and verifies word counts. Proof: a per-article word-count table.
19. Given "write a team of seven agents, 600 words each, plus a 1,000-word workflow", the brain meets the stated lengths and registers the agents in the right folder. Proof: word counts and a listing of the agent files.
20. Given a question in Spanish, or an audience that reads Spanish, the brain answers in Spanish and keeps technical terms correct. Proof: a blind back-translation check on a sample.
21. Given a legal-research style question, the brain cites its sources, states its limits and separates fact from estimate. Proof: every claim of law carries a citation.

**Reuse and learning**

22. Given "I love this app, make a blueprint so an empty repo becomes the same kind of app for another topic", the brain produces a reusable template and proves it by generating a second small app from it. Proof: the second app builds.
23. Given a finished project, the brain's learning pipeline distils lessons into its own files, and a regression suite shows no earlier capability got worse. Proof: before and after scores on the brain's eval set.
24. Given project work, no file in the brain repo changes outside the learning pipeline. Proof: a hook that blocks the write, and a test that tries it.
25. Given a project that needs its own agents or tools, the brain places them in the project repo, not in the brain. Proof: a listing of both repos after the task.

**Data and integrations**

26. Given "identify plants with PlantNet and validate with GBIF" or "harvest eBird data", the brain builds the pipeline behind an interface with caching, and handles quota errors by switching source or writing a needs-you note. Proof: tests with a recorded fixture and a simulated quota error.
27. Given an API key requirement, the brain asks through the secure credential form and never repeats a key that was pasted in chat. Proof: a scan of the repo and the reply for key patterns.
28. Given "generate audio for one lesson so I can judge the voice", the brain produces one sample and waits for a yes before the full run. Proof: one file and a recorded decision.

**Owner's own machine**

29. Given "how do I run this on my Mac" or pasted Windows terminal errors, the brain gives one copy-and-paste box per step, explains the error in one sentence and prefers a browser route when one exists. Proof: the steps work on a clean checkout.
30. Given "I'm done, close everything", the brain gives the single command or tap that stops all of it. Proof: a list of what was stopped.

**Rubrics and audits**

31. Given a pasted list of required deliverables and "make sure we have all of this", the brain returns a table of present, missing and wrong, and fixes what it can. Proof: the table and the commits. If the repo is empty, the first sentence says so.
32. Given "analyze the test coverage and propose improvements", the brain reports measured coverage and a ranked list. Proof: coverage numbers.

**Efficiency and reliability**

33. Given any ticket, the brain routes each step to the cheapest model that meets the quality bar and records tokens and cost. Proof: a per-ticket ledger, and a comparison against the Travel Journal baseline.
34. Given a task that could fan out, the brain caps parallel agents below the rate limit and still finishes. Proof: zero 429 errors in the run log.
35. Given a very large file or a pasted blob, the brain never writes it in one step and never inlines binaries. Proof: a size check in a hook.
36. Given a model that is unavailable or overloaded, the brain falls back to the next model and says which one did the work. Proof: a logged fallback.
37. Given a noisy performance measurement, the brain re-runs on a quiet machine before calling a release red. Proof: two runs recorded with machine load.
38. Given a decision only the owner can make, the brain writes a numbered needs-you item with click-only steps and continues with other work. Proof: the item exists and the session did not stop.

**Creative and one-off builds**

39. Given "build a small game and keep improving it", the brain ships in waves with tests and a short note per wave. Proof: wave log and test counts.
40. Given "design Minecraft structures for my Xbox world", the brain researches the transfer path first and says which steps need a PC or a paid service. Proof: a feasibility note before any build.

---

## Decision-relevant findings, short list

1. No memory store exists, and consumer chats are unreachable. Cloud history is reachable: 120 sessions, 55 started by the owner, sampled as described in section 0.
2. The "brain repo" idea is not new for him. He built versions of it four times: the Japan app team (April), the legal counsel system with a "Cerebro" brain agent and a "set up" trigger (May), the learning-app blueprint (June), the Costa Rica knowledge base (October), then the Travel Journal company repo.
3. The most repeated standing instruction is "`main` is always the deployable app and Vercel shows it". It appears in five projects.
4. The most repeated complaint is context exhaustion and the forced change of chat. Handover must be a built-in, one-message capability.
5. He works from an iPhone, with dictated messages, one-word triggers and no terminal.
6. He wants autonomy: decide, record, continue. Questions are a failure unless only he can answer.
7. The cost baseline is high: about 3,200 USD list-price equivalent across 39 owner sessions with a readable figure, with single sessions at 496 and 627 USD, before the 65 child sessions.
8. Too many parallel agents has already failed outright (20 agents, 429, nothing produced) and blocked releases through CPU noise.
9. Large single writes and large pastes have timed out or killed sessions. Chunking rules and size guards belong in hooks.
10. "Quantum logic", "machine learning systems" and "most efficient ever" need honest reframing as measurable, file-based mechanisms.
11. His scope is wide: apps, design, research, long writing, bilingual output, data pipelines, games, legal analysis, course rubrics, and help running software on his own machines. The 40 acceptance tests in B.4.d cover each.
12. He likes numbered options with images and a small sample before a full run. Both cut wasted work and should be default behaviours.
