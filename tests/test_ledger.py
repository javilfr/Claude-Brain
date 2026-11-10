"""Ledger: de-duplication, pricing arithmetic and idempotent capture, on a
hand-written transcript in tests/fixtures/ledger/ (totals worked out below);
close options, used records, and the repair of unclosed sessions."""
import argparse
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import common as c
from engine import ledger, learn

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "ledger"
MAIN = FIX / "sess-1.jsonl"
SUBS = [FIX / "sess-1" / "subagents" / "agent-x.jsonl"]
MODELS = json.loads((ROOT / "memory" / "models.json").read_text())

# msg_1 (opus, kept copy with out 200): 100*4 + 600*5 + 400*8 + 5000*0.2 + 200*20 = 11600 per million
# msg_2 (sonnet, no split):             10*2 + 2000*0.1 + 100*10                  = 1220
# msg_3 (unknown, fallback):            1000*4 + 1000*20                          = 24000
OPUS, SONNET, HELPER = 0.0116, 0.00122, 0.024


class TranscriptTest(unittest.TestCase):
    def test_repeated_message_ids_count_once_largest_output_wins(self):
        t = ledger.read_transcript(MAIN)
        self.assertEqual(len(t["messages"]), 2)  # msg_1 twice, msg_2, synthetic skipped
        opus = next(m for m in t["messages"] if m["model"] == "claude-opus-5-5")
        self.assertEqual(opus["usage"]["out"], 200)
        self.assertEqual(opus["usage"]["thinking"], 50)
        self.assertEqual(t["big_tool_results"], 1)
        self.assertEqual(t["effort"], "medium")

    def test_pricing_arithmetic(self):
        s = ledger.summarise(MAIN, SUBS, MODELS)
        self.assertAlmostEqual(s["models"]["claude-opus-5-5"]["cost"], OPUS, places=9)
        self.assertAlmostEqual(s["models"]["claude-sonnet-5-5"]["cost"], SONNET, places=9)
        self.assertAlmostEqual(s["models"]["mystery-model"]["cost"], HELPER, places=9)
        self.assertAlmostEqual(s["totals"]["cost"], OPUS + SONNET + HELPER, places=9)
        self.assertEqual(s["totals"]["in"], 1110)
        self.assertEqual(s["totals"]["cache_write"], 1000)
        self.assertEqual(s["totals"]["out"], 1300)
        self.assertAlmostEqual(s["cache_read_share"], round(7000 / 8110, 4))
        self.assertAlmostEqual(s["helper_cost_share"], round(HELPER / (OPUS + SONNET + HELPER), 4))
        self.assertEqual(s["helpers"], 1)
        self.assertEqual(s["wall_minutes"], 30.0)
        self.assertEqual((s["first"], s["last"]), ("2026-11-10T10:00:00Z", "2026-11-10T10:30:00Z"))
        self.assertEqual(s["main_model"], "claude-opus-5-5")

    def test_cache_writes_without_split_price_as_five_minute(self):
        u = ledger._usage({"cache_creation_input_tokens": 1000})
        self.assertEqual((u["cache_write_5m"], u["cache_write_1h"]), (1000, 0))
        self.assertAlmostEqual(ledger.price("claude-opus-5-5", u, MODELS), 0.005)

    def test_summary_lines_are_short(self):
        lines = ledger.format_summary("sess-1", ledger.summarise(MAIN, SUBS, MODELS))
        self.assertLessEqual(len(lines), 12)


class CloseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.brain = self.tmp / "brain"
        (self.brain / "memory").mkdir(parents=True)
        for f in ("models.json", "ml_config.json"):
            if (ROOT / "memory" / f).is_file():
                shutil.copy(ROOT / "memory" / f, self.brain / "memory" / f)
        self.proj = self.tmp / "secret-project-name"
        (self.proj / ".brain" / "log").mkdir(parents=True)
        c.write_json(self.proj / ".brain" / "project.json",
                     {"contract": 1, "project": {"id": "proj-xyz", "title": "Secret Title"}, "family": "software",
                      "gates": [{"id": "checks", "kind": "command", "command": "make test"},
                                {"id": "look", "kind": "manual"}]})
        rows = [{"session": "sess-1", "gate": "checks", "exit": 1, "at": "2026-11-10T10:05:00Z", "commit": "abc123"},
                {"session": "sess-1", "gate": "checks", "exit": 0, "at": "2026-11-10T10:15:00Z", "commit": "def456"},
                {"session": "other", "gate": "checks", "exit": 0}]
        (self.proj / ".brain" / "log" / "gates.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        self.env = mock.patch.dict(os.environ, {"BRAIN_NOW": "2026-11-10T11:00:00Z", "HOME": str(self.tmp / "home")})
        self.env.start()
        os.environ.pop("BRAIN_TRANSCRIPT", None)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp)

    def capture(self, **kw):
        return ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj, outcome="ok",
                              classes=["build", "fix"], tier=2, **kw)

    def inbox(self):
        files = list((self.brain / "learning" / "inbox").glob("*.jsonl"))
        self.assertEqual(len(files), 1)
        return files[0], c.read_jsonl(files[0])

    def test_close_is_idempotent_and_keeps_project_private(self):
        """I-05: inbox records carry the family only, never project names,
        paths, notes, gate commands or commit ids."""
        self.capture(used=[("lsn-aa", True)])
        self.capture(note="second run")
        path, recs = self.inbox()
        kinds = sorted(r["kind"] for r in recs)
        self.assertEqual(kinds, ["ledger", "outcome", "outcome", "used"])  # used kept by the second capture
        self.assertEqual(len({r["id"] for r in recs}), 4)
        led = next(r for r in recs if r["kind"] == "ledger")
        self.assertEqual((led["family"], led["task_class"], led["model"]), ("software", "build", "opus"))
        (use,) = [r for r in recs if r["kind"] == "used"]
        self.assertEqual((use["item"], use["followed"]), ("lsn-aa", True))
        self.assertNotIn("helped", use)
        blob = path.read_text()
        for private in ("proj-xyz", "Secret Title", "secret-project-name", "second run", "abc123", "make test"):
            self.assertNotIn(private, blob)
        logs = list((self.proj / ".brain" / "log").glob("*-sess-1.json"))
        self.assertEqual(len(logs), 1)
        run = c.read_json(logs[0])
        self.assertEqual(run["note"], "second run")
        self.assertEqual(len(run["gates"]), 2)

    def test_outcome_fields(self):
        self.capture(declared={"risk": "trivial", "est_tokens": 9000, "est_minutes": 20.0, "explored": True,
                               "propensity": 0.25})
        _, recs = self.inbox()
        out = [r for r in recs if r["kind"] == "outcome"]
        self.assertEqual([r["task_class"] for r in out], ["build", "fix"])
        o = out[0]
        for field in ("id", "task_class", "family", "tier", "risk", "model", "effort", "has_check", "passed",
                      "first_pass", "rework", "tokens", "minutes", "est_tokens", "est_minutes", "explored", "propensity"):
            self.assertIn(field, o)
        self.assertEqual((o["passed"], o["first_pass"], o["rework"]), (True, False, 1))  # red, then green
        self.assertEqual((o["model"], o["model_id"], o["effort"]), ("opus", "claude-opus-5-5", "medium"))
        self.assertEqual((o["risk"], o["est_tokens"], o["est_minutes"], o["explored"], o["propensity"]),
                         ("trivial", 9000, 20.0, True, 0.25))
        self.assertTrue(o["has_check"])
        self.assertEqual((o["family"], o["tier"], o["minutes"]), ("software", 2, 15.0))
        self.assertEqual(o["evidence"], ["gate:checks exit 1"])
        self.assertEqual([g["exit"] for g in o["gate_runs"]], [1, 0])
        self.assertNotEqual(o["gate_runs"][0]["commit"], o["gate_runs"][1]["commit"])
        # A later capture without options (the Stop hook) keeps what close declared.
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj)
        _, recs = self.inbox()
        again = [r for r in recs if r["kind"] == "outcome"]
        self.assertEqual([r["task_class"] for r in again], ["build", "fix"])
        self.assertEqual((again[0]["risk"], again[0]["est_tokens"], again[0]["id"]), ("trivial", 9000, o["id"]))

    def test_has_check_needs_a_command_gate(self):
        m = c.load_manifest(self.proj)
        m["gates"] = [{"id": "checks", "kind": "command", "command": "  "}]
        c.write_json(self.proj / ".brain" / "project.json", m)
        self.capture()
        _, recs = self.inbox()
        self.assertFalse(next(r for r in recs if r["kind"] == "outcome")["has_check"])
        self.capture(declared={"has_check": True})
        _, recs = self.inbox()
        self.assertTrue(next(r for r in recs if r["kind"] == "outcome")["has_check"])

    def test_close_after_consolidation_does_not_count_twice(self):
        self.capture()
        delta, rejected = learn.build_consolidation(self.brain)
        self.assertIsNotNone(delta, rejected)
        ok, lines = learn.apply_delta(delta, self.brain)
        self.assertTrue(ok, lines)
        r = self.capture()
        self.assertTrue(r["skipped"])
        self.assertEqual(len(list((self.brain / "learning" / "inbox").glob("*.jsonl"))), 1)

    def test_close_without_project_still_records_ledger(self):
        r = ledger.capture(self.brain, "sess-1", MAIN, SUBS, None)
        self.assertEqual(r["run_record"], "")
        recs = c.read_jsonl(r["inbox"])
        self.assertEqual([x["kind"] for x in recs], ["ledger"])
        self.assertEqual(recs[0]["family"], "")

    def close_cmd(self, *argv):
        import io
        from contextlib import redirect_stdout
        p = argparse.ArgumentParser(prog="brain")
        ledger.register(p.add_subparsers())
        args = p.parse_args(["close", "--project", str(self.proj), *argv])
        args.brain_root = self.brain
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"BRAIN_SESSION_ID": "sess-1"}), redirect_stdout(buf):
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            code = args.func(args)
        return code, buf.getvalue()

    def test_close_without_transcript_records_outcomes_with_unknown_usage(self):
        """S6: no transcript still records the gate outcomes and clears the marker."""
        ledger.mark_open(self.proj, "sess-1")
        with mock.patch.dict(os.environ, {"BRAIN_TRANSCRIPT": str(self.tmp / "gone.jsonl")}):
            code, out = self.close_cmd("--outcome", "ok", "--class", "build", "--tier", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("token usage unknown", out)
        self.assertLessEqual(len(out.splitlines()), 15)
        _, recs = self.inbox()
        led = next(r for r in recs if r["kind"] == "ledger")
        (o,) = [r for r in recs if r["kind"] == "outcome"]
        self.assertEqual((led["usage"], led["models"]), ("unknown", {}))
        self.assertEqual((o["usage"], o["tokens"], o["cost"], o["minutes"]), ("unknown", None, None, None))
        self.assertEqual((o["passed"], o["first_pass"], o["rework"]), (True, False, 1))
        self.assertFalse((self.proj / ".brain" / "log" / ledger.OPEN_MARKER).exists())

    def test_request_words_are_salted_hashes_kept_with_the_rule_tier(self):
        """S9: sizing data from close: salted word hashes and the rule tier, never the words."""
        request = "Fix the colour of the login button"
        with mock.patch.dict(os.environ, {"BRAIN_TRANSCRIPT": str(MAIN)}):
            code, out = self.close_cmd("--class", "build", "--tier", "1", "--request", request)
            self.assertEqual(code, 0, out)
            _, recs = self.inbox()
            (o,) = [r for r in recs if r["kind"] == "outcome"]
            self.assertIsInstance(o["rule_tier"], int)
            self.assertTrue(o["words"] and all(len(w) == 12 and int(w, 16) >= 0 for w in o["words"]))
            path, _ = self.inbox()
            blob = path.read_text()
            for word in ("colour", "login", "button", request):
                self.assertNotIn(word, blob)
            salt = (self.proj / ".brain" / "log" / "salt").read_text().strip()
            self.assertRegex(salt, r"^[0-9a-f]{32}$")
            self.assertFalse(list(self.brain.rglob("salt")), "the salt stays in the project")
            self.assertEqual(o["words"], learn.hashed_words(request, salt))
            self.assertNotEqual(o["words"], learn.hashed_words(request, "0" * 32))
            # A later capture without --request (the Stop hook) keeps the sizing fields.
            ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj)
            _, recs = self.inbox()
            self.assertEqual(next(r for r in recs if r["kind"] == "outcome")["words"], o["words"])



class CloseCommandTest(unittest.TestCase):
    def parser(self):
        p = argparse.ArgumentParser(prog="brain")
        ledger.register(p.add_subparsers())
        return p

    def test_used_is_parsed_and_helped_is_never_accepted(self):
        """I-07: whether an item helped cannot be declared on the command line."""
        args = self.parser().parse_args(["close", "--used", "lsn-aa:1", "--used", "fact-bb:0"])
        self.assertEqual(ledger.parse_used(args.used), ([("lsn-aa", True), ("fact-bb", False)], ""))
        for bad in (["close", "--helped", "lsn-aa"], ["close", "--used", "lsn-aa:1", "--helped", "1"]):
            with self.subTest(bad), mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                self.parser().parse_args(bad)
        for value in ("lsn-aa:yes", "lsn-aa", "BAD:1", "lsn-aa:1:1"):
            with self.subTest(value):
                self.assertTrue(ledger.parse_used([value])[1])

    def test_bad_used_value_is_one_line_and_exit_2(self):
        args = self.parser().parse_args(["close", "--used", "lsn-aa:maybe"])
        with mock.patch("builtins.print") as out:
            self.assertEqual(args.func(args), 2)
        self.assertEqual(out.call_count, 1)


class UnclosedSessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.brain = self.tmp / "brain"
        (self.brain / "memory").mkdir(parents=True)
        shutil.copy(ROOT / "memory" / "models.json", self.brain / "memory" / "models.json")
        self.proj = self.tmp / "proj"
        (self.proj / ".brain").mkdir(parents=True)
        c.write_json(self.proj / ".brain" / "project.json", {"contract": 1, "family": "data"})
        self.home = self.tmp / "home"
        self.env = mock.patch.dict(os.environ, {"BRAIN_NOW": "2026-11-10T11:00:00Z", "HOME": str(self.home)})
        self.env.start()
        os.environ.pop("BRAIN_TRANSCRIPT", None)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp)

    def marker(self):
        return c.read_json(self.proj / ".brain" / "log" / ledger.OPEN_MARKER)

    def test_mark_open_returns_only_another_sessions_marker(self):
        self.assertIsNone(ledger.mark_open(self.proj, "a"))
        self.assertEqual(self.marker()["session"], "a")
        self.assertIsNone(ledger.mark_open(self.proj, "a"))  # same session booting again
        prev = ledger.mark_open(self.proj, "b")
        self.assertEqual(prev, {"session": "a", "at": "2026-11-10T11:00:00Z"})
        self.assertEqual(self.marker()["session"], "b")

    def test_capture_clears_only_its_own_marker(self):
        ledger.mark_open(self.proj, "other")
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj)
        self.assertEqual(self.marker()["session"], "other")
        ledger.mark_open(self.proj, "sess-1")
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj)
        self.assertIsNone(self.marker())

    def test_repair_from_transcript_on_disk(self):
        tdir = self.home / ".claude" / "projects" / "slug"
        tdir.mkdir(parents=True)
        shutil.copy(MAIN, tdir / "sess-1.jsonl")
        ledger.mark_open(self.proj, "sess-1")
        prev = ledger.mark_open(self.proj, "sess-2")
        line = ledger.repair_unclosed(self.proj, prev, self.brain)
        self.assertIn("recorded it from its transcript", line)
        self.assertNotIn("\n", line)
        (rec,) = c.read_jsonl(next((self.brain / "learning" / "inbox").glob("*-sess-1.jsonl")))
        self.assertEqual((rec["kind"], rec["family"]), ("ledger", "data"))
        self.assertIn("claude-opus-5-5", rec["models"])
        self.assertEqual(self.marker()["session"], "sess-2")  # the new session stays open

    def test_repair_without_transcript_records_the_gap(self):
        line = ledger.repair_unclosed(self.proj, {"session": "gone-1", "at": "2026-11-09T09:00:00Z"}, self.brain)
        self.assertIn("transcript is gone", line)
        (rec,) = c.read_jsonl(next((self.brain / "learning" / "inbox").glob("*-gone-1.jsonl")))
        self.assertEqual((rec["kind"], rec["unrecorded"], rec["started"]), ("ledger", True, "2026-11-09T09:00:00Z"))
        self.assertEqual(len(rec["id"]), 16)
        ledger.repair_unclosed(self.proj, {"session": "gone-1", "at": "2026-11-09T09:00:00Z"}, self.brain)
        self.assertEqual(len(c.read_jsonl(next((self.brain / "learning" / "inbox").glob("*-gone-1.jsonl")))), 1)


if __name__ == "__main__":
    unittest.main()
