"""Scheduling tickets onto parallel helpers: `brain plan schedule` and `brain plan assign`.

Why: when a plan has independent items, running them in parallel buys elapsed
time (never tokens: each helper starts cold). The question is the order. The
method, measured in docs/research/04-algorithms.md section 1.3:

1. Critical-path priority: the ticket with the longest chain of work behind
   it starts first.
2. Simulated annealing over that priority order (swap two tickets, accept a
   worse order with probability exp(-delta/T), geometric cooling). Annealing is
   the classical method quantum annealers imitate, hence "quantum-inspired".
   It starts from the critical-path order and keeps the best order seen, so
   its result is never worse than step 1.

Both orders are turned into a timetable by the same serial schedule
generator: tickets are placed one at a time (highest priority among those
whose dependencies are placed) at the earliest time when an agent is free and
no conflicting ticket is running. Two tickets conflict when they write the same
path or one path is a directory containing the other. Serial generation can
reach an optimal schedule for some order, which is why searching over orders
is worth doing.

When the learning state has calibration data, ``plan schedule`` first scales
each ticket that names a ``class`` by that class's typical actual/estimate
ratio (engine/mlearn.calibrate), because a timetable built on estimates that
run 1.5x long is wrong in a predictable way. ``plan packet`` prints the brief a
helper needs for one ticket, so every delegation carries its acceptance
command and return format.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from . import common as c
from . import mlearn
from . import route

EPS = 1e-9
CLIQUE_STEP_CAP = 20000


class PlanError(ValueError):
    """A one-line problem with the input plan."""


# ---------------------------------------------------------------- input
def _conflicts(a: str, b: str) -> bool:
    a, b = a.strip().rstrip("/"), b.strip().rstrip("/")
    return a == b or b.startswith(a + "/") or a.startswith(b + "/")


def load_plan(data: dict, agents: int | None = None) -> dict:
    """Validate and normalise a plan; raises PlanError with one clear line."""
    if not isinstance(data, dict) or not isinstance(data.get("tickets"), list):
        raise PlanError('input must be a JSON object with a "tickets" list')
    n_agents = agents if agents is not None else data.get("agents", 4)
    if not isinstance(n_agents, int) or isinstance(n_agents, bool) or n_agents < 1:
        raise PlanError("agents must be a positive integer")
    ids: list[str] = []
    tickets = []
    for pos, t in enumerate(data["tickets"]):
        if not isinstance(t, dict) or not t.get("id"):
            raise PlanError(f"ticket #{pos + 1} has no id")
        tid = str(t["id"])
        if tid in ids:
            raise PlanError(f"duplicate ticket id: {tid}")
        est = t.get("est")
        if not isinstance(est, (int, float)) or isinstance(est, bool) or not est > 0 or math.isinf(est):
            raise PlanError(f"ticket {tid}: est must be a number greater than 0")
        deps = t.get("deps", []) or []
        files = t.get("files", []) or []
        if not isinstance(deps, list) or not isinstance(files, list):
            raise PlanError(f"ticket {tid}: deps and files must be lists")
        tokens = t.get("tokens", 0) or 0
        if not isinstance(tokens, (int, float)) or tokens < 0:
            raise PlanError(f"ticket {tid}: tokens must be a non-negative number")
        ids.append(tid)
        tickets.append({"id": tid, "est": est, "deps": [str(d) for d in deps],
                        "files": [str(f) for f in files], "tokens": tokens})
    index = {tid: i for i, tid in enumerate(ids)}
    for t in tickets:
        for d in t["deps"]:
            if d not in index:
                raise PlanError(f"ticket {t['id']}: unknown dependency {d}")
            if d == t["id"]:
                raise PlanError(f"ticket {t['id']} depends on itself")
    deps = [sorted({index[d] for d in t["deps"]}) for t in tickets]
    order = _topological(deps)
    if order is None:
        raise PlanError("dependency cycle: " + " -> ".join(_find_cycle(deps, ids)))
    n = len(tickets)
    conflict = [[False] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if any(_conflicts(a, b) for a in tickets[i]["files"] for b in tickets[j]["files"]):
                conflict[i][j] = conflict[j][i] = True
    start_cost = data.get("helper_start_tokens", 0) or 0
    if not isinstance(start_cost, (int, float)) or start_cost < 0:
        raise PlanError("helper_start_tokens must be a non-negative number")
    return {"agents": n_agents, "tickets": tickets, "ids": ids, "deps": deps, "topo": order,
            "est": [float(t["est"]) for t in tickets], "conflict": conflict,
            "helper_start_tokens": start_cost}


def _topological(deps: list[list[int]]) -> list[int] | None:
    n = len(deps)
    indeg = [len(d) for d in deps]
    succ: list[list[int]] = [[] for _ in range(n)]
    for i, ds in enumerate(deps):
        for d in ds:
            succ[d].append(i)
    ready = [i for i in range(n) if indeg[i] == 0]
    order = []
    while ready:
        i = ready.pop(0)
        order.append(i)
        for s in succ[i]:
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
    return order if len(order) == n else None


def _find_cycle(deps: list[list[int]], ids: list[str]) -> list[str]:
    colour = [0] * len(deps)
    stack: list[int] = []

    def visit(i: int) -> list[int] | None:
        colour[i] = 1
        stack.append(i)
        for d in deps[i]:
            if colour[d] == 1:
                return stack[stack.index(d):] + [d]
            if colour[d] == 0:
                found = visit(d)
                if found:
                    return found
        stack.pop()
        colour[i] = 2
        return None

    for i in range(len(deps)):
        if colour[i] == 0:
            cyc = visit(i)
            if cyc:
                return [ids[k] for k in reversed(cyc)]
    return []


# ---------------------------------------------------------------- core
def critical_tails(plan: dict) -> list[float]:
    """Length of the longest chain of work starting at each ticket."""
    n = len(plan["est"])
    succ: list[list[int]] = [[] for _ in range(n)]
    for i, ds in enumerate(plan["deps"]):
        for d in ds:
            succ[d].append(i)
    tail = [0.0] * n
    for i in reversed(plan["topo"]):
        tail[i] = plan["est"][i] + max((tail[s] for s in succ[i]), default=0.0)
    return tail


def decode(plan: dict, order: list[int]) -> tuple[list[float], float, float]:
    """Serial schedule generation: (start times, makespan, mean finish).

    ``order`` is a priority list; at each step the earliest-listed ticket whose
    dependencies are placed goes to the earliest feasible start. A start is
    feasible when fewer than N placed tickets overlap its interval at any
    moment and no conflicting ticket overlaps it; the earliest feasible start
    is always the ready time or some placed ticket's finish time.
    """
    est, deps, conflict, cap = plan["est"], plan["deps"], plan["conflict"], plan["agents"]
    n = len(est)
    rank = [0] * n
    for pos, i in enumerate(order):
        rank[i] = pos
    start = [-1.0] * n
    finish = [0.0] * n
    placed: list[int] = []
    remaining = set(range(n))
    for _ in range(n):
        i = min((j for j in remaining if all(start[d] >= 0 for d in deps[j])), key=rank.__getitem__)
        remaining.discard(i)
        ready = max((finish[d] for d in deps[i]), default=0.0)
        d_i = est[i]
        for t in sorted({ready} | {finish[j] for j in placed if finish[j] > ready + EPS}):
            end = t + d_i
            overlapping = [j for j in placed if start[j] < end - EPS and finish[j] > t + EPS]
            if any(conflict[i][j] for j in overlapping):
                continue
            if len(overlapping) >= cap:
                points = [t] + [start[j] for j in overlapping if start[j] > t + EPS]
                if max(sum(1 for j in overlapping if start[j] <= p + EPS and finish[j] > p + EPS)
                       for p in points) >= cap:
                    continue
            start[i], finish[i] = t, end
            break
        placed.append(i)
    makespan = max(finish, default=0.0)
    return start, makespan, (sum(finish) / n if n else 0.0)


def assign_agents(plan: dict, start: list[float]) -> list[int]:
    """Agent number (1-based) per ticket: interval partitioning, lowest free
    agent first, so the numbering is stable for a given timetable."""
    est = plan["est"]
    agent = [0] * len(est)
    free_at: list[float] = []
    for i in sorted(range(len(est)), key=lambda k: (start[k], k)):
        slot = next((a for a, f in enumerate(free_at) if f <= start[i] + EPS), None)
        if slot is None:
            slot = len(free_at)
            free_at.append(0.0)
        free_at[slot] = start[i] + est[i]
        agent[i] = slot + 1
    return agent


def lower_bound(plan: dict) -> tuple[float, str]:
    """Best of: longest dependency chain, total work / agents, and the total of
    the heaviest set of mutually conflicting tickets found (they must run one
    after another). Any clique found is a valid bound, so the clique search
    stops after a fixed number of steps on large plans."""
    est = plan["est"]
    n = len(est)
    if n == 0:
        return 0.0, "empty"
    cp = max(critical_tails(plan))
    work = sum(est) / plan["agents"]
    if all(float(e).is_integer() for e in est):
        work = math.ceil(work - EPS)
    clique = _heaviest_conflict_clique(plan)
    best = max((cp, "critical path"), (work, "work / agents"), (clique, "conflicting tickets"), key=lambda x: x[0])
    return best


def _heaviest_conflict_clique(plan: dict) -> float:
    est, conflict = plan["est"], plan["conflict"]
    n = len(est)
    nbrs = [{j for j in range(n) if conflict[i][j]} for i in range(n)]
    best = max(est, default=0.0)
    steps = 0

    def expand(weight: float, cand: set[int]) -> None:
        nonlocal best, steps
        steps += 1
        if weight > best:
            best = weight
        if steps > CLIQUE_STEP_CAP or weight + sum(est[v] for v in cand) <= best + EPS:
            return
        for v in sorted(cand, key=lambda k: -est[k]):
            expand(weight + est[v], cand & nbrs[v])
            cand = cand - {v}
            if weight + sum(est[u] for u in cand) <= best + EPS:
                return

    expand(0.0, {i for i in range(n) if nbrs[i]})
    return best


def _anneal(plan: dict, order: list[int], rng: random.Random, iters: int, floor: float) -> tuple[list[int], tuple[float, float]]:
    """Swap-neighbourhood annealing over a priority list; returns the best seen.
    Energy is makespan plus a tiny mean-finish term, which breaks the long
    plateaus of equal makespan without ever outweighing a real improvement."""
    n = len(order)
    _, ms, mf = decode(plan, order)
    best_order, best = list(order), (ms, mf)
    if n < 2 or ms <= floor + EPS:
        return best_order, best
    scale = sum(plan["est"]) / n
    t0, t1 = 0.5 * scale, 0.005 * scale
    cur = list(order)
    cur_e = ms + 1e-3 * mf
    for it in range(iters):
        temp = t0 * (t1 / t0) ** (it / max(1, iters - 1))
        a, b = rng.randrange(n), rng.randrange(n)
        if a == b:
            continue
        cur[a], cur[b] = cur[b], cur[a]
        _, ms, mf = decode(plan, cur)
        e = ms + 1e-3 * mf
        if e <= cur_e or rng.random() < math.exp((cur_e - e) / temp):
            cur_e = e
            if (ms, mf) < (best[0] - EPS, best[1]) or (abs(ms - best[0]) <= EPS and mf < best[1] - EPS):
                best_order, best = list(cur), (ms, mf)
                if ms <= floor + EPS:
                    break
        else:
            cur[a], cur[b] = cur[b], cur[a]
    return best_order, best


def iterations_for(n: int) -> int:
    """Fixed annealing budget scaled by plan size (deterministic, no clock)."""
    return min(3000, max(300, 60 * n))


def schedule(data: dict, agents: int | None = None, seed: int = 0, anneal: bool = True,
             helper_start_tokens: float | None = None) -> dict:
    """Schedule a plan; returns the timeline and the quality numbers."""
    plan = load_plan(data, agents)
    n = len(plan["est"])
    lb, lb_kind = lower_bound(plan)
    tails = critical_tails(plan)
    cp_order = sorted(range(n), key=lambda i: (-tails[i], -plan["est"][i], i))
    cp_start, cp_ms, _ = decode(plan, cp_order)
    order, start, makespan, method = cp_order, cp_start, cp_ms, "critical-path"
    if anneal and n > 1:
        best_order, (ms, _) = _anneal(plan, cp_order, random.Random(seed), iterations_for(n), lb)
        if ms < cp_ms - EPS:
            order, makespan, method = best_order, ms, "annealed, quantum-inspired"
            start = decode(plan, order)[0]
    agent = assign_agents(plan, start)
    sequential = sum(plan["est"])
    timeline = sorted(
        ({"id": plan["ids"][i], "agent": agent[i], "start": _num(start[i]), "end": _num(start[i] + plan["est"][i]),
          "est": _num(plan["est"][i])} for i in range(n)),
        key=lambda r: (r["start"], r["agent"]))
    out = {
        "agents": plan["agents"], "makespan": _num(makespan), "critical_path_makespan": _num(cp_ms),
        "lower_bound": _num(lb), "lower_bound_kind": lb_kind,
        "gap_pct": round(100 * (makespan - lb) / lb, 1) if lb > 0 else 0.0,
        "sequential": _num(sequential), "speedup": round(sequential / makespan, 2) if makespan else 1.0,
        "method": method, "seed": seed, "timeline": timeline,
    }
    work_tokens = sum(t["tokens"] for t in plan["tickets"])
    start_cost = plan["helper_start_tokens"] if helper_start_tokens is None else helper_start_tokens
    if work_tokens or start_cost:
        used = max(agent, default=1)
        out["tokens"] = {"work": _num(work_tokens), "helper_start": _num(start_cost), "helpers": used,
                         "parallel_total": _num(work_tokens + used * start_cost),
                         "sequential_total": _num(work_tokens + start_cost)}
    return out


def _num(x: float) -> float | int:
    return int(round(x)) if abs(x - round(x)) < 1e-6 else round(x, 3)


def render(out: dict, max_lines: int = 14) -> list[str]:
    """Compact timeline: one line per start time, then one summary line."""
    groups: dict = {}
    for r in out["timeline"]:
        groups.setdefault(r["start"], []).append(f"A{r['agent']} {r['id']} ({r['est']})")
    lines = [f"t={t} " + " | ".join(parts) for t, parts in groups.items()]
    if len(lines) > max_lines:
        hidden = len(lines) - max_lines + 1
        lines = lines[: max_lines - 1] + [f"... {hidden} more start times (use --json)"]
    lines.append(f"makespan {out['makespan']}, lower bound {out['lower_bound']}, gap {out['gap_pct']}%, "
                 f"sequential {out['sequential']} ({out['speedup']}x), method: {out['method']}")
    tok = out.get("tokens")
    if tok:
        lines.append(f"tokens: {tok['work']} of work either way; {tok['helpers']} helpers each start cold at "
                     f"{tok['helper_start']}: parallel {tok['parallel_total']} vs sequential {tok['sequential_total']}")
    return lines


def calibrate_plan(data: dict, state: dict, cfg: dict | None = None) -> tuple[dict, dict]:
    """(plan with calibrated est/tokens, {tickets, outcomes}). Only tickets
    with a ``class`` change, and only when that class or its family has enough
    outcomes (mlearn.calibrate acting at class or family level): a ratio from
    unrelated families would rescale on someone else's evidence. ``outcomes``
    counts the outcomes behind the levels used, once each."""
    if not isinstance(data, dict) or not isinstance(data.get("tickets"), list):
        return data, {"tickets": 0, "outcomes": 0}
    out = dict(data)
    out["tickets"] = []
    changed, used = 0, {}
    for t in data["tickets"]:
        t2 = dict(t) if isinstance(t, dict) else t
        cls = t2.get("class") if isinstance(t2, dict) else None
        est = t2.get("est") if isinstance(t2, dict) else None
        if isinstance(cls, str) and isinstance(est, (int, float)) and not isinstance(est, bool) and est > 0:
            fam = str(t2.get("family") or cls.split(".")[0])
            tok = t2.get("tokens") if isinstance(t2.get("tokens"), (int, float)) and t2.get("tokens") else None
            cal = mlearn.calibrate(state, cls, fam, tok, est, cfg)
            if cal["level"] in ("class", "family") and cal["minutes_p50"]:
                t2["est"] = cal["minutes_p50"]
                if tok and cal["tokens_p50"]:
                    t2["tokens"] = cal["tokens_p50"]
                changed += 1
                used[(cal["level"], cls if cal["level"] == "class" else fam)] = cal["n"]
        out["tickets"].append(t2)
    return out, {"tickets": changed, "outcomes": sum(used.values())}


PACKET_RETURN = ("at most 250 words: what changed, the acceptance command and its result line, "
                 "anything that differs from the brief")


def packet(data: dict, ticket_id: str, max_lines: int = 25) -> list[str]:
    """The delegation brief for one ticket, at most max_lines lines. Raises
    PlanError for an unknown id or a plan without tickets."""
    if not isinstance(data, dict) or not isinstance(data.get("tickets"), list):
        raise PlanError('input must be a JSON object with a "tickets" list')
    tickets = {str(t.get("id")): t for t in data["tickets"] if isinstance(t, dict) and t.get("id")}
    t = tickets.get(str(ticket_id))
    if t is None:
        raise PlanError(f"no ticket {ticket_id} in the plan ({len(tickets)} tickets)")
    files = [str(f) for f in t.get("files", []) or []]
    deps = [str(d) for d in t.get("deps", []) or []]
    lines = [f"Ticket {t['id']}: {c.clip(t.get('goal') or t.get('title') or '(no title)', 200)}"]
    if t.get("reason"):
        lines.append(f"Why: {c.clip(t['reason'], 300)}")
    lines.append("Files you own (change nothing else):" if files else "Files you own: none listed (ask the lead)")
    shown = files if len(files) <= 10 else files[:9]
    lines += [f"- {f}" for f in shown]
    if len(files) > len(shown):
        lines.append(f"- ... and {len(files) - len(shown)} more (see the plan file)")
    if deps:
        status = ", ".join(f"{d} ({tickets.get(d, {}).get('status', 'unknown')})" for d in deps)
        lines.append(f"Depends on: {c.clip(status, 300)}")
    else:
        lines.append("Depends on: nothing")
    for key, label in (("interfaces", "Interfaces"), ("constraints", "Constraints")):
        val = t.get(key)
        if isinstance(val, list):
            val = "; ".join(map(str, val))
        if val:
            lines.append(f"{label}: {c.clip(val, 400)}")
    accept = t.get("accept")
    lines.append(f"Acceptance command: {accept}" if accept else "Acceptance command: none recorded; add one before delegating")
    lines.append(f"Return: {PACKET_RETURN}.")
    lines.append("Do not commit; the lead reviews and commits.")
    return lines[:max_lines]


# ---------------------------------------------------------------- cli
def _read_input(path: str) -> dict | None:
    p = Path(path)
    if not p.is_file():
        print(f"plan: file not found: {path}")
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"plan: {path} is not valid JSON ({e.msg if hasattr(e, 'msg') else e})")
        return None


def cmd_schedule(args) -> int:
    data = _read_input(args.file)
    if data is None:
        return 2
    info = {"tickets": 0, "outcomes": 0}
    state = mlearn.load()
    if state["n"]:
        try:
            data, info = calibrate_plan(data, state, mlearn.config())
        except ValueError as e:
            print(f"plan: calibration skipped ({e})")
    try:
        out = schedule(data, agents=args.agents, seed=args.seed, anneal=not args.no_anneal,
                       helper_start_tokens=args.start_tokens)
    except PlanError as e:
        print(f"plan: {e}")
        return 2
    if info["tickets"]:
        out["calibration"] = info
    if args.json:
        print(json.dumps(out, ensure_ascii=False))
        return 0
    lines = render(out, max_lines=13 if info["tickets"] else 14)
    if info["tickets"]:
        lines.append(f"calibration applied: {info['tickets']} ticket estimates scaled by their class's typical "
                     f"actual/estimate ratio ({info['outcomes']} outcomes)")
    print("\n".join(lines))
    return 0


def cmd_packet(args) -> int:
    data = _read_input(args.file)
    if data is None:
        return 2
    try:
        lines = packet(data, args.ticket)
    except PlanError as e:
        print(f"plan packet: {e}")
        return 1
    print("\n".join(lines))
    return 0


def cmd_assign(args) -> int:
    data = _read_input(args.file)
    if data is None:
        return 2
    budget = args.budget if args.budget is not None else (data.get("budget") if isinstance(data, dict) else None)
    try:
        res = route.assign(data.get("tasks") if isinstance(data, dict) else None, budget)
    except ValueError as e:
        print(f"plan assign: {e}")
        return 2
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    rows = list(res["choice"].items())
    for tid, opt in rows[:13]:
        print(f"{tid}: {opt['model']}/{opt['effort']} cost {opt['cost']} quality {opt['quality']}")
    if len(rows) > 13:
        print(f"... {len(rows) - 13} more tasks (use --json)")
    state = "within budget" if res["feasible"] else "OVER BUDGET: cheapest option for every task"
    print(f"total cost {res['cost']} of {budget}, quality {res['quality']}, {state}")
    return 0 if res["feasible"] else 1


def register(sub) -> None:
    p = sub.add_parser("plan", help="schedule parallel work and assign models under a budget")
    s = p.add_subparsers(dest="plan_cmd")
    k = s.add_parser("schedule", help="timeline for tickets on N agents (critical path, then annealing)")
    k.add_argument("file", help='JSON: {"agents": 4, "tickets": [{"id", "est", "deps", "files", "tokens"}]}')
    k.add_argument("--agents", type=int)
    k.add_argument("--seed", type=int, default=0)
    k.add_argument("--no-anneal", action="store_true", help="critical-path order only")
    k.add_argument("--start-tokens", type=float, help="tokens each parallel helper spends starting cold")
    k.add_argument("--json", action="store_true")
    k.set_defaults(func=cmd_schedule)
    a = s.add_parser("assign", help="model and effort per task maximising quality within a budget")
    a.add_argument("file", help='JSON: {"budget": 100, "tasks": [{"id", "options": [{"model", "effort", "cost", "quality"}]}]}')
    a.add_argument("--budget", type=int)
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_assign)
    pk = s.add_parser("packet", help="delegation brief for one ticket (at most 25 lines)")
    pk.add_argument("file", help="tickets JSON, e.g. docs/plan/tickets.json")
    pk.add_argument("ticket", help="ticket id")
    pk.set_defaults(func=cmd_packet)
    p.set_defaults(func=lambda args: (p.print_help(), 2)[1])
