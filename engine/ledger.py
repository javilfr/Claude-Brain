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
"""
from __future__ import annotations

import datetime as _dt
import json
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
        out.append({"gate": str(r.get("gate") or r.get("id") or "gate"), "exit_code": code, "at": str(r.get("at", ""))})
    return out


def _model_rows(s: dict) -> dict:
    return {m: {k: v[k] for k in ("in", "cache_write", "cache_read", "out", "cost")} for m, v in s["models"].items()}


def capture(brain_root: Path | None = None, sid: str | None = None, main_path=None, sub_paths=None,
            project: Path | None = None, outcome: str = "", classes: list[str] | None = None,
            tier: int | None = None, note: str = "", models_cfg: dict | None = None) -> dict:
    """Write the run record and inbox records for one session. Safe to call
    again: both are keyed by session id and replaced, never duplicated."""
    root = Path(brain_root or c.BRAIN_ROOT)
    sid = sid or c.session_id()
    if main_path is None:
        main_path, sub_paths = c.transcript_paths(sid)
    cfg = models_cfg if models_cfg is not None else c.read_json(root / "memory" / "models.json", {})
    s = summarise(main_path, sub_paths or [], cfg)
    classes = [x for x in (classes or []) if x]
    at = c.now_iso()
    result = {"session": sid, "summary": s, "run_record": "", "inbox": "", "inbox_records": 0, "skipped": ""}

    family = ""
    gates: list[dict] = []
    if project is not None and c.is_managed(project):
        family = str(c.load_manifest(project).get("family", ""))
        gates = _gate_rows(project, sid)
        log_dir = Path(project) / ".brain" / "log"
        safe = learn.safe_session(sid)
        existing = sorted(log_dir.glob(f"*-{safe}.json"))
        path = existing[0] if existing else log_dir / f"{c.today()}-{safe}.json"
        record = {"session": sid, "at": at, "tier": tier, "classes": classes, "outcome": outcome,
                  "note": note, "models": _model_rows(s), "totals": s["totals"], "helpers": s["helpers"],
                  "cache_read_share": s["cache_read_share"], "wall_minutes": s["wall_minutes"], "gates": gates}
        c.write_json(path, record)
        result["run_record"] = str(path)

    records = [{"kind": "ledger", "session": sid, "at": at, "family": family,
                "task_class": classes[0] if classes else "", "classes": classes, "tier": tier,
                "outcome": outcome, "models": _model_rows(s), "helpers": s["helpers"],
                "cache_read_share": s["cache_read_share"], "wall_minutes": s["wall_minutes"]}]
    if classes and gates:
        first_runs: dict[str, dict] = {}
        for g in gates:
            first_runs.setdefault(g["gate"], g)
        passed = all(g["exit_code"] == 0 for g in first_runs.values())
        share = _tokens(s["totals"]) // len(classes)
        for cls in classes:
            records.append({"kind": "outcome", "session": sid, "at": at, "task_class": cls,
                            "model": s["main_model"], "effort": s["main_effort"], "passed": passed,
                            "tokens": share,
                            "evidence": [f"gate:{g['gate']} exit {g['exit_code']}" for g in first_runs.values()]})
    written = learn.replace_session_records(root, sid, records, kinds=("ledger", "outcome"))
    if written is None:
        result["skipped"] = "this session's ledger was already consolidated"
    else:
        result["inbox"] = str(written)
        result["inbox_records"] = len(records)

    if project is not None:
        try:
            from . import state
            state.write_status(project)
        except (ImportError, AttributeError):
            pass
    return result


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
    main, subs = c.transcript_paths(sid)
    if main is None or not main.is_file():
        print(f"no transcript found for session {sid}")
        return 1
    project = c.resolve_project(args.project)
    if project is not None and not c.is_managed(project):
        project = None
    r = capture(sid=sid, main_path=main, sub_paths=subs, project=project, outcome=args.outcome or "",
                classes=args.cls, tier=args.tier, note=args.note or "")
    if args.json:
        print(json.dumps(r, indent=2, sort_keys=True))
        return 0
    s = r["summary"]
    t = s["totals"]
    print(f"tokens: {_k(_tokens(t))} (in {_k(t['in'])}, cache write {_k(t['cache_write'])}, "
          f"cache read {_k(t['cache_read'])}, out {_k(t['out'])})")
    print(f"cost: ${t['cost']:.2f}; helpers {s['helpers']} ({s['helper_cost_share']:.0%} of cost)")
    print(f"main conversation read from cache: {s['cache_read_share']:.0%}")
    print(f"run record: {r['run_record'] or 'none (no managed project)'}")
    print(f"inbox: {r['skipped'] or str(r['inbox_records']) + ' record(s) in ' + Path(r['inbox']).name}")
    return 0


def register(sub) -> None:
    p = sub.add_parser("ledger", help="real token use and cost of a session")
    p.add_argument("--session", help="session id (default: this session)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_ledger)

    k = sub.add_parser("close", help="end-of-session capture: run record and ledger")
    c.add_project_arg(k)
    k.add_argument("--session", help="session id (default: this session)")
    k.add_argument("--outcome", choices=("ok", "partial", "failed"))
    k.add_argument("--class", dest="cls", action="append", default=[], help="task class (repeatable)")
    k.add_argument("--tier", type=int, choices=(0, 1, 2, 3))
    k.add_argument("--note", help="short note for the project's run record")
    k.add_argument("--json", action="store_true")
    k.set_defaults(func=cmd_close)
