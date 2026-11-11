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
that session's transcript or records it as unrecorded (``repair_unclosed``).
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
def rates_for(model: str, models_cfg: dict) -> dict:
    """Per-million prices for a model id or alias; unknown models use the fallback."""
    models = (models_cfg or {}).get("models", {})
    if model in models:
        return models[model]
    for mid, m in models.items():
        if m.get("alias") == model or model.startswith(mid):
            return m
    return (models_cfg or {}).get("fallback_price", {})


def price(model: str, u: dict, models_cfg: dict) -> float:
    r = rates_for(model, models_cfg)
    w5 = r.get("cache_write_5m", r.get("cache_write", 0.0))
    w1 = r.get("cache_write_1h", w5)
    cost = (u["in"] * r.get("in", 0.0) + u["cache_write_5m"] * w5 + u["cache_write_1h"] * w1
            + u["cache_read"] * r.get("cache_read", 0.0) + u["out"] * r.get("out", 0.0)) / 1_000_000
    return cost


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


def summarise(main_path, sub_paths, models_cfg: dict) -> dict:
    """Priced totals for one session: per model, main versus helpers, cache
    share of the main conversation, oversized tool results, and wall time."""
    per_model: dict[str, dict] = {}
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
    return {
        "models": {k: _round(v) for k, v in sorted(per_model.items())},
        "main": _round(main_acc),
        "helpers_total": _round(help_acc),
        "totals": _round(totals),
        "cache_read_share": round(main_acc["cache_read"] / denom, 4) if denom else 0.0,
        "helpers": helpers,
        "helper_cost_share": round(help_acc["cost"] / totals["cost"], 4) if totals["cost"] else 0.0,
        "big_tool_results": main["big_tool_results"],
        "main_model": max(sorted(main_models), key=lambda m: main_models[m]) if main_models else "",
        "main_effort": main["effort"],
        "first": first,
        "last": last,
        "wall_minutes": wall,
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


def format_summary(sid: str, s: dict) -> list[str]:
    lines = [f"session {sid[:12]}: {s['wall_minutes']} min, {s['helpers']} helper(s), main model {s['main_model'] or 'none'}"]
    for model, m in list(s["models"].items())[:6]:
        lines.append(f"  {model}: in {_k(m['in'])}, cache write {_k(m['cache_write'])}, cache read {_k(m['cache_read'])}, "
                     f"out {_k(m['out'])} (thinking {_k(m['thinking'])}), ${m['cost']:.2f}")
    t = s["totals"]
    lines.append(f"total: {_k(_tokens(t))} tokens, ${t['cost']:.2f}; helpers {s['helper_cost_share']:.0%} of cost")
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
            rec.update(tokens=None, cost=None, tokens_all=None, cost_all=None, minutes=None, usage="unknown")
        out.append(rec)
    return out


def capture(brain_root: Path | None = None, sid: str | None = None, main_path=None, sub_paths=None,
            project: Path | None = None, outcome: str = "", classes: list[str] | None = None,
            tier: int | None = None, note: str = "", models_cfg: dict | None = None,
            used: list[tuple[str, bool]] | None = None, declared: dict | None = None) -> dict:
    """Write the run record and inbox records for one session. Safe to call
    again: both are keyed by session id and replaced, never duplicated.

    What only ``close`` knows (classes, tier, outcome, ``declared`` outcome
    fields such as risk and estimates) is kept from this session's earlier
    records when a later call (the Stop hook) does not repeat it; ``used``
    records are replaced only when ``used`` is given. ``declared`` may hold
    risk, model, effort, est_tokens, est_minutes, explored, propensity and
    has_check; anything absent comes from the transcript and the manifest."""
    root = Path(brain_root or c.BRAIN_ROOT)
    sid = sid or c.session_id()
    if main_path is None:
        main_path, sub_paths = c.transcript_paths(sid)
    cfg = models_cfg if models_cfg is not None else c.read_json(root / "memory" / "models.json", {})
    usage_known = main_path is not None and Path(main_path).is_file()
    s = summarise(main_path if usage_known else None, sub_paths if usage_known else [], cfg)
    earlier = learn.pending_session_records(root, sid)
    prev_ledger = next((r for r in earlier if r.get("kind") == "ledger"), {})
    prev_out = {str(r.get("task_class")): r for r in earlier if r.get("kind") == "outcome"}
    classes = [x for x in (classes or []) if x] or list(prev_ledger.get("classes") or [])
    tier = tier if tier is not None else prev_ledger.get("tier")
    outcome = outcome or str(prev_ledger.get("outcome") or "")
    declared = {k: v for k, v in (declared or {}).items() if v is not None}
    at = c.now_iso()
    result = {"session": sid, "summary": s, "run_record": "", "inbox": "", "inbox_records": 0, "skipped": "",
              "usage": "known" if usage_known else "unknown"}

    family = ""
    gates: list[dict] = []
    command_gates: set[str] = set()
    if project is not None and c.is_managed(project):
        family = str(c.load_manifest(project).get("family", ""))
        gates = _gate_rows(project, sid)
        command_gates = _command_gates(project)
        log_dir = Path(project) / ".brain" / "log"
        safe = learn.safe_session(sid)
        existing = sorted(log_dir.glob(f"*-{safe}.json"))
        path = existing[0] if existing else log_dir / f"{c.today()}-{safe}.json"
        record = {"session": sid, "at": at, "tier": tier, "classes": classes, "outcome": outcome,
                  "note": note, "models": _model_rows(s), "totals": s["totals"], "helpers": s["helpers"],
                  "cache_read_share": s["cache_read_share"], "wall_minutes": s["wall_minutes"],
                  "gates": [{k: g[k] for k in ("gate", "exit_code", "at")} for g in gates]}
        if not usage_known:
            record["usage"] = "unknown"
        c.write_json(path, record)
        result["run_record"] = str(path)

    records = [{"kind": "ledger", "session": sid, "at": at, "family": family,
                "task_class": classes[0] if classes else "", "classes": classes, "tier": tier,
                "outcome": outcome, "model": _alias(s["main_model"], cfg), "models": _model_rows(s),
                "helpers": s["helpers"], "cache_read_share": s["cache_read_share"], "wall_minutes": s["wall_minutes"]}]
    if not usage_known:
        records[0].update(models={}, cache_read_share=None, wall_minutes=None, usage="unknown")
    if classes and gates:
        per_class = []
        for cls in classes:
            keep = {k: prev_out.get(cls, {}).get(k) for k in DECLARED}
            per_class.append({**{k: v for k, v in keep.items() if v is not None}, **declared})
        # Classes share one session, so the declared fields of the first class stand for all.
        records += _outcomes(sid, at, family, classes, tier, s, gates, command_gates, per_class[0], cfg, usage_known)
    kinds: tuple[str, ...] = ("ledger", "outcome")
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
    if project is not None and c.is_managed(project):
        clear_open(project, sid)
        try:
            from . import state
            state.write_status(project)
        except (ImportError, AttributeError):
            pass
    return result


# ---------------------------------------------------------------- unclosed sessions
def _marker(project: Path) -> Path:
    return Path(project) / ".brain" / "log" / OPEN_MARKER


def mark_open(project: Path, sid: str | None = None) -> dict | None:
    """Record at boot that this session is open, so a later boot can tell
    when it ended without ``close``. Writes ``.brain/log/open-session.json``
    ``{session, at}`` when it is absent or belongs to another session, and
    returns that other session's marker (the one to repair), else None."""
    sid = sid or c.session_id()
    path = _marker(project)
    prev = c.read_json(path)
    prev = prev if isinstance(prev, dict) and prev.get("session") else None
    if prev is not None and prev["session"] == sid:
        return None
    c.write_json(path, {"session": sid, "at": c.now_iso()})
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


def repair_unclosed(project: Path, previous_marker: dict, brain_root: Path | None = None) -> str:
    """Close the gap an earlier session left by ending without ``close``.

    If its transcript is still on disk, capture it now (same records as
    ``close`` would have written, without the classes only the model knew);
    otherwise append an inbox ``ledger`` record marked ``unrecorded: true``
    so the ledger shows the gap instead of hiding it. Returns one short line
    for boot to print."""
    root = Path(brain_root or c.BRAIN_ROOT)
    sid = str((previous_marker or {}).get("session") or "")
    if not sid:
        return ""
    main, subs = c.transcript_paths(sid)
    if main is not None and main.is_file():
        r = capture(root, sid, main, subs, project)
        if r["skipped"]:
            return f"earlier session {sid[:12]} was not closed; its ledger was already consolidated"
        return f"earlier session {sid[:12]} was not closed; recorded it from its transcript"
    family = str(c.load_manifest(project).get("family", "")) if c.is_managed(project) else ""
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
    s = summarise(main, subs, c.read_json(c.BRAIN_ROOT / "memory" / "models.json", {}))
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
    main, subs = c.transcript_paths(sid)
    known = main is not None and main.is_file()
    project = c.resolve_project(args.project, getattr(args, "brain_root", None))
    if project is not None and not c.is_managed(project):
        project = None
    declared = {"risk": args.risk, "model": args.model, "effort": args.effort, "est_tokens": args.est_tokens,
                "est_minutes": args.est_minutes, "explored": None if args.explored is None else bool(args.explored),
                "propensity": args.propensity, "has_check": None if args.has_check is None else bool(args.has_check)}
    box = None
    if args.tier is not None:
        # The size's timebox is the time estimate when none was declared, so
        # every closed small session teaches the calibration what such work
        # really takes, and the next timebox tightens or widens to match.
        from . import timebox
        box = timebox.for_size(args.tier, (args.cls or [""])[0] if isinstance(args.cls, list) else (args.cls or ""))
        if box and declared["est_minutes"] is None:
            declared["est_minutes"] = box["target"]
    if getattr(args, "request", None) and project is not None:
        # The request text is used here and dropped: only salted hashes of
        # its words leave this function, and the salt stays in the project.
        from . import route
        declared["words"] = learn.hashed_words(args.request, learn.project_salt(project))
        declared["rule_tier"] = int(route.classify(args.request, c.load_manifest(project))["tier"])
    r = capture(brain_root=getattr(args, "brain_root", None), sid=sid, main_path=main if known else None,
                sub_paths=subs if known else [], project=project, outcome=args.outcome or "",
                classes=args.cls, tier=args.tier, note=args.note or "",
                used=used if args.used else None, declared=declared)
    if args.json:
        print(json.dumps(r, indent=2, sort_keys=True))
        return 0
    s = r["summary"]
    t = s["totals"]
    if not known:
        print(f"no transcript found for session {sid}: outcomes recorded from the gate log, token usage unknown")
    else:
        print(f"tokens: {_k(_tokens(t))} (in {_k(t['in'])}, cache write {_k(t['cache_write'])}, "
              f"cache read {_k(t['cache_read'])}, out {_k(t['out'])})")
        print(f"cost: ${t['cost']:.2f}; helpers {s['helpers']} ({s['helper_cost_share']:.0%} of cost)")
        print(f"main conversation read from cache: {s['cache_read_share']:.0%}")
        est = declared.get("est_minutes")
        if s.get("wall_minutes") and est:
            stop = box["stop"] if box else est * 2
            verdict = "within the target" if s["wall_minutes"] <= est else "within the stop" if s["wall_minutes"] <= stop else "OVER THE STOP"
            print(f"time: {s['wall_minutes']:g} min against a timebox of {est:g} (stop {stop:g}): {verdict}")
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
    k.add_argument("--tier", type=int, choices=(0, 1, 2, 3))
    k.add_argument("--note", help="short note for the project's run record")
    # Whether an item helped is never accepted here: mlearn derives it from
    # the gate outcomes (I-07). Only whether it was followed is declared.
    k.add_argument("--used", action="append", metavar="ID:FOLLOWED",
                   help="a recalled item and whether it was followed (1) or not (0); repeatable")
    k.add_argument("--risk", choices=RISKS, help="risk of the work (default standard)")
    k.add_argument("--model", help="model alias of the work (default: the main conversation's)")
    k.add_argument("--effort", help="effort level (default: the transcript's)")
    k.add_argument("--est-tokens", type=int, help="tokens estimated before the work")
    k.add_argument("--est-minutes", type=float, help="minutes estimated before the work")
    k.add_argument("--explored", type=int, choices=(0, 1), help="1 if a cheaper arm was being tried")
    k.add_argument("--propensity", type=float, help="probability the routing choice had (default 1)")
    k.add_argument("--has-check", type=int, choices=(0, 1),
                   help="override: did a verifying command gate run (default: read from the gate log)")
    k.add_argument("--request", help="the owner's request; only salted hashes of its words are kept (sizing data)")
    k.add_argument("--json", action="store_true")
    k.set_defaults(func=cmd_close)
