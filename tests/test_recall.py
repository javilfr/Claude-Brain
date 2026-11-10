"""Tests for engine/recall.py on a temporary brain (never the real memory)."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import recall as r


def item(iid, text, **kw):
    base = {"id": iid, "type": "rule", "scope": "global", "text": text, "trust": "observed",
            "status": "active", "importance": 2, "created": "2026-11-01", "evidence": ["test"], "class": []}
    base.update(kw)
    return base


class RecallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "brain"
        (self.root / "memory").mkdir(parents=True)
        (self.root / "owner").mkdir()
        self.env = mock.patch.dict(os.environ, {"BRAIN_NOW": "2026-11-10T12:00:00Z"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write(self, rel, rows):
        p = self.root / rel if not str(rel).startswith("/") else Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")

    def ids(self, query, **kw):
        return [x["id"] for x in r.recall(query, brain_root=self.root, **kw)]

    def test_relevance_ordering_and_tags_count(self):
        self.write("memory/items.jsonl", [
            item("rule-release", "Release only on a green gate and check the live address afterwards.",
                 **{"class": ["release", "deploy"]}),
            item("rule-typo", "Spell-check headings before committing."),
            item("rule-deploy-note", "A deploy note goes in the digest.", importance=1),
        ])
        got = self.ids("how do I release and deploy")
        self.assertEqual(got[0], "rule-release")
        self.assertNotIn("rule-typo", got)

    def test_prefix_and_stem_matching(self):
        self.write("memory/items.jsonl", [item("rule-deploy", "Deployment must be checked on the phone.")])
        self.assertEqual(self.ids("deploying"), ["rule-deploy"])

    def test_scope_filtering(self):
        self.write("memory/items.jsonl", [
            item("rule-g", "Translation glossary first."),
            item("rule-lang", "Translation needs a back-translation check.", scope="family:language"),
            item("rule-soft", "Translation strings live in one table.", scope="family:software"),
            item("rule-orphan", "Translation project item stored in the brain.", scope="project"),
        ])
        self.assertEqual(set(self.ids("translation")), {"rule-g"})
        self.assertEqual(set(self.ids("translation", family="language")), {"rule-g", "rule-lang"})
        proj = Path(self.tmp.name) / "proj"
        (proj / ".brain").mkdir(parents=True)
        (proj / ".brain" / "project.json").write_text("{}")
        self.write(str(proj / ".brain" / "memory" / "items.jsonl"),
                   [item("rule-local", "Translation files are in locales/.", scope="project")])
        self.assertIn("rule-local", self.ids("translation", project=proj))
        self.assertNotIn("rule-local", self.ids("translation"))
        log = proj / ".brain" / "log" / "recall.jsonl"
        self.assertTrue(log.is_file())
        self.assertIn("rule-local", log.read_text())

    def test_candidates_excluded_probation_flagged(self):
        self.write("memory/items.jsonl", [
            item("rule-cand", "Cache entries expire.", status="candidate"),
            item("rule-prob", "Cache keys include the code hash.", status="probation"),
        ])
        res = r.recall("cache", brain_root=self.root)
        self.assertEqual([x["id"] for x in res], ["rule-prob"])
        self.assertEqual(res[0]["status"], "probation")
        self.assertIn("rule-cand", self.ids("cache", include_candidates=True))

    def test_budget_and_k_respected(self):
        rows = [item(f"rule-m{i}", f"Memory packing note {i}: " + " ".join(f"word{i}x{j}" for j in range(30)))
                for i in range(10)]
        self.write("memory/items.jsonl", rows)
        res = r.recall("memory packing", brain_root=self.root, budget_tokens=200)
        cost = sum(r.c.est_tokens(r._line(x)) for x in res)
        self.assertLessEqual(cost, 200)
        self.assertGreater(len(res), 0)
        self.assertLessEqual(len(r.recall("memory packing", brain_root=self.root, k=3, budget_tokens=5000)), 3)

    def test_near_duplicates_not_both_chosen(self):
        text = "Before any release run the full gate, then push main and check the live site on the phone."
        self.write("memory/items.jsonl", [
            item("rule-a", text),
            item("rule-b", text.replace("Before any", "Prior to a")),
            item("rule-c", "Release notes list what changed for the owner in plain words."),
        ])
        got = self.ids("release gate phone", budget_tokens=60)
        self.assertFalse({"rule-a", "rule-b"} <= set(got), got)
        got = self.ids("release gate phone", budget_tokens=600)
        self.assertFalse({"rule-a", "rule-b"} <= set(got), got)
        self.assertIn("rule-c", got)

    def test_owner_standing_floor(self):
        rows = [item(f"rule-l{i}", f"Release lesson {i}: release release release checks.", importance=3,
                     helpful=20, **{"class": ["release"]}) for i in range(6)]
        rows.append(item("own-main", "Keep main deployable; mention release once.", type="standing",
                         trust="owner-stated", importance=1, created="2024-01-01"))
        self.write("owner/standing.jsonl", rows[-1:])
        self.write("memory/items.jsonl", rows[:-1])
        res = r.recall("release", brain_root=self.root, k=2)
        self.assertIn("own-main", [x["id"] for x in res])
        self.assertGreaterEqual(next(x for x in res if x["id"] == "own-main")["score"], r.STANDING_FLOOR)

    def test_python_fallback_matches_fts5(self):
        self.write("memory/items.jsonl", [
            item("rule-x", "Scheduler uses annealing over priority orders.", **{"class": ["schedule"]}),
            item("rule-y", "Annealing is not used for packing."),
            item("rule-z", "Unrelated note about colours."),
        ])
        fast = self.ids("annealing schedule")
        with mock.patch.object(r, "_fts5_relevance", side_effect=sqlite3.OperationalError("no fts5")):
            slow = self.ids("annealing schedule")
        self.assertEqual(fast, slow)
        self.assertEqual(slow[0], "rule-x")

    def test_empty_memory_and_empty_query(self):
        self.assertEqual(r.recall("anything", brain_root=self.root), [])
        self.write("memory/items.jsonl", [item("rule-a", "Something.")])
        self.assertEqual(r.recall("the of and", brain_root=self.root), [])

    def test_recency_decay(self):
        self.assertEqual(r.recency({"created": "2026-11-01"}), 1.0)
        self.assertAlmostEqual(r.recency({"created": "2025-11-10"}), 0.7, places=2)
        self.assertGreater(r.recency({"created": "2026-05-10"}), 0.7)


if __name__ == "__main__":
    unittest.main()
