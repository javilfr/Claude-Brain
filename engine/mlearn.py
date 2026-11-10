"""All statistical learning of the brain: `brain ml report`, `brain ml alarms`.

Why one module: every learner here runs as plain Python on tens of data
points, at zero model tokens, and shares the same needs: shrink toward a prior,
refuse to act below a minimum of data, say how little data a suggestion rests
on, and stay deterministic. Specs: docs/EXECUTION_PLAN.md section 4.1, with the
formulas of docs/research/round2/03-routing-ml.md (sections 2-3),
08-online-learning.md (sections 3-5, 9, 11, 12) and 07-evaluation.md (4.4).

State lives in one JSON object, ``stats/ml.json``. ``fold`` is the only thing
that changes it, and is pure: it never reads the clock or a file, records are
applied in a canonical order (``at``, kind, id), and a record id already seen
is a no-op, so replaying the learning manifest reproduces the file byte for
byte. Writing the file is the job of ``learn apply`` (op ``ML_FOLD``); this
module only reads (``load``, ``config``).

Every tunable constant is in ``memory/ml_config.json`` (EXECUTION_PLAN rule 8).
Functions whose binding signature has no ``cfg`` take an optional ``cfg`` and
otherwise read that file once.

Record kinds folded (EXECUTION_PLAN 4.2; optional fields may be missing):
``outcome`` (id, session, at, task_class, family, tier, risk, model, effort,
model_id, has_check, passed, first_pass, rework, tokens, cost, minutes,
est_tokens, est_minutes, explored, propensity, gate, commit, gate_runs, words,
rule_tier), ``used`` (item, followed), ``review`` (found_a, found_b, both),
``correction`` (item and/or session; words, rule_tier and tier make it a
sizing label) and ``promotion`` (item), which lets a drift alarm name the
item promoted just before a shift. Other kinds are ignored.
"""
from __future__ import annotations

import datetime as dt
import functools
import hashlib
import json
import math
import random
import re
from pathlib import Path
from typing import Callable

from . import common as c
from . import items as items_mod

KIND_ORDER = {"promotion": 0, "used": 1, "correction": 2, "review": 3, "outcome": 4}
SKELETON = {
    "version": 1, "n": 0, "last_at": "", "seen": [],
    "bandit": {"g": {}, "f": {}, "c": {}, "raw_g": {}, "raw_c": {}, "ids": {}, "cost": {"g": {}, "f": {}, "c": {}}},
    "window": [], "log": [],
    "calib": {"c": {}, "f": {}, "g": {}},
    "drift": {}, "alarms": [], "promotions": [],
    "credit": {}, "baseline": {}, "pending": {}, "corrections": 0,
    "gates": {}, "reviews": [],
    "sizing": {"counts": {}, "tot": {}, "docs": {}, "vocab": {}, "strong": 0,
               "shadow": {"n": 0, "hint_right": 0, "rule_right": 0}},
}


# ---------------------------------------------------------------- loading
def empty_state() -> dict:
    return json.loads(json.dumps(SKELETON))


def load(brain_root: Path | str | None = None) -> dict:
    """The learning state from stats/ml.json; a missing or broken file is the
    empty state, so every caller falls back to the safe defaults."""
    raw = c.read_json(Path(brain_root or c.BRAIN_ROOT) / "stats" / "ml.json", None)
    return _ensure(raw if isinstance(raw, dict) else {})


def config(brain_root: Path | str | None = None) -> dict:
    """memory/ml_config.json with memory/models.json under ``models`` (the
    role defaults and prices the bandit needs). Raises ValueError when the
    config is missing, because silently inventing constants would hide it."""
    root = Path(brain_root or c.BRAIN_ROOT)
    cfg = c.read_json(root / "memory" / "ml_config.json", None)
    if not isinstance(cfg, dict) or "bandit" not in cfg:
        raise ValueError(f"mlearn: {root / 'memory' / 'ml_config.json'} is missing or invalid")
    cfg = dict(cfg)
    cfg.setdefault("models", c.read_json(root / "memory" / "models.json", {}) or {})
    return cfg


@functools.lru_cache(maxsize=1)
def _default_cfg() -> dict:
    return config()


def _cfg(cfg: dict | None) -> dict:
    return cfg if cfg is not None else _default_cfg()


def _ensure(state: dict) -> dict:
    """Fill keys missing from an older or partial state with the skeleton."""
    def fill(dst: dict, src: dict) -> None:
        for k, v in src.items():
            if k not in dst or type(dst[k]) is not type(v):
                dst[k] = json.loads(json.dumps(v))
            elif isinstance(v, dict) and v:
                fill(dst[k], v)
    out = json.loads(json.dumps(state))
    fill(out, SKELETON)
    return out


# ---------------------------------------------------------------- arms and prices
def _alias(model: str, cfg: dict) -> str:
    """Short model name ('sonnet') from an id or alias; an unknown future id
    like 'claude-sonnet-5-6' maps by its family word, so a version change keeps
    the arm and triggers the model-change shrink instead of a new arm."""
    m = str(model or "").strip().lower()
    table = cfg.get("models", {}).get("models", {})
    if m in table:
        return str(table[m].get("alias") or m)
    if any(v.get("alias") == m for v in table.values()):
        return m
    hit = re.match(r"claude-([a-z]+)-", m)
    return hit.group(1) if hit else m


def _arm(model: str, effort: str, cfg: dict) -> str:
    return f"{_alias(model, cfg)}/{str(effort).strip().lower()}"


def _split(arm: str) -> tuple[str, str]:
    model, effort = arm.split("/", 1)
    return model, effort


def baseline(cfg: dict, role: str) -> tuple[str, str]:
    """The role default from memory/models.json: the safe arm, always allowed."""
    roles = cfg.get("models", {}).get("roles", {})
    d = roles.get(role) or roles.get("lead") or {"model": "opus", "effort": "medium"}
    return _alias(d["model"], cfg), str(d["effort"])


def _blended(model: str, cfg: dict) -> float:
    """Dollars per million tokens of a typical task's mix (mostly input)."""
    mix = cfg["bandit"]["token_mix"]
    table = cfg.get("models", {}).get("models", {})
    alias = _alias(model, cfg)
    price = next((v for k, v in table.items() if alias in (k, v.get("alias"))), None)
    price = price or cfg.get("models", {}).get("fallback_price", {"in": 4.0, "out": 20.0})
    return float(price.get("in", 0)) * mix["in"] + float(price.get("out", 0)) * mix["out"]


def _unit_price(arm: tuple[str, str] | str, cfg: dict) -> float:
    model, effort = _split(arm) if isinstance(arm, str) else arm
    return _blended(model, cfg) * float(cfg["bandit"]["effort_cost"].get(effort, 1.0))


def safe_arms(cfg: dict, role: str, risk: str | None, tier: int | None, has_check: bool) -> list[tuple[str, str]]:
    """Invariant I-10: cheaper arms are allowed only when the task has a
    verifying check, its risk is trivial or standard, and its tier is at most
    2; otherwise the baseline alone. More expensive arms are never explored:
    escalation on a failed check already covers them."""
    base = baseline(cfg, role)
    ex = cfg["explore"]
    if not has_check or risk not in ex["safe_risks"] or not isinstance(tier, int) or tier > ex["max_tier"]:
        return [base]
    limit = _unit_price(base, cfg)
    cheaper = []
    for model, effort in cfg["bandit"]["arms"]:
        arm = (_alias(model, cfg), effort)
        if arm != base and arm not in cheaper and _unit_price(arm, cfg) < limit:
            cheaper.append(arm)
    return [base] + cheaper


def _why_baseline(cfg: dict, risk, tier, has_check) -> str:
    if not has_check:
        return "no verifying check"
    if risk not in cfg["explore"]["safe_risks"]:
        return f"risk {risk or 'unknown'}"
    if not isinstance(tier, int) or tier > cfg["explore"]["max_tier"]:
        return f"tier {tier}"
    return "no cheaper arm"


# ---------------------------------------------------------------- bandit
def _upd(cell: list, s: float, gamma: float, ncap: float) -> None:
    """Discounted Beta update of one (arm, level) cell [S, N] (round2/03 2.3)."""
    cell[0] = gamma * cell[0] + s
    cell[1] = gamma * cell[1] + 1.0
    if cell[1] > ncap:
        k = ncap / cell[1]
        cell[0] *= k
        cell[1] = ncap


def _scale(cell: list, n0: float) -> None:
    if cell[1] > n0:
        k = n0 / cell[1]
        cell[0] *= k
        cell[1] *= k


def _arm_cells(b: dict, arm: str) -> list[list]:
    cells = [b["g"][arm]] if arm in b["g"] else []
    for level in ("f", "c"):
        cells += [t[arm] for _, t in sorted(b[level].items()) if arm in t]
    if arm in b["raw_g"]:
        cells.append(b["raw_g"][arm])
    cells += [t[arm] for _, t in sorted(b["raw_c"].items()) if arm in t]
    return cells


def posterior(state: dict, cfg: dict, arm: str, task_class: str, family: str) -> tuple[float, float, float]:
    """(alpha, beta, family effective n) of the class posterior: global ->
    family -> class shrinkage with capped pseudo-counts K_G, K_F (round2/03 2.2).
    A new class therefore starts from its family, a new family from global."""
    b, bc = state["bandit"], cfg["bandit"]
    sg, ng = b["g"].get(arm, [0.0, 0.0])
    pg = (sg + 1.0) / (ng + 2.0)
    sf, nf = b["f"].get(family, {}).get(arm, [0.0, 0.0])
    pf = (sf + bc["K_G"] * pg) / (nf + bc["K_G"])
    sc, nc = b["c"].get(task_class, {}).get(arm, [0.0, 0.0])
    return sc + bc["K_F"] * pf, (nc - sc) + bc["K_F"] * (1.0 - pf), nf


def expected_cost(state: dict, cfg: dict, arm: str, task_class: str, family: str) -> float:
    """EW mean list-price cost of one attempt, most specific level first;
    unobserved arms start from price x effort x a typical task size."""
    cost = state["bandit"]["cost"]
    for v in (cost["c"].get(task_class, {}).get(arm), cost["f"].get(family, {}).get(arm), cost["g"].get(arm)):
        if isinstance(v, (int, float)):
            return float(v)
    return cfg["bandit"]["prior_tokens"] / 1e6 * _unit_price(arm, cfg)


def _beta_q(alpha: float, beta: float, z: float) -> float:
    """Normal-approximation lower quantile of a Beta: mean - z sd. Deterministic
    and cheap, which is why it is used instead of sampling 2000 draws."""
    n = alpha + beta
    m = alpha / n
    return m - z * math.sqrt(alpha * beta / (n * n * (n + 1.0)))


def _budget_ok(state: dict, cfg: dict) -> bool:
    """Exploration cap over the folded window: at most max_rate of eligible
    tasks explore (counting this one), and wasted spend under max_waste."""
    ex = cfg["explore"]
    win = state["window"][-ex["window"]:]
    elig = sum(1 for w in win if w[0])
    expl = sum(1 for w in win if w[0] and w[1])
    spend = sum(w[2] for w in win)
    waste = sum(w[3] for w in win)
    return expl + 1 <= ex["max_rate"] * (elig + 1) + 1e-9 and waste <= ex["max_waste"] * spend + 1e-12


def _exploit_ok(state, cfg, arm, base, task_class, family) -> bool:
    """A cheaper arm is exploited (not explored) once its 10th-percentile pass
    rate is within the margin of the baseline's mean, on enough family data."""
    ex = cfg["explore"]
    a, b_, nf = posterior(state, cfg, arm, task_class, family)
    ba, bb, _ = posterior(state, cfg, base, task_class, family)
    return nf >= ex["exploit_n"] and _beta_q(a, b_, ex["z10"]) >= ba / (ba + bb) - ex["exploit_margin"]


def suggest_arm(state: dict, cfg: dict, task_class: str, family: str, role: str, risk: str | None,
                tier: int | None, has_check: bool, rng: random.Random) -> dict:
    """{model, effort, explored, propensity, basis} for one task.

    Thompson step (EXECUTION_PLAN 4.1): draw a pass rate per safe arm from its
    hierarchical posterior; among arms within near_best of the best draw take
    the lowest expected cost per success. A cheaper arm that is not yet
    exploitable counts as exploration and falls back to the baseline when the
    exploration cap is reached. The first of propensity_draws seeded draws is
    the choice; the share of draws agreeing is its logged propensity (needed
    for offline IPS). Acts only when min_arms safe arms each have min_outcomes
    pooled outcomes; otherwise the baseline, and the basis says so."""
    state = _ensure(state or {})
    base = baseline(cfg, role)
    arms = safe_arms(cfg, role, risk, tier, has_check)

    def answer(arm: tuple[str, str], explored: bool, prop: float, basis: str) -> dict:
        return {"model": arm[0], "effort": arm[1], "explored": explored, "propensity": round(prop, 4), "basis": basis}

    if arms == [base]:
        return answer(base, False, 1.0, f"role default only ({_why_baseline(cfg, risk, tier, has_check)})")
    bc = cfg["bandit"]
    keys = [f"{m}/{e}" for m, e in arms]
    base_key = keys[0]
    raw = state["bandit"]["raw_g"]
    pooled = sum(raw.get(k, [0.0, 0.0])[1] for k in keys)
    ready = [k for k in keys if raw.get(k, [0.0, 0.0])[1] >= bc["min_outcomes"]]
    if len(ready) < bc["min_arms"]:
        return answer(base, False, 1.0,
                      f"role default: {len(ready)} of {len(keys)} safe arms have {bc['min_outcomes']}+ outcomes "
                      f"({pooled:g} pooled); learning needs {bc['min_arms']}")
    post = {k: posterior(state, cfg, k, task_class, family)[:2] for k in keys}
    cost = {k: expected_cost(state, cfg, k, task_class, family) for k in keys}
    exploit = {k: k == base_key or _exploit_ok(state, cfg, k, base_key, task_class, family) for k in keys}
    cap_ok = _budget_ok(state, cfg)
    counts: dict[str, int] = {}
    first = None
    for _ in range(bc["propensity_draws"]):
        draws = [(rng.betavariate(max(post[k][0], 1e-3), max(post[k][1], 1e-3)), k) for k in keys]
        top = max(d for d, _ in draws)
        near = [(cost[k] / max(d, 1e-6), k) for d, k in draws if d >= top - bc["near_best"]]
        pick = min(near)[1]
        if not exploit[pick] and not cap_ok:
            pick = base_key
        counts[pick] = counts.get(pick, 0) + 1
        first = first or pick
    prop = counts[first] / bc["propensity_draws"]
    explored = not exploit[first]
    basis = f"Thompson on {pooled:g} outcomes over {len(ready)} arms"
    if explored:
        basis += "; exploring a cheaper arm (check escalates to the default on failure)"
    elif not cap_ok:
        basis += "; exploration paused (cap reached)"
    return answer(_split(first), explored, prop, basis)


def arm_probabilities(state: dict, cfg: dict, task_class: str, family: str, role: str, risk, tier, has_check,
                      rng: random.Random, draws: int = 1000) -> dict[str, float]:
    """Choice probability of every arm, estimated by repeated suggestions;
    the values sum to 1 (used to check logged propensities)."""
    counts: dict[str, int] = {}
    for _ in range(draws):
        s = suggest_arm(state, cfg, task_class, family, role, risk, tier, has_check, rng)
        k = f"{s['model']}/{s['effort']}"
        counts[k] = counts.get(k, 0) + 1
    return {k: v / draws for k, v in sorted(counts.items())}


# ---------------------------------------------------------------- offline check
def ips(rows: list[dict], target: Callable[[dict], float], cfg: dict) -> dict:
    """Self-normalised inverse propensity estimate of a target policy's mean
    reward from logged rows {arm, reward, propensity} (round2/03 2.6). Weights
    are clipped; the effective sample size says how much the log really
    supports; trusted only at ESS >= min_ess and min_per_arm runs per arm."""
    off = cfg["offline"]
    sw = swr = sw2 = 0.0
    per_arm: dict[str, int] = {}
    for r in rows:
        prop = float(r.get("propensity") or 1.0)
        w = min(off["clip"], float(target(r)) / max(prop, 1e-9))
        sw += w
        sw2 += w * w
        swr += w * float(r.get("reward", 0.0))
        per_arm[r.get("arm", "?")] = per_arm.get(r.get("arm", "?"), 0) + 1
    ess = sw * sw / sw2 if sw2 > 0 else 0.0
    value = swr / sw if sw > 0 else None
    trusted = ess >= off["min_ess"] and bool(per_arm) and min(per_arm.values()) >= off["min_per_arm"]
    return {"value": value, "ess": round(ess, 3), "n": len(rows), "per_arm": per_arm, "trusted": trusted}


def offline_check(state: dict, cfg: dict) -> dict:
    """IPS value of the greedy policy (highest posterior mean among the arms
    logged in each class) against the logged mean reward."""
    state = _ensure(state)
    rows = [{"cls": r[1], "fam": r[2], "arm": r[3], "reward": r[4], "propensity": r[5]} for r in state["log"]]
    best: dict[str, str] = {}
    for cls in sorted({r["cls"] for r in rows}):
        arms = sorted({r["arm"] for r in rows if r["cls"] == cls})
        fam = next(r["fam"] for r in rows if r["cls"] == cls)
        means = [(lambda ab: ab[0] / (ab[0] + ab[1]))(posterior(state, cfg, a, cls, fam)) for a in arms]
        best[cls] = arms[max(range(len(arms)), key=lambda i: (means[i], -i))]
    out = ips(rows, lambda r: 1.0 if best.get(r["cls"]) == r["arm"] else 0.0, cfg)
    out["logged"] = sum(r["reward"] for r in rows) / len(rows) if rows else None
    return out


# ---------------------------------------------------------------- calibration
def _ew(cell: dict, r: float, cfg: dict) -> None:
    """EW mean and variance of log ratios, half-life in tasks (round2/08 4)."""
    alpha = 1.0 - 2.0 ** (-1.0 / cfg["calibration"]["half_life"])
    if cell["n"] == 0:
        cell["mu"], cell["var"] = r, 0.0
    else:
        d = r - cell["mu"]
        cell["mu"] += alpha * d
        cell["var"] = (1.0 - alpha) * (cell["var"] + alpha * d * d)
    cell["n"] += 1
    cell["r"] = (cell["r"] + [r])[-cfg["state"]["ratio_cap"]:]


def _conformal(rs: list[float], q: float) -> float:
    """Distribution-free quantile: the ceil((n+1)q)-th smallest (the largest
    when that index runs past the sample)."""
    xs = sorted(rs)
    k = math.ceil((len(xs) + 1) * q)
    return xs[min(k, len(xs)) - 1]


def calibrate(state: dict, task_class: str, family: str, est_tokens, est_minutes, cfg: dict | None = None) -> dict:
    """Calibrated p50/p80 of tokens and minutes for an estimate.

    The class level is used at n >= min_n, pooled toward its family with K
    pseudo-tasks; below that the family, then all tasks; below that the prior
    (p50 = estimate, p80 = prior factor). ``n`` is the count of the level used
    (0 = prior), ``level`` names it."""
    cfg = _cfg(cfg)
    state = _ensure(state or {})
    cal, cc = state["calib"], cfg["calibration"]
    out: dict = {"n": 0, "level": "prior"}
    for metric, est in (("tok", est_tokens), ("min", est_minutes)):
        name = "tokens" if metric == "tok" else "minutes"
        if not isinstance(est, (int, float)) or isinstance(est, bool) or est <= 0:
            out[f"{name}_p50"] = out[f"{name}_p80"] = None
            continue
        levels = [("class", cal["c"].get(task_class, {}).get(metric)), ("family", cal["f"].get(family, {}).get(metric)),
                  ("all", cal["g"].get("all", {}).get(metric))]
        levels = [(lv, cell) for lv, cell in levels if cell and cell["n"] > 0]
        use = next((i for i, (_, cell) in enumerate(levels) if cell["n"] >= cc["min_n"]), None)
        if use is None:
            p50, p80, n, level = 1.0, cc["prior_p80_factor"], 0, "prior"
        else:
            level, own = levels[use]
            parent = levels[use + 1][1] if use + 1 < len(levels) else None
            n = own["n"]
            mu, q80 = own["mu"], _conformal(own["r"], 0.8)
            if parent:
                k = cc["K"]
                mu = (n * mu + k * parent["mu"]) / (n + k)
                q80 = (n * q80 + k * _conformal(parent["r"], 0.8)) / (n + k)
            p50, p80 = math.exp(mu), math.exp(max(q80, mu))
        out[f"{name}_p50"] = round(est * p50, 3)
        out[f"{name}_p80"] = round(est * p80, 3)
        if metric == "tok" or out["level"] == "prior":
            out["n"], out["level"] = n, level
    return out


# ---------------------------------------------------------------- drift
def _new_chart() -> dict:
    return {"ref": [], "ref_fail": [], "mu0": 0.0, "sigma0": 1.0, "p0": 0.0, "ew": 0.0,
            "ph": [0, 0.0, 0.0, 0.0], "cu": 0.0, "k": 0, "sig": [], "open": False, "total": 0}


def _drift_step(st: dict, cfg: dict, cls: str, x: float | None, fail: int | None, at: str) -> None:
    """One observation into the class's three charts (round2/08 5, round2/07
    4.4): EWMA and Page-Hinkley on log tokens normalised by the class's
    reference median and MAD, one-sided CUSUM on first-pass failures. An alarm
    needs confirm_charts different charts within confirm_window observations
    (about 20 classes x 3 charts would otherwise false-alarm often)."""
    d = cfg["drift"]
    ch = st["drift"].setdefault(cls, _new_chart())
    ch["total"] += 1
    if len(ch["ref"]) < d["ref_n"]:
        if x is not None:
            ch["ref"].append(x)
            ch["ref_fail"].append(fail if fail is not None else 0)
        if len(ch["ref"]) == d["ref_n"]:
            xs = sorted(ch["ref"])
            med = xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2
            dev = sorted(abs(v - med) for v in xs)
            mad = dev[len(dev) // 2] if len(dev) % 2 else (dev[len(dev) // 2 - 1] + dev[len(dev) // 2]) / 2
            ch["mu0"], ch["sigma0"] = med, max(d["sigma_floor"], 1.4826 * mad)
            ch["p0"] = (sum(ch["ref_fail"]) + 1.0) / (len(ch["ref_fail"]) + 2.0)
            ch["open"] = False
        return
    ch["k"] += 1
    signals = []
    if x is not None:
        z = (x - ch["mu0"]) / ch["sigma0"]
        lam = d["ewma_lam"]
        ch["ew"] = lam * z + (1.0 - lam) * ch["ew"]
        if abs(ch["ew"]) > d["ewma_L"] * math.sqrt(lam / (2.0 - lam)):
            signals.append("ewma")
        ph = ch["ph"]  # [t, mean, m, M]
        ph[0] += 1
        ph[1] += (z - ph[1]) / ph[0]
        ph[2] += z - ph[1] - d["ph_delta"]
        ph[3] = min(ph[3], ph[2])
        if ph[2] - ph[3] > d["ph_lambda"]:
            signals.append("page-hinkley")
    if fail is not None:
        ch["cu"] = max(0.0, ch["cu"] + fail - (ch["p0"] + d["cusum_k"]))
        if ch["cu"] > d["cusum_h"]:
            signals.append("cusum")
    ch["sig"] = [s for s in ch["sig"] if s[0] > ch["k"] - d["confirm_window"]] + [[ch["k"], s] for s in signals]
    charts = sorted({s[1] for s in ch["sig"]})
    if len(charts) < d["confirm_charts"]:
        return
    direction = "down" if ch["ew"] < 0 and "cusum" not in charts else "up"
    promoted = [p for p in st["promotions"] if str(p[0]) <= at]
    st["alarms"] = (st["alarms"] + [{"cls": cls, "at": at, "n": ch["total"], "charts": charts, "dir": direction,
                                     "promoted": promoted[-1][1] if promoted else ""}])[-cfg["state"]["alarm_cap"]:]
    fresh = _new_chart()
    fresh.update(open=True, total=ch["total"])
    st["drift"][cls] = fresh
    # Consequences (never a revert): forget part of the bandit's class history
    # and keep only the most recent ratios for calibration.
    g = cfg["bandit"]["drift_gamma"]
    for cell in st["bandit"]["c"].get(cls, {}).values():
        cell[0] *= g
        cell[1] *= g
    cap = cfg["calibration"]["drift_cap"]
    for cell in st["calib"]["c"].get(cls, {}).values():
        cell["n"] = min(cell["n"], cap)
        cell["r"] = cell["r"][-cap:]


def alarms(state: dict, cfg: dict) -> list[str]:
    """At most three short boot lines: open drift alarms (the class's charts
    are rebuilding their reference), newest first, then gates to investigate."""
    state = _ensure(state or {})
    lines, shown = [], set()
    for a in reversed(state["alarms"]):
        if state["drift"].get(a["cls"], {}).get("open") and a["cls"] not in shown:
            shown.add(a["cls"])
            what = "tokens per task " + a["dir"] if a["charts"] != ["cusum"] else "first-pass failures up"
            line = f"drift: {what} in {a['cls']} at outcome {a['n']} ({'+'.join(a['charts'])})"
            if a.get("promoted"):
                line += f"; last promoted before it: {a['promoted']}"
            lines.append(line + "; check it, nothing was reverted")
    for key in sorted(state["gates"]):
        if flaky(state, key, cfg) >= cfg["flaky"]["investigate"]:
            lines.append(f"gate {key} looks flaky ({flaky(state, key, cfg):.2f}); investigate")
    return lines[:3]


# ---------------------------------------------------------------- credit
def item_score(state: dict, item: dict, cfg: dict | None = None) -> float:
    """Recall ranking multiplier in [low, high] from the lower bound (mean -
    z sd) of the item's Beta posterior: trust prior from engine/items.py plus
    fractional credit. Neutral 1.0 until min_n followed uses. Owner-stated
    items always get the top multiplier: learning never outranks them (I-08)."""
    cfg = _cfg(cfg)
    cr = cfg["credit"]
    if item.get("trust") == "owner-stated":
        return float(cr["high"])
    cell = _ensure(state or {})["credit"].get(str(item.get("id", "")))
    if not cell or cell[2] < cr["min_n"]:
        return 1.0
    a0, b0 = items_mod.PRIOR.get(item.get("trust", "derived"), (1, 1))
    a, b = a0 + 1.0 + cell[0], b0 + 1.0 + cell[1]
    lcb = _beta_q(a, b, cr["z"])
    return round(min(cr["high"], max(cr["low"], cr["base"] + cr["slope"] * lcb)), 4)


def _y(r: dict, cfg: dict) -> float | None:
    """Outcome score from the verifying check only (I-07): 1 first-pass green,
    0.5 green after one rework round, 0 otherwise; None without a check."""
    if not r.get("has_check") or not isinstance(r.get("passed"), bool):
        return None
    if not r["passed"]:
        return 0.0
    rework = r.get("rework") or 0
    rework = rework if isinstance(rework, (int, float)) and not isinstance(rework, bool) else 0
    if r.get("first_pass", True) is not False and rework == 0:
        return 1.0
    return float(cfg["bandit"]["score_rework_pass"]) if rework <= 1 else 0.0


def _pending(st: dict, session: str) -> dict:
    return st["pending"].setdefault(session, {"followed": [], "adv": [], "corrected": False})


def _settle_credit(st: dict, cfg: dict) -> None:
    """Credit sessions that have both followed items and scored outcomes:
    advantage over the class baseline, split equally (round2/08 3)."""
    for sess in list(st["pending"]):
        p = st["pending"][sess]
        if not (p["followed"] and p["adv"]):
            continue
        adv = sum((0.0 if p["corrected"] else y) - b for y, b in p["adv"]) / len(p["adv"])
        w = 1.0 / len(p["followed"])
        for item in p["followed"]:
            cell = st["credit"].setdefault(item, [0.0, 0.0, 0, 0])
            if adv > 0:
                cell[0] += w * adv
            else:
                cell[1] += w * -adv
            cell[2] += 1
        del st["pending"][sess]
    extra = len(st["pending"]) - cfg["state"]["pending_session_cap"]
    for sess in list(st["pending"])[:max(0, extra)]:
        del st["pending"][sess]


# ---------------------------------------------------------------- gates, forgetting, reviews
def flaky(state: dict, gate_key: str, cfg: dict | None = None) -> float:
    """Beta mean that a red run of this gate turns green on an unchanged
    commit. At or above flaky.rerun: re-run once before calling it red."""
    cfg = _cfg(cfg)
    f, s = _ensure(state or {})["gates"].get(gate_key, {}).get("fs", [0, 0])
    fl = cfg["flaky"]
    return round((fl["prior_a"] + f) / (fl["prior_a"] + fl["prior_b"] + f + s), 4)


def _gate_event(st: dict, gate: str, commit, passed: bool) -> None:
    g = st["gates"].setdefault(gate, {"fs": [0, 0], "last": None})
    last = g["last"]
    if last is not None and not last[1]:
        if passed and commit is not None and last[0] == commit:
            g["fs"][0] += 1
        else:
            g["fs"][1] += 1
    g["last"] = [commit, bool(passed)]


def retention(item: dict, now, cfg: dict | None = None) -> float:
    """R = exp(-t/S): t days since the last followed use, S from the item type
    grown by each followed use (round2/08 11). Owner-stated and standing items
    never decay; importance 3 doubles S so rare-but-critical items survive."""
    cfg = _cfg(cfg)
    rc = cfg["retention"]
    if item.get("trust") == "owner-stated" or item.get("type") == "standing":
        return 1.0
    last = item.get("last_followed") or item.get("last_used") or item.get("created")
    try:
        ref = dt.datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        when = now if isinstance(now, dt.datetime) else dt.datetime.fromisoformat(str(now).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 1.0
    ref = ref if ref.tzinfo else ref.replace(tzinfo=dt.timezone.utc)
    when = when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)
    t = max(0.0, (when - ref).total_seconds() / 86400.0)
    stab = item.get("stability")
    if not isinstance(stab, (int, float)) or stab <= 0:
        uses = item.get("followed", item.get("uses", 0))
        uses = uses if isinstance(uses, int) and uses > 0 else 0
        stab = min(rc["cap_days"], rc["s0_days"].get(item.get("type"), rc["s0_default"]) * (1.0 + rc["growth"]) ** uses)
    if item.get("importance") == 3:
        stab *= rc["important_factor"]
    return round(math.exp(-t / stab), 6)


def review_stop(found_a: int, found_b: int, both: int, rounds: int = 2, cfg: dict | None = None) -> dict:
    """Chapman capture-recapture after two independent review passes.

    N = (n1+1)(n2+1)/(m+1) - 1; remaining = N - |A u B|. Reviewers from one
    model family are correlated, so this underestimates: a lower bound. With
    overlap below min_overlap the estimate is unreliable and small overlap
    means many unseen defects, so another round is run; never past max_rounds."""
    cfg = _cfg(cfg)
    rv = cfg["review"]
    n1, n2, m = int(found_a), int(found_b), int(both)
    if min(n1, n2, m) < 0 or m > min(n1, n2):
        raise ValueError("review_stop: need 0 <= both <= min(found_a, found_b)")
    remaining = (n1 + 1) * (n2 + 1) / (m + 1) - 1 - (n1 + n2 - m)
    if rounds >= rv["max_rounds"]:
        another = False
    elif n1 + n2 == 0:
        another = False
    elif m < rv["min_overlap"]:
        another = True
    else:
        another = remaining >= rv["min_remaining"]
    return {"estimated_remaining": round(remaining, 3), "another_round": another}


# ---------------------------------------------------------------- sizing (shadow)
def _nb_posterior(st: dict, cfg: dict, words: list[str], rule_tier: int) -> dict[int, float]:
    """Multinomial Naive Bayes with the rule tier as a strong prior and the
    likelihood damped by 1/sqrt(words), so long texts cannot outvote the rules."""
    sz, nb = cfg["sizing"], st["sizing"]
    tiers = sz["tiers"]
    v = max(1, len(nb["vocab"]))
    words = [str(w) for w in words or []]
    damp = 1.0 / math.sqrt(len(words)) if words else 0.0
    rest = (1.0 - sz["rule_prior"]) / max(1, len(tiers) - 1)
    logs = {}
    for t in tiers:
        counts, tot = nb["counts"].get(str(t), {}), nb["tot"].get(str(t), 0.0)
        ll = sum(math.log((counts.get(w, 0.0) + sz["alpha"]) / (tot + sz["alpha"] * v)) for w in words)
        logs[t] = math.log(sz["rule_prior"] if t == rule_tier else rest) + damp * ll
    top = max(logs.values())
    z = sum(math.exp(l - top) for l in logs.values())
    return {t: math.exp(l - top) / z for t, l in logs.items()}


def _nb_hint(st: dict, cfg: dict, words: list[str], rule_tier: int) -> tuple[int, float]:
    post = _nb_posterior(st, cfg, words, rule_tier)
    best = max(post, key=lambda t: (post[t], t == rule_tier, -t))
    if best == rule_tier or post[best] < cfg["sizing"]["min_conf"] or abs(best - rule_tier) != 1:
        return rule_tier, post.get(rule_tier, 0.0)
    if rule_tier == 0 and best > 0:  # I-11: a question is never sized up by learning
        return 0, post.get(0, 0.0)
    return best, post[best]


def sizing_hint(state: dict, cfg: dict, hashed_words: list[str], rule_tier: int) -> dict:
    """{tier, confidence, acted, reason}. Shadow by default: the hint is only
    reported. It needs min_strong strong labels; it acts only when
    cfg.sizing.act is true and it lowers the tier, since a raise could size a
    small edit as a project (I-11); a tier-0 result is never raised at all."""
    state = _ensure(state or {})
    sz = cfg["sizing"]
    strong = state["sizing"]["strong"]
    if strong < sz["min_strong"]:
        return {"tier": rule_tier, "confidence": 0.0, "acted": False,
                "reason": f"shadow: {strong} of {sz['min_strong']} strong labels"}
    tier, conf = _nb_hint(state, cfg, hashed_words, rule_tier)
    acted = bool(sz["act"]) and tier < rule_tier
    reason = "rules agree" if tier == rule_tier else ("acted: lowered" if acted else "hint only")
    return {"tier": tier, "confidence": round(conf, 4), "acted": acted, "reason": reason}


def _sizing_learn(st: dict, cfg: dict, r: dict, strong: bool) -> None:
    words, rule, label = r.get("words"), r.get("rule_tier"), r.get("tier")
    tiers = cfg["sizing"]["tiers"]
    if not isinstance(words, list) or rule not in tiers or label not in tiers:
        return
    nb = st["sizing"]
    if strong:  # prequential: score the hint before learning from this label
        hint, _ = _nb_hint(st, cfg, words, rule)
        nb["shadow"]["n"] += 1
        nb["shadow"]["hint_right"] += int(hint == label)
        nb["shadow"]["rule_right"] += int(rule == label)
        nb["strong"] += 1
    w = 1.0 if strong else cfg["sizing"]["weak_weight"]
    counts = nb["counts"].setdefault(str(label), {})
    for word in (str(x) for x in words):
        if word not in nb["vocab"]:
            if len(nb["vocab"]) >= cfg["sizing"]["max_vocab"]:
                continue
            nb["vocab"][word] = 1
        counts[word] = counts.get(word, 0.0) + w
        nb["tot"][str(label)] = nb["tot"].get(str(label), 0.0) + w
    nb["docs"][str(label)] = nb["docs"].get(str(label), 0.0) + w


# ---------------------------------------------------------------- fold
def _rid(r: dict) -> str:
    rid = r.get("id")
    if rid:
        return str(rid)
    return "h-" + hashlib.sha256(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None


def _fold_outcome(st: dict, cfg: dict, rid: str, r: dict) -> None:
    bc, ex = cfg["bandit"], cfg["explore"]
    cls, fam = str(r.get("task_class") or "unknown"), str(r.get("family") or "unknown")
    at = str(r.get("at", ""))
    arm = _arm(r["model"], r["effort"], cfg) if r.get("model") and r.get("effort") else None
    tokens = _num(r.get("tokens"))
    cost = _num(r.get("cost"))
    if cost is None and tokens is not None and arm:
        cost = tokens / 1e6 * _blended(_split(arm)[0], cfg)
    y = _y(r, cfg)
    b = st["bandit"]
    if arm and y is not None:
        model_id = str(r.get("model_id") or (r["model"] if _alias(r["model"], cfg) != str(r["model"]).lower() else ""))
        if model_id:
            if b["ids"].get(arm) not in (None, model_id):
                for cell in _arm_cells(b, arm):
                    _scale(cell, bc["model_change_n"])
            b["ids"][arm] = model_id
        _upd(b["g"].setdefault(arm, [0.0, 0.0]), y, bc["gamma"], bc["n_cap"])
        _upd(b["f"].setdefault(fam, {}).setdefault(arm, [0.0, 0.0]), y, bc["gamma"], bc["n_cap"])
        _upd(b["c"].setdefault(cls, {}).setdefault(arm, [0.0, 0.0]), y, bc["gamma"], bc["n_cap"])
        for raw in (b["raw_g"].setdefault(arm, [0.0, 0.0]), b["raw_c"].setdefault(cls, {}).setdefault(arm, [0.0, 0.0])):
            raw[0] += y
            raw[1] += 1.0
        prop = _num(r.get("propensity"))
        st["log"] = (st["log"] + [[rid, cls, fam, arm, y, prop if prop and prop > 0 else 1.0]])[-cfg["state"]["outcome_log_cap"]:]
    if arm and cost is not None:
        keep = bc["cost_decay"]
        for table in (b["cost"]["g"], b["cost"]["f"].setdefault(fam, {}), b["cost"]["c"].setdefault(cls, {})):
            table[arm] = cost if arm not in table else keep * table[arm] + (1.0 - keep) * cost
    if cost is not None:
        eligible = bool(r.get("has_check")) and r.get("risk") in ex["safe_risks"] and isinstance(r.get("tier"), int) \
            and r["tier"] <= ex["max_tier"]
        explored = bool(r.get("explored"))
        st["window"] = (st["window"] + [[int(eligible), int(explored), cost,
                                         cost if explored and r.get("passed") is not True else 0.0]])[-ex["window"]:]
    for metric, act, est in (("tok", tokens, _num(r.get("est_tokens"))), ("min", _num(r.get("minutes")), _num(r.get("est_minutes")))):
        if act and est:
            lr = math.log(act / est)
            for level, key in (("c", cls), ("f", fam), ("g", "all")):
                _ew(st["calib"][level].setdefault(key, {}).setdefault(metric, {"mu": 0.0, "var": 0.0, "n": 0, "r": []}), lr, cfg)
    fail = None if y is None or "first_pass" not in r else int(r.get("first_pass") is not True)
    if tokens or fail is not None:
        _drift_step(st, cfg, cls, math.log(tokens) if tokens else None, fail, at)
    if y is not None:
        base = st["baseline"].get(cls, cfg["credit"]["baseline_prior"])
        _pending(st, str(r.get("session") or "_"))["adv"].append([y, base])
        st["baseline"][cls] = base + cfg["credit"]["baseline_alpha"] * (y - base)
    runs = r.get("gate_runs")
    if isinstance(runs, list):
        for g in runs:
            if isinstance(g, dict) and g.get("gate") and ("exit" in g or "passed" in g):
                _gate_event(st, str(g["gate"]), g.get("commit"), g.get("exit") == 0 if "exit" in g else bool(g["passed"]))
    elif r.get("gate") and isinstance(r.get("passed"), bool):
        _gate_event(st, str(r["gate"]), r.get("commit"), r["passed"])
    _sizing_learn(st, cfg, r, strong=bool(r.get("escalated")))


def _fold_one(st: dict, cfg: dict, rid: str, r: dict) -> None:
    kind = r.get("kind")
    if kind == "outcome":
        _fold_outcome(st, cfg, rid, r)
    elif kind == "used":
        item = str(r.get("item") or "")
        if not item:
            return
        if r.get("followed"):
            p = _pending(st, str(r.get("session") or "_"))
            if item not in p["followed"]:
                p["followed"].append(item)
        else:
            st["credit"].setdefault(item, [0.0, 0.0, 0, 0])[3] += 1
        # A 'helped' field is ignored on purpose: credit comes only from
        # check results and owner corrections, never from a self-report (I-07).
    elif kind == "correction":
        st["corrections"] += 1
        if r.get("item"):
            cell = st["credit"].setdefault(str(r["item"]), [0.0, 0.0, 0, 0])
            cell[1] += cfg["credit"]["correction_weight"]
            cell[2] += 1
        if r.get("session"):
            _pending(st, str(r["session"]))["corrected"] = True
        _sizing_learn(st, cfg, r, strong=True)
    elif kind == "review":
        vals = [r.get("found_a"), r.get("found_b"), r.get("both")]
        if all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in vals) and vals[2] <= min(vals[:2]):
            st["reviews"] = (st["reviews"] + [vals])[-cfg["state"]["review_cap"]:]
    elif kind == "promotion" and r.get("item"):
        st["promotions"] = (st["promotions"] + [[str(r.get("at", "")), str(r["item"])]])[-cfg["state"]["promotion_cap"]:]


def _round(obj, digits: int):
    if isinstance(obj, float):
        v = round(obj, digits)
        return 0.0 if v == 0 else v
    if isinstance(obj, list):
        return [_round(v, digits) for v in obj]
    if isinstance(obj, dict):
        return {k: _round(v, digits) for k, v in obj.items()}
    return obj


def fold(state: dict, records: list[dict], cfg: dict) -> dict:
    """Apply new records to the state; returns a new state, the input is not
    changed. Deterministic: no clock, records applied in (at, kind, id) order,
    floats rounded; idempotent per record id through a bounded seen-id list."""
    st = _ensure(state or {})
    seen = set(st["seen"])
    todo: dict[str, dict] = {}
    for r in records or []:
        if not isinstance(r, dict) or r.get("kind") not in KIND_ORDER:
            continue
        rid = _rid(r)
        if rid not in seen and rid not in todo:
            todo[rid] = r
    for rid, r in sorted(todo.items(), key=lambda kv: (str(kv[1].get("at", "")), KIND_ORDER[kv[1]["kind"]], kv[0])):
        _fold_one(st, cfg, rid, r)
        st["seen"].append(rid)
        st["n"] += 1
        st["last_at"] = max(st["last_at"], str(r.get("at", "")))
    _settle_credit(st, cfg)
    st["seen"] = st["seen"][-cfg["state"]["seen_cap"]:]
    return _round(st, cfg["state"]["round_digits"])


# ---------------------------------------------------------------- report
def _label(n: float, cfg: dict, ess: float) -> str:
    rp = cfg["report"]
    if n < rp["too_early"]:
        return "too early, using the safe default"
    if n < rp["medium"]:
        return "LOW"
    if n < rp["high"] or ess < cfg["offline"]["min_ess"]:
        return "MEDIUM"
    return "HIGH"


def report(state: dict, cfg: dict) -> list[str]:
    """Owner wording, at most report.max_lines lines, with n for every claim."""
    st = _ensure(state or {})
    rp = cfg["report"]
    outcomes = sum(v[1] for v in st["bandit"]["raw_g"].values())
    if st["n"] == 0:
        return ["Nothing learned yet: every choice uses the safe defaults (n=0 records)."]
    lines = [f"Learned from {st['n']} records ({outcomes:g} checked task outcomes), latest {st['last_at'][:10] or 'undated'}."]
    off = offline_check(st, cfg)
    classes = sorted(st["bandit"]["raw_c"].items(), key=lambda kv: (-sum(v[1] for v in kv[1].values()), kv[0]))
    for cls, arms in classes[:3]:
        arm, (p, n) = sorted(arms.items(), key=lambda kv: (-kv[1][1], kv[0]))[0]
        fam = next((f for f, t in sorted(st["bandit"]["f"].items()) if arm in t), "unknown")
        a, b, _ = posterior(st, cfg, arm, cls, fam)
        lines.append(f"{cls}: {arm} passed its checks {p:g} of {n:g} times; 90% sure it succeeds at least "
                     f"{max(0.0, _beta_q(a, b, cfg['explore']['z10'])):.0%} of the time; confidence {_label(n, cfg, off['ess'])}.")
    win = st["window"]
    if win:
        elig = sum(w[0] for w in win)
        expl = sum(1 for w in win if w[0] and w[1])
        spend = sum(w[2] for w in win)
        waste = sum(w[3] for w in win) / spend if spend else 0.0
        lines.append(f"Cheaper models were tried on {expl} of {elig} eligible tasks (last {len(win)} tasks); "
                     f"wasted spend {waste:.0%} (cap {cfg['explore']['max_waste']:.0%}).")
    cal = [(cell["tok"]["n"], cls, cell["tok"]) for cls, cell in sorted(st["calib"]["c"].items()) if "tok" in cell]
    if cal:
        n, cls, cell = max(cal, key=lambda t: (t[0], t[1]))
        if n >= cfg["calibration"]["min_n"]:
            lines.append(f"Estimates: {cls} tasks took {math.exp(cell['mu']):.2f}x the estimated tokens (typical, n={n}).")
        else:
            lines.append(f"Estimates: not calibrated yet (largest class n={n}; needs {cfg['calibration']['min_n']}).")
    open_alarms = alarms(st, cfg)
    charted = sum(1 for ch in st["drift"].values() if len(ch["ref"]) >= cfg["drift"]["ref_n"] or ch["k"])
    lines += open_alarms or [f"Drift: no open alarm ({charted} classes charted; {len(st['alarms'])} alarms ever)."]
    if st["credit"]:
        ready = sum(1 for v in st["credit"].values() if v[2] >= cfg["credit"]["min_n"])
        uses = sum(v[2] for v in st["credit"].values())
        lines.append(f"Memory: {ready} of {len(st['credit'])} items have enough followed uses to move their ranking "
                     f"({uses} credited uses, {st['corrections']} owner corrections).")
    if st["gates"]:
        fl = [k for k in sorted(st["gates"]) if flaky(st, k, cfg) >= cfg["flaky"]["rerun"]]
        lines.append(f"Gates: {len(fl)} of {len(st['gates'])} look flaky (re-run once before calling them red)"
                     + (f": {', '.join(fl[:3])}." if fl else "."))
    sh = st["sizing"]["shadow"]
    if sh["n"]:
        lines.append(f"Sizing learner (shadow, not acting): {st['sizing']['strong']} of {cfg['sizing']['min_strong']} "
                     f"strong labels; would have been right {sh['hint_right']} of {sh['n']} vs the rules {sh['rule_right']}.")
    if off["n"]:
        verdict = "trusted" if off["trusted"] else f"not trusted yet (needs ESS {cfg['offline']['min_ess']:g})"
        val = "n/a" if off["value"] is None else f"{off['value']:.2f}"
        lines.append(f"Offline check: greedy policy {val} vs logged {off['logged']:.2f} mean score, "
                     f"ESS {off['ess']:.1f} of {off['n']} runs; {verdict}.")
    if st["reviews"]:
        more = sum(1 for a, b, m in st["reviews"] if review_stop(a, b, m, cfg=cfg)["another_round"])
        lines.append(f"Reviews: {len(st['reviews'])} paired reviews; another round was indicated in {more}.")
    return lines[:rp["max_lines"]]


# ---------------------------------------------------------------- cli
def _cmd(kind: str):
    def run(args) -> int:
        try:
            cfg = config()
        except ValueError as e:
            print(str(e))
            return 2
        st = load()
        lines = report(st, cfg) if kind == "report" else alarms(st, cfg)
        if getattr(args, "json", False):
            print(json.dumps({"lines": lines}, ensure_ascii=False))
        else:
            print("\n".join(lines) if lines else "no alarms")
        return 0
    return run


def register(sub) -> None:
    p = sub.add_parser("ml", help="what the statistical learners have learned, and drift alarms")
    s = p.add_subparsers(dest="ml_cmd")
    r = s.add_parser("report", help="owner-worded summary with the number of cases behind each claim")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=_cmd("report"))
    a = s.add_parser("alarms", help="open drift alarms and flaky gates (at most 3 lines)")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=_cmd("alarms"))
    p.set_defaults(func=_cmd("report"))
