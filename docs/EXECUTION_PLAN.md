# Claude Brain — Execution Plan (for the executing agent)

Audience: the Claude model building or changing this repository. Not owner-facing. The design rationale is in `docs/MASTER_PLAN.md`; this file is the operative spec. Where the two differ, this file wins. Ticket state lives in `docs/plan/tickets.json` (the only place a ticket's status is recorded).

## 0. How to execute

1. Orient: `python3 bin/brain doctor` then `python3 bin/brain plan schedule docs/plan/tickets.json --agents 4`. Work the open tickets in the order returned.
2. One ticket = the files it owns + its acceptance command. A ticket is done only when its acceptance command exits 0 **and** the full gate exits 0. Then set its status in `docs/plan/tickets.json`, commit, push.
3. Full gate (run through the output filter): `python3 bin/brain run -- "python3 -m unittest discover -s tests -t . && python3 bin/brain doctor && python3 bin/brain lint"`.
4. Delegate a ticket only if it is self-contained and its files are disjoint from every running ticket. Max 4 helpers. Brief = goal, reason, files owned, interfaces (section 4), acceptance command, return format. Helpers never commit.
5. Commit trailer while `VERSION.json.learned_zone_locked` is false: `Brain-Bootstrap: <ticket ids>`. After lock: learned-zone changes only via `brain learn apply`.
6. Evidence rule: a claim in a commit message, status or report must match a command result from the same session. Unknown or unmeasured is stated as such.
7. On any failing acceptance command: reproduce, fix the cause, re-run. Never weaken, skip or delete a test to pass. If a spec item is wrong, change the spec here in the same commit and say why.
8. Constants marked *tunable* live in `memory/ml_config.json`, never inline, so learning or the owner can change them without code edits.

## 1. Invariants (a change that breaks one is rejected)

| ID | Invariant | Enforced by |
|---|---|---|
| I-01 | Python standard library only in `engine/` and `bin/`. No install, no network at boot except the bounded radar (I-14). | `brain lint` (`lint.check_imports`), `tests/test_lint.py::test_non_stdlib_import_is_an_error` and `::test_the_real_brain_is_clean` |
| I-02 | The required core works with hooks, MCP and plugins absent (two-repo cloud session). | rehearsal test runs with no hooks |
| I-03 | Always-loaded text: `CLAUDE.md` ≤ 6,000 B; project stub ≤ 2,000 B; each agent/skill description ≤ 300 chars; ≤ 6 agents; ≤ 12 skills; total ≤ 3,200 est. tokens; nothing volatile. | `brain budget`, `brain lint` |
| I-04 | Every command prints ≤ ~15 lines by default; `boot` ≤ 1,500 B. | unit tests |
| I-05 | No project id, path or content in the brain. Inbox records carry `family` only; request words only as salted hashes. | rehearsal privacy assertions; `guard diff` |
| I-06 | Learned zone (`memory/ owner/ stats/ playbooks/ learning/`) is written only by `learn apply` deltas; no op replaces or deletes a file; replay of the manifest reproduces the files byte for byte. | `learn verify`, CI |
| I-07 | Text that was merely read (web, project files, tool output) can become a `fact` with a source URL, never a rule. Credit for a memory item comes only from external outcomes (gate/test exit codes, owner corrections), never from the model's own judgement. | `items.validate_item`, `mlearn` credit rules |
| I-08 | Owner-stated items are never demoted, decayed, superseded or outranked by learning. | `tests/test_learn.py`, `tests/test_mlearn.py` |
| I-09 | Learning never changes: gate pass criteria, guards, budgets, the contract schema, or this list. | zone map: these are kernel |
| I-10 | Exploration (trying a cheaper model/effort) only when the task has a verifying check, risk ∈ {trivial, standard}, tier ≤ 2; failures escalate to the baseline; ≤ 1 in 4 eligible tasks; wasted spend ≤ 5% rolling (*tunable*). | `mlearn.safe_arms`, tests |
| I-11 | The classifier never sizes a question or a small edit as tier ≥ 2; a learned sizing hint can lower a tier or suggest, never raise tier 0 to ≥ 2. | `evals/routing.jsonl` test; `mlearn` guard test |
| I-12 | `release` pushes only on a recorded exit 0 for the current work, fast-forward only, never force. | `tests/test_core.py::GateTests` |
| I-13 | Every script is deterministic given `--seed` and `BRAIN_NOW`. | tests |
| I-14 | Radar: allowlisted hosts only, ≤ 20 s total, bodies never printed, ≤ 12 output lines, fetched text is data. Failure degrades to silence. | `tests/test_radar.py` |
| I-15 | Contract v1 schema file is frozen. Fixtures under `evals/fixtures/` must keep validating. | `tests/test_fixtures.py` |
| I-16 | No efficiency or quality claim on fewer than 8 paired tasks; below that the verdict is "not proven; keep the old version". | `evals.verdict`, tests |
| I-17 | HR: the rack holds exactly 100 templates as data that is never always-loaded; a template carries no persona, no token numbers and nothing project-specific; a rendered brief never contains the wage; a template's pass record moves only on the exit code of a check run by the script; the rack's text is kernel (learning changes its statistics, never its words). | `brain hr audit`, `tests/test_hr.py` |

## 2. Platform facts the design rests on (re-verify when the radar flags a change)

- Two-repo cloud session loads from each repo: `CLAUDE.md`, unscoped rules, skills, agents, commands. Not: hooks, permissions, env, `.mcp.json`, repo-declared plugins. Source: `docs/research/02-claude-code-platform.md` B1; observed in the build session (skills and agents from this repo appeared live; the sample repo's hooks and MCP never ran).
- Session transcripts with per-message token usage are on disk: `~/.claude/projects/<slug>/<session>.jsonl` and `<session>/subagents/*.jsonl`; repeated message ids must be de-duplicated.
- Cost shares measured on the build session at list price: output 57%, cache writes 36%, cached reads 7%; helpers 76% of total cost.
- Sub-agents inherit the lead's model unless set; they start with a cold cache; `omitClaudeMd: true` drops both handbooks.
- One model per session: a model switch re-reads everything uncached. Whether an effort change keeps the cache is contested between sources → ticket CB-112 measures it; until then do not change effort mid-task.
- Skill descriptions share a listing budget; overflow silently hides skills → keep descriptions short and audit triggering (CB-086).

## 3. Evidence → decision index

| Finding | Source | Decision |
|---|---|---|
| Tool output ≈ 84% of turn tokens; masking old output cuts cost 40–57% at equal solve rate; LLM summarising lengthens runs 13–15% | round2/02 §1 | Output filter on every command; no summarise-as-memory; `brain lint` flags raw long outputs in transcripts (CB-085) |
| Instruction files added > 20% cost without raising success in one study | round2/02, round2/06 | Byte budgets; `brain ablate` to test whether each always-loaded rule earns its place (CB-083) |
| Retrieving 1 memory beat 4 (49.7 vs 44.4); attack success 6% → 38% as retrieval went 3 → 10 | round2/01 | `recall` default k = 3, silence allowed (CB-081) |
| Whole-file memory rewrite collapsed 18k tokens to 122 and fell below baseline | 08, round2/01 | Delta ops only; collapse invariants (existing + CB-081) |
| Model-judged credit scored poisoned entries at 1.0 | round2/01 | I-07; credit from exit codes and owner corrections only |
| Curated skills +16.6 pp; ≤ 3 modules best; self-generated skills ≈ 0 or negative | round2/01, round2/06 | Self-written playbook lines stay `candidate` until evidence thresholds; skills are kernel, never auto-written (I-09) |
| Opus 5.5 medium $0.22/solved vs Fable 5.2 high $1.39; re-run-failures ≈ −40% | 01 B10 | Role defaults in `memory/models.json`; escalate on failed check |
| Routing papers' savings are single-turn; with tens of outcomes use hierarchical discounted Thompson; contextual models only after ~60+ per arm | round2/03 | CB-080 spec; contextual upgrade stays in shadow |
| n = 10 paired tasks proves only large effects (9/10 wins) | round2/07 | I-16; sign test + SPRT; pre-registration (CB-083) |
| Harness noise ≈ 6 points from infrastructure alone | round2/07 | A/A run before any A/B; interleave arms |
| Greedy coverage packing = 99.1% of optimum; annealing helps scheduling only | 04 | Keep as built |
| 8 of 11 update sources answer 304 with zero bytes when unchanged; whole radar run < 1 s | round2/09 | CB-082 |
| Unpushed work is invisible to the next cloud session | round2/05 | `checkpoint --push` (CB-084) |
| `close` relies on the model remembering | round2/05, 08 | `boot` repairs an unclosed previous session from disk if present, else records the gap (CB-084) |
| Multi-agent ≈ 15× chat tokens; 20 parallel agents hit 429 in the owner's history | 03, 07 | Cap 4; scheduler shows token cost of parallelism |

## 4. Component specs (round 2)

Existing modules and their tests are the baseline (118 tests green at commit of this file). Interfaces below are binding between tickets.

### 4.1 `engine/mlearn.py` — all statistical learning (CB-080)

Pure functions over one state object persisted at `stats/ml.json`. No I/O except `load(brain_root)`; writing happens only through `learn apply` (op `ML_FOLD`).

```
fold(state: dict, records: list[dict], cfg: dict) -> dict      # deterministic; order-stable; idempotent per record id
suggest_arm(state, cfg, task_class, family, role, risk, tier, has_check, rng) -> {model, effort, explored: bool, propensity: float, basis: str}
safe_arms(cfg, role, risk, tier, has_check) -> list[(model, effort)]
calibrate(state, task_class, family, est_tokens, est_minutes) -> {tokens_p50, tokens_p80, minutes_p50, minutes_p80, n}
item_score(state, item) -> float            # multiplier in [0.7, 1.3] from a Beta lower bound; 1.0 when unknown
alarms(state, cfg) -> list[str]             # ≤ 3 short lines for boot
flaky(state, gate_key) -> float
sizing_hint(state, cfg, hashed_words, rule_tier) -> {tier, confidence, acted: bool}   # shadow unless cfg.sizing.act
review_stop(found_a, found_b, both) -> {estimated_remaining, another_round: bool}
retention(item, now) -> float               # usage-based forgetting curve
report(state, cfg) -> list[str]             # owner wording with n for every claim
```

Algorithms (formulas and pseudocode are specified in the memos; implement them as written and put every constant in `memory/ml_config.json`):

1. **Routing bandit** — `round2/03` §2–3. Two quantities per arm, never one mixed scalar: pass posterior Beta(α, β) and a cost estimate (EW mean of tokens converted to list price). Hierarchy global → family → class with capped pseudo-counts (K_G = 4, K_F = 6, *tunable*). Discount γ = 0.97 per new outcome in the class; on a model-id change for an arm shrink its counts to an effective 4. Choice: Thompson draw per safe arm; among arms within δ = 0.05 of the best draw, lowest expected cost per success. Log `explored` and `propensity` (Monte-Carlo estimate over 200 seeded draws). Baseline arm = role default from `memory/models.json`. Acts only when ≥ 8 outcomes exist on ≥ 2 arms in the pooled view; otherwise returns the default with `basis` saying so.
2. **Safe exploration** — I-10. `safe_arms` returns only the baseline when the conditions fail.
3. **Estimate calibration** — `round2/08` §4. Ratio actual/estimate per class, EW mean pooled toward family (K = 5), empirical quantiles from the last 30 ratios; acts at n ≥ 5.
4. **Drift** — `round2/08` §5 and `round2/07` §4.4. EWMA chart on log tokens per task normalised by class; CUSUM on first-pass failures; Page–Hinkley on log tokens. An alarm prints a boot line, caps calibration n, applies an extra discount to the bandit, and names the last promoted item before the shift. It never reverts anything by itself.
5. **Memory credit** — `round2/08` §3, `round2/01` §3.1–3.2. Only items logged as *followed* get credit; advantage = outcome − class baseline; split 1/|F|; fractional counts kept in `ml.json` (item counters in JSONL stay integers). Ranking multiplier from the Beta lower bound (mean − 1.28 sd), clamped to ±30%. Owner-stated items are fixed at the top multiplier (I-08).
6. **Gate flakiness** — pass-after-fail on an unchanged commit raises the score; ≥ 0.2 means "re-run once before calling it red".
7. **Forgetting** — `round2/08` §11: R = exp(−t/S), S grows with each followed use; `learn decay` proposes demotion when R < threshold instead of a fixed 90 days.
8. **Review stopping** — Chapman estimator; treated as a lower bound; rule: second round only if estimated remaining ≥ 1 blocking, never more than three rounds.
9. **Learned sizing (shadow)** — multinomial Naive Bayes over salted word hashes with the rule result as a 0.7 prior; needs 30 strong labels; records its hint and whether it would have been right; acts only if `cfg.sizing.act` is true and I-11 holds.
10. **Offline check** — self-normalised IPS with weights clipped at 10; report effective sample size; trust only at ESS ≥ 30 and ≥ 10 runs per arm (`round2/03` §2.6).

Not learned automatically (I-08, I-09; `round2/08` §14).

### 4.2 Learning pipeline changes (CB-081)

- Inbox record kinds become: `ledger`, `outcome`, `used`, `note`, `review`, `correction`, `lead`. `outcome` carries: `id`, `task_class`, `family`, `tier`, `risk`, `model`, `effort`, `has_check`, `passed`, `first_pass`, `rework`, `tokens`, `minutes`, `est_tokens`, `est_minutes`, `explored`, `propensity`. Update `docs/ENGINE_SPEC.md` accordingly.
- `consolidate` emits one `ML_FOLD` op holding the new `outcome`/`used`/`review`/`correction` records; `apply` calls `mlearn.fold` and writes `stats/ml.json`. `ROUTE_OUTCOME` and `stats/routing.json` are removed (no history exists yet). `route.suggest` delegates to `mlearn.suggest_arm`.
- `recall`: default `k = 3`, budget 300 tokens; returns nothing when the best score is under a floor (*tunable*); ranking multiplied by `mlearn.item_score`; writes an injection log (`.brain/log/recall.jsonl`: ids shown, query hash).
- `close --used <id>:<followed 0|1>` (repeatable) records `used` rows; `helped` is computed by `mlearn` from outcomes, never passed in (I-07).
- Facts are bi-temporal: optional `valid_from`, `valid_to`; new op `SUPERSEDE {old, new}` sets `valid_to` on the old fact and links both; superseded facts are excluded from recall, never deleted (`round2/01` §3.6).
- Admission gate before `ADD` (`round2/01` §3.5): reject a note that is not actionable (no verb), not checkable (no evidence prefix), a near-duplicate (word Jaccard ≥ 0.6 or containment ≥ 0.8), or project-specific.
- Promotion needs two independent keys: evidence from ≥ 2 sessions **and** a positive lower bound from `mlearn` (*tunable* 0.6), or one owner statement.
- New item `type: "pitfall"` created only from a fail-then-pass pair in the same class (`round2/01` §3.7).
- `EDIT_TEXT` refused when the edit ratio exceeds 0.3 or the item shrinks below 40 characters (collapse invariant).
- Items gain optional `by_model` provenance; counters remain integers.

### 4.3 `engine/radar.py` — update radar (CB-082)

Port of the tested prototype (`round2/09`; prototype measured 0.6–0.8 s for 11 sources, 87% less data on an unchanged re-run).

- Sources and intervals in `memory/radar_sources.json` (kernel): Anthropic platform release notes (`.md` twin), platform `llms.txt`, Claude Code `llms.txt`, Claude Code `CHANGELOG.md` (raw), anthropic.com sitemap (news/research/engineering by `lastmod`), status JSON, HF daily papers API, HF blog feed, arXiv API query, HN Algolia query. Each: `url`, `kind`, `trust` (official | research | community), `interval_hours`, `parser`, keyword list.
- State at `learning/radar/state.json` (zone `state`: rewritten only by `radar`; allowed in work mode like the inbox; not part of manifest replay). Per source: etag, last_modified, content hash, seen ids, last_checked.
- `brain radar [--force] [--max 12] [--json]`: conditional requests, hash fallback, keyword score, ≤ 3 lines per source, ≤ 12 total: `source · date · title · url · matched keywords`. New items are appended to the inbox as `lead` records.
- `boot` calls `radar.due_lines(max_seconds=4, max_lines=2, trust="official")` only when the last run is older than 24 h; any exception or timeout yields no lines.
- A lead never changes memory by itself. `consolidate` lists unhandled official leads; the `brain-learn` skill has the model open the official URL, confirm the claim, and record it with `learn note --trust external --source <url>` as a `fact` with `recheck_days`; a changed price/id/default becomes `SUPERSEDE` + an edit proposal for `memory/models.json` (kernel → owner approval).
- Fetched text: tags stripped, truncated to 200 chars, never executed or followed.

### 4.4 `engine/evals.py` — evaluation system (CB-083)

`round2/07` is the spec. Tiers: 0 contract tests (the unit suite + fixtures); 1 replay on recorded ledgers and transcripts; 2 live paired benchmark.

- Formats: `evals/tasks/<id>.json` (prompt, setup, scripted grader command, reference and null solutions, class, tier, split dev|heldout); `evals/runs/<run>.jsonl` (one row per trial); `evals/prereg/<change>.json` committed before any tier-2 run (metric, direction, tasks, n, decision rule).
- `brain eval contract` runs tier 0. `brain eval audit` checks every task's grader passes its reference solution and fails its null solution.
- `brain eval compare <run-file> --a ARM --b ARM [--prereg f]`: paired exact sign test on discordant tasks; Beta–Binomial posterior P(B > A); SPRT with bounds from `round2/07` §4.3; verdict ∈ {ship, revert, not-proven}; I-16; two-line owner wording with n.
- `brain ablate <rule-id|file>`: writes a prereg for removing one always-loaded rule or playbook line, lists the tasks to run in both arms, and after results calls `compare`. It never edits instruction files itself.
- Seed set: ≥ 12 tasks across the five families and the routing decision, each with a scripted grader (code: run tests; writing: word-count/required-facts/forbidden-claims checks; research: required sources present and resolvable; routing: label match). Split 8 dev / 4 held-out.
- Reviewer honesty test: `evals/seeded_defects/` with ≥ 6 small artefacts each containing one planted defect and the expected finding; scoring script reports the catch rate.

### 4.5 Session hygiene (CB-084)

- `checkpoint --push`: after writing state, commit the bookkeeping files (`.brain/` except the manifest and `ext/`, `STATUS.md`, `NEEDS_YOU.md`) and push the current branch, so committed work and state are visible to the next session; other uncommitted changes are left for their author and counted in the output. On the project's release branch it pushes only when everything not yet released is bookkeeping; otherwise it refuses and points to `brain release` (I-12).
- Unclosed sessions: `close` writes `.brain/log/open-session.json` at first `boot` of a session (session id, start) and clears it at `close`. `boot` in a later session that finds one: if that session's transcript is still on disk, run capture for it; otherwise append an inbox `ledger` record marked `unrecorded: true`. One boot line reports it.
- Task packet: `brain plan packet <tickets.json> <ticket-id>` prints a ≤ 25-line brief from the ticket JSON (title, and where present goal, reason and interfaces; files owned; acceptance command; return format). Every delegated task carries an acceptance command.
- Unattended runs: `.brain/CHECKLIST.md` generated from open tickets/requirements; skills `brain-start` and `brain-build` tell the lead to continue while it has open items and no blocker, with a cap of 3 automatic continuations (`round2/05` finding 4).
- `brain resume`: compaction-proof restatement (≤ 12 lines): state, open checklist items, files in flight, last gate result.

### 4.6 `engine/lint.py` — context and instruction lint (CB-085, CB-086)

`brain lint` exits non-zero on: budget violations (reuses `budget.check`); a `brain` command or flag named in any skill, method file, playbook, `CLAUDE.md` or template that does not exist in the real argparse tree; duplicated instruction sentences across always-loaded and on-demand files (normalised sentence hash appearing in ≥ 3 files); unscoped "never"/"always" without a reason clause in always-loaded text (report only); a non-stdlib import under `engine/` or `bin/`; a project id from `evals/known_project_ids.txt`; relative links that do not resolve. `brain lint --transcript` adds the six rules of `round2/02` §4 computed from the current session's transcript (raw tool results > 5,000 tokens, repeated full-file reads, sequential independent reads, sub-agent replies over cap, model switches, cache-read share).

`brain skill-audit` reads recent transcripts for skill invocations versus trigger phrases in user turns and reports skills that never fire or misfire (CB-086).

### 4.7 Retrieval (CB-087)

Apply the measured winner from `round2/04` (pending at the time of writing): keep FTS5 BM25; port only improvements that raised recall@5/MRR on the labelled set; store the labelled set as `evals/recall_golden.jsonl` with a regression test asserting recall@5 does not drop below the measured value minus 0.03.

### 4.8 Audit fixes (CB-088)

Apply every blocking and should-fix item from `round2/10-audit.md` (pending at the time of writing) to the instruction surface; each fix must leave `brain lint` green.

### 4.9 `engine/hr.py` — HR department (CB-120 to CB-125; owner decision D-13)

Evidence: `docs/research/round3/` (01 briefs and templates, 02 archetypes, 03 selection and wages, 04 domain methods). Rules for template text: `hr/GUIDELINES.md`; fields and limits: `hr/template.schema.json`.

- **Rack**: `hr/rack/<group>.jsonl`, ten groups of ten, 100 templates. Each maps onto one of the six runtime agents (`base_agent`), which supplies tools and the default model. Nothing in the rack is loaded until a hire asks for it.
- **`brain hr hire "<goal>" [--why --owns --input --check --also --family --class --risk --tier --size --agent --template --material-tokens --parallel --force --seed --json]`**:
  1. *Hire or not*: no check → the lead does it; small material and not parallel → the lead does it (a helper costs a cold start); otherwise hire. At most four open contracts.
  2. *Template*: BM25 over `when`, name and keywords (stemmed, English and Spanish), blended with query coverage; multiplied by the template's record (lower bound of a Beta pass rate, shrunk template → group → rack, clamped to ±30%); untried templates are not boosted on high-risk work; a template on probation is marked down; below the fit floor no template is used and a plain brief is written.
  3. *Model and effort*: `mlearn.suggest_arm` for the base agent's role (safe exploration, I-10).
  4. *Wage*: output-equivalent tokens (all usage priced at list rates ÷ the model's output price). Size band (S 20k, M 60k, L 200k, XL 450k; only M rests on measurements, from 34 helpers in the build session) × the 80th-percentile ratio of real use **to the band** once five hires are settled (the template's own ratios, else its size band's, else all), bounded 0.4×–3×. The ratio is never taken against the wage itself: that would cancel each correction and make wages swing back.
  5. *Brief*: rendered in the order task, why, working folder, role line, scope, inputs, all method lines and drift plus every lead-supplied constraint, up to two pitfalls, done-when, tier block, hygiene line for agents that read outside content, return contract. Written to `<project>/.brain/log/hr/<contract>.md`; the contract JSON sits beside it. The delegation message is one line pointing at the brief. Brief lint: a note above 350 words and an error above 500, required parts present, and no persona, budget or thinking wording in what HR adds (the lead's own task text is exempt), nor a verification paragraph for Opus and Fable. Contract ids never collide; a new hire for the same task supersedes this session's earlier open one; the four-contract cap counts this session's contracts with or without a project; `--dry-run` writes nothing.
- **`brain hr settle [contract]`** (also run by `brain close` for this session's open contracts): finds the helper's transcript by the contract id, prices its real usage, runs the contract's check command itself, writes the result into the contract, and appends one `hire` record to the inbox (template, group, agent, size, model, effort, class, family, risk, wage, band, actual, passed, sealed; no project detail). The check's fingerprint is sealed outside the project at hire time: a `passed` value found in the contract file is ignored, and a check that was changed after hiring is not run and counts for nothing. A contract whose helper cannot be found yet stays open; `--abandon` drops one. Settling twice records once. `--passed` is ignored: only an exit code counts, and only a sealed result moves a template's record.
- **Learning**: `hire` records are folded by `mlearn.fold` → `hr.fold_hire` into `stats/ml.json` under `hr` (pass counts with discount per template, group and rack; wage ratios per template, size and overall). Probation: at least five checked hires and a lower bound under 0.35; shown by `brain hr report`. Rewriting a template is a kernel change, trialled with `brain eval` (paired, pre-registered).
- **`brain hr staff <tickets.json> [--budget N]`**: template, agent, model and wage per open ticket, total payroll, and whether it fits the budget.
- **`brain hr rack [--search q | --id t]`**, **`brain hr audit`**, **`brain hr report`**.
- Also fixed with this work: a session outcome now charges the lead's model with the lead's own usage only (`tokens`, `cost`), keeping the whole task's usage beside it (`tokens_all`, `cost_all`) for estimates and drift.

## 5. Tickets

Authoritative copy: `docs/plan/tickets.json` (fields: id, title, deps, files, est, accept, status). Summary:

| ID | Deliverable | Depends on | Acceptance command |
|---|---|---|---|
| CB-080 | `engine/mlearn.py`, `memory/ml_config.json`, `tests/test_mlearn.py`; `route.suggest` delegates to it; `schedule` uses `calibrate` when stats exist | — | `python3 -m unittest tests.test_mlearn tests.test_route tests.test_schedule` |
| CB-081 | Pipeline changes of 4.2 in `learn.py`, `items.py`, `recall.py`, `ledger.py`, `guard.py`, specs and tests | CB-080 (interface only) | `python3 -m unittest tests.test_learn tests.test_recall tests.test_ledger tests.test_guard tests.test_rehearsal` |
| CB-082 | `engine/radar.py`, `memory/radar_sources.json`, `tests/test_radar.py` (offline fixtures + one live smoke), boot hook | — | `python3 -m unittest tests.test_radar && python3 bin/brain radar --force` |
| CB-083 | `engine/evals.py`, `evals/tasks/`, `evals/seeded_defects/`, `tests/test_evals.py` | — | `python3 -m unittest tests.test_evals && python3 bin/brain eval audit` |
| CB-084 | Session hygiene of 4.5 in `state.py`, `detect.py`, `schedule.py` (packet), tests | — | `python3 -m unittest tests.test_core tests.test_hygiene` |
| CB-085 | `engine/lint.py`, `tests/test_lint.py`; CI workflow `.github/workflows/ci.yml` running the full gate, `guard diff`, `learn verify` | CB-080..084 merged | `python3 bin/brain lint && python3 -m unittest tests.test_lint` |
| CB-086 | `brain skill-audit` | CB-085 | `python3 -m unittest tests.test_lint` |
| CB-087 | Retrieval improvements + golden set regression | CB-081 | `python3 -m unittest tests.test_recall` |
| CB-088 | Audit fixes to `CLAUDE.md`, skills, agents, method, items | CB-085 | `python3 bin/brain lint && python3 bin/brain items check` |
| CB-089 | Skills and method files updated for new commands (`radar`, `eval`, `ablate`, `resume`, `plan packet`, `checkpoint --push`, `close --used`); owner files updated | CB-080..088 | `python3 bin/brain lint` |
| CB-090 | Fresh-context review of the whole brain against section 1 and `docs/REQUIREMENTS.md`; blocking findings fixed | all above | reviewer report has zero open blocking items; full gate exits 0 |
| CB-091 | `docs/REQUIREMENTS.md` (owner clauses → mechanism → evidence), `docs/BUILD_STATUS.md`, final commit and push | CB-090 | full gate exits 0; `git status` clean; branch pushed |
| CB-120 | HR research (four memos) | — | `test -f docs/research/round3/02-archetypes.md` |
| CB-121 | `hr/GUIDELINES.md`, `hr/template.schema.json` | CB-120 | `python3 bin/brain hr audit` |
| CB-122 | Rack of 100 templates | CB-121 | `python3 bin/brain hr audit` |
| CB-123 | `engine/hr.py`, `tests/test_hr.py`, learner integration | CB-121 | `python3 -m unittest tests.test_hr tests.test_mlearn tests.test_learn` |
| CB-124 | Skills, guide and plan updated for HR | CB-122, CB-123 | `python3 bin/brain lint` |
| CB-125 | Fresh-context review of HR and fixes | CB-124 | full gate and `python3 bin/brain hr audit` exit 0 |

Phase B (live two-repo sessions; cannot be closed inside the build session): CB-101…CB-112 as listed in `docs/plan/tickets.json` (loading check, tier-0 zero-process check, new-project flow, resume flow, helper settings honoured, environment-level hooks, skill hooks, two-repo push with branch protection, A/A then first paired benchmark, first real project, plugin manifest on desktop, effort-change cache measurement).

Phase C: weekly consolidation routine; first routing statistics; tag `brain-v1.0.0` and lock the learned zone; review after the third project removing whatever went unused.

## 6. Definition of done for the brain itself

1. Full gate exits 0 from a clean clone with only Python and git present.
2. Rehearsal test passes with no hooks, no MCP, no network.
3. Every invariant in section 1 has a test that fails when the invariant is broken (mutation spot-check on at least five of them, recorded in `docs/BUILD_STATUS.md`).
4. `brain lint` reports no missing command or flag anywhere in the instruction surface.
5. Always-loaded estimate ≤ 3,200 tokens.
6. `docs/REQUIREMENTS.md` has evidence for every owner clause or marks it open with the reason.
7. Phase B tickets are listed as open with exact steps; none is claimed done without a live session.

## 7. Rejected, with evidence (do not re-add without new measurements)

| Rejected | Why |
|---|---|
| Hooks, MCP or plugins as required mechanisms | Not loaded in two-repo cloud sessions |
| Vector/embedding index by default | Install and download cost at every session; BM25 within 4 points on the available set; revisit only on a measured gap (CB-087) |
| LLM summarisation as memory or as tool-output compression | Longer trajectories (13–15%), lossy; masking and scripts win |
| Compact output formats (e.g. TOON) for model output | −9 accuracy points in agent pipelines for ≤ 18% tokens |
| Lossy prompt compression of instructions or code | Meaning loss; no evidence it holds on code |
| Swarms, persona chains, spec constitutions, large always-on tool surfaces | No independent evidence of gains; measured context cost (e.g. ~21k tokens for a 36-tool surface) |
| Same-session stop-hook loops | Context accumulation and drift; hooks unavailable anyway |
| Auto-written skills or auto-promoted self-generated rules | ≈ 0 or negative in SkillsBench-type results |
| Model-judged credit for memory | Poisoned entries scored 1.0 |
| Shapley credit, contextual bandits now | Data far too small; one subset observed per session |
| Annealing for context packing or model assignment | Greedy 99.1% of optimum; knapsack is exact |
| Mid-session model switching for routing | Cache forfeited; route at the helper boundary only |
| Hub router models (RouteLLM etc.) | Need an embedding/LLM at runtime; trained on single-turn chat preferences |
| Fixed 90-day decay | Replaced by usage-based retention |
| Board, HR catalogue, payroll, 500-idea table | Unused in the sample repo; paid for in every session |
