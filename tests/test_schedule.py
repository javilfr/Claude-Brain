"""Tests for engine/schedule.py: validity, never worse than critical path,
determinism, optimality against brute force on tiny plans, calibration of
estimates from learned ratios, and the delegation packet."""
import io
import itertools
import json
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from engine import mlearn
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


def calibrated_state(ratio=2.0, n=10):
    """Learning state where software.feature tasks take ``ratio`` times their estimate."""
    rows = [{"kind": "outcome", "id": f"o{i}", "at": f"2026-01-01T{i:04d}", "task_class": "software.feature",
             "family": "software", "model": "opus", "effort": "medium", "has_check": True, "passed": True,
             "tokens": int(1000 * ratio), "est_tokens": 1000, "minutes": 10 * ratio, "est_minutes": 10}
            for i in range(n)]
    return mlearn.fold(mlearn.empty_state(), rows, mlearn.config())


def run_cli(argv, state=None):
    parser = __import__("argparse").ArgumentParser()
    s.register(parser.add_subparsers())
    buf = io.StringIO()
    with redirect_stdout(buf), mock.patch.object(mlearn, "load", return_value=state or mlearn.empty_state()):
        args = parser.parse_args(argv)
        code = args.func(args)
    return code, buf.getvalue().strip().splitlines()


class Calibration(unittest.TestCase):
    PLAN = {"agents": 2, "tickets": [
        {"id": "a", "est": 30, "class": "software.feature", "tokens": 5000},
        {"id": "b", "est": 30, "deps": ["a"]},
        {"id": "c", "est": 30, "class": "knowledge.research"}]}

    def test_scales_only_tickets_with_a_calibrated_class(self):
        data, info = s.calibrate_plan(self.PLAN, calibrated_state(2.0), mlearn.config())
        est = {t["id"]: t["est"] for t in data["tickets"]}
        self.assertAlmostEqual(est["a"], 60, delta=0.5)
        self.assertEqual(est["b"], 30)
        self.assertEqual(est["c"], 30)  # its family has no outcomes: the prior leaves it alone
        self.assertAlmostEqual(data["tickets"][0]["tokens"], 10_000, delta=10)
        self.assertEqual(info, {"tickets": 1, "outcomes": 10})
        self.assertEqual(self.PLAN["tickets"][0]["est"], 30, "the input plan is not changed")

    def test_below_min_n_changes_nothing(self):
        data, info = s.calibrate_plan(self.PLAN, calibrated_state(2.0, n=4), mlearn.config())
        self.assertEqual(data, self.PLAN)
        self.assertEqual(info["tickets"], 0)

    def test_cli_prints_one_calibration_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "plan.json"
            p.write_text(json.dumps(self.PLAN))
            code, lines = run_cli(["plan", "schedule", str(p)], calibrated_state(2.0))
            self.assertEqual(code, 0)
            self.assertLessEqual(len(lines), 15)
            self.assertEqual(sum("calibration applied" in l for l in lines), 1)
            self.assertIn("10 outcomes", lines[-1])
            self.assertIn("makespan 90", "\n".join(lines))
            code, lines = run_cli(["plan", "schedule", str(p)])
            self.assertFalse(any("calibration" in l for l in lines))
            self.assertIn("makespan 60", "\n".join(lines))


class Packet(unittest.TestCase):
    PLAN = {"tickets": [
        {"id": "T-1", "title": "Build the parser", "files": ["src/parse.py", "tests/test_parse.py"],
         "accept": "python3 -m unittest tests.test_parse", "status": "done"},
        {"id": "T-2", "goal": "Wire the parser into the CLI", "reason": "the owner asked for one command",
         "deps": ["T-1"], "files": [f"src/f{i}.py" for i in range(30)], "interfaces": ["parse(text) -> dict"],
         "accept": "python3 -m unittest tests.test_cli"},
        {"id": "T-3", "title": "No check yet"}]}

    def write(self, d):
        p = Path(d) / "tickets.json"
        p.write_text(json.dumps(self.PLAN))
        return str(p)

    def test_brief_contents_and_length(self):
        with tempfile.TemporaryDirectory() as d:
            code, lines = run_cli(["plan", "packet", self.write(d), "T-2"])
        self.assertEqual(code, 0)
        self.assertLessEqual(len(lines), 25)
        text = "\n".join(lines)
        for part in ("Wire the parser into the CLI", "Why: the owner asked for one command", "- src/f0.py",
                     "and 21 more", "Depends on: T-1 (done)", "Interfaces: parse(text) -> dict",
                     "Acceptance command: python3 -m unittest tests.test_cli",
                     "at most 250 words: what changed, the acceptance command and its result line, "
                     "anything that differs from the brief"):
            self.assertIn(part, text)

    def test_missing_acceptance_is_flagged(self):
        lines = s.packet(self.PLAN, "T-3")
        self.assertIn("Acceptance command: none recorded", "\n".join(lines))
        self.assertIn("Depends on: nothing", lines)

    def test_unknown_id_one_line_exit_1(self):
        with tempfile.TemporaryDirectory() as d:
            code, lines = run_cli(["plan", "packet", self.write(d), "T-9"])
        self.assertEqual(code, 1)
        self.assertEqual(len(lines), 1)
        self.assertIn("T-9", lines[0])

    def test_real_ticket_file(self):
        real = Path(__file__).resolve().parents[1] / "docs" / "plan" / "tickets.json"
        data = json.loads(real.read_text())
        lines = s.packet(data, data["tickets"][0]["id"])
        self.assertLessEqual(len(lines), 25)
        self.assertTrue(any(l.startswith("Acceptance command: ") for l in lines))


if __name__ == "__main__":
    unittest.main()
