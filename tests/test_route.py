"""Tests for engine/route.py: sizing on the labelled set, Thompson sampling,
the cascade rule, and the exact assignment against brute force."""
import itertools
import json
import random
import unittest
from pathlib import Path

from engine import route

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


class Suggest(unittest.TestCase):
    def test_defaults_without_enough_outcomes(self):
        stats = {"classes": {"software.feature": {"sonnet/medium": {"pass": 9, "fail": 1}, "opus/medium": {"pass": 3}}}}
        got = route.suggest("software.feature", "builder", stats, CFG, seed=1)
        self.assertEqual((got["model"], got["effort"]), ("sonnet", "medium"))
        self.assertIn("default", got["basis"])

    def test_thompson_prefers_cheap_option_that_passes(self):
        stats = {"classes": {"software.feature": {
            "sonnet/medium": {"pass": 40, "fail": 4, "tokens": 44 * 100_000},
            "opus/high": {"pass": 42, "fail": 2, "tokens": 44 * 300_000}}}}
        picks = [route.suggest("software.feature", "builder", stats, CFG, seed=k)["model"] for k in range(200)]
        # Cheaper and nearly as good: chosen most of the time, while the
        # stronger option is still tried now and then (that is the learning).
        self.assertGreater(picks.count("sonnet"), 100)
        self.assertGreater(picks.count("opus"), 0)
        got = route.suggest("software.feature", "builder", stats, CFG, seed=3)
        self.assertIn("88 outcomes over 2 options", got["basis"])

    def test_thompson_avoids_option_that_fails(self):
        stats = {"software.bugfix": {
            "haiku/low": {"pass": 3, "fail": 17, "tokens": 20 * 10_000},
            "sonnet/medium": {"pass": 18, "fail": 2, "tokens": 20 * 100_000}}}
        picks = [route.suggest("software.bugfix", "builder", stats, CFG, seed=k)["model"] for k in range(200)]
        self.assertGreater(picks.count("sonnet"), 190)

    def test_reproducible_with_seed(self):
        stats = {"classes": {"x": {"a/low": {"pass": 5, "fail": 5}, "b/low": {"pass": 5, "fail": 5}}}}
        self.assertEqual(route.suggest("x", "lead", stats, CFG, seed=42), route.suggest("x", "lead", stats, CFG, seed=42))

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
