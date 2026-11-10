"""Tests for engine/evals.py.

The research memo's statistics were written by hand and never executed, so
every function is checked numerically here: the sign test against direct
binomial sums and its critical values, the Beta posteriors against numerical
integration, the SPRT's error rates by seeded simulation. The rest covers the
decision rule (I-16 included), graders, audit, pairing, pre-registration
refusals, ablation and defect scoring. Everything runs in temporary folders."""
import argparse
import contextlib
import io
import json
import math
import os
import random
import shutil
import tempfile
import unittest
from fractions import Fraction
from math import comb
from pathlib import Path

from engine import common as c
from engine import evals as E

BRAIN = Path(__file__).resolve().parents[1]
FIX = BRAIN / "tests" / "fixtures" / "evals"
NOW = "2026-11-10T12:00:00Z"


def cli(argv, root):
    """Run a command through the real argparse tree; (exit code, output lines)."""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    E.register(sub)
    args = parser.parse_args(argv)
    args.root = str(root)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = args.func(args)
    return code, buf.getvalue().splitlines()


def binom_tail(m, b):
    """P(X >= b), X ~ Bin(m, 1/2), as an exact fraction from the pmf."""
    return sum(Fraction(comb(m, j), 2 ** m) for j in range(b, m + 1))


def beta_pdf(x, a, b):
    return math.exp((a - 1) * math.log(x) + (b - 1) * math.log(1 - x) - E._log_beta(a, b))


def beta_cdf_int(x, a, b):
    """Regularised incomplete beta for integer a, b: P(Bin(a+b-1, x) >= a)."""
    n = a + b - 1
    return sum(comb(n, j) * x ** j * (1 - x) ** (n - j) for j in range(a, n + 1))


def simpson(f, lo, hi, steps=4000):
    h = (hi - lo) / steps
    s = f(lo) + f(hi)
    for i in range(1, steps):
        s += (4 if i % 2 else 2) * f(lo + i * h)
    return s * h / 3


def pairs(spec):
    """Pairs from a string: W win for B, L loss, T tie (both pass)."""
    out = []
    for i, ch in enumerate(spec):
        a, b = {"W": (0, 1), "L": (1, 0), "T": (1, 1)}[ch]
        out.append({"task": f"t{i}", "pass_a": a, "pass_b": b})
    return out


def prereg(**kw):
    base = {"change": "x", "hypothesis": "h", "metric": "pass", "direction": "up", "tasks": ["t"],
            "min_pairs": 8, "decision": dict(E.DEFAULT_DECISION), "created": "2026-11-01T00:00:00Z"}
    base.update(kw)
    return base


class SignTest(unittest.TestCase):
    def test_matches_direct_binomial_sums(self):
        for m in range(0, 31):
            for b in range(0, m + 1):
                self.assertAlmostEqual(E.sign_test(b, m - b), float(binom_tail(m, b)), places=12)
        self.assertEqual(E.sign_test(0, 0), 1.0)

    def test_memo_values_and_critical_wins(self):
        self.assertEqual(E.sign_test(7, 1), 9 / 256)
        self.assertEqual(E.sign_test(6, 2), 37 / 256)
        self.assertEqual(E.sign_test(9, 1), 11 / 1024)
        self.assertEqual(E.sign_test(8, 2), 56 / 1024)
        self.assertEqual(E.sign_test(15, 5), 21700 / 2 ** 20)
        crit = {m: min(b for b in range(m + 1) if E.sign_test(b, m - b) <= 0.05) for m in (8, 10, 20, 30)}
        self.assertEqual(crit, {8: 7, 10: 9, 20: 15, 30: 20})

    def test_memo_power_at_ten(self):
        power = sum(comb(10, j) * 0.9 ** j * 0.1 ** (10 - j) for j in range(9, 11))
        self.assertAlmostEqual(power, 0.736, places=3)


class BetaPosteriors(unittest.TestCase):
    CASES = [(0, 0, 0, 0), (3, 10, 7, 10), (7, 10, 3, 10), (1, 4, 6, 9), (10, 10, 9, 10), (0, 5, 5, 5)]

    def test_unpaired_matches_numerical_integration(self):
        for pa, na, pb, nb in self.CASES:
            aa, ba, ab, bb = 1 + pa, 1 + na - pa, 1 + pb, 1 + nb - pb
            num = simpson(lambda x: beta_pdf(x, ab, bb) * beta_cdf_int(x, aa, ba), 1e-12, 1 - 1e-12)
            self.assertAlmostEqual(E.beta_binomial_prob_b_better(pa, na, pb, nb), num, places=6)

    def test_unpaired_symmetry_and_seeded_sampling(self):
        rng = random.Random(7)
        for pa, na, pb, nb in self.CASES:
            p = E.beta_binomial_prob_b_better(pa, na, pb, nb)
            self.assertAlmostEqual(p + E.beta_binomial_prob_b_better(pb, nb, pa, na), 1.0, places=9)
            draws = 40000
            hits = sum(rng.betavariate(1 + pb, 1 + nb - pb) > rng.betavariate(1 + pa, 1 + na - pa) for _ in range(draws))
            self.assertLess(abs(hits / draws - p), 0.01)
        self.assertAlmostEqual(E.beta_binomial_prob_b_better(0, 0, 0, 0), 0.5)
        with self.assertRaises(E.EvalError):
            E.beta_binomial_prob_b_better(5, 4, 0, 1)

    def test_paired_share_matches_integration_and_memo_example(self):
        self.assertAlmostEqual(E.prob_win_share_above_half(9, 1), 1 - 12 / 2048, places=12)
        for w, l in ((0, 0), (9, 1), (1, 4), (3, 3), (7, 1)):
            num = simpson(lambda x: beta_pdf(x, 1 + w, 1 + l), 0.5, 1 - 1e-12)
            self.assertAlmostEqual(E.prob_win_share_above_half(w, l), num, places=6)


class Sprt(unittest.TestCase):
    def test_bounds_and_memo_stopping_points(self):
        r = E.sprt([])
        self.assertAlmostEqual(r["upper"], math.log(16))
        self.assertAlmostEqual(r["lower"], math.log(0.2 / 0.95))
        self.assertEqual(r["decision"], "continue")
        self.assertEqual(E.sprt([1] * 6)["decision"], "continue")
        seven = E.sprt([1] * 7 + [-1] * 5)
        self.assertEqual((seven["decision"], seven["used"]), ("accept-better", 7))
        self.assertAlmostEqual(seven["llr"], 7 * math.log(1.5))
        self.assertEqual(E.sprt([-1, -1])["decision"], "continue")
        three = E.sprt([-1, -1, -1])
        self.assertEqual((three["decision"], three["used"]), ("accept-not-better", 3))
        self.assertEqual(E.sprt([True] * 7)["decision"], "accept-better")
        self.assertEqual(E.sprt([False] * 3)["decision"], "accept-not-better")

    def simulate(self, p_win, seed, runs=20000):
        rng = random.Random(seed)
        accepted, used = 0, 0
        for _ in range(runs):
            stream = (1 if rng.random() < p_win else -1 for _ in range(10 ** 4))
            r = E.sprt(stream)
            accepted += r["decision"] == "accept-better"
            used += r["used"]
        return accepted / runs, used / runs

    def test_error_rates_by_seeded_simulation(self):
        false_ship, n0 = self.simulate(0.5, seed=1)
        power, n1 = self.simulate(0.75, seed=2)
        # Wald: realised alpha <= alpha / (1 - beta) = 0.0625, beta <= beta / (1 - alpha) = 0.21.
        # Measured about 0.045 and 0.15: inside the nominal 0.05 / 0.20.
        self.assertLessEqual(false_ship, 0.05 + 0.006)
        self.assertGreaterEqual(power, 0.80)
        # Average discordant tasks needed: about 12 under H0 and 17 under H1, so the
        # SPRT rarely finishes inside a 10-task budget (the memo implies it saves runs).
        self.assertGreater(n0, 10)
        self.assertGreater(n1, 15)


class Bootstrap(unittest.TestCase):
    def test_deterministic_and_close_to_normal_theory(self):
        rng = random.Random(3)
        vals = [rng.gauss(10, 2) for _ in range(400)]
        lo, hi = E.bootstrap_ci(vals, seed=5)
        self.assertEqual((lo, hi), E.bootstrap_ci(vals, seed=5))
        mean = sum(vals) / len(vals)
        self.assertLess(lo, mean)
        self.assertGreater(hi, mean)
        sd = (sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
        theory = 2 * 1.96 * sd / len(vals) ** 0.5
        self.assertLess(abs((hi - lo) - theory) / theory, 0.15)
        self.assertEqual(E.bootstrap_ci([4, 4, 4], seed=1), (4.0, 4.0))
        with self.assertRaises(E.EvalError):
            E.bootstrap_ci([], seed=1)


class Verdict(unittest.TestCase):
    def test_under_eight_pairs_is_never_a_claim(self):
        for spec in ("WWWWWWW", "LLLLLLL", "W"):
            v = E.verdict(pairs(spec))
            self.assertEqual(v["decision"], "not-proven")
            self.assertIn("8", v["reason"])
        lines = E.owner_lines(E.verdict(pairs("WWWWWWW")))
        self.assertEqual(len(lines), 2)
        self.assertIn("7 test tasks", lines[0])
        self.assertIn("not proven", lines[1])

    def test_ship_needs_nine_of_ten(self):
        v = E.verdict(pairs("WWWWWWWWWL"))
        self.assertEqual((v["decision"], v["n"], v["discordant"]), ("ship", 10, 10))
        self.assertAlmostEqual(v["p"], 11 / 1024)
        self.assertGreater(v["prob_better"], 0.99)
        lines = E.owner_lines(v)
        self.assertIn("9 of 10", lines[0])
        self.assertIn("adopted", lines[1])
        self.assertNotIn("p ", " ".join(lines).replace("up ", ""))
        self.assertEqual(E.verdict(pairs("WWWWWWWWLL"))["decision"], "not-proven")

    def test_preregistered_revert_and_its_threshold(self):
        data = pairs("WLLLLTTTTTT")  # 6 of 11 tied; P(B worse) = P(Bin(6, .5) >= 2) = 57/64
        v = E.verdict(data, prereg())
        self.assertEqual(v["decision"], "revert")
        self.assertIn("worse", E.owner_lines(v)[1])
        strict = prereg(decision=dict(E.DEFAULT_DECISION, revert_prob=0.95))
        self.assertEqual(E.verdict(data, strict)["decision"], "not-proven")
        self.assertIn("saturated", v["reason"])

    def test_min_pairs_from_prereg_and_all_ties(self):
        self.assertEqual(E.verdict(pairs("WWWWWWWWWW"), prereg(min_pairs=12))["decision"], "not-proven")
        v = E.verdict(pairs("TTTTTTTTTT"))
        self.assertEqual((v["decision"], v["discordant"]), ("not-proven", 0))

    def test_cost_guard_blocks_an_expensive_win(self):
        data = pairs("WWWWWWWWWL")
        for p in data:
            p.update(tokens_a=1000, tokens_b=1500)
        v = E.verdict(data)
        self.assertEqual(v["decision"], "not-proven")
        self.assertIn("guard", v["reason"])
        self.assertIn("50% more tokens", E.owner_lines(v)[0])

    def test_token_metric_requires_no_loss_of_passes(self):
        data = [{"task": f"t{i}", "pass_a": 1, "pass_b": 1, "tokens_a": 1000, "tokens_b": 800} for i in range(10)]
        pre = prereg(metric="tokens", direction="down")
        self.assertEqual(E.verdict(data, pre)["decision"], "ship")
        data[0]["pass_b"] = 0
        v = E.verdict(data, pre)
        self.assertEqual(v["decision"], "not-proven")
        self.assertIn("B must not pass fewer", v["reason"])


class Checks(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        c.write_text(self.root / "a.md", "One two three [x](b.md) [web](https://example.org) [up](#top)\n")
        c.write_text(self.root / "b.md", "{\"tier\": 1, \"ok\": true}")
        c.write_text(self.root / "c.md", "[gone](missing.md)\n")

    def check(self, **chk):
        return E.run_check(chk, self.root)

    def test_each_type_passes_and_fails(self):
        cases = [
            ({"type": "file_exists", "path": "a.md"}, {"type": "file_exists", "path": "z.md"}),
            ({"type": "min_words", "path": "a.md", "n": 3}, {"type": "min_words", "path": "a.md", "n": 50}),
            ({"type": "max_words", "path": "a.md", "n": 50}, {"type": "max_words", "path": "a.md", "n": 2}),
            ({"type": "contains_all", "path": "a.md", "items": ["one", "THREE"]},
             {"type": "contains_all", "path": "a.md", "items": ["one", "four"]}),
            ({"type": "contains_none", "path": "a.md", "items": ["four"]},
             {"type": "contains_none", "path": "a.md", "items": ["Two"]}),
            ({"type": "regex", "path": "a.md", "pattern": r"^One"}, {"type": "regex", "path": "a.md", "pattern": r"^Two"}),
            ({"type": "regex", "path": "a.md", "pattern": "four", "must_match": False},
             {"type": "regex", "path": "a.md", "pattern": "two", "must_match": False, "ignore_case": True}),
            ({"type": "json_valid", "path": "b.md"}, {"type": "json_valid", "path": "a.md"}),
            ({"type": "json_equals", "path": "b.md", "fields": {"tier": 1}},
             {"type": "json_equals", "path": "b.md", "fields": {"tier": 2}}),
            ({"type": "links_resolve", "path": "a.md"}, {"type": "links_resolve", "path": "c.md"}),
        ]
        for good, bad in cases:
            E._check_spec(good, "t")
            self.assertIsNone(self.check(**good), good)
            self.assertIsNotNone(self.check(**bad), bad)

    def test_json_equals_does_not_confuse_true_with_one(self):
        self.assertIsNotNone(self.check(type="json_equals", path="b.md", fields={"ok": 1}))
        self.assertIsNone(self.check(type="json_equals", path="b.md", fields={"ok": True}))

    def test_links_need_min_count_and_stay_inside(self):
        self.assertIsNotNone(self.check(type="links_resolve", path="a.md", min_links=2))
        c.write_text(self.root / "d.md", "[out](../../etc/hostname)\n")
        self.assertIsNotNone(self.check(type="links_resolve", path="d.md"))

    def test_bad_specs_are_one_line_errors(self):
        for bad in ({"type": "nope", "path": "a"}, {"type": "regex", "path": "a", "pattern": "("},
                    {"type": "min_words", "path": "a"}, {"type": "contains_all", "path": "a", "items": []}):
            with self.assertRaises(E.EvalError) as ctx:
                E._check_spec(bad, "t")
            self.assertNotIn("\n", str(ctx.exception))


class Audit(unittest.TestCase):
    def test_catches_a_grader_that_passes_the_null_solution(self):
        why = E.audit_task(E.load_task(FIX / "broken-task.json"))
        self.assertIn("null solution passes", why)
        self.assertIn("reference solution fails", E.audit_task(E.load_task(FIX / "bad-reference.json")))

    def test_audit_command_exits_non_zero_on_a_broken_task(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        shutil.copytree(FIX, root / "evals" / "tasks")
        shutil.copy(BRAIN / "evals" / "tasks" / "route-question.json", root / "evals" / "tasks")
        code, out = cli(["eval", "audit"], root)
        self.assertEqual(code, 1)
        self.assertEqual(out[-1], "audit: 3 tasks, 1 sound, 2 broken")

    def test_invalid_task_files_are_reported(self):
        good = json.loads((BRAIN / "evals" / "tasks" / "route-question.json").read_text())
        for field, value in (("split", "test"), ("tier", 5), ("family", "x"), ("setup", [{"path": "../x", "content": ""}])):
            with self.assertRaises(E.EvalError):
                E.validate_task(dict(good, **{field: value}))


class ShippedTasks(unittest.TestCase):
    def test_every_shipped_task_passes_audit(self):
        results = E.audit(BRAIN / "evals" / "tasks")
        self.assertGreaterEqual(len(results), 12)
        self.assertEqual([r for r in results if r[1]], [])

    def test_split_families_and_size(self):
        tasks = E.load_tasks(BRAIN / "evals" / "tasks").values()
        splits = [t["split"] for t in tasks]
        self.assertEqual((splits.count("dev"), splits.count("heldout")), (8, 4))
        self.assertEqual({t["family"] for t in tasks}, set(E.FAMILIES))
        for t in tasks:
            lines = sum(f["content"].count("\n") for f in t["setup"])
            self.assertLess(lines, 60, t["id"])

    def test_grade_command_reports_failing_check(self):
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        c.write_text(work / "route.json", '{"tier": 2}')
        code, out = cli(["eval", "grade", "route-question", str(work)], BRAIN)
        self.assertEqual(code, 1)
        self.assertIn("route-question: fail · json_equals", out[0])
        c.write_text(work / "route.json", '{"tier": 0}')
        self.assertEqual(cli(["eval", "grade", "route-question", str(work)], BRAIN), (0, ["route-question: pass"]))

    def test_setup_lays_out_a_clean_trial_and_refuses_a_used_folder(self):
        work = Path(tempfile.mkdtemp()) / "trial"
        self.addCleanup(shutil.rmtree, work.parent)
        code, out = cli(["eval", "setup", "sw-fix-median", str(work)], BRAIN)
        self.assertEqual(code, 0)
        self.assertIn("Fix stats.py", out[0])
        self.assertTrue((work / "stats.py").is_file())
        self.assertEqual(cli(["eval", "grade", "sw-fix-median", str(work)], BRAIN)[0], 1)  # unsolved
        self.assertEqual(cli(["eval", "setup", "sw-fix-median", str(work)], BRAIN)[0], 1)

    def test_command_grader_cannot_be_fooled_by_editing_the_test(self):
        task = E.load_task(BRAIN / "evals" / "tasks" / "sw-fix-median.json")
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        E._write_files(work, task["setup"])
        c.write_text(work / "test_stats.py", "import unittest\n")
        before = (work / "test_stats.py").read_text()
        self.assertFalse(E.grade(task, work)[0])
        self.assertEqual((work / "test_stats.py").read_text(), before)


class Runs(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        os.environ["BRAIN_NOW"] = NOW
        self.addCleanup(os.environ.pop, "BRAIN_NOW", None)

    def rows(self):
        out = []
        for i in range(10):
            a, b = (1, 1) if i == 9 else (0, 1)
            out.append({"task": f"t{i}", "arm": "A", "trial": 1, "passed": a, "tokens": 100, "at": NOW})
            out.append({"task": f"t{i}", "arm": "B", "trial": 1, "passed": b, "tokens": 100, "at": NOW})
        return out

    def test_pairs_by_task_with_trials_and_infra_errors(self):
        rows = self.rows()
        rows += [{"task": "t0", "arm": "B", "trial": 2, "passed": 0, "tokens": 300, "at": NOW},
                 {"task": "t0", "arm": "B", "trial": 3, "passed": 1, "tokens": 50, "at": NOW, "infra_error": True},
                 {"task": "t10", "arm": "A", "trial": 1, "passed": 1, "at": NOW},
                 {"task": "t11", "arm": "A", "trial": 1, "passed": 1, "at": NOW},
                 {"task": "t11", "arm": "B", "trial": 1, "passed": 0, "at": NOW, "infra_error": True}]
        prs, info = E.pair_runs(rows, "A", "B")
        self.assertEqual(len(prs), 10)
        self.assertEqual(info, {"dropped_infra": 2, "unpaired": ["t10", "t11"]})
        t0 = prs[0]
        self.assertEqual((t0["pass_b"], t0["trials_b"], t0["tokens_b"]), (0.5, 2, 200))
        v = E.compare(rows, "A", "B")
        self.assertEqual((v["wins"], v["losses"], v["ties"], v["decision"]), (9, 0, 1, "ship"))

    def test_record_then_compare_through_the_cli(self):
        run = self.root / "evals" / "runs" / "r1.jsonl"
        for i in range(8):
            for arm, passed in (("A", "0"), ("B", "1")):
                code, _ = cli(["eval", "record", str(run), "--task", f"t{i}", "--arm", arm, "--passed", passed,
                               "--tokens", "500"], self.root)
                self.assertEqual(code, 0)
        code, out = cli(["eval", "record", str(run), "--task", "t0", "--arm", "A", "--passed", "1", "--infra-error"], self.root)
        self.assertIn("trial 2: infra error", out[0])
        rows = E.load_run(run)
        self.assertEqual(len(rows), 17)
        self.assertEqual(rows[0]["at"], NOW)
        code, out = cli(["eval", "compare", str(run), "--a", "A", "--b", "B"], self.root)
        self.assertEqual(code, 0)
        self.assertLessEqual(len(out), 15)
        self.assertIn("1 infra-error trial(s) dropped", out[0])
        self.assertIn("verdict: ship", out[1])
        self.assertIn("8 of 8", out[3])

    def test_refuses_on_preregistration_violations(self):
        rows = self.rows()
        tasks = [f"t{i}" for i in range(10)]
        self.assertEqual(E.compare(rows, "A", "B", prereg(tasks=tasks))["decision"], "ship")
        with self.assertRaises(E.EvalError) as ctx:
            E.compare(rows, "A", "B", prereg(tasks=tasks[:9]))
        self.assertIn("outside the pre-registration: t9", str(ctx.exception))
        with self.assertRaises(E.EvalError) as ctx:
            E.compare(rows, "A", "B", prereg(tasks=tasks, created="2026-11-11T00:00:00Z"))
        self.assertIn("after the first trial", str(ctx.exception))
        undated = [{k: v for k, v in r.items() if k != "at"} for r in rows]
        with self.assertRaises(E.EvalError):
            E.compare(undated, "A", "B", prereg(tasks=tasks))
        run = self.root / "late.jsonl"
        c.write_jsonl(run, rows)
        pre = self.root / "late.json"
        c.write_json(pre, prereg(tasks=tasks, created="2026-12-01T00:00:00Z"))
        code, out = cli(["eval", "compare", str(run), "--a", "A", "--b", "B", "--prereg", str(pre)], self.root)
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1)

    def test_malformed_run_rows_are_errors(self):
        run = self.root / "bad.jsonl"
        c.write_text(run, '{"task": "t", "arm": "A", "trial": 0, "passed": 1}\n')
        with self.assertRaises(E.EvalError) as ctx:
            E.load_run(run)
        self.assertIn("line 1", str(ctx.exception))
        c.write_text(run, "not json\n")
        with self.assertRaises(E.EvalError):
            E.load_run(run)


class Prereg(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        shutil.copytree(BRAIN / "evals" / "tasks", self.root / "evals" / "tasks")
        os.environ["BRAIN_NOW"] = NOW
        self.addCleanup(os.environ.pop, "BRAIN_NOW", None)

    def test_writes_once_and_refuses_overwrite(self):
        argv = ["eval", "prereg", "review-v2", "--hypothesis", "fewer misses", "--metric", "pass",
                "--direction", "up", "--tasks", "route-question,route-project"]
        code, out = cli(argv, self.root)
        self.assertEqual(code, 0)
        path = self.root / "evals" / "prereg" / "review-v2.json"
        pre = E.load_prereg(path)
        self.assertEqual((pre["created"], pre["tasks"], pre["min_pairs"]), (NOW, ["route-question", "route-project"], 8))
        before = path.read_text()
        code, out = cli(argv, self.root)
        self.assertEqual(code, 1)
        self.assertIn("never overwritten", out[0])
        self.assertEqual(path.read_text(), before)

    def test_refuses_bad_input(self):
        base = ["eval", "prereg", "c2", "--hypothesis", "h", "--metric", "pass", "--direction", "up"]
        for extra in (["--tasks", "no-such-task"], ["--tasks", "route-question", "--min-pairs", "5"],
                      ["--tasks", "route-question,route-question"]):
            code, out = cli(base + extra, self.root)
            self.assertEqual((code, len(out)), (1, 1), extra)
        code, out = cli(["eval", "prereg", "Bad Id", "--hypothesis", "h", "--metric", "pass", "--direction", "up",
                         "--tasks", "route-question"], self.root)
        self.assertEqual(code, 1)
        with self.assertRaises(E.EvalError):
            E.validate_prereg(prereg(metric="pass", direction="down"))


class Ablate(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        shutil.copytree(BRAIN / "evals" / "tasks", self.root / "evals" / "tasks")
        c.write_text(self.root / "CLAUDE.md", "# Brain\n\nRule one.\n\nRule two.\n")
        c.write_jsonl(self.root / "memory" / "items.jsonl", [{"id": "rule-a", "text": "Do the thing."}])
        c.write_jsonl(self.root / "playbooks" / "data.jsonl", [{"id": "data-b", "text": "Check totals."}])
        os.environ["BRAIN_NOW"] = NOW
        self.addCleanup(os.environ.pop, "BRAIN_NOW", None)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): c.sha256_file(p) for p in self.root.rglob("*") if p.is_file()}

    def test_writes_prereg_and_changes_nothing_else(self):
        for target, name in (("rule-a", "ablate-rule-a"), ("CLAUDE.md:3", "ablate-claude-md-l3"),
                             ("data-b", "ablate-data-b"), ("CLAUDE.md", "ablate-claude-md")):
            before = self.snapshot()
            code, out = cli(["ablate", target], self.root)
            self.assertEqual(code, 0, out)
            self.assertLessEqual(len(out), 15)
            after = self.snapshot()
            new = set(after) - set(before)
            self.assertEqual(new, {f"evals/prereg/{name}.json"})
            self.assertEqual({k: after[k] for k in before}, before)
            pre = E.load_prereg(self.root / "evals" / "prereg" / f"{name}.json")
            self.assertEqual((pre["metric"], pre["direction"], len(pre["tasks"])), ("tokens", "down", 12))
            self.assertTrue(any(line.startswith("arm B") for line in out))

    def test_task_subset_and_bad_targets(self):
        code, out = cli(["ablate", "rule-a", "--tasks", "route-question,route-project"], self.root)
        self.assertIn("tasks (2)", out[3])
        for bad in ("no-such-rule", "CLAUDE.md:2", "CLAUDE.md:99", "../outside.md"):
            code, out = cli(["ablate", bad], self.root)
            self.assertEqual((code, len(out)), (1, 1), bad)


class Defects(unittest.TestCase):
    def test_shipped_defects_are_complete(self):
        defects = E.load_defects(BRAIN / "evals" / "seeded_defects")
        self.assertGreaterEqual(len(defects), 6)
        exts = {Path(d["artefact"]).suffix for d in defects}
        self.assertTrue({".py", ".md"} <= exts)

    def test_score_arithmetic(self):
        defects = [{"id": f"d{i}", "artefact": f"d{i}.md", "defect": "x", "expected_finding_keywords": ["Off-By-One", "range"]}
                   for i in range(4)]
        findings = [{"defect": "d0", "finding": "the loop is off-by-one"},
                    {"artefact": "d1.md", "finding": "wrong RANGE end"},
                    {"defect": "d2", "finding": "looks fine"},
                    {"defect": "d3", "finding": ""}, {"defect": "d2-other", "finding": "range"}]
        s = E.score_defects(findings, defects)
        self.assertEqual((s["caught"], s["total"], s["rate"], s["missed"]), (2, 4, 0.5, ["d2", "d3"]))
        self.assertEqual(E.score_defects([], [])["rate"], 0.0)

    def test_score_command_one_line(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        found = root / "findings.jsonl"
        c.write_jsonl(found, [{"defect": "code-last-items", "finding": "Off-by-one: the last item is skipped"},
                              {"defect": "test-trivial", "finding": "The test is a tautology"}])
        code, out = cli(["eval", "defects", "score", str(found)], BRAIN)
        self.assertEqual(code, 0)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("caught 2 of 6 planted defects (33%)"), out[0])
        self.assertEqual(cli(["eval", "defects", "score", str(root / "none.jsonl")], BRAIN)[0], 1)


class Contract(unittest.TestCase):
    def make(self, body):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        c.write_text(root / "tests" / "__init__.py", "")
        c.write_text(root / "tests" / "test_x.py", "import unittest\n\nclass T(unittest.TestCase):\n" + body)
        return root

    def test_green_suite_prints_one_line(self):
        root = self.make("    def test_a(self):\n        pass\n\n    def test_b(self):\n        pass\n")
        self.assertEqual(cli(["eval", "contract"], root), (0, ["contract: 2 tests, OK"]))

    def test_red_suite_exits_non_zero_and_names_the_test(self):
        root = self.make("    def test_bad(self):\n        self.fail('no')\n")
        code, out = cli(["eval", "contract"], root)
        self.assertNotEqual(code, 0)
        self.assertEqual(out[0], "contract: 1 tests, FAILED (failures=1)")
        self.assertIn("test_bad", out[1])


if __name__ == "__main__":
    unittest.main()
