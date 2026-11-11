"""Parkinson's law as an algorithm: time budgets learned from past runs."""
import json
import tempfile
import unittest
from pathlib import Path

from engine import gate, hr, schedule, timebox


class Allot(unittest.TestCase):
    def test_no_runs_keeps_the_old_default(self):
        a = timebox.allot(None, 3600, floor=30)
        self.assertEqual(a["limit"], 3600)
        self.assertIsNone(a["target"])

    def test_an_estimate_sets_target_and_twice_it_as_stop(self):
        a = timebox.allot({}, 3600, est=20)
        self.assertEqual((a["target"], a["limit"]), (20, 40))

    def test_few_runs_allow_three_times_the_slowest(self):
        a = timebox.allot({"d": [10, 12]}, 3600, floor=1)
        self.assertEqual(a["limit"], 36)

    def test_enough_runs_give_median_target_and_q90_stop(self):
        a = timebox.allot({"d": [10, 11, 12, 13, 14, 15]}, 3600, floor=1)
        self.assertEqual(a["target"], 12.5)
        self.assertEqual(a["limit"], 15 * timebox.SAFETY)  # q90 of 6 is the largest
        self.assertLess(a["limit"], 3600)

    def test_the_budget_shrinks_as_the_work_gets_faster(self):
        slow = timebox.allot({"d": [100] * 20}, 3600, floor=1)
        faster = timebox.allot({"d": [100] * 5 + [40] * 15}, 3600, floor=1)
        self.assertLess(faster["target"], slow["target"])

    def test_each_timeout_in_a_row_doubles_the_stop_up_to_the_cap(self):
        base = timebox.allot({"d": [10] * 5}, 3600, floor=1)["limit"]
        self.assertEqual(timebox.allot({"d": [10] * 5, "to": 1}, 3600, floor=1)["limit"], base * 2)
        self.assertEqual(timebox.allot({"d": [10] * 5, "to": 2}, 3600, floor=1)["limit"], base * 4)
        self.assertEqual(timebox.allot({"d": [10] * 5, "to": 30}, 3600, floor=1)["limit"], 3600)

    def test_floor_and_explicit(self):
        self.assertEqual(timebox.allot({"d": [0.1] * 6}, 3600, floor=30)["limit"], 30)
        self.assertEqual(timebox.allot({"d": [10] * 6}, 3600, explicit=7)["limit"], 7)
        self.assertEqual(timebox.allot({"d": [10] * 6}, 3600, floor=30, explicit=0)["limit"], 0)


class Store(unittest.TestCase):
    def test_timeout_is_censored_and_a_success_resets_the_streak(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tb.json"
            timebox.observe(p, "k", 5)
            rec = timebox.observe(p, "k", 0, timed_out=True)
            self.assertEqual((rec["d"], rec["to"]), ([5], 1))
            rec = timebox.observe(p, "k", 6)
            self.assertEqual((rec["d"], rec["to"]), ([5, 6], 0))

    def test_window_and_key_cap(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tb.json"
            for i in range(timebox.WINDOW + 5):
                timebox.observe(p, "k", i)
            self.assertEqual(len(timebox.load(p)["k"]["d"]), timebox.WINDOW)
            data = {f"x{i}": {"d": [1]} for i in range(timebox.KEYS_CAP)}
            p.write_text(json.dumps(data))
            timebox.observe(p, "new", 1)
            data = timebox.load(p)
            self.assertEqual(len(data), timebox.KEYS_CAP)
            self.assertIn("new", data)
            self.assertNotIn("x0", data)


class Commands(unittest.TestCase):
    def test_successful_runs_teach_the_command_its_timebox(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            for _ in range(timebox.MIN_N):
                r = gate.run_filtered("true", proj, proj)
                self.assertEqual(r["exit"], 0)
            self.assertEqual(r["timebox"], 3600)  # the first runs still had the default
            r = gate.run_filtered("true", proj, proj)
            self.assertEqual(r["timebox"], timebox.COMMAND_FLOOR)  # now the learned stop, at the floor
            self.assertTrue((proj / ".brain" / "log" / "timebox.json").is_file())

    def test_failures_do_not_shorten_the_timebox(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            for _ in range(timebox.MIN_N + 1):
                gate.run_filtered("false", proj, proj)
            self.assertEqual(gate.run_filtered("false", proj, proj)["timebox"], 3600)

    def test_a_timeout_is_recorded_as_a_streak(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            r = gate.run_filtered("sleep 3", proj, proj, timeout=0.3)
            self.assertEqual(r["exit"], 124)
            data = timebox.load(timebox.store_path(proj))
            self.assertEqual(data[timebox.key_for("cmd", "sleep 3")]["to"], 1)

    def test_the_live_wait_is_learned_and_capped(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            self.assertEqual(gate.live_wait(proj, "https://x.example")[1]["limit"], gate.LIVE_WAIT)
            self.assertEqual(gate.live_wait(proj, "https://x.example", 0)[1]["limit"], 0)
            key = timebox.key_for("live", "https://x.example")
            for s in (5, 6, 7, 8, 9):
                timebox.observe(timebox.store_path(proj), key, s)
            self.assertLess(gate.live_wait(proj, "https://x.example")[1]["limit"], gate.LIVE_WAIT)


class Minutes(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(timebox.for_size(1, "general")["target"] > 0, True)
        self.assertLess(timebox.for_size(0)["stop"], timebox.for_size(1)["stop"])
        self.assertIsNone(timebox.for_size(2))
        self.assertIsNone(timebox.for_size("x"))

    def test_ticket_box_and_packet(self):
        self.assertEqual(timebox.ticket_box({"est": 30}), {"target": 30, "stop": 60})
        self.assertEqual(timebox.ticket_box({"est": 30, "stop": 45}), {"target": 30, "stop": 45})
        self.assertIsNone(timebox.ticket_box({}))
        plan = {"tickets": [{"id": "A", "goal": "Do A.", "est": 30, "accept": "true"}]}
        lines = schedule.packet(plan, "A")
        self.assertTrue(any(l.startswith("Timebox: aim for 30 min; at 60 min stop") for l in lines))

    def test_helper_time_wage_tightens_with_evidence(self):
        hc = hr.cfg_of()
        fresh = hr.time_wage("M", None, {}, hc)
        self.assertEqual((fresh["target"], fresh["stop"]), (20, 40))
        state = {}
        for _ in range(hc["min_settled"]):
            hr.fold_hire(state, {}, {"size": "M", "band_minutes": 20, "actual_minutes": 10})
        tight = hr.time_wage("M", None, state, hc)
        self.assertEqual(tight["target"], 10)
        self.assertGreaterEqual(tight["stop"], 15)
        self.assertLess(tight["stop"], fresh["stop"])

    def test_brief_carries_the_timebox(self):
        text = hr.compose_brief(None, "builder", "Do X.", "", [], [], "true", "opus", "high", "n",
                                timebox={"target": 20, "stop": 40})
        self.assertIn("<timebox>Aim to finish in about 20 minutes. At 40 minutes, stop", text)
        self.assertNotIn("<timebox>", hr.compose_brief(None, "builder", "Do X.", "", [], [], "true", "opus", "high", "n"))


if __name__ == "__main__":
    unittest.main()
