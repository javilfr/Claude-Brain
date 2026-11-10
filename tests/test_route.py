"""Tests for engine/route.py: sizing on the labelled set, the delegation of
model choice to engine/mlearn.py, the cascade rule, and the exact assignment
against brute force."""
import argparse
import io
import itertools
import json
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from engine import mlearn, route

EVAL = Path(__file__).resolve().parents[1] / "evals" / "routing.jsonl"
CFG = {"roles": {"lead": {"model": "opus", "effort": "medium"}, "builder": {"model": "sonnet", "effort": "medium"}},
       "models": {"claude-sonnet-5-5": {"alias": "sonnet", "in": 2.0, "out": 10.0},
                  "claude-opus-5-5": {"alias": "opus", "in": 4.0, "out": 20.0}}}


def rows():
    return [json.loads(line) for line in EVAL.read_text(encoding="utf-8").splitlines() if line.strip()]


class Classify(unittest.TestCase):
    def test_eval_set_size_and_shape(self):
        data = rows()
        self.assertGreaterEqual(len(data), 70)
        for r in data:
            self.assertIn(r["tier"], (0, 1, 2, 3))
            self.assertTrue(r["text"].strip())

    def test_a_real_word_is_not_a_typo_for_another(self):
        # 'tests' is one edit from Spanish 'tesis'; the slip rule must not fire
        # on a word the vocabularies already know, or a Python CLI with tests
        # is routed as a thesis.
        self.assertFalse(route._close("tests", "tesis"))
        self.assertTrue(route._close("tets", "test") or route._close("calcualtor", "calculator"))
        got = route.classify("New project: a command-line calculator in Python with tests")
        self.assertEqual(got["family"], "software")
        self.assertNotIn("no task verb", got["reason"])

    def test_trigger_phrases_all_correct(self):
        for r in (r for r in rows() if r.get("trigger")):
            with self.subTest(text=r["text"]):
                got = route.classify(r["text"])
                self.assertEqual(got["tier"], r["tier"])
                if "class" in r:
                    self.assertEqual(got["task_class"], r["class"])

    def test_never_oversize_small_requests(self):
        for r in (r for r in rows() if r["tier"] <= 1):
            with self.subTest(text=r["text"]):
                self.assertLessEqual(route.classify(r["text"])["tier"], 1)

    def test_overall_accuracy(self):
        data = rows()
        hits = sum(route.classify(r["text"])["tier"] == r["tier"] for r in data)
        self.assertGreaterEqual(hits / len(data), 0.85, f"tier accuracy {hits}/{len(data)}")

    def test_resume_uses_recorded_tier(self):
        self.assertEqual(route.classify("Continue", {"tier": 3})["tier"], 3)
        self.assertEqual(route.classify("sigue", {})["tier"], 2)
        self.assertEqual(route.classify("start running", {"family": "knowledge"})["family"], "knowledge")

    def test_manifest_family_default(self):
        self.assertEqual(route.classify("make it shorter", {"family": "language"})["family"], "language")

    def test_typo_tolerance(self):
        self.assertEqual(route.classify("contniue")["task_class"], "resume")
        self.assertEqual(route.classify("trnaslate the whole website to japanese")["family"], "language")


def outcomes(model, n, passed=True, start=0):
    return [{"kind": "outcome", "id": f"{model}{start + i}", "at": f"2026-01-01T{start + i:05d}",
             "task_class": "software.feature", "family": "software", "tier": 1, "risk": "standard", "model": model,
             "effort": "medium", "has_check": True, "passed": passed, "first_pass": passed, "tokens": 100_000}
            for i in range(n)]


def ml_cfg():
    out = json.loads(json.dumps(mlearn.config()))
    out["models"] = CFG
    out["bandit"]["arms"] = [["sonnet", "medium"]]
    return out


class Suggest(unittest.TestCase):
    """route.suggest only delegates to mlearn.suggest_arm; the statistics are
    tested in tests/test_mlearn.py. These check the wiring."""

    def test_defaults_without_enough_outcomes(self):
        c_ = ml_cfg()
        state = mlearn.fold(mlearn.empty_state(), outcomes("sonnet", 9) + outcomes("opus", 3), c_)
        got = route.suggest("software.feature", "lead", "software", "standard", 1, True, state, c_, seed=1)
        self.assertEqual((got["model"], got["effort"], got["explored"]), ("opus", "medium", False))
        self.assertIn("role default", got["basis"])
        self.assertIn("12 pooled", got["basis"])

    def test_no_check_means_role_default(self):
        c_ = ml_cfg()
        state = mlearn.fold(mlearn.empty_state(), outcomes("sonnet", 30) + outcomes("opus", 30, False, 100), c_)
        for seed in range(20):
            got = route.suggest("software.feature", "lead", "software", "standard", 1, False, state, c_, seed=seed)
            self.assertEqual(got["model"], "opus")
        self.assertIn("no verifying check", got["basis"])

    def test_learns_once_two_arms_have_outcomes(self):
        c_ = ml_cfg()
        state = mlearn.fold(mlearn.empty_state(), outcomes("sonnet", 30) + outcomes("opus", 30, False, 100), c_)
        picks = [route.suggest("software.feature", "lead", "software", "standard", 1, True, state, c_, seed=k)
                 for k in range(40)]
        self.assertGreater(sum(p["model"] == "sonnet" for p in picks), 30)
        self.assertIn("Thompson on 60 outcomes over 2 arms", picks[0]["basis"])

    def test_reproducible_with_seed(self):
        c_ = ml_cfg()
        state = mlearn.fold(mlearn.empty_state(), outcomes("sonnet", 10) + outcomes("opus", 10, start=50), c_)
        a = route.suggest("software.feature", "lead", "software", "standard", 1, True, state, c_, seed=42)
        self.assertEqual(a, route.suggest("software.feature", "lead", "software", "standard", 1, True, state, c_, seed=42))

    def test_cli_two_lines_with_basis_and_exploration(self):
        parser = argparse.ArgumentParser()
        route.register(parser.add_subparsers())
        with tempfile.TemporaryDirectory() as d:
            for argv in (["route", "fix the typo in the footer", "--seed", "1", "--check", "--project", d],
                         ["route", "what is a bandit?", "--project", d]):
                buf = io.StringIO()
                with redirect_stdout(buf), mock.patch.object(mlearn, "load", return_value=mlearn.empty_state()):
                    args = parser.parse_args(argv)
                    self.assertEqual(args.func(args), 0)
                lines = buf.getvalue().strip().splitlines()
                self.assertTrue(1 <= len(lines) <= 2, lines)
                self.assertIn("model basis:", lines[-1])
                self.assertRegex(lines[-1], r"exploration")
                self.assertRegex(lines[-1], r"\d+")

    def test_cascade_rule(self):
        self.assertTrue(route.cheap_first(0.8, 10, 5, 100))
        self.assertFalse(route.cheap_first(0.1, 10, 5, 100))
        self.assertFalse(route.cheap_first(0.5, 40, 20, 100))
        self.assertFalse(route.cheap_first(0.9, 1, 1, 0))


def brute_assign(tasks, budget):
    best = None
    for combo in itertools.product(*[range(len(t["options"])) for t in tasks]):
        cost = sum(t["options"][k]["cost"] for t, k in zip(tasks, combo))
        q = sum(t["options"][k]["quality"] for t, k in zip(tasks, combo))
        if cost <= budget and (best is None or q > best[0] + 1e-9 or (abs(q - best[0]) <= 1e-9 and cost < best[1])):
            best = (q, cost)
    return best


class Assign(unittest.TestCase):
    def test_matches_brute_force(self):
        for seed in range(60):
            r = random.Random(seed)
            tasks = [{"id": f"t{i}", "options": [
                {"model": m, "effort": e, "cost": r.randint(1, 30), "quality": round(r.random(), 3)}
                for m, e in r.sample([("haiku", "low"), ("sonnet", "medium"), ("opus", "medium"), ("opus", "high")],
                                     r.randint(1, 4))]} for i in range(r.randint(1, 5))]
            budget = r.randint(5, 90)
            got = route.assign(tasks, budget)
            ref = brute_assign(tasks, budget)
            with self.subTest(seed=seed):
                if ref is None:
                    self.assertFalse(got["feasible"])
                    self.assertEqual(got["cost"], sum(min(o["cost"] for o in t["options"]) for t in tasks))
                else:
                    self.assertTrue(got["feasible"])
                    self.assertAlmostEqual(got["quality"], ref[0], places=6)
                    self.assertEqual(got["cost"], ref[1])
                    self.assertEqual(sum(o["cost"] for o in got["choice"].values()), got["cost"])
                    self.assertLessEqual(got["cost"], budget)

    def test_large_budget_is_fast(self):
        tasks = [{"id": f"t{i}", "options": [{"model": "a", "effort": "low", "cost": 100_000 + i, "quality": 0.6},
                                             {"model": "b", "effort": "high", "cost": 400_000 + i, "quality": 0.9}]}
                 for i in range(40)]
        got = route.assign(tasks, 8_000_000)
        self.assertTrue(got["feasible"])
        self.assertLessEqual(got["cost"], 8_000_000)

    def test_bad_input(self):
        for tasks, budget in (([], 10), ([{"id": "a", "options": []}], 10),
                              ([{"id": "a", "options": [{"cost": 1.5, "quality": 1}]}], 10),
                              ([{"id": "a", "options": [{"cost": 1, "quality": 1}]}], -1)):
            with self.assertRaises(ValueError):
                route.assign(tasks, budget)


if __name__ == "__main__":
    unittest.main()
