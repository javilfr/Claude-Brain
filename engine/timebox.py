"""Time budgets by Parkinson's law: work expands to fill the time allowed.

Why: a generous fixed allowance (a one-hour command timeout, a two-minute
deploy wait, an open-ended task) is time the work will use, or time a hung
step wastes before anyone notices. So every time budget the brain hands out
is the tightest one the evidence supports, it has a soft target and a hard
stop, and at the stop a decision is made instead of more waiting.

One algorithm serves every place a time budget appears (``allot``):

1. An explicit value from the caller always wins.
2. With at least ``MIN_N`` observed durations (the last ``WINDOW``): the
   target is their median, the stop is the conformal 90th percentile times
   ``SAFETY`` plus ``slack``. Old, slower history ages out of the window, so
   the budget shrinks as the work gets faster.
3. With 1 to MIN_N-1 observations: the stop is the slowest seen times
   ``SMALL_N_FACTOR``.
4. With none: the estimate (target) and the estimate times ``PRIOR_FACTOR``
   (stop); without an estimate, the caller's old fixed default.
5. A run that hit the stop is censored, not a duration: each consecutive one
   doubles the next stop (``BACKOFF``), up to the cap. The first run that
   finishes resets the streak, and the stop comes from evidence again.
6. Every stop is clipped to [floor, cap].

The same numbers, in minutes, give the timeboxes for a request by size, a
plan ticket and a helper's brief: the target is what to aim for, the stop is
where to finish what is there, re-size, or report what is left.
"""
from __future__ import annotations

import math
from pathlib import Path

from . import common as c

MIN_N = 5            # observations before the evidence sets the budget
WINDOW = 20          # recent observations kept per key
SAFETY = 1.5         # stop = q90 x SAFETY + slack
SMALL_N_FACTOR = 3.0
PRIOR_FACTOR = 2.0   # stop = estimate x PRIOR_FACTOR when nothing was observed
BACKOFF = 2.0        # each consecutive timeout doubles the next stop
KEYS_CAP = 400       # keys kept in one store (least recently used dropped)

# Timeboxes for a request by size, in minutes (target, stop). Size 0 is a
# reply; size 1 one bounded change; sizes 2 and 3 take their timebox from the
# plan's tickets, so they get none here. Seeded from the brain's own sessions
# (docs/BUILD_STATUS.md); mlearn calibration replaces them once a class has
# enough outcomes.
SIZE_MINUTES = {0: (3, 6), 1: (20, 40)}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _conformal(xs: list[float], q: float) -> float:
    """Distribution-free quantile: the ceil((n+1)q)-th smallest, the largest
    when that runs past the sample (errs long on small samples)."""
    s = sorted(xs)
    k = math.ceil((len(s) + 1) * q)
    return s[min(k, len(s)) - 1]


def allot(rec: dict | None, default: float, floor: float = 1.0, cap: float | None = None,
          est: float | None = None, explicit: float | None = None, slack: float = 0.0,
          safety: float = SAFETY, small_n: float | None = SMALL_N_FACTOR) -> dict:
    """{target, limit, n, basis} for one key's record ({"d": durations, "to":
    consecutive timeouts}). ``cap`` defaults to ``default``: evidence can only
    tighten a budget below the old fixed value or, after timeouts, grow it
    back toward it, never beyond what was allowed before. ``small_n=None``
    keeps the default until MIN_N runs are seen (for work where killing a
    healthy run costs more than waiting on a hung one)."""
    cap = default if cap is None else cap
    if _num(explicit) and explicit >= 0:
        return {"target": None, "limit": float(explicit), "n": 0, "basis": "set by the caller"}
    rec = rec if isinstance(rec, dict) else {}
    ds = [float(x) for x in rec.get("d", []) if _num(x) and x >= 0][-WINDOW:]
    streak = int(rec.get("to", 0) or 0)
    if len(ds) >= MIN_N:
        target = _median(ds)
        limit = _conformal(ds, 0.9) * safety + slack
        basis = f"from {len(ds)} runs: median {target:.4g}, 90th percentile x {safety:g}"
    elif ds and small_n is None:
        target, limit = _median(ds), float(default)
        basis = f"{len(ds)} run(s) seen, {MIN_N} needed: the default"
    elif ds:
        target = _median(ds)
        limit = max(ds) * small_n + slack
        basis = f"from {len(ds)} run(s): slowest x {small_n:g}"
    elif _num(est) and est > 0:
        target, limit = float(est), float(est) * PRIOR_FACTOR
        basis = f"no runs yet: estimate x {PRIOR_FACTOR:g}"
    else:
        target, limit = None, float(default)
        basis = "no runs yet: the default"
    if streak:
        limit *= BACKOFF ** streak
        basis += f"; x{BACKOFF ** streak:g} after {streak} timeout(s) in a row"
    limit = max(floor, min(cap, limit))
    if target is not None:
        target = round(min(target, limit), 1)
    return {"target": target, "limit": round(limit, 1), "n": len(ds), "basis": basis}


# ---------------------------------------------------------------- store
def store_path(project: Path | None) -> Path:
    """Next to the run logs: inside the project when there is one, else the
    temporary folder (the brain's own files change only through learn)."""
    from .gate import log_dir
    return log_dir(project).parent / "timebox.json"


def load(path: Path) -> dict:
    data = c.read_json(path, {}) or {}
    return data if isinstance(data, dict) else {}


def key_for(kind: str, text: str) -> str:
    return f"{kind}:{c.sha256_text(' '.join(str(text).split()))[:12]}"


def observe(path: Path, key: str, seconds: float, timed_out: bool = False, label: str = "") -> dict:
    """Fold one run into the store. A timeout is censored: it extends the
    streak and adds no duration."""
    data = load(path)
    rec = data.pop(key, None) or {"d": [], "to": 0}
    if timed_out:
        rec["to"] = int(rec.get("to", 0) or 0) + 1
    elif _num(seconds) and seconds >= 0:
        rec["d"] = (list(rec.get("d", [])) + [round(float(seconds), 2)])[-WINDOW:]
        rec["to"] = 0
    rec["at"] = c.now_iso()
    if label:
        rec["label"] = c.clip(label, 80)
    data[key] = rec  # re-inserted last: the dict order is the recency order
    while len(data) > KEYS_CAP:
        data.pop(next(iter(data)))
    try:
        c.write_json(path, data)
    except OSError:
        pass  # a read-only folder must never break the command it times
    return rec


COMMAND_FLOOR = 120.0  # seconds: no learned command timebox is shorter
COMMAND_SAFETY = 3.0   # a cold cache or a busy machine can triple a build


def for_command(command: str, project: Path | None, default: float, floor: float = COMMAND_FLOOR,
                explicit: float | None = None) -> tuple[str, dict]:
    """(key, allotment) for a shell command, in seconds. Wider than other
    timeboxes on purpose: a killed healthy build costs its whole run again,
    a hung one only the stop. So: the default until MIN_N successful runs,
    then 3 x their 90th percentile, never under two minutes."""
    key = key_for("cmd", command)
    rec = load(store_path(project)).get(key)
    return key, allot(rec, default, floor=floor, explicit=explicit, slack=10.0, safety=COMMAND_SAFETY, small_n=None)


# ---------------------------------------------------------------- minutes
def for_size(tier, task_class: str = "", family: str = "") -> dict | None:
    """The timebox for a request by size, in minutes, or None (sizes 2 and 3
    take theirs from the plan). Calibrated by mlearn when the class or its
    family has enough outcomes, otherwise the seeded prior."""
    try:
        tier = int(tier)
    except (TypeError, ValueError):
        return None
    if tier not in SIZE_MINUTES:
        return None
    target, stop = SIZE_MINUTES[tier]
    basis = "prior"
    try:
        from . import mlearn
        state = mlearn.load()
        if state.get("n"):
            cal = mlearn.calibrate(state, task_class, family or task_class.split(".")[0], None, target)
            if cal["level"] in ("class", "family") and cal["minutes_p50"]:
                target = cal["minutes_p50"]
                stop = max(cal["minutes_p80"] or 0, target * 1.25)
                basis = f"calibrated on {cal['n']} outcome(s) of the {cal['level']}"
    except Exception:
        pass
    return {"target": round(target, 1), "stop": round(stop, 1), "basis": basis}


def ticket_box(t: dict) -> dict | None:
    """(target, stop) minutes for a plan ticket: its estimate (calibrated p50
    when the schedule calibrated it) and its recorded stop, else the estimate
    x PRIOR_FACTOR."""
    est = t.get("est") if isinstance(t, dict) else None
    if not (_num(est) and est > 0):
        return None
    stop = t.get("stop")
    stop = float(stop) if _num(stop) and stop >= est else est * PRIOR_FACTOR
    return {"target": round(float(est), 1), "stop": round(stop, 1)}


def box_line(box: dict | None, unit: str = "min") -> str:
    if not box:
        return ""
    return (f"Timebox: aim for {box['target']:g} {unit}; at {box['stop']:g} {unit} stop, "
            f"and finish what is there, split the rest, or report what is left.")


# ---------------------------------------------------------------- cli
def cmd_timebox(args) -> int:
    project = c.resolve_project(args.project)
    if project is not None and not c.is_managed(project):
        project = None
    path = store_path(project)
    data = load(path)
    print(f"timebox store: {path} · {len(data)} key(s)")
    rows = list(data.items())[-args.limit:][::-1]
    for key, rec in rows:
        if key.startswith("cmd:"):
            a = allot(rec, 3600, floor=COMMAND_FLOOR, slack=10.0, safety=COMMAND_SAFETY, small_n=None)
        else:
            a = allot(rec, 120, floor=30.0, slack=20.0)
        tgt = f"target {a['target']:g}s, " if a["target"] is not None else ""
        print(f"- {rec.get('label') or key}: {tgt}stop {a['limit']:g}s · {a['basis']}")
    for tier, name in ((0, "answer"), (1, "small task")):
        b = for_size(tier, args.task_class or "", "")
        print(f"size {tier} ({name}): aim for {b['target']:g} min, stop at {b['stop']:g} min · {b['basis']}")
    return 0


def register(sub) -> None:
    p = sub.add_parser("timebox", help="show the time budgets learned from past runs (Parkinson's law)")
    c.add_project_arg(p)
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--task-class", default="")
    p.set_defaults(func=cmd_timebox)
