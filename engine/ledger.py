"""Token ledger: real token use from Claude Code transcripts, priced, and the
end-of-session capture (`brain close`).

Why: every claim the brain makes about saving tokens must rest on measured
numbers, not estimates. Claude Code writes one JSONL transcript per session
(plus one per sub-agent); assistant lines carry the API ``usage`` block. The
same message id is repeated on one line per content block with the usage
repeated too, so each id is counted once (the copy with the largest
``output_tokens`` wins, because streaming copies can be partial).

Pricing comes from ``memory/models.json`` (US dollars per million tokens).
``output_tokens`` already includes thinking tokens, so thinking is reported
as a share of output and never added on top.

``close`` relies on the model remembering to run it, which it does not
always do (round2/05). So boot marks the session open
(``.brain/log/open-session.json``, ``mark_open``), capture clears the mark,
and a later boot that finds another session's mark repairs the gap from
that session's last live capture, its transcript, or records it as
unrecorded (``repair_unclosed``).

Two copies of a session's records exist. The Stop hook captures after every
turn into ``learning/inbox/.live/`` (``capture(live=True)``), which git
ignores: a tracked file rewritten every turn left the tree dirty every turn.
``close`` writes the tracked inbox file and removes the live one. Each
capture reads both, so neither loses what the other knew.

Units. ``tokens`` counts every token, and in a long session over nine in
ten are cache reads, so it does not measure work. ``tokens_oe`` (output-
equivalent) is the cost divided by the main model's output price, the unit
HR wages use. ``wall_minutes`` runs from the first to the last timestamp;
``active_minutes`` adds the gaps between consecutive timestamps, each
counted up to a cap, so a night between two turns is not a night of work.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from . import common as c
from . import learn

COUNTERS = ("in", "cache_write", "cache_read", "out", "thinking")
BIG_TOOL_RESULT_TOKENS = 5000
ACTIVE_GAP_MINUTES = 5.0   # tunable: memory/ml_config.json ledger.active_gap_minutes
LIVE_DIR = c.INBOX_DIR + ".live/"   # git-ignored: what the Stop hook captures between closes


# ---------------------------------------------------------------- reading
def _usage(raw: dict) -> dict:
    """Normalise an API usage block into the ledger's counters, with the
    cache-write split needed for pricing (absent split means all 5-minute)."""
    def num(v) -> int:
        return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0

    cw = num(raw.get("cache_creation_input_tokens"))
    split = raw.get("cache_creation") if isinstance(raw.get("cache_creation"), dict) else {}
    cw_1h = min(cw, num(split.get("ephemeral_1h_input_tokens")))
    cw_5m = cw - cw_1h
    details = raw.get("output_tokens_details") if isinstance(raw.get("output_tokens_details"), dict) else {}
    return {
        "in": num(raw.get("input_tokens")),
        "cache_write": cw,
        "cache_write_5m": cw_5m,
        "cache_write_1h": cw_1h,
        "cache_read": num(raw.get("cache_read_input_tokens")),
        "out": num(raw.get("output_tokens")),
        "thinking": num(details.get("thinking_tokens")),
        "fast": raw.get("speed") == "fast",
    }


def _tool_result_text(block: dict) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def read_transcript(path: Path | str) -> dict:
    """One pass over a transcript: unique assistant messages, timestamps,
    the main effort level, and the count of oversized tool results."""
    messages: dict[str, dict] = {}
    stamps: list[str] = []
    efforts: dict[str, int] = {}
    big = 0
    for row in c.iter_jsonl_stream(path):
        ts = row.get("timestamp")
        if isinstance(ts, str) and ts:
            stamps.append(ts)
        msg = row.get("message") if isinstance(row.get("message"), dict) else {}
        kind = row.get("type")
        if kind == "assistant" and isinstance(msg.get("usage"), dict):
            model = str(msg.get("model") or "unknown")
            if model == "<synthetic>":  # client-made placeholder, never billed
                continue
            key = str(msg.get("id") or row.get("uuid") or len(messages))
            u = _usage(msg["usage"])
            prev = messages.get(key)
            if prev is None or u["out"] > prev["usage"]["out"]:
                messages[key] = {"model": model, "usage": u}
            eff = row.get("effort")
            if isinstance(eff, str) and eff:
                efforts[eff] = efforts.get(eff, 0) + 1
        elif kind == "user" and isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    if c.est_tokens(_tool_result_text(block)) > BIG_TOOL_RESULT_TOKENS:
                        big += 1
    effort = max(sorted(efforts), key=lambda e: efforts[e]) if efforts else ""
    return {"messages": list(messages.values()), "stamps": stamps, "effort": effort, "big_tool_results": big}


# ---------------------------------------------------------------- pricing
def known_rates(model: str, models_cfg: dict) -> dict | None:
    """The price row of a model id or alias, or None when the brain has none."""
    models = (models_cfg or {}).get("models", {})
    if model in models:
        return models[model]
    for mid, m in models.items():
        if m.get("alias") == model or model.startswith(mid):
            return m
    return None


def rates_for(model: str, models_cfg: dict) -> dict:
    """Per-million prices for a model id or alias; unknown models use the fallback."""
    known = known_rates(model, models_cfg)
    return known if known is not None else (models_cfg or {}).get("fallback_price", {})


def _fast_factor(model: str, u: dict, models_cfg: dict) -> float | None:
    """The multiplier for a fast-mode message, 1.0 for a standard one, None
    when the message was fast and the price row records no ``fast_multiplier``
    (it is then priced as standard and the summary says so)."""
    if not u.get("fast"):
        return 1.0
    f = rates_for(model, models_cfg).get("fast_multiplier")
    return float(f) if isinstance(f, (int, float)) and not isinstance(f, bool) and f > 0 else None


def price(model: str, u: dict, models_cfg: dict) -> float:
    r = rates_for(model, models_cfg)
    w5 = r.get("cache_write_5m", r.get("cache_write", 0.0))
    w1 = r.get("cache_write_1h", w5)
    cost = (u["in"] * r.get("in", 0.0) + u["cache_write_5m"] * w5 + u["cache_write_1h"] * w1
            + u["cache_read"] * r.get("cache_read", 0.0) + u["out"] * r.get("out", 0.0)) / 1_000_000
    return cost * (_fast_factor(model, u, models_cfg) or 1.0)


def output_equivalent(cost: float, model: str, models_cfg: dict) -> int:
    """A cost as tokens of the model's output: the one unit in which sessions,
    helpers and HR wages can be compared (cost / output price)."""
    out = rates_for(model, models_cfg).get("out") if model else None
    out = out or (models_cfg or {}).get("fallback_price", {}).get("out") or 20.0
    return int(round(cost / out * 1_000_000))


def gap_cap(brain_root: Path | None = None) -> float:
    """Minutes one gap between two timestamps may add to ``active_minutes``."""
    cfg = c.read_json(Path(brain_root or c.BRAIN_ROOT) / "memory" / "ml_config.json", {})
    v = (cfg.get("ledger") or {}).get("active_gap_minutes") if isinstance(cfg, dict) and isinstance(cfg.get("ledger"), dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else ACTIVE_GAP_MINUTES


def _empty() -> dict:
    return {k: 0 for k in COUNTERS} | {"cost": 0.0, "messages": 0}


def _add(acc: dict, u: dict, cost: float) -> None:
    for k in COUNTERS:
        acc[k] += u[k]
    acc["cost"] += cost
    acc["messages"] += 1


def _round(acc: dict) -> dict:
    return {**acc, "cost": round(acc["cost"], 6)}


def _parse_ts(ts: str) -> _dt.datetime | None:
    try:
        d = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def summarise(main_path, sub_paths, models_cfg: dict, gap_minutes: float = ACTIVE_GAP_MINUTES) -> dict:
    """Priced totals for one session: per model, main versus helpers, cache
    share of the main conversation, oversized tool results, wall and active
    time, the totals in output-equivalent tokens, and what was priced by
    guess (models at the fallback rate, fast mode at the standard rate)."""
    per_model: dict[str, dict] = {}
    fast_at_standard = 0
    main_acc, help_acc = _empty(), _empty()
    stamps: list[str] = []
    main_models: dict[str, int] = {}
    main = read_transcript(main_path) if main_path else {"messages": [], "stamps": [], "effort": "", "big_tool_results": 0}
    helpers = 0
    sources = [(main, True)] + [(read_transcript(p), False) for p in sub_paths or []]
    for data, is_main in sources:
        stamps += data["stamps"]
        if not is_main and data["messages"]:
            helpers += 1
        for m in data["messages"]:
            cost = price(m["model"], m["usage"], models_cfg)
            fast_at_standard += _fast_factor(m["model"], m["usage"], models_cfg) is None
            _add(per_model.setdefault(m["model"], _empty()), m["usage"], cost)
            _add(main_acc if is_main else help_acc, m["usage"], cost)
            if is_main:
                main_models[m["model"]] = main_models.get(m["model"], 0) + 1
    totals = _empty()
    for acc in (main_acc, help_acc):
        for k in COUNTERS:
            totals[k] += acc[k]
        totals["cost"] += acc["cost"]
        totals["messages"] += acc["messages"]
    denom = main_acc["in"] + main_acc["cache_write"] + main_acc["cache_read"]
    times = sorted(t for t in (_parse_ts(s) for s in stamps) if t)
    first = times[0].strftime("%Y-%m-%dT%H:%M:%SZ") if times else ""
    last = times[-1].strftime("%Y-%m-%dT%H:%M:%SZ") if times else ""
    wall = round((times[-1] - times[0]).total_seconds() / 60, 1) if times else 0.0
    active = round(sum(min((b - a).total_seconds() / 60, gap_minutes) for a, b in zip(times, times[1:])), 1)
    main_model = max(sorted(main_models), key=lambda m: main_models[m]) if main_models else ""
    return {
        "models": {k: _round(v) for k, v in sorted(per_model.items())},
        "main": _round(main_acc),
        "helpers_total": _round(help_acc),
        "totals": _round(totals),
        "cache_read_share": round(main_acc["cache_read"] / denom, 4) if denom else 0.0,
        "helpers": helpers,
        "helper_cost_share": round(help_acc["cost"] / totals["cost"], 4) if totals["cost"] else 0.0,
        "big_tool_results": main["big_tool_results"],
        "main_model": main_model,
        "main_effort": main["effort"],
        "first": first,
        "last": last,
        "wall_minutes": wall,
        "active_minutes": active,
        "tokens_oe": output_equivalent(totals["cost"], main_model, models_cfg),
        "tokens_oe_main": output_equivalent(main_acc["cost"], main_model, models_cfg),
        "unpriced_models": sorted(m for m in per_model if known_rates(m, models_cfg) is None),
        "fast_at_standard": fast_at_standard,
    }


# ---------------------------------------------------------------- output
def _k(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def _tokens(acc: dict) -> int:
    return acc["in"] + acc["cache_write"] + acc["cache_read"] + acc["out"]


def pricing_notes(s: dict) -> list[str]:
    """What the cost rests on a guess for; empty when every price is recorded."""
    out = []
    if s.get("unpriced_models"):
        out.append(f"priced at the fallback rate: {', '.join(s['unpriced_models'][:4])}; add it to memory/models.json")
    if s.get("fast_at_standard"):
        out.append(f"fast mode priced at the standard rate: {s['fast_at_standard']} message(s); memory/models.json has no fast_multiplier")
    return out


def format_summary(sid: str, s: dict) -> list[str]:
    lines = [f"session {sid[:12]}: {s['wall_minutes']} min ({s['active_minutes']} active), {s['helpers']} helper(s), "
             f"main model {s['main_model'] or 'none'}"]
    for model, m in list(s["models"].items())[:6]:
        lines.append(f"  {model}: in {_k(m['in'])}, cache write {_k(m['cache_write'])}, cache read {_k(m['cache_read'])}, "
                     f"out {_k(m['out'])} (thinking {_k(m['thinking'])}), ${m['cost']:.2f}")
    t = s["totals"]
    lines.append(f"total: {_k(_tokens(t))} tokens ({_k(s['tokens_oe'])} output-equivalent), ${t['cost']:.2f}; "
                 f"helpers {s['helper_cost_share']:.0%} of cost")
    lines += pricing_notes(s)
    lines.append(f"main conversation read from cache: {s['cache_read_share']:.0%} (target 80% or more)")
    lines.append(f"tool results over {BIG_TOOL_RESULT_TOKENS} tokens in main: {s['big_tool_results']}")
    return lines


# ---------------------------------------------------------------- close
OPEN_MARKER = "open-session.json"
RISKS = ("trivial", "standard", "high", "one-way-door")   # contract/v1.schema.json
USED_RE = re.compile(r"^(?P<item>[a-z]{2,8}-[a-z0-9][a-z0-9-]{1,60}):(?P<followed>[01])$")
# What close may declare about an outcome; a later capture of the same
# session (the Stop hook, a second close) keeps these unless given again.
DECLARED = ("risk", "est_tokens", "est_minutes", "explored", "propensity", "words", "rule_tier")


def _gate_rows(project: Path, sid: str) -> list[dict]:
    """This session's gate results. The gate module owns the row shape, so a
    few field spellings are accepted for the id and exit code."""
    out = []
    for r in c.read_jsonl(Path(project) / ".brain" / "log" / "gates.jsonl"):
        if str(r.get("session", "")) != sid:
            continue
        code = next((r[k] for k in ("exit_code", "exit", "code") if isinstance(r.get(k), int)), None)
        if code is None:
            continue
        out.append({"gate": str(r.get("gate") or r.get("id") or "gate"), "exit_code": code, "at": str(r.get("at", "")),
                    "commit": str(r.get("commit") or "")})
    return out


def _model_rows(s: dict) -> dict:
    return {m: {k: v[k] for k in ("in", "cache_write", "cache_read", "out", "cost")} for m, v in s["models"].items()}


def _alias(model: str, models_cfg: dict) -> str:
    """The short name the routing tables use ('opus'), or the id itself."""
    return str(rates_for(model, models_cfg).get("alias") or model) if model else ""


def _command_gates(project: Path) -> set[str]:
    """Ids of the project's gates that run a real command: only those verify."""
    return {str(g.get("id")) for g in c.load_manifest(project).get("gates", []) or []
            if isinstance(g, dict) and g.get("kind") == "command" and str(g.get("command") or "").strip()}


def parse_used(values: list[str] | None) -> tuple[list[tuple[str, bool]], str]:
    """``ID:0|1`` pairs from ``--used``; the second value is an error line."""
    out = []
    for v in values or []:
        m = USED_RE.match(str(v).strip())
        if not m:
            return [], f"--used {v!r}: expected ITEM-ID:1 (followed) or ITEM-ID:0 (shown, not followed)"
        out.append((m["item"], m["followed"] == "1"))
    return out, ""


def _outcomes(sid: str, at: str, family: str, classes: list[str], tier, s: dict, gates: list[dict],
              command_gates: set[str], declared: dict, models_cfg: dict, usage_known: bool = True) -> list[dict]:
    """One outcome per task class, judged only by this session's gate exit
    codes (I-07): ``first_pass`` when every gate's first run was green,
    ``passed`` when every gate's last run was, ``rework`` = red runs before
    the last. Tokens, minutes and cost are split evenly across classes."""
    first: dict[str, dict] = {}
    last: dict[str, dict] = {}
    for g in gates:
        first.setdefault(g["gate"], g)
        last[g["gate"]] = g
    reds = sum(1 for g in gates if g["exit_code"] != 0 and last[g["gate"]] is not g)
    n = len(classes)
    has_check = declared.get("has_check")
    if has_check is None:
        has_check = any(g in command_gates for g in last)
    out = []
    for cls in classes:
        rec = {"kind": "outcome", "session": sid, "at": at, "task_class": cls, "family": family, "tier": tier,
               "risk": declared.get("risk") or "standard",
               "model": declared.get("model") or _alias(s["main_model"], models_cfg),
               "model_id": s["main_model"], "effort": declared.get("effort") or s["main_effort"],
               "has_check": bool(has_check),
               "passed": all(g["exit_code"] == 0 for g in last.values()),
               "first_pass": all(g["exit_code"] == 0 for g in first.values()),
               # The lead's own usage is what its model and effort are judged
               # on; helpers have their own contracts (brain hr). The whole
               # task's usage is kept beside it for estimates and drift.
               "rework": reds, "tokens": _tokens(s["main"]) // n, "cost": round(s["main"]["cost"] / n, 6),
               "tokens_all": _tokens(s["totals"]) // n, "cost_all": round(s["totals"]["cost"] / n, 6),
               "minutes": round(s["wall_minutes"] / n, 1),
               # The same usage in units that mean work (see the module text).
               "tokens_oe": output_equivalent(s["main"]["cost"], s["main_model"], models_cfg) // n,
               "tokens_oe_all": output_equivalent(s["totals"]["cost"], s["main_model"], models_cfg) // n,
               "active_minutes": round(s["active_minutes"] / n, 1) if s.get("active_minutes") is not None else None,
               "est_tokens": declared.get("est_tokens"), "est_minutes": declared.get("est_minutes"),
               "explored": bool(declared.get("explored")),
               "propensity": declared.get("propensity") if declared.get("propensity") is not None else 1.0,
               # Commits are hashed: equality is all flakiness needs, and the
               # brain must not hold project identifiers (I-05).
               "gate_runs": [{"gate": g["gate"], "exit": g["exit_code"],
                              "commit": c.sha256_text(g["commit"])[:12] if g["commit"] else None} for g in gates],
               "evidence": [f"gate:{g['gate']} exit {g['exit_code']}" for g in first.values()]}
        # Sizing data (S9): salted hashes of the request's words and the tier
        # the rules gave it; mlearn learns from them in shadow mode only.
        if isinstance(declared.get("words"), list) and isinstance(declared.get("rule_tier"), int):
            rec["words"], rec["rule_tier"] = list(declared["words"]), declared["rule_tier"]
        if not usage_known:
            # No transcript: the gates still say what happened; the cost does not exist.
            rec.update(tokens=None, cost=None, tokens_all=None, cost_all=None, minutes=None, tokens_oe=None,
                       tokens_oe_all=None, active_minutes=None, usage="unknown")
        out.append(rec)
    return out


SESSION_FILE = r"\d{4}-\d{2}-\d{2}-%s(?:-n\d+)?\.jsonl"


def _session_files(folder: Path, sid: str) -> list[Path]:
    """The files of one session in an inbox folder, matched on the whole name
    (a glob on the tail would also take sessions whose id ends the same)."""
    safe = learn.safe_session(sid)
    pat = re.compile(SESSION_FILE % re.escape(safe))
    return sorted(f for f in folder.glob(f"*-{safe}*.jsonl") if pat.fullmatch(f.name)) if folder.is_dir() else []


def live_file(brain_root: Path, sid: str) -> Path:
    """Where the Stop hook keeps this session's capture between closes."""
    folder = Path(brain_root) / LIVE_DIR
    hits = _session_files(folder, sid)
    return hits[0] if hits else folder / f"{c.today()}-{learn.safe_session(sid)}.jsonl"


def live_records(brain_root: Path, sid: str) -> list[dict]:
    return [r for f in _session_files(Path(brain_root) / LIVE_DIR, sid) for r in c.read_jsonl(f) if r.get("session") == sid]


def drop_live(brain_root: Path, sid: str) -> None:
    for f in _session_files(Path(brain_root) / LIVE_DIR, sid):
        try:
            f.unlink()
        except OSError:
            pass


def promote_live(brain_root: Path | None = None, sid: str | None = None) -> Path | None:
    """Move a session's live capture into its tracked inbox file and remove
    the live file. Returns the tracked file, or None when there was nothing
    to move or the session was already consolidated. For whatever is about
    to commit the inbox (a checkpoint that pushes, a repair): the live copy
    exists only in this container."""
    root = Path(brain_root or c.BRAIN_ROOT)
    sid = sid or c.session_id()
    recs = live_records(root, sid)
    # Only kinds the live copy holds are replaced: a capture that could not
    # see the project has no outcomes, and must not erase the tracked ones.
    kinds = tuple(k for k in ("ledger", "outcome") if any(r.get("kind") == k for r in recs))
    written = learn.replace_session_records(root, sid, recs, kinds=kinds) if kinds else None
    drop_live(root, sid)
    return written


def _promote_orphans(root: Path, keep: str) -> None:
    """Live files of other sessions belong to sessions that ended without
    ``close`` (or are still running; their own close then replaces the
    record). Without a project there is no open marker to trigger a repair,
    so the next close moves them into the tracked inbox."""
    folder = root / LIVE_DIR
    for f in sorted(folder.glob("*.jsonl")) if folder.is_dir() else []:
        for sid in sorted({str(r.get("session")) for r in c.read_jsonl(f) if r.get("session")} - {keep}):
            promote_live(root, sid)


def tracked_ledgers(brain_root: Path, sid: str) -> list[dict]:
    """This session's ledger records in the tracked inbox, consolidated or not."""
    return [r for f in _session_files(Path(brain_root) / c.INBOX_DIR, sid) for r in c.read_jsonl(f)
            if r.get("kind") == "ledger" and r.get("session") == sid]


def is_closed(brain_root: Path, sid: str) -> bool:
    """True when the session ran ``close``: its tracked ledger record says so."""
    return any(r.get("closed") for r in tracked_ledgers(brain_root, sid))


def recorded_tier(project: Path) -> int | None:
    """The size the project's work is recorded at: ``tier`` in the head of
    ``.brain/STATE.md``, then the manifest's ``tier``."""
    for line in c.read_text(Path(project) / ".brain" / "STATE.md").splitlines():
        if line.startswith("## "):
            break
        m = re.fullmatch(r"tier:\s*([0-3])\s*", line)
        if m:
            return int(m.group(1))
    t = c.load_manifest(project).get("tier")
    return t if isinstance(t, int) and not isinstance(t, bool) and 0 <= t <= 3 else None


def _save_run_record(project: Path, sid: str, record: dict) -> Path:
    log_dir = Path(project) / ".brain" / "log"
    existing = sorted(log_dir.glob(f"*-{learn.safe_session(sid)}.json"))
    path = existing[0] if existing else log_dir / f"{c.today()}-{learn.safe_session(sid)}.json"
    c.write_json(path, record)
    return path


def _after_record(project: Path, sid: str) -> None:
    """A tracked record exists for the session: its marker goes, the status page is redrawn."""
    clear_open(project, sid)
    try:
        from . import state
        state.write_status(project)
    except (ImportError, AttributeError):
        pass


def capture(brain_root: Path | None = None, sid: str | None = None, main_path=None, sub_paths=None,
            project: Path | None = None, outcome: str = "", classes: list[str] | None = None,
            tier: int | None = None, note: str = "", models_cfg: dict | None = None,
            used: list[tuple[str, bool]] | None = None, declared: dict | None = None,
            live: bool = False, closed: bool = False) -> dict:
    """Write the run record and inbox records for one session. Safe to call
    again: both are keyed by session id and replaced, never duplicated.

    What only ``close`` knows (classes, tier, outcome, ``declared`` outcome
    fields such as risk and estimates) is kept from this session's earlier
    records, tracked and live, when a later call does not repeat it; ``used``
    records are replaced only when ``used`` is given. ``declared`` may hold
    risk, model, effort, est_tokens, est_minutes, explored, propensity and
    has_check; anything absent comes from the transcript and the manifest.

    ``live=True`` is the Stop hook's capture after every turn. It is
    provisional, so it writes only the git-ignored live file: no tracked
    inbox record, nothing in the project, and the open marker stays, which is
    what lets a later boot repair a session that never closed. ``closed=True``
    (``brain close``) marks the ledger record so that a stale marker of this
    session is never taken for an unclosed one."""
    root = Path(brain_root or c.BRAIN_ROOT)
    sid = sid or c.session_id()
    if main_path is None:
        main_path, sub_paths = c.transcript_paths(sid)
    cfg = models_cfg if models_cfg is not None else c.read_json(root / "memory" / "models.json", {})
    usage_known = main_path is not None and Path(main_path).is_file()
    s = summarise(main_path if usage_known else None, sub_paths if usage_known else [], cfg, gap_cap(root))
    # A live file is always written after the tracked one it read, so where both exist it is the later copy.
    earlier = learn.pending_session_records(root, sid) + live_records(root, sid)
    prev_ledger = next((r for r in reversed(earlier) if r.get("kind") == "ledger"), {})
    prev_out = {str(r.get("task_class")): r for r in earlier if r.get("kind") == "outcome"}
    classes = [x for x in (classes or []) if x] or list(prev_ledger.get("classes") or [])
    tier = tier if tier is not None else prev_ledger.get("tier")
    outcome = outcome or str(prev_ledger.get("outcome") or "")
    closed = closed or bool(prev_ledger.get("closed"))
    declared = {k: v for k, v in (declared or {}).items() if v is not None}
    at = c.now_iso()
    result = {"session": sid, "summary": s, "run_record": "", "inbox": "", "inbox_records": 0, "skipped": "",
              "usage": "known" if usage_known else "unknown", "live": live}

    managed = project is not None and c.is_managed(project)
    family = ""
    gates: list[dict] = []
    command_gates: set[str] = set()
    if managed:
        family = str(c.load_manifest(project).get("family", ""))
        gates = _gate_rows(project, sid)
        command_gates = _command_gates(project)
    if managed and not live:
        record = {"session": sid, "at": at, "tier": tier, "classes": classes, "outcome": outcome,
                  "note": note, "models": _model_rows(s), "totals": s["totals"], "helpers": s["helpers"],
                  "cache_read_share": s["cache_read_share"], "wall_minutes": s["wall_minutes"],
                  "active_minutes": s["active_minutes"], "tokens_oe": s["tokens_oe"],
                  "gates": [{k: g[k] for k in ("gate", "exit_code", "at")} for g in gates]}
        if not usage_known:
            record.update(usage="unknown", active_minutes=None, tokens_oe=None)
        result["run_record"] = str(_save_run_record(project, sid, record))

    records = [{"kind": "ledger", "session": sid, "at": at, "family": family,
                "task_class": classes[0] if classes else "", "classes": classes, "tier": tier,
                "outcome": outcome, "model": _alias(s["main_model"], cfg), "models": _model_rows(s),
                "helpers": s["helpers"], "cache_read_share": s["cache_read_share"], "wall_minutes": s["wall_minutes"],
                "active_minutes": s["active_minutes"], "tokens_oe": s["tokens_oe"]}]
    if s["unpriced_models"]:
        records[0]["unpriced_models"] = s["unpriced_models"]
    if closed:
        records[0]["closed"] = True
    if not usage_known:
        records[0].update(models={}, cache_read_share=None, wall_minutes=None, active_minutes=None, tokens_oe=None,
                          usage="unknown")
    kinds: tuple[str, ...] = ("ledger",)
    if classes and gates:
        per_class = []
        for cls in classes:
            keep = {k: prev_out.get(cls, {}).get(k) for k in DECLARED}
            per_class.append({**{k: v for k, v in keep.items() if v is not None}, **declared})
        # Classes share one session, so the declared fields of the first class stand for all.
        records += _outcomes(sid, at, family, classes, tier, s, gates, command_gates, per_class[0], cfg, usage_known)
        # Outcomes are replaced only by outcomes: a capture that cannot see the
        # project (no gate log) must not erase the ones an earlier capture wrote.
        kinds += ("outcome",)
    if live:
        path = live_file(root, sid)
        c.write_jsonl(path, [learn.with_id(r) for r in records])
        result["inbox"], result["inbox_records"] = str(path), len(records)
        return result
    if used is not None:
        kinds += ("used",)
        records += [{"kind": "used", "session": sid, "at": at, "item": item, "followed": followed}
                    for item, followed in used]
    written = learn.replace_session_records(root, sid, records, kinds=kinds)
    if written is None:
        result["skipped"] = "this session's ledger was already consolidated"
    else:
        result["inbox"] = str(written)
        result["inbox_records"] = len(records)
    drop_live(root, sid)
    if managed:
        _after_record(project, sid)
    return result


# ---------------------------------------------------------------- unclosed sessions
def _marker(project: Path) -> Path:
    return Path(project) / ".brain" / "log" / OPEN_MARKER


def mark_open(project: Path, sid: str | None = None, brain_root: Path | None = None) -> dict | None:
    """Record at boot that this session is open, so a later boot can tell
    when it ended without ``close``. Writes ``.brain/log/open-session.json``
    ``{session, at}`` when it is absent or belongs to another session, and
    returns that other session's marker (the one to repair), else None.

    A marker can outlive a session that did close: a checkpoint pushed it
    before the close removed it, or the session closed on another project.
    Such a marker is taken over without a word, because nothing is missing."""
    sid = sid or c.session_id()
    path = _marker(project)
    prev = c.read_json(path)
    prev = prev if isinstance(prev, dict) and prev.get("session") else None
    if prev is not None and prev["session"] == sid:
        return None
    c.write_json(path, {"session": sid, "at": c.now_iso()})
    if prev is not None and is_closed(Path(brain_root or c.BRAIN_ROOT), str(prev["session"])):
        return None
    return prev


def clear_open(project: Path, sid: str) -> None:
    """Remove the open-session marker if it is this session's (capture ran)."""
    path = _marker(project)
    prev = c.read_json(path)
    if isinstance(prev, dict) and prev.get("session") == sid:
        try:
            path.unlink()
        except OSError:
            pass


def _record_from_ledger(project: Path, sid: str, led: dict) -> None:
    """The project's run record for a session known only from its ledger
    record (a promoted live capture), so the project's cost page counts it."""
    models = led.get("models") if isinstance(led.get("models"), dict) else {}
    totals = {k: sum(m.get(k, 0) for m in models.values() if isinstance(m, dict)) for k in ("in", "cache_write", "cache_read", "out")}
    totals["cost"] = round(sum(m.get("cost", 0.0) for m in models.values() if isinstance(m, dict)), 6)
    _save_run_record(project, sid, {
        "session": sid, "at": led.get("at", c.now_iso()), "tier": led.get("tier"), "classes": led.get("classes") or [],
        "outcome": led.get("outcome") or "", "note": "recorded from the last capture; the session did not close",
        "models": models, "totals": totals, "helpers": led.get("helpers", 0),
        "cache_read_share": led.get("cache_read_share"), "wall_minutes": led.get("wall_minutes"),
        "active_minutes": led.get("active_minutes"), "tokens_oe": led.get("tokens_oe"),
        "gates": [{k: g[k] for k in ("gate", "exit_code", "at")} for g in _gate_rows(project, sid)]})


def repair_unclosed(project: Path, previous_marker: dict, brain_root: Path | None = None) -> str:
    """Close the gap an earlier session left by ending without ``close``.

    In this order: a session whose ledger says it closed needs nothing (""
    is returned); its last live capture, if this container still has it,
    becomes the tracked record; else its transcript, if still on disk, is
    captured now (same records as ``close`` would have written, without the
    classes only the model knew); else a real record an earlier capture left
    is kept as it is; else an inbox ``ledger`` record marked ``unrecorded:
    true`` shows the gap instead of hiding it. A real record is never
    replaced by that stub. Returns one short line for boot to print."""
    root = Path(brain_root or c.BRAIN_ROOT)
    sid = str((previous_marker or {}).get("session") or "")
    if not sid or is_closed(root, sid):
        return ""
    managed = c.is_managed(project)
    live = live_records(root, sid)
    if live:
        written = promote_live(root, sid)
        if written is None:
            return f"earlier session {sid[:12]} was not closed; its ledger was already consolidated"
        if managed:
            _record_from_ledger(project, sid, next((r for r in live if r.get("kind") == "ledger"), {}))
            _after_record(project, sid)
        return f"earlier session {sid[:12]} was not closed; recorded it from its last capture"
    main, subs = c.transcript_paths(sid)
    if main is not None and main.is_file():
        r = capture(root, sid, main, subs, project)
        if r["skipped"]:
            return f"earlier session {sid[:12]} was not closed; its ledger was already consolidated"
        return f"earlier session {sid[:12]} was not closed; recorded it from its transcript"
    if any(not r.get("unrecorded") for r in tracked_ledgers(root, sid)):
        return f"earlier session {sid[:12]} was not closed; its last recorded ledger is kept"
    family = str(c.load_manifest(project).get("family", "")) if managed else ""
    rec = {"kind": "ledger", "session": sid, "at": c.now_iso(), "family": family, "unrecorded": True,
           "started": str(previous_marker.get("at", "")), "models": {}}
    written = learn.replace_session_records(root, sid, [rec], kinds=("ledger",))
    if written is None:
        return f"earlier session {sid[:12]} was not closed; its ledger was already consolidated"
    return f"earlier session {sid[:12]} was not closed and its transcript is gone; recorded the gap"


# ---------------------------------------------------------------- cli
def cmd_ledger(args) -> int:
    sid = args.session or c.session_id()
    main, subs = c.transcript_paths(sid)
    if main is None or not main.is_file():
        print(f"no transcript found for session {sid}")
        return 1
    s = summarise(main, subs, c.read_json(c.BRAIN_ROOT / "memory" / "models.json", {}), gap_cap())
    if args.json:
        print(json.dumps(s, indent=2, sort_keys=True))
    else:
        print("\n".join(format_summary(sid, s)))
    return 0


def cmd_close(args) -> int:
    sid = args.session or c.session_id()
    used, err = parse_used(args.used)
    if err:
        print(err)
        return 2
    for name in ("est_tokens", "est_minutes"):
        if getattr(args, name) is not None and getattr(args, name) < 0:
            print(f"--{name.replace('_', '-')} must not be negative")
            return 2
    if args.propensity is not None and not 0 < args.propensity <= 1:
        print("--propensity must be in (0, 1]")
        return 2
    problem = c.secret_problem(args.note or "")
    if problem:  # the note is written into the project's run record, which the next checkpoint pushes
        print(problem)
        return 2
    main, subs = c.transcript_paths(sid)
    known = main is not None and main.is_file()
    project = c.resolve_project(args.project, getattr(args, "brain_root", None))
    if project is not None and not c.is_managed(project):
        project = None
    declared = {"risk": args.risk, "model": args.model, "effort": args.effort, "est_tokens": args.est_tokens,
                "est_minutes": args.est_minutes, "explored": None if args.explored is None else bool(args.explored),
                "propensity": args.propensity, "has_check": None if args.has_check is None else bool(args.has_check)}
    if getattr(args, "request", None) and project is not None:
        # The request text is used here and dropped: only salted hashes of
        # its words leave this function, and the salt stays in the project.
        from . import route
        declared["words"] = learn.hashed_words(args.request, learn.project_salt(project))
        declared["rule_tier"] = int(route.classify(args.request, c.load_manifest(project))["tier"])
    tier = args.tier
    if tier is None and project is not None:
        # The size the work ran at is on disk; without it the sizing learner
        # gets no label from a session closed the documented way.
        tier = recorded_tier(project)
    root = Path(getattr(args, "brain_root", None) or c.BRAIN_ROOT)
    r = capture(brain_root=root, sid=sid, main_path=main if known else None,
                sub_paths=subs if known else [], project=project, outcome=args.outcome or "",
                classes=args.cls, tier=tier, note=args.note or "",
                used=used if args.used else None, declared=declared, closed=True)
    _promote_orphans(root, sid)
    if args.json:
        print(json.dumps(r, indent=2, sort_keys=True))
        return 0
    s = r["summary"]
    t = s["totals"]
    if not known:
        print(f"no transcript found for session {sid}: outcomes recorded from the gate log, token usage unknown")
    else:
        print(f"tokens: {_k(_tokens(t))} (in {_k(t['in'])}, cache write {_k(t['cache_write'])}, "
              f"cache read {_k(t['cache_read'])}, out {_k(t['out'])}); {_k(s['tokens_oe'])} output-equivalent")
        print(f"cost: ${t['cost']:.2f}; helpers {s['helpers']} ({s['helper_cost_share']:.0%} of cost); "
              f"{s['active_minutes']} active min of {s['wall_minutes']}")
        print(f"main conversation read from cache: {s['cache_read_share']:.0%}")
        for line in pricing_notes(s):
            print(line)
    print(f"run record: {r['run_record'] or 'none (no managed project)'}")
    print(f"inbox: {r['skipped'] or str(r['inbox_records']) + ' record(s) in ' + Path(r['inbox']).name}")
    try:  # helpers hired this session are settled here, so no wage goes unrecorded
        from . import hr
        line = hr.settle_open(project, brain_root=getattr(args, "brain_root", None), sub_paths=subs if known else [])
        if line:
            print(line)
    except Exception as e:  # settlement must never stop a session from closing
        print(f"hr: contracts not settled ({type(e).__name__})")
    return 0


def register(sub) -> None:
    p = sub.add_parser("ledger", help="real token use and cost of a session")
    p.add_argument("--session", help="session id (default: this session)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_ledger)

    k = sub.add_parser("close", help="end-of-session capture: run record, ledger, outcomes, items used")
    c.add_project_arg(k)
    k.add_argument("--session", help="session id (default: this session)")
    k.add_argument("--outcome", choices=("ok", "partial", "failed"))
    k.add_argument("--class", dest="cls", action="append", default=[], help="task class (repeatable)")
    k.add_argument("--tier", type=int, choices=(0, 1, 2, 3),
                   help="size the work ran at (default: the project's STATE.md, then its manifest)")
    k.add_argument("--note", help="short note for the project's run record")
    # Whether an item helped is never accepted here: mlearn derives it from
    # the gate outcomes (I-07). Only whether it was followed is declared.
    k.add_argument("--used", action="append", metavar="ID:FOLLOWED",
                   help="a recalled item and whether it was followed (1) or not (0); repeatable")
    k.add_argument("--risk", choices=RISKS, help="risk of the work (default standard)")
    k.add_argument("--model", help="model alias of the work (default: the main conversation's)")
    k.add_argument("--effort", help="effort level (default: the transcript's)")
    k.add_argument("--est-tokens", type=int,
                   help="tokens estimated before the work, in output-equivalent tokens (the unit of HR wages)")
    k.add_argument("--est-minutes", type=float, help="minutes estimated before the work")
    k.add_argument("--explored", type=int, choices=(0, 1), help="1 if a cheaper arm was being tried")
    k.add_argument("--propensity", type=float, help="probability the routing choice had (default 1)")
    k.add_argument("--has-check", type=int, choices=(0, 1),
                   help="override: did a verifying command gate run (default: read from the gate log)")
    k.add_argument("--request", help="the owner's request; only salted hashes of its words are kept (sizing data)")
    k.add_argument("--json", action="store_true")
    k.set_defaults(func=cmd_close)
