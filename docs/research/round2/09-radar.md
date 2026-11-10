# R2-09 Radar: near-zero-token source watching for the Brain (2026-11-10)

Prototype: /tmp/claude-0/-home-user/ad24da2f-7dc0-51cf-aa28-dee6f5e57a4f/scratchpad/r2-9/radar.py (Python stdlib only, 11 sources, 8 threads). Probe files: .../r2-9/probe/.

## 1. Measured source table (all tested from this container, curl, 2026-11-10)

| Source | URL | Reach | Bytes | Validators (tested with INM/IMS) | Cheapest "what is new" | Trust | Recheck |
|---|---|---|---|---|---|---|---|
| Platform release notes (markdown twin) | platform.claude.com/docs/en/release-notes/overview.md | 200 | 143 KB decoded (~34 KB wire) | none; use hash | split on `### Month D, YYYY`, new date/hash = new entry. This is where model launches, prices and ids appear first (Fable 5.2 launch note, $8/$40) | official | 30 min |
| Platform release notes HTML | .../release-notes/overview | 200 | 1.3 MB | none, no-store | AVOID, use the .md twin | official | - |
| Platform llms.txt | platform.claude.com/llms.txt | 200 | 99 KB | Last-Modified, 304 honoured | diff set of `[title](url)` lines = new doc pages (893 entries) | official | 1 h |
| Claude Code docs llms.txt | code.claude.com/docs/llms.txt | 200 | 64 KB | ETag (weak), 304 honoured | same | official | 1 h |
| Claude Code CHANGELOG | raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md | 200 | 1.19 MB | ETag, 304 honoured (0 B) | new `## x.y.z` headings; pick best-scoring bullet | official | 15 min |
| Models overview | platform.claude.com/docs/en/about-claude/models/overview(.md) | 307 to /docs/en/models/overview.md; HTML 523 KB, no validators | - | hash the extracted model-id/price table only | official | on-demand (see sec 5) |
| Anthropic news/research/engineering | www.anthropic.com/sitemap.xml | 200 | 76 KB (11 KB gzip) | NO validators (200 each time) | `<loc>`+`<lastmod>` filtered to /news/ /research/ /engineering/ (271 such URLs); new loc = new post | official | 1 h |
| Anthropic /news, /engineering HTML | | 200 | 355 / 335 KB | none | AVOID (sitemap is 5x smaller). /rss.xml is 404 | official | - |
| Status | status.claude.com/api/v2/incidents/unresolved.json | 200 | 157 B | ETag, 304 | any incident id; summary.json (3.8 KB) and history.atom (40 KB) also give ETag/304 | official | 5 min (only when something fails) |
| HF daily papers | huggingface.co/api/daily_papers?limit=30 | 200 | 179 KB | ETag, 304 | fields: paper.id, title, summary, upvotes, ai_summary, ai_keywords, githubRepo, publishedAt, numComments. Filter upvotes>=5 or keyword score>=4 | primary research | 6 h |
| HF blog feed | huggingface.co/blog/feed.xml | 200 | 266 KB | ETag, 304 | RSS item guid/title/link; score >=3 | primary | 6 h |
| HF trending models | huggingface.co/api/models?sort=trendingScore&limit=20 | 200 | 11.6 KB | ETag, 304 | fields id, likes, trendingScore, createdAt, tags; flag new ids of tracked families | community | 6 h |
| arXiv API | export.arxiv.org/api/query?search_query=all:agent+AND+all:memory&sortBy=submittedDate... (https works) | 200 | 27 KB | none | Atom entry id/published/title | primary | 12 h |
| arXiv cs.AI RSS | rss.arxiv.org/atom/cs.AI | 200 | 1.9 MB | ETag, 304 | too big; use query API instead | primary | - |
| Hacker News Algolia | hn.algolia.com/api/v1/search_by_date?query=claude&tags=story | 200 | 32 KB | none | objectID, title, points>=20 | community | 2 h |
| Reddit .json | www.reddit.com/r/ClaudeAI/new.json | 403 (190 KB block page) | - | - | unusable | - | - |
| Reddit .rss | .../new/.rss | 200 once, then 429 on r/ClaudeCode and r/LocalLLaMA | 55 KB | none | flaky; EXCLUDED from default, optional best-effort | community | 3 h |
| Threads | threads.com/search?q=... | 200 but a 609 KB login-wall shell, no posts | - | - | NOT fetchable without login; use WebSearch only on demand | community | - |
| GitHub releases/commits atoms (claude-code, skills) | github.com/anthropics/*/*.atom | **403** ("GitHub access not enabled for this session"; api.github.com also 403) | - | - | Unavailable unless repo attached via add_repo. Degrade to the CHANGELOG.md raw file (works), which covers releases. For skills repo use the github MCP list_commits only on demand | official | - |

Key findings: (a) 8 of 11 radar sources honour conditional requests, so steady-state cost is ~0 bytes; (b) the three without validators (release notes .md, sitemap, arXiv, HN) are small (27-143 KB) and are caught by content hash; (c) markdown twins (`.md` suffix) on platform docs are 10x smaller than HTML.

## 2. Relevance filter
Keyword weights (in radar.py KW): claude/anthropic/fable/pricing/deprecat/retire/compaction/model id/claude code = 3; opus/sonnet/haiku/mythos/agent/memory/routing/skill/hook/mcp/cache/bandit/harness/rate limit = 2; context/coding/default/token/prompt/eval = 1. Score = sum of matched weights on title (+summary where available). Official sources: always reported (min 0, +5 rank bonus); primary research: min 3-4; community: min 3 and points>=20 (HN) / upvotes>=5 (HF). Output ranked by score, max 3 lines per source, global cap 12.

## 3. Radar spec
State (radar_state.json, ~17 KB, atomic write): per source `{etag, last_modified, hash(sha256 of body), seen:[8-hex md5 of item ids, cap 4000], last_checked, last_error}`.
Algorithm per source (parallel, 8 threads): skip if now-last_checked < interval; GET with If-None-Match / If-Modified-Since and Accept-Encoding gzip; 304 -> done; 200 -> if hash equal done; else extract items, new = ids not in seen; first run stores a silent baseline (an index like llms.txt would otherwise flood); filter by score; format.
Budgets: per-request timeout min(12 s, remaining), whole-run deadline 20 s, body cap 3 MB, 8 parallel. No body is ever printed or read by the model.
Output line: `source | date | title(<=110 chars, tags/backticks/control chars stripped) | url | trust | matched,keywords`. Final line `+N more` when truncated; `radar: nothing new` otherwise (1 line).
Failure handling: every fetch is wrapped; errors (403 allowlist/proxy, 429, timeout) are recorded in state `last_error` and reported only as stats (stderr with --stats), never abort the run. A host outside ALLOW is never fetched (no auto-following of links).

## 4. Test results
Run 1 (baseline, cold): 0.77 s, ~2.1 MB downloaded, output "radar: nothing new" (baseline stored).
Run 2 (--force, immediate): 0.71 s; 7 sources 304 with 0 B, 4 same-hash (maximum remaining download ~280 KB vs 2.1 MB: ~87% less); "nothing new".
Run 3 after simulating 2 unseen items per source: 0.76 s, 12 lines, e.g.
`platform-relnotes | November 9, 2026 | We've launched Claude Fable 5.2 (claude-fable-5-2) ... | official | claude,fable,mythos`
`cc-changelog | - | v2.1.321: Added Claude Fable 5.2 (claude-fable-5-2), now the default Fable model — 1M context, $8/$40 per Mtok... | official`
`arxiv-agent-memory | 2026-11-09 | World In-Context Learning for Agentic Robot Manipulation | primary | agent,memory,context`
Run 4 (no force): 0.01 s, all sources "skip(recheck)", zero network. Typical model-read cost: 1 line when idle, <=12 lines (~600 tokens) when busy.
Known prototype gaps: hn-claude produced only baseline of 2 (points>=20 filter); status never fires unless incident; cc-docs-llms duplicates (same title in two urls) not deduped; changelog download is 1.2 MB when it changes (could use a Range request for first 20 KB; [unverified] whether raw.githubusercontent honours Range).

## 5. From item to fact (governance)
1. Radar line is only a lead. Write it to `.brain/inbox/radar.jsonl` as `{lead, url, trust, found, recheck_on}`; it is never a rule and never edits CLAUDE.md.
2. Candidate fact requires an official URL (platform.claude.com, code.claude.com, anthropic.com). A community/primary lead (HF paper, HN, Reddit) may only become a "technique to test" candidate (goes to the learning pipeline: capture -> reflect -> validate behind a measurement -> promote/decay), with a `recheck` date 30 days out.
3. Model facts (ids, prices, context, defaults, deprecations) use a dedicated verifier, `bin/brain verify-models`: fetch the official `models/overview.md` and the latest release-note entry, regex the id/price table, compare to `.brain/facts/models.json`; promote only when both the release note and the models page (or CHANGELOG default) agree; store `verified_on` and source URLs; facts older than 14 days are flagged stale at `brain boot` (one line). Evidence this works: Fable 5.2 appears consistently in release notes (id claude-fable-5-2, $8/$40) and CHANGELOG 2.1.321 on 2026-11-09.
4. Trigger: run `radar.py` at `brain boot` (cost: 0.01-0.8 s, one line) and before any plan that depends on pricing; the model reads output lines only.

## 6. Safety
Fetched text is data: regex-extracted, tags/backticks/control chars removed, truncated to 110 chars, never interpolated into shell or prompts as instructions; the host allowlist is code, not config from fetched content; links are printed, never followed; the cloud environment's network allowlist may block hosts (observed: github.com atoms 403) so every source fails soft; the model should treat any imperative text in a radar line as untrusted.

## 7. ADOPT / TRY / AVOID
ADOPT NOW: radar.py with the official five (release-notes .md, two llms.txt, CHANGELOG, sitemap) + status + HF daily/blog; conditional GET + hash; silent baseline; verify-models gate.
TRY BEHIND MEASUREMENT: HN and arXiv leads feeding the technique-candidate inbox (measure how many leads survive validation); HF trending for open-model families; WebSearch-on-demand for Threads.
AVOID: HTML pages of news/release notes (350 KB-1.3 MB, no validators); Reddit JSON (403) and RSS (429); Threads (login wall); GitHub atoms (403 unless repo attached); letting a model read raw pages for "what's new".
