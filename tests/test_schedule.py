"""Tests for engine/schedule.py: validity, never worse than critical path,
determinism, and optimality against brute force on tiny plans."""
import io
import itertools
import json
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from engine import schedule as s

CASES = Path(__file__).resolve().parents[1] / "evals" / "schedule_cases"


def check_valid(test, data, out):
    """Every dependency finished first; no agent runs two tickets at once; no
    two conflicting tickets overlap; never more tickets at once than agents."""
    plan = s.load_plan(data, out["agents"])
    rows = {r["id"]: r for r in out["timeline"]}
    test.assertEqual(set(rows), set(plan["ids"]))
    for t in plan["tickets"]:
        for d in t["deps"]:
            test.assertGreaterEqual(rows[t["id"]]["start"] + 1e-9, rows[d]["end"], f"{t['id']} before {d}")
    items = list(rows.values())
    for a, b in itertools.combinations(items, 2):
        overlap = a["start"] < b["end"] - 1e-9 and b["start"] < a["end"] - 1e-9
        if not overlap:
            continue
        test.assertNotEqual(a["agent"], b["agent"], f"{a['id']} and {b['id']} share an agent")
        i, j = plan["ids"].index(a["id"]), plan["ids"].index(b["id"])
        test.assertFalse(plan["conflict"][i][j], f"{a['id']} and {b['id']} conflict but overlap")
    test.assertLessEqual(max(r["agent"] for r in items), out["agents"])
    test.assertAlmostEqual(out["makespan"], max(r["end"] for r in items))


def reference_optimum(data, agents):
    """Brute force, written independently of the engine: every priority order,
    each decoded on an integer time grid by trying start times one unit apart.
    The best active schedule over all orders is an optimal schedule."""
    plan = s.load_plan(data, agents)
    est = [int(e) for e in plan["est"]]
    n = len(est)
    horizon = sum(est)
    best = horizon
    for perm in itertools.permutations(range(n)):
        start = [None] * n
        busy = [[] for _ in range(horizon + 1)]
        todo = list(perm)
        while todo:
            i = next(k for k in todo if all(start[d] is not None for d in plan["deps"][k]))
            todo.remove(i)
            t = max((start[d] + est[d] for d in plan["deps"][i]), default=0)
            while True:
                slots = range(t, t + est[i])
                if all(len(busy[u]) < agents and not any(plan["conflict"][i][j] for j in busy[u]) for u in slots):
                    break
                t += 1
            start[i] = t
            for u in range(t, t + est[i]):
                busy[u].append(i)
        best = min(best, max(start[k] + est[k] for k in range(n)))
    return best


def random_plan(seed, n, nfiles=5):
    r = random.Random(seed)
    tickets = []
    for i in range(n):
        tickets.append({"id": f"t{i}", "est": r.choice([1, 2, 2, 3, 4, 6]),
                        "deps": [f"t{j}" for j in range(i) if r.random() < 0.2],
                        "files": [f"src/f{k}" for k in r.sample(range(nfiles), r.randint(0, 2))]})
    return {"agents": 2, "tickets": tickets}


class ScheduleCases(unittest.TestCase):
    def cases(self):
        files = sorted(CASES.glob("*.json"))
        self.assertGreaterEqual(len(files), 3)
        return [(f.name, json.loads(f.read_text())) for f in files]

    def test_cases_valid_and_never_worse(self):
        for name, data in self.cases():
            with self.subTest(case=name):
                ann = s.schedule(data, seed=0)
                cp = s.schedule(data, anneal=False)
                check_valid(self, data, ann)
                check_valid(self, data, cp)
                self.assertLessEqual(ann["makespan"], cp["makespan"])
                self.assertGreaterEqual(ann["makespan"], ann["lower_bound"])
                exp = data.get("expect", {})
                if exp.get("annealed_lt_cp"):
                    self.assertLess(ann["makespan"], cp["makespan"])
                    self.assertEqual(ann["method"], "annealed, quantum-inspired")
                if "optimal" in exp:
                    self.assertEqual(ann["makespan"], exp["optimal"])

    def test_cases_match_brute_force(self):
        for name, data in self.cases():
            if len(data["tickets"]) > 8:
                continue
            with self.subTest(case=name):
                self.assertEqual(s.schedule(data)["makespan"], reference_optimum(data, data["agents"]))

    def test_file_conflicts_never_overlap(self):
        data = json.loads((CASES / "conflicts.json").read_text())
        out = s.schedule(data)
        rows = {r["id"]: r for r in out["timeline"]}
        for a, b in (("ui-grid", "ui-viewer"), ("api", "api-auth")):
            ra, rb = rows[a], rows[b]
            self.assertTrue(ra["end"] <= rb["start"] or rb["end"] <= ra["start"], (a, b))

    def test_deterministic_for_seed(self):
        data = random_plan(11, 12)
        data["agents"] = 3
        a, b = s.schedule(data, seed=5), s.schedule(data, seed=5)
        self.assertEqual(a, b)

    def test_random_tiny_plans_optimal(self):
        """Tiny plans (<= 7 tickets, 2 agents): exactly the brute-force optimum
        (critical-path order alone misses it on 3 of these 25)."""
        for seed in range(25):
            data = random_plan(seed, random.Random(seed).randint(4, 7))
            out = s.schedule(data, seed=seed)
            check_valid(self, data, out)
            self.assertLessEqual(out["makespan"], s.schedule(data, anneal=False)["makespan"])
            opt = reference_optimum(data, 2)
            self.assertEqual(out["makespan"], opt, f"seed {seed}")

    def test_lower_bound_parts(self):
        data = {"agents": 4, "tickets": [
            {"id": "a", "est": 3, "files": ["x/"]}, {"id": "b", "est": 3, "files": ["x/y.ts"]},
            {"id": "c", "est": 3, "files": ["x/z.ts"]}, {"id": "d", "est": 1, "files": ["x/y.ts"]}]}
        out = s.schedule(data)
        self.assertEqual(out["lower_bound"], 7)  # a, b, d all touch x/y.ts or its folder
        self.assertEqual(out["lower_bound_kind"], "conflicting tickets")
        check_valid(self, data, out)

    def test_validation_errors(self):
        bad = [
            ({"tickets": [{"id": "a", "est": 1}, {"id": "a", "est": 2}]}, "duplicate"),
            ({"tickets": [{"id": "a", "est": 1, "deps": ["zz"]}]}, "unknown dependency zz"),
            ({"tickets": [{"id": "a", "est": 1, "deps": ["b"]}, {"id": "b", "est": 1, "deps": ["a"]}]}, "cycle"),
            ({"tickets": [{"id": "a", "est": 0}]}, "est"),
            ({"tickets": "nope"}, "tickets"),
            ({"agents": 0, "tickets": []}, "agents"),
        ]
        for data, word in bad:
            with self.subTest(word=word):
                with self.assertRaises(s.PlanError) as cm:
                    s.schedule(data)
                self.assertIn(word, str(cm.exception))
                self.assertNotIn("\n", str(cm.exception))

    def test_tokens_report(self):
        data = {"agents": 2, "helper_start_tokens": 1000, "tickets": [
            {"id": "a", "est": 1, "tokens": 500}, {"id": "b", "est": 1, "tokens": 700}]}
        tok = s.schedule(data)["tokens"]
        self.assertEqual(tok["work"], 1200)
        self.assertEqual(tok["parallel_total"], 3200)
        self.assertEqual(tok["sequential_total"], 2200)

    def test_cli_output(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "plan.json"
            p.write_text((CASES / "anneal_beats_cp.json").read_text())
            parser = __import__("argparse").ArgumentParser()
            s.register(parser.add_subparsers())
            buf = io.StringIO()
            with redirect_stdout(buf):
                args = parser.parse_args(["plan", "schedule", str(p), "--seed", "1"])
                code = args.func(args)
            lines = buf.getvalue().strip().splitlines()
            self.assertEqual(code, 0)
            self.assertTrue(lines[0].startswith("t=0 A1 "))
            self.assertIn("method: annealed, quantum-inspired", lines[-1])
            self.assertLessEqual(len(lines), 15)
            p.write_text("{not json")
            buf = io.StringIO()
            with redirect_stdout(buf):
                args = parser.parse_args(["plan", "schedule", str(p)])
                self.assertEqual(args.func(args), 2)
            self.assertEqual(len(buf.getvalue().strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
