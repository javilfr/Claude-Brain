"""Ledger: de-duplication, pricing arithmetic and idempotent capture, on a
hand-written transcript in tests/fixtures/ledger/ (totals worked out below)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

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
        shutil.copy(ROOT / "memory" / "models.json", self.brain / "memory" / "models.json")
        self.proj = self.tmp / "secret-project-name"
        (self.proj / ".brain" / "log").mkdir(parents=True)
        c.write_json(self.proj / ".brain" / "project.json",
                     {"contract": 1, "project": {"id": "proj-xyz", "title": "Secret Title"}, "family": "software"})
        rows = [{"session": "sess-1", "gate": "checks", "exit_code": 1, "at": "2026-11-10T10:05:00Z"},
                {"session": "sess-1", "gate": "checks", "exit_code": 0, "at": "2026-11-10T10:15:00Z"},
                {"session": "other", "gate": "checks", "exit_code": 0}]
        (self.proj / ".brain" / "log" / "gates.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        os.environ["BRAIN_NOW"] = "2026-11-10T11:00:00Z"

    def tearDown(self):
        os.environ.pop("BRAIN_NOW", None)
        shutil.rmtree(self.tmp)

    def capture(self, **kw):
        return ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj, outcome="ok",
                              classes=["build", "fix"], tier=2, **kw)

    def test_close_is_idempotent_and_keeps_project_private(self):
        self.capture()
        self.capture(note="second run")
        inbox = list((self.brain / "learning" / "inbox").glob("*.jsonl"))
        self.assertEqual(len(inbox), 1)
        recs = c.read_jsonl(inbox[0])
        kinds = sorted(r["kind"] for r in recs)
        self.assertEqual(kinds, ["ledger", "outcome", "outcome"])
        led = next(r for r in recs if r["kind"] == "ledger")
        self.assertEqual(led["family"], "software")
        self.assertEqual(led["task_class"], "build")
        out = [r for r in recs if r["kind"] == "outcome"]
        self.assertTrue(all(r["passed"] is False for r in out))  # first run of the gate failed
        self.assertEqual(out[0]["evidence"], ["gate:checks exit 1"])
        blob = inbox[0].read_text()
        for private in ("proj-xyz", "Secret Title", "secret-project-name", "second run"):
            self.assertNotIn(private, blob)
        logs = list((self.proj / ".brain" / "log").glob("*-sess-1.json"))
        self.assertEqual(len(logs), 1)
        run = c.read_json(logs[0])
        self.assertEqual(run["note"], "second run")
        self.assertEqual(len(run["gates"]), 2)

    def test_close_after_consolidation_does_not_count_twice(self):
        self.capture()
        delta, _ = learn.build_consolidation(self.brain)
        ok, _ = learn.apply_delta(delta, self.brain)
        self.assertTrue(ok)
        r = self.capture()
        self.assertTrue(r["skipped"])
        self.assertEqual(len(list((self.brain / "learning" / "inbox").glob("*.jsonl"))), 1)

    def test_close_without_project_still_records_ledger(self):
        r = ledger.capture(self.brain, "sess-1", MAIN, SUBS, None)
        self.assertEqual(r["run_record"], "")
        recs = c.read_jsonl(r["inbox"])
        self.assertEqual([x["kind"] for x in recs], ["ledger"])
        self.assertEqual(recs[0]["family"], "")


if __name__ == "__main__":
    unittest.main()
