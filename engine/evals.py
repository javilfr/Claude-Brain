"""Evaluation system: `brain eval ...` and `brain ablate` (ticket CB-083).

Why this exists: agent systems fool themselves. With about ten tasks only a
large effect can be proven (9 wins out of 10 discordant tasks), harness noise
alone moves results by several points, and model-graded results are biased
(docs/research/round2/07-evaluation.md). So every claim that a change of the
brain helped goes through scripted graders and the paired statistics below,
and anything short of proof means "not proven; keep the old version" (I-16).

Three tiers (memo section 2): 0 contract tests (`eval contract`, the unit
suite); 1 replay on recorded artefacts (the other test modules); 2 a live
paired benchmark over `evals/tasks/` whose trials are recorded with
`eval record` and judged with `eval compare` against a pre-registration.

Everything here is deterministic and standard library only (I-01, I-13): the
statistics are exact sums, the one resampling function takes a seed.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import random
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
from math import comb, lgamma, log
from pathlib import Path

from . import common as c

MIN_PAIRS = 8  # I-16: below this no claim is made in either direction.
FAMILIES = ("software", "data", "knowledge", "language", "operations", "routing")
METRICS = ("pass", "tokens", "minutes")
DEFAULT_DECISION = {"alpha": 0.05, "ship_prob": 0.95, "revert_prob": 0.80, "cost_guard": 1.10}
CHECK_TYPES = ("file_exists", "min_words", "max_words", "contains_all", "contains_none",
               "regex", "json_valid", "json_equals", "links_resolve")
GRADER_TIMEOUT = 120
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class EvalError(ValueError):
    """An expected input problem; its message is the one line the user sees."""


# ================================================================ statistics
def sign_test(wins: int, losses: int) -> float:
    """Exact one-sided p-value P(X >= wins), X ~ Binomial(wins + losses, 1/2).

    Ties are dropped by the caller: a tied task says nothing about which arm
    is better, and counting it would inflate n."""
    m = wins + losses
    if m <= 0:
        return 1.0
    return sum(comb(m, j) for j in range(wins, m + 1)) / 2 ** m


def _log_beta(a: float, b: float) -> float:
    return lgamma(a) + lgamma(b) - lgamma(a + b)


def beta_binomial_prob_b_better(pass_a: int, n_a: int, pass_b: int, n_b: int) -> float:
    """Exact P(rate_b > rate_a) with independent Beta(1, 1) priors.

    For unpaired pass rates (two arms, or routing accuracy before and after).
    Closed form for an integer first shape parameter (E. Miller's sum), so no
    sampling noise: sum_{i < aB} B(aA+i, bA+bB) / ((bB+i) B(1+i, bB) B(aA, bA))."""
    if not (0 <= pass_a <= n_a and 0 <= pass_b <= n_b):
        raise EvalError("passes must lie between 0 and the number of trials")
    a_a, b_a = 1 + pass_a, 1 + n_a - pass_a
    a_b, b_b = 1 + pass_b, 1 + n_b - pass_b
    total = 0.0
    for i in range(a_b):
        total += math.exp(_log_beta(a_a + i, b_a + b_b) - log(b_b + i)
                          - _log_beta(1 + i, b_b) - _log_beta(a_a, b_a))
    return min(1.0, max(0.0, total))


def prob_win_share_above_half(wins: int, losses: int) -> float:
    """Paired posterior P(theta > 1/2), theta = P(B wins | the task differs),
    prior Beta(1, 1). Exact via I_x(a, b) = P(Bin(a+b-1, x) >= a), which gives
    P(theta > 1/2) = P(Bin(wins + losses + 1, 1/2) <= wins) (memo section 4.2)."""
    n = wins + losses + 1
    return sum(comb(n, j) for j in range(0, wins + 1)) / 2 ** n


def sprt(outcomes, p0: float = 0.5, p1: float = 0.75, alpha: float = 0.05, beta: float = 0.20) -> dict:
    """Wald sequential test on discordant tasks, in their pre-set order.

    Answers "do I need to run more tasks", not "ship": the verdict still comes
    from ``verdict``. An outcome > 0 (or True) is a win for B, anything else a
    loss; ties must be left out by the caller."""
    upper, lower = log((1 - beta) / alpha), log(beta / (1 - alpha))
    step_win, step_loss = log(p1 / p0), log((1 - p1) / (1 - p0))
    llr, used = 0.0, 0
    for o in outcomes:
        used += 1
        llr += step_win if (o is True or (not isinstance(o, bool) and o > 0)) else step_loss
        if llr >= upper:
            return {"decision": "accept-better", "llr": llr, "used": used, "upper": upper, "lower": lower}
        if llr <= lower:
            return {"decision": "accept-not-better", "llr": llr, "used": used, "upper": upper, "lower": lower}
    return {"decision": "continue", "llr": llr, "used": used, "upper": upper, "lower": lower}


def bootstrap_ci(values, seed: int, n: int = 2000, level: float = 0.95) -> tuple[float, float]:
    """Percentile bootstrap interval of the mean (seeded, so reruns agree).

    Indicative only for small samples: below about 10 values the interval is
    too narrow, which is why decisions use the sign test instead."""
    vals = [float(v) for v in values]
    if not vals:
        raise EvalError("bootstrap needs at least one value")
    rng = random.Random(seed)
    k = len(vals)
    means = sorted(sum(rng.choices(vals, k=k)) / k for _ in range(n))
    tail = (1 - level) / 2
    lo_i = max(0, int(math.floor(tail * n)))
    hi_i = min(n - 1, int(math.ceil((1 - tail) * n)) - 1)
    return means[lo_i], means[hi_i]


def _decision_cfg(prereg: dict | None) -> dict:
    cfg = dict(DEFAULT_DECISION)
    cfg.update((prereg or {}).get("decision") or {})
    return cfg


def verdict(pairs: list[dict], prereg: dict | None = None) -> dict:
    """Pre-registered decision over paired tasks: ship, revert or not-proven.

    ``pairs``: one dict per task with ``pass_a``/``pass_b`` (pass fraction over
    trials) and optional ``tokens_a/b``, ``minutes_a/b`` (medians). The rule:
    under max(8, min_pairs) pairs always not-proven (I-16); revert when the
    posterior that B is worse reaches ``revert_prob`` (harm is cheaper to act
    on than benefit is to prove); ship only when the exact sign test p <=
    ``alpha`` and P(better) >= ``ship_prob`` and the guard holds (pass metric:
    median tokens of B within ``cost_guard`` x A; cost metrics: B passes no
    fewer tasks than A); otherwise not-proven."""
    pre = prereg or {}
    cfg = _decision_cfg(pre)
    metric = pre.get("metric", "pass")
    sign = 1 if pre.get("direction", "down" if metric != "pass" else "up") == "up" else -1
    need = max(MIN_PAIRS, int(pre.get("min_pairs", MIN_PAIRS)))
    wins = losses = 0
    for p in pairs:
        va, vb = p.get(f"{metric}_a"), p.get(f"{metric}_b")
        if va is None or vb is None:
            continue
        d = (vb - va) * sign
        wins += d > 0
        losses += d < 0
    n = len(pairs)
    ties = n - wins - losses
    p_val = sign_test(wins, losses)
    prob = prob_win_share_above_half(wins, losses)
    tok_a = [p["tokens_a"] for p in pairs if p.get("tokens_a")]
    tok_b = [p["tokens_b"] for p in pairs if p.get("tokens_b")]
    token_change = None
    if tok_a and tok_b and len(tok_a) == len(tok_b) == n:
        token_change = statistics.median(tok_b) / statistics.median(tok_a) - 1
    if metric == "pass":
        if token_change is None:
            guard_ok, guard = True, "tokens not recorded, cost guard not checked"
        else:
            guard_ok = token_change + 1 <= cfg["cost_guard"]
            guard = f"median tokens B/A {token_change + 1:.2f} (limit {cfg['cost_guard']:.2f})"
    else:
        pa, pb = sum(p.get("pass_a", 0) for p in pairs), sum(p.get("pass_b", 0) for p in pairs)
        guard_ok, guard = pb >= pa, f"B passes {pb:g} vs A {pa:g} (B must not pass fewer)"
    out = {"decision": "not-proven", "n": n, "discordant": wins + losses, "wins": wins,
           "losses": losses, "ties": ties, "p": p_val, "prob_better": prob,
           "token_change": token_change, "metric": metric, "min_pairs": need,
           "change": pre.get("change")}
    if n < need:
        out["reason"] = f"{n} paired tasks; at least {need} are needed for any claim"
        return out
    if wins + losses == 0:
        out["reason"] = "every task tied; the tasks do not discriminate, replace them"
        return out
    saturated = "; over half the tasks tied, the set is saturated" if ties * 2 > n else ""
    if 1 - prob >= cfg["revert_prob"]:
        out["decision"] = "revert"
        out["reason"] = f"P(B worse) {1 - prob:.2f} >= {cfg['revert_prob']:.2f}{saturated}"
    elif p_val <= cfg["alpha"] and prob >= cfg["ship_prob"] and guard_ok:
        out["decision"] = "ship"
        out["reason"] = f"sign test p {p_val:.3f} <= {cfg['alpha']}; {guard}{saturated}"
    else:
        why = []
        if p_val > cfg["alpha"]:
            why.append(f"sign test p {p_val:.3f} > {cfg['alpha']}")
        if prob < cfg["ship_prob"]:
            why.append(f"P(better) {prob:.2f} < {cfg['ship_prob']:.2f}")
        if not guard_ok:
            why.append(f"guard failed: {guard}")
        out["reason"] = "; ".join(why) + saturated
    return out


def owner_lines(v: dict) -> list[str]:
    """Two plain lines for the owner, always with n and never a p-value (memo
    section 6): what happened, then what is done about it."""
    n = v["n"]
    tok = ""
    if v.get("token_change") is not None:
        tok = f"; it used {abs(v['token_change']) * 100:.0f}% {'more' if v['token_change'] > 0 else 'fewer'} tokens"
    head = f"Change: {v['change']}. " if v.get("change") else ""
    first = (f"{head}On {v['wins']} of {n} test tasks the new version did better, "
             f"on {v['losses']} worse and on {v['ties']} the same{tok}.")
    if v["decision"] == "ship":
        second = f"Verdict: adopted. With only {n} tasks a small gain can still be luck, so it is re-checked later on new tasks."
    elif v["decision"] == "revert":
        second = f"Verdict: not adopted; over {n} tasks it did worse, so the old version stays."
    elif n < v.get("min_pairs", MIN_PAIRS):
        second = f"Verdict: not proven yet; {n} tasks are too few to tell (the minimum is {v.get('min_pairs', MIN_PAIRS)}), so the old version stays."
    else:
        second = f"Verdict: not proven yet; over {n} tasks the difference could be luck, so the old version stays."
    return [first, second]


# ================================================================ formats
def _files(value, field: str, where: str) -> list[dict]:
    if not isinstance(value, list):
        raise EvalError(f"{where}: '{field}' must be a list of {{path, content}}")
    for f in value:
        if not isinstance(f, dict) or not isinstance(f.get("path"), str) or not isinstance(f.get("content"), str):
            raise EvalError(f"{where}: every '{field}' entry needs a string path and content")
        p = Path(f["path"])
        if p.is_absolute() or ".." in p.parts or not f["path"].strip():
            raise EvalError(f"{where}: '{field}' path {f['path']!r} must be relative and stay inside the task")
    return value


def _check_spec(chk, where: str) -> None:
    if not isinstance(chk, dict) or chk.get("type") not in CHECK_TYPES:
        raise EvalError(f"{where}: check type must be one of {', '.join(CHECK_TYPES)}")
    t = chk["type"]
    if not isinstance(chk.get("path"), str):
        raise EvalError(f"{where}: check {t} needs a path")
    if t in ("min_words", "max_words") and not isinstance(chk.get("n"), int):
        raise EvalError(f"{where}: check {t} needs an integer n")
    if t in ("contains_all", "contains_none") and not (isinstance(chk.get("items"), list) and chk["items"]):
        raise EvalError(f"{where}: check {t} needs a non-empty items list")
    if t == "regex":
        try:
            re.compile(chk.get("pattern", ""))
        except (re.error, TypeError):
            raise EvalError(f"{where}: check regex has an invalid pattern") from None
        if not chk.get("pattern"):
            raise EvalError(f"{where}: check regex needs a pattern")
    if t == "json_equals" and not (isinstance(chk.get("fields"), dict) and chk["fields"]):
        raise EvalError(f"{where}: check json_equals needs a fields object")


def validate_task(task, where: str = "task") -> dict:
    """Raise EvalError with one line naming the first problem in a task file."""
    if not isinstance(task, dict):
        raise EvalError(f"{where}: not a JSON object")
    for key in ("id", "title", "family", "task_class", "prompt"):
        if not isinstance(task.get(key), str) or not task[key].strip():
            raise EvalError(f"{where}: missing text field '{key}'")
    if not _SAFE_ID.match(task["id"]):
        raise EvalError(f"{where}: id {task['id']!r} must be lower-case letters, digits, '.', '_' or '-'")
    if task["family"] not in FAMILIES:
        raise EvalError(f"{where}: family must be one of {', '.join(FAMILIES)}")
    if task.get("tier") not in (0, 1, 2, 3):
        raise EvalError(f"{where}: tier must be the request size 0, 1, 2 or 3")
    if task.get("split") not in ("dev", "heldout"):
        raise EvalError(f"{where}: split must be dev or heldout")
    for field in ("setup", "reference", "null"):
        _files(task.get(field), field, where)
    g = task.get("grader")
    if not isinstance(g, dict) or g.get("type") not in ("command", "checks"):
        raise EvalError(f"{where}: grader.type must be command or checks")
    if g["type"] == "command":
        if not isinstance(g.get("command"), str) or not g["command"].strip():
            raise EvalError(f"{where}: grader.command must be a command line")
        _files(g.get("files", []), "grader.files", where)
    else:
        if not isinstance(g.get("checks"), list) or not g["checks"]:
            raise EvalError(f"{where}: grader.checks must be a non-empty list")
        for chk in g["checks"]:
            _check_spec(chk, where)
    return task


def load_task(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise EvalError(f"{Path(path).name}: unreadable task file ({type(e).__name__})") from None
    task = validate_task(data, Path(path).name)
    if Path(path).stem != task["id"]:
        raise EvalError(f"{Path(path).name}: file name must be <id>.json (id is {task['id']})")
    return task


def load_tasks(tasks_dir: Path) -> dict[str, dict]:
    """All tasks by id; the first invalid file raises EvalError."""
    return {t["id"]: t for t in (load_task(p) for p in sorted(Path(tasks_dir).glob("*.json")))}


def validate_run_row(row, line_no: int) -> dict:
    where = f"line {line_no}"
    if not isinstance(row, dict):
        raise EvalError(f"{where}: not a JSON object")
    for key in ("task", "arm"):
        if not isinstance(row.get(key), str) or not row[key]:
            raise EvalError(f"{where}: missing '{key}'")
    if not isinstance(row.get("trial"), int) or row["trial"] < 1:
        raise EvalError(f"{where}: trial must be an integer from 1")
    if row.get("passed") not in (0, 1, True, False):
        raise EvalError(f"{where}: passed must be 0 or 1")
    for key in ("tokens", "minutes"):
        v = row.get(key)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0):
            raise EvalError(f"{where}: {key} must be a non-negative number")
    if not isinstance(row.get("infra_error", False), bool):
        raise EvalError(f"{where}: infra_error must be true or false")
    if row.get("at") is not None and _parse_time(row["at"]) is None:
        raise EvalError(f"{where}: 'at' is not an ISO date")
    return row


def load_run(path: Path) -> list[dict]:
    """Rows of a run file, validated; a malformed line is an error, not skipped,
    because a silently dropped trial would change the verdict."""
    p = Path(path)
    if not p.is_file():
        raise EvalError(f"run file not found: {p}")
    rows = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            raise EvalError(f"line {i}: not valid JSON") from None
        rows.append(validate_run_row(row, i))
    if not rows:
        raise EvalError(f"run file has no trials: {p}")
    return rows


def validate_prereg(pre, where: str = "prereg") -> dict:
    if not isinstance(pre, dict):
        raise EvalError(f"{where}: not a JSON object")
    for key in ("change", "hypothesis", "created"):
        if not isinstance(pre.get(key), str) or not pre[key].strip():
            raise EvalError(f"{where}: missing '{key}'")
    if _parse_time(pre["created"]) is None:
        raise EvalError(f"{where}: created is not an ISO date")
    if pre.get("metric") not in METRICS:
        raise EvalError(f"{where}: metric must be one of {', '.join(METRICS)}")
    if pre.get("direction") not in ("up", "down"):
        raise EvalError(f"{where}: direction must be up or down")
    if pre["metric"] == "pass" and pre["direction"] != "up":
        raise EvalError(f"{where}: a pass-rate metric can only improve upwards")
    tasks = pre.get("tasks")
    if not isinstance(tasks, list) or not tasks or not all(isinstance(t, str) for t in tasks):
        raise EvalError(f"{where}: tasks must be a non-empty list of task ids")
    if not isinstance(pre.get("min_pairs"), int) or pre["min_pairs"] < MIN_PAIRS:
        raise EvalError(f"{where}: min_pairs must be an integer of at least {MIN_PAIRS} (I-16)")
    dec = pre.get("decision")
    if not isinstance(dec, dict):
        raise EvalError(f"{where}: missing decision rule")
    for key, lo, hi in (("alpha", 0, 0.5), ("ship_prob", 0.5, 1), ("revert_prob", 0.5, 1), ("cost_guard", 1, 10)):
        v = dec.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo < v <= hi:
            raise EvalError(f"{where}: decision.{key} must be a number in ({lo}, {hi}]")
    return pre


def load_prereg(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise EvalError(f"{Path(path).name}: unreadable pre-registration ({type(e).__name__})") from None
    return validate_prereg(data, Path(path).name)


def _parse_time(value) -> _dt.datetime | None:
    try:
        d = _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


# ================================================================ graders
def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def run_check(chk: dict, root: Path) -> str | None:
    """None when the check passes, else a one-line reason. Scripted checks
    grade non-code work (writing, research, routing) without a model judge."""
    t, rel = chk["type"], chk["path"]
    target = root / rel
    if t == "file_exists":
        return None if target.is_file() else f"{rel} does not exist"
    text = _read(target)
    if text is None:
        return f"{rel} is missing or unreadable"
    fold = (lambda s: s.lower()) if chk.get("ignore_case", True) else (lambda s: s)
    if t in ("min_words", "max_words"):
        count = len(text.split())
        if t == "min_words" and count < chk["n"]:
            return f"{rel} has {count} words, fewer than {chk['n']}"
        if t == "max_words" and count > chk["n"]:
            return f"{rel} has {count} words, more than {chk['n']}"
        return None
    if t == "contains_all":
        missing = [s for s in chk["items"] if fold(s) not in fold(text)]
        return f"{rel} lacks: {', '.join(missing)}" if missing else None
    if t == "contains_none":
        found = [s for s in chk["items"] if fold(s) in fold(text)]
        return f"{rel} contains: {', '.join(found)}" if found else None
    if t == "regex":
        flags = re.IGNORECASE if chk.get("ignore_case", False) else 0
        hit = re.search(chk["pattern"], text, flags | re.MULTILINE) is not None
        want = chk.get("must_match", True)
        return None if hit == want else f"{rel} {'does not match' if want else 'matches'} /{chk['pattern']}/"
    if t in ("json_valid", "json_equals"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return f"{rel} is not valid JSON"
        if t == "json_valid":
            return None
        if not isinstance(data, dict):
            return f"{rel} is not a JSON object"
        wrong = [k for k, v in chk["fields"].items() if k not in data or data[k] != v or type(data[k]) is bool and type(v) is not bool]
        return f"{rel} has wrong or missing: {', '.join(wrong)}" if wrong else None
    # links_resolve: relative links only; web links are never fetched (no network).
    links = [m.group(1) for m in _LINK.finditer(text)]
    rel_links = [u.split("#")[0] for u in links if not re.match(r"^[a-z][a-z0-9+.-]*:", u, re.I) and not u.startswith("#")]
    if chk.get("min_links", 1) > len(rel_links):
        return f"{rel} has {len(rel_links)} relative links, fewer than {chk.get('min_links', 1)}"
    base = target.parent
    broken = [u for u in rel_links if not (base / u).resolve().exists()
              or not str((base / u).resolve()).startswith(str(root.resolve()))]
    return f"{rel} has broken links: {', '.join(broken[:3])}" if broken else None


def _write_files(root: Path, files: list[dict]) -> None:
    for f in files:
        c.write_text(root / f["path"], f["content"])


def grade(task: dict, produced: Path) -> tuple[bool, str | None]:
    """Grade a produced directory: (passed, first failing reason or None).

    A command grader runs on a temporary copy with ``grader.files`` written
    over it, so the graded work cannot edit its own tests (memo section 5.6)
    and grading never changes the directory it was given."""
    produced = Path(produced)
    if not produced.is_dir():
        return False, f"not a directory: {produced}"
    g = task["grader"]
    if g["type"] == "checks":
        for chk in g["checks"]:
            why = run_check(chk, produced)
            if why:
                return False, f"{chk['type']}: {why}"
        return True, None
    with tempfile.TemporaryDirectory(prefix="brain-grade-") as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(produced, work)
        _write_files(work, g.get("files", []))
        argv = [sys.executable if a == "{python}" else a for a in shlex.split(g["command"])]
        try:
            proc = subprocess.run(argv, cwd=work, capture_output=True, text=True, timeout=GRADER_TIMEOUT)
        except FileNotFoundError:
            return False, f"command not found: {argv[0]}"
        except subprocess.TimeoutExpired:
            return False, f"command timed out after {GRADER_TIMEOUT} s"
    if proc.returncode == 0:
        return True, None
    tail = [ln for ln in (proc.stdout + "\n" + proc.stderr).splitlines() if ln.strip()]
    return False, f"command exit {proc.returncode}: {c.clip(tail[-1] if tail else '', 140)}"


def audit_task(task: dict) -> str | None:
    """None when the grader passes the reference and fails the null solution.

    A grader that cannot tell them apart would produce verdicts about nothing
    (memo section 5.6: a broken grader once turned 42% into 95%)."""
    with tempfile.TemporaryDirectory(prefix="brain-audit-") as tmp:
        ref, null = Path(tmp) / "reference", Path(tmp) / "null"
        for d, sol in ((ref, task["reference"]), (null, task["null"])):
            d.mkdir()
            _write_files(d, task["setup"])
            _write_files(d, sol)
        ok_ref, why_ref = grade(task, ref)
        ok_null, _ = grade(task, null)
    if not ok_ref:
        return f"reference solution fails ({why_ref})"
    if ok_null:
        return "null solution passes; the grader cannot tell work from no work"
    return None


def audit(tasks_dir: Path) -> list[tuple[str, str | None]]:
    """(task id or file, problem or None) for every task file in a directory."""
    out = []
    for p in sorted(Path(tasks_dir).glob("*.json")):
        try:
            task = load_task(p)
        except EvalError as e:
            out.append((p.stem, str(e)))
            continue
        out.append((task["id"], audit_task(task)))
    return out


# ================================================================ runs and comparison
def pair_runs(rows: list[dict], arm_a: str, arm_b: str) -> tuple[list[dict], dict]:
    """Pair trials by task: infra errors dropped (re-run, not counted as fails),
    each task scored per arm as its pass fraction over trials (the memo's
    s = passes / k; with one trial it is the plain result) and the median of
    tokens and minutes. Tasks keep the order of their first trial."""
    dropped = sum(1 for r in rows if r.get("infra_error"))
    cells: dict[tuple[str, str], list[dict]] = {}
    order: list[str] = []
    for r in rows:
        if r.get("infra_error") or r["arm"] not in (arm_a, arm_b):
            continue
        if r["task"] not in order:
            order.append(r["task"])
        cells.setdefault((r["task"], r["arm"]), []).append(r)
    pairs, unpaired = [], []
    for task in order:
        a, b = cells.get((task, arm_a)), cells.get((task, arm_b))
        if not a or not b:
            unpaired.append(task)
            continue
        pair = {"task": task}
        for side, trials in (("a", a), ("b", b)):
            pair[f"pass_{side}"] = sum(1 for t in trials if t["passed"]) / len(trials)
            pair[f"trials_{side}"] = len(trials)
            for key in ("tokens", "minutes"):
                vals = [t[key] for t in trials if t.get(key) is not None]
                pair[f"{key}_{side}"] = statistics.median(vals) if vals else None
        pairs.append(pair)
    return pairs, {"dropped_infra": dropped, "unpaired": unpaired}


def check_prereg_against_run(pre: dict, rows: list[dict]) -> str | None:
    """A reason to refuse, or None. The pre-registration must predate the first
    trial and cover every task run, or the analysis could have been chosen
    after seeing the data (memo section 5.1)."""
    outside = sorted({r["task"] for r in rows} - set(pre["tasks"]))
    if outside:
        return f"run uses tasks outside the pre-registration: {', '.join(outside[:5])}"
    stamps = [t for t in (_parse_time(r.get("at")) for r in rows) if t is not None]
    if not stamps:
        return "run rows carry no dates, so the pre-registration cannot be shown to come first"
    created = _parse_time(pre["created"])
    if created > min(stamps):
        return f"pre-registration created {pre['created']} after the first trial ({min(stamps).isoformat()})"
    return None


def compare(rows: list[dict], arm_a: str, arm_b: str, prereg: dict | None = None) -> dict:
    if prereg is not None:
        why = check_prereg_against_run(prereg, rows)
        if why:
            raise EvalError(why)
    pairs, info = pair_runs(rows, arm_a, arm_b)
    v = verdict(pairs, prereg)
    metric = v["metric"]
    sign = 1 if (prereg or {}).get("direction", "up" if metric == "pass" else "down") == "up" else -1
    stream = [1 if (p[f"{metric}_b"] - p[f"{metric}_a"]) * sign > 0 else -1 for p in pairs
              if p.get(f"{metric}_a") is not None and p.get(f"{metric}_b") is not None
              and p[f"{metric}_b"] != p[f"{metric}_a"]]
    v["sprt"] = sprt(stream)
    v.update(info)
    v["pairs"] = pairs
    return v


# ================================================================ seeded defects
def load_defects(defects_dir: Path) -> list[dict]:
    """Sidecars ``<id>.json``: {id, artefact, defect, expected_finding_keywords}."""
    out = []
    for p in sorted(Path(defects_dir).glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise EvalError(f"{p.name}: unreadable defect sidecar") from None
        if not isinstance(d, dict) or not all(isinstance(d.get(k), str) and d[k] for k in ("id", "artefact", "defect")):
            raise EvalError(f"{p.name}: needs id, artefact and defect")
        kws = d.get("expected_finding_keywords")
        if not isinstance(kws, list) or not kws or not all(isinstance(k, str) and k for k in kws):
            raise EvalError(f"{p.name}: expected_finding_keywords must be a non-empty list")
        if not (Path(defects_dir) / d["artefact"]).is_file():
            raise EvalError(f"{p.name}: artefact {d['artefact']} not found")
        out.append(d)
    return out


def score_defects(findings: list[dict], defects: list[dict]) -> dict:
    """Catch rate of a reviewer: a planted defect counts as caught when some
    finding naming it (by ``defect`` id or ``artefact`` file) contains one of
    its expected keywords, case-insensitively."""
    caught, missed = [], []
    for d in defects:
        texts = [str(f.get("finding", "")).lower() for f in findings
                 if f.get("defect") == d["id"] or f.get("artefact") == d["artefact"]]
        hit = any(k.lower() in t for t in texts for k in d["expected_finding_keywords"])
        (caught if hit else missed).append(d["id"])
    total = len(defects)
    return {"caught": len(caught), "total": total, "rate": len(caught) / total if total else 0.0, "missed": missed}


# ================================================================ ablation
def _ablation_target(target: str, root: Path) -> tuple[str, str]:
    """(slug, description) for one always-loaded rule, playbook line or file."""
    ids = {}
    for f in [root / "memory" / "items.jsonl", *sorted((root / "playbooks").glob("*.jsonl"))]:
        for row in c.read_jsonl(f):
            if row.get("id"):
                ids[row["id"]] = f.relative_to(root).as_posix()
    if target in ids:
        return target, f"item {target} in {ids[target]}"
    m = re.match(r"^(.+):(\d+)$", target)
    path, line = (m.group(1), int(m.group(2))) if m else (target, None)
    p = (root / path).resolve()
    if not str(p).startswith(str(root.resolve())) or not p.is_file():
        raise EvalError(f"not a rule id or brain file: {target}")
    rel = p.relative_to(root.resolve()).as_posix()
    slug = re.sub(r"[^a-z0-9]+", "-", rel.lower()).strip("-")
    if line is None:
        return slug, f"file {rel}"
    lines = p.read_text(encoding="utf-8").splitlines()
    if not 1 <= line <= len(lines) or not lines[line - 1].strip():
        raise EvalError(f"{rel} has no non-empty line {line}")
    return f"{slug}-l{line}", f"line {line} of {rel}: {c.clip(lines[line - 1], 70)}"


def make_prereg(change: str, hypothesis: str, metric: str, direction: str, tasks: list[str],
                tasks_dir: Path, min_pairs: int = MIN_PAIRS) -> dict:
    known = load_tasks(tasks_dir)
    unknown = [t for t in tasks if t not in known]
    if unknown:
        raise EvalError(f"unknown task ids: {', '.join(unknown[:5])}")
    if len(set(tasks)) != len(tasks):
        raise EvalError("a task is listed twice")
    pre = {"change": change, "hypothesis": hypothesis, "metric": metric, "direction": direction,
           "tasks": list(tasks), "min_pairs": min_pairs, "decision": dict(DEFAULT_DECISION),
           "decision_text": ("revert if P(B worse) >= revert_prob; ship if exact sign test p <= alpha and "
                             "P(B better) >= ship_prob and the guard holds; otherwise keep A; "
                             f"fewer than {max(MIN_PAIRS, min_pairs)} paired tasks is always not proven"),
           "created": c.now_iso()}
    return validate_prereg(pre)


def write_prereg(pre: dict, prereg_dir: Path) -> Path:
    if not _SAFE_ID.match(pre["change"]):
        raise EvalError(f"change id {pre['change']!r} must be lower-case letters, digits, '.', '_' or '-'")
    path = Path(prereg_dir) / f"{pre['change']}.json"
    if path.exists():
        raise EvalError(f"{path.name} already exists; a pre-registration is never overwritten, use a new change id")
    c.write_json(path, pre)
    return path


# ================================================================ commands
def _root(args) -> Path:
    return Path(getattr(args, "root", None) or c.BRAIN_ROOT)


def _resolve(value: str, root: Path, folder: str, ext: str) -> Path:
    """A bare name means ``<root>/<folder>/<name><ext>``; anything else is a path."""
    if "/" not in value and not value.endswith(ext):
        return root / folder / f"{value}{ext}"
    return Path(value).expanduser()


def _fail(msg: str) -> int:
    print(msg)
    return 1


def cmd_contract(args) -> int:
    root = _root(args)
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                          cwd=root, capture_output=True, text=True)
    out = proc.stdout + "\n" + proc.stderr
    ran = re.search(r"Ran (\d+) tests?", out)
    status = re.findall(r"^(OK.*|FAILED.*)$", out, re.MULTILINE)
    print(f"contract: {ran.group(1) if ran else 0} tests, {status[-1] if status else 'no result (exit %d)' % proc.returncode}")
    for name in re.findall(r"^(?:FAIL|ERROR): (\S+)", out, re.MULTILINE)[:5]:
        print(f"  failed: {name}")
    return proc.returncode


def cmd_audit(args) -> int:
    results = audit(_root(args) / "evals" / "tasks")
    broken = [(t, why) for t, why in results if why]
    for t, why in broken[:10]:
        print(f"broken {t}: {why}")
    print(f"audit: {len(results)} tasks, {len(results) - len(broken)} sound, {len(broken)} broken")
    return 1 if broken or not results else 0


def cmd_setup(args) -> int:
    """Lay out a task's starting files in a new, empty folder for one trial,
    and print the prompt the arm is given."""
    path = _root(args) / "evals" / "tasks" / f"{args.task_id}.json"
    if not path.is_file():
        return _fail(f"no task {args.task_id}")
    task = load_task(path)
    d = Path(args.dir)
    if d.exists() and any(d.iterdir()):
        return _fail(f"{d} is not empty: each trial needs a clean folder")
    d.mkdir(parents=True, exist_ok=True)
    _write_files(d, task["setup"])
    print(task["prompt"])
    return 0


def cmd_grade(args) -> int:
    path = _root(args) / "evals" / "tasks" / f"{args.task_id}.json"
    if not path.is_file():
        return _fail(f"no task {args.task_id}")
    ok, why = grade(load_task(path), Path(args.dir))
    print(f"{args.task_id}: pass" if ok else f"{args.task_id}: fail · {why}")
    return 0 if ok else 1


def cmd_record(args) -> int:
    path = _resolve(args.run_file, _root(args), "evals/runs", ".jsonl")
    rows = load_run(path) if path.is_file() and path.read_text(encoding="utf-8").strip() else []
    trial = 1 + sum(1 for r in rows if r["task"] == args.task and r["arm"] == args.arm)
    row = {"task": args.task, "arm": args.arm, "trial": trial, "passed": int(args.passed),
           "tokens": args.tokens, "minutes": args.minutes, "infra_error": bool(args.infra_error), "at": c.now_iso()}
    validate_run_row(row, len(rows) + 1)
    c.append_jsonl(path, row)
    print(f"recorded {args.task} arm {args.arm} trial {trial}: {'infra error' if args.infra_error else ('pass' if args.passed else 'fail')}")
    return 0


def cmd_compare(args) -> int:
    root = _root(args)
    rows = load_run(_resolve(args.run_file, root, "evals/runs", ".jsonl"))
    pre = load_prereg(_resolve(args.prereg, root, "evals/prereg", ".json")) if args.prereg else None
    v = compare(rows, args.a, args.b, pre)
    if args.json:
        print(json.dumps({k: v[k] for k in v if k != "pairs"}, sort_keys=True))
        return 0
    extra = f"; {len(v['unpaired'])} task(s) lacked an arm" if v["unpaired"] else ""
    print(f"pairs {v['n']} ({v['dropped_infra']} infra-error trial(s) dropped, re-run them{extra}) · "
          f"wins {v['wins']} · losses {v['losses']} · ties {v['ties']}")
    print(f"verdict: {v['decision']} · p {v['p']:.3f} · P(better) {v['prob_better']:.2f} · {v['reason']}")
    s = v["sprt"]
    print(f"sequential check: {s['decision']} (log-likelihood ratio {s['llr']:.2f}, bounds {s['lower']:.2f}/{s['upper']:.2f})")
    for line in owner_lines(v):
        print(line)
    return 0


def cmd_prereg(args) -> int:
    root = _root(args)
    tasks = [t for t in args.tasks.split(",") if t.strip()]
    pre = make_prereg(args.change_id, args.hypothesis, args.metric, args.direction,
                      [t.strip() for t in tasks], root / "evals" / "tasks", args.min_pairs)
    path = write_prereg(pre, root / "evals" / "prereg")
    print(f"wrote {path.relative_to(root) if path.is_relative_to(root) else path} · {len(tasks)} tasks · "
          f"metric {args.metric} {args.direction}; commit it before the first trial")
    return 0


def cmd_defects_score(args) -> int:
    root = _root(args)
    defects = load_defects(root / "evals" / "seeded_defects")
    if not Path(args.findings).is_file():
        return _fail(f"findings file not found: {args.findings}")
    findings = c.read_jsonl(args.findings)
    s = score_defects(findings, defects)
    missed = f"; missed: {', '.join(s['missed'][:6])}" if s["missed"] else ""
    print(f"caught {s['caught']} of {s['total']} planted defects ({s['rate'] * 100:.0f}%){missed}")
    return 0


def cmd_ablate(args) -> int:
    root = _root(args)
    slug, desc = _ablation_target(args.target, root)
    tasks_dir = root / "evals" / "tasks"
    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()] if args.tasks else sorted(load_tasks(tasks_dir))
    change = f"ablate-{slug}"[:64].rstrip("-.")
    pre = make_prereg(change, f"Removing {desc} keeps the pass rate and lowers tokens",
                      "tokens", "down", tasks, tasks_dir)
    path = write_prereg(pre, root / "evals" / "prereg")
    print(f"wrote {path.relative_to(root) if path.is_relative_to(root) else path}")
    print("arm A: the brain as it is now")
    print(f"arm B: a scratch copy with {desc} removed (instruction files here are not edited)")
    print(f"tasks ({len(tasks)}): {c.clip(', '.join(tasks), 160)}")
    print(f"record each trial: brain eval record {change} --task T --arm A|B --passed 0|1 --tokens N")
    print(f"then: brain eval compare {change} --a A --b B --prereg {change}")
    return 0


def _guarded(func):
    """Turn expected input errors into one line and exit 1, never a traceback."""
    def run(args) -> int:
        try:
            return func(args)
        except EvalError as e:
            return _fail(str(e))
    return run


def register(sub) -> None:
    p = sub.add_parser("eval", help="evaluation: contract, audit, grade, record, compare, prereg, defects")
    p.add_argument("--root", help=argparse.SUPPRESS)
    es = p.add_subparsers(dest="eval_command")

    s = es.add_parser("contract", help="run the unit suite (tier 0) and print one line")
    s.set_defaults(func=_guarded(cmd_contract))
    s = es.add_parser("audit", help="every task's grader passes its reference and fails its null solution")
    s.set_defaults(func=_guarded(cmd_audit))
    s = es.add_parser("setup", help="lay out a task's starting files in a clean folder and print its prompt")
    s.add_argument("task_id")
    s.add_argument("dir")
    s.set_defaults(func=_guarded(cmd_setup))
    s = es.add_parser("grade", help="grade a produced directory against a task")
    s.add_argument("task_id")
    s.add_argument("dir")
    s.set_defaults(func=_guarded(cmd_grade))
    s = es.add_parser("record", help="append one trial to a run file")
    s.add_argument("run_file")
    s.add_argument("--task", required=True)
    s.add_argument("--arm", required=True)
    s.add_argument("--passed", required=True, type=int, choices=(0, 1))
    s.add_argument("--tokens", type=int)
    s.add_argument("--minutes", type=float)
    s.add_argument("--infra-error", action="store_true")
    s.set_defaults(func=_guarded(cmd_record))
    s = es.add_parser("compare", help="paired verdict between two arms of a run")
    s.add_argument("run_file")
    s.add_argument("--a", required=True)
    s.add_argument("--b", required=True)
    s.add_argument("--prereg")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_guarded(cmd_compare))
    s = es.add_parser("prereg", help="write a pre-registration before any live run")
    s.add_argument("change_id")
    s.add_argument("--hypothesis", required=True)
    s.add_argument("--metric", required=True, choices=METRICS)
    s.add_argument("--direction", required=True, choices=("up", "down"))
    s.add_argument("--tasks", required=True)
    s.add_argument("--min-pairs", type=int, default=MIN_PAIRS)
    s.set_defaults(func=_guarded(cmd_prereg))
    s = es.add_parser("defects", help="reviewer honesty test over evals/seeded_defects")
    ds = s.add_subparsers(dest="defects_command")
    d = ds.add_parser("score", help="catch rate from a reviewer's findings JSONL")
    d.add_argument("findings")
    d.set_defaults(func=_guarded(cmd_defects_score))

    p = sub.add_parser("ablate", help="pre-register removing one always-loaded rule, line or file")
    p.add_argument("target", help="item id, FILE:LINE or FILE")
    p.add_argument("--tasks", help="comma-separated task ids (default: all)")
    p.add_argument("--root", help=argparse.SUPPRESS)
    p.set_defaults(func=_guarded(cmd_ablate))
