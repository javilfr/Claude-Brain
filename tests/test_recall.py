"""Tests for engine/recall.py on a temporary brain (never the real memory),
plus a read-only regression on the labelled set evals/recall_golden.jsonl."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import common as c
from engine import items as it
from engine import learn
from engine import recall as r

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "evals" / "recall_golden.jsonl"


def item(iid, text, **kw):
    base = {"id": iid, "type": "rule", "scope": "global", "text": text, "trust": "observed",
            "status": "active", "importance": 2, "created": "2026-11-01", "evidence": ["test"], "class": []}
    base.update(kw)
    return base


class FakeML:
    def __init__(self, scores):
        self.scores = scores

    def item_score(self, state, item):
        return self.scores.get(item["id"], 1.0)


class RecallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "brain"
        (self.root / "memory").mkdir(parents=True)
        (self.root / "owner").mkdir()
        self.env = mock.patch.dict(os.environ, {"BRAIN_NOW": "2026-11-10T12:00:00Z"})
        self.env.start()

    def tearDown(self):
        learn.MLEARN = None
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

    def test_porter_stemming_matches_word_forms(self):
        self.write("memory/items.jsonl", [item("rule-phone", "Deployment must be checked on the phone.")])
        self.assertEqual(self.ids("deployments"), ["rule-phone"])
        self.assertEqual(r.query_terms("Deployments, deployment: how?"), ["deploy"])

    def test_porter_port_matches_sqlite(self):
        """The pure-Python stemmer must index exactly what FTS5's porter
        tokenizer indexes, or the fallback ranks differently."""
        words = sorted({w for p in sorted((ROOT / "docs").rglob("*.md")) for w in r._raw_tokens(c.read_text(p))})
        words += ["sses", "ies", "eed", "agreed", "hopping", "filing", "sky", "generalization", "allli", "relational"]
        con = sqlite3.connect(":memory:")
        try:
            con.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='porter unicode61')")
            con.execute("CREATE VIRTUAL TABLE v USING fts5vocab(t, 'instance')")
        except sqlite3.OperationalError:
            self.fail("this Python's SQLite has no FTS5; the port cannot be checked here")
        con.executemany("INSERT INTO t(rowid, x) VALUES (?, ?)", list(enumerate(words, 1)))
        got = dict(con.execute("SELECT doc, term FROM v"))
        con.close()
        bad = [(w, got.get(i), r.porter(w)) for i, w in enumerate(words, 1) if got.get(i) != r.porter(w)]
        self.assertGreater(len(words), 1000)
        self.assertEqual(bad, [])

    def test_scope_filtering_and_injection_log(self):
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
        self.assertIn("rule-local", self.ids("Secret translation question", project=proj, floor=0))
        self.assertNotIn("rule-local", self.ids("translation"))
        (row,) = c.read_jsonl(proj / ".brain" / "log" / "recall.jsonl")
        self.assertIn("rule-local", row["ids"])
        self.assertEqual(len(row["query_sha"]), 16)
        self.assertNotIn("Secret", json.dumps(row))

    def test_candidates_excluded_probation_flagged(self):
        self.write("memory/items.jsonl", [
            item("rule-cand", "Cache entries expire.", status="candidate"),
            item("rule-prob", "Cache keys include the code hash.", status="probation"),
        ])
        res = r.recall("cache", brain_root=self.root)
        self.assertEqual([x["id"] for x in res], ["rule-prob"])
        self.assertEqual(res[0]["status"], "probation")
        self.assertIn("rule-cand", self.ids("cache", include_candidates=True))

    def test_defaults_are_three_items_in_300_tokens(self):
        rows = [item(f"rule-m{i}", f"Memory packing note {i}: " + " ".join(f"word{i}x{j}" for j in range(30)))
                for i in range(10)]
        self.write("memory/items.jsonl", rows)
        self.assertEqual((r.DEFAULT_K, r.DEFAULT_BUDGET), (3, 300))
        res = r.recall("memory packing", brain_root=self.root)
        self.assertGreater(len(res), 0)
        self.assertLessEqual(len(res), 3)
        self.assertLessEqual(sum(c.est_tokens(r._line(x)) for x in res), 300)
        res = r.recall("memory packing", brain_root=self.root, budget_tokens=200)
        self.assertLessEqual(sum(c.est_tokens(r._line(x)) for x in res), 200)

    def test_near_duplicates_not_both_chosen(self):
        text = "Before any release run the full gate, then push main and check the live site on the phone."
        self.write("memory/items.jsonl", [
            item("rule-a", text),
            item("rule-b", text.replace("Before any", "Prior to a")),
            item("rule-c", "Release notes list what changed for the owner in plain words."),
        ])
        got = self.ids("release gate phone", budget_tokens=60, floor=0)
        self.assertFalse({"rule-a", "rule-b"} <= set(got), got)
        got = self.ids("release gate phone", budget_tokens=600, floor=0)
        self.assertFalse({"rule-a", "rule-b"} <= set(got), got)
        self.assertIn("rule-c", got)

    def test_silence_below_the_floor(self):
        """A best match covering little of the query yields nothing at all."""
        self.write("memory/items.jsonl", [
            item("rule-plan", "Plan the release before writing code."),
            item("rule-gate", "Run the gate before every push."),
        ])
        q = "plan a birthday party for my cat with balloons and cake"
        self.assertEqual(r.recall(q, brain_root=self.root), [])
        self.assertEqual(self.ids(q, floor=0), ["rule-plan"])
        self.assertEqual(self.ids("plan the release"), ["rule-plan"])
        c.write_json(self.root / "memory" / "ml_config.json", {"recall": {"floor": 0.95}})
        self.assertEqual(self.ids("plan the release code"), ["rule-plan"])
        self.assertEqual(self.ids("plan the release carefully"), [])

    def test_superseded_and_future_facts_are_not_recalled(self):
        self.write("memory/facts.jsonl", [
            item("fact-old", "Opus costs four dollars per million input tokens.", type="fact", valid_to="2026-11-01"),
            item("fact-new", "Opus costs three dollars per million input tokens.", type="fact", valid_from="2026-11-01"),
            item("fact-later", "Opus costs two dollars per million input tokens.", type="fact", valid_from="2027-01-01"),
            item("fact-ends", "Batch pricing for Opus halves the token price until December.", type="fact",
                 valid_to="2026-12-01"),
        ])
        self.assertEqual(set(self.ids("opus price per million tokens", k=5, floor=0)), {"fact-new", "fact-ends"})

    def test_learned_multiplier_reorders_but_never_lowers_the_owner(self):
        self.write("memory/items.jsonl", [
            item("rule-one", "Check the release notes before every deploy."),
            item("rule-two", "Before a deploy, check release tags, changelog wording and rollback steps."),
        ])
        self.write("owner/preferences.jsonl", [
            item("own-pref", "Ask the owner before a deploy that changes what he sees on his phone.", type="preference",
                 trust="owner-stated", importance=1)])
        learn.MLEARN = FakeML({"rule-one": 0.7, "rule-two": 1.3, "own-pref": 0.7})
        q = "check release before deploy"
        score = lambda res, iid: next(x["score"] for x in res if x["id"] == iid)
        before = r.recall(q, brain_root=self.root, floor=0)  # no stats/ml.json yet: lessons are neutral
        ids = [x["id"] for x in before]
        self.assertLess(ids.index("rule-one"), ids.index("rule-two"))
        c.write_json(self.root / "stats" / "ml.json", {"credit": {}})
        after = r.recall(q, brain_root=self.root, floor=0)
        ids = [x["id"] for x in after]
        self.assertIn("rule-two", ids)  # rule-one now ranks below it, or is packed out as redundant
        self.assertTrue("rule-one" not in ids or ids.index("rule-two") < ids.index("rule-one"), ids)
        # I-08: the owner item keeps the top multiplier whatever mlearn says.
        self.assertEqual(score(before, "own-pref"), score(after, "own-pref"))
        mult = r.item_multiplier(self.root)
        self.assertEqual(mult({"id": "own-pref", "trust": "owner-stated"}), r.TOP_MULTIPLIER)
        self.assertEqual(mult({"id": "rule-one", "trust": "observed"}), 0.7)
        learn.MLEARN = FakeML({"rule-two": 9.0})
        self.assertEqual(r.item_multiplier(self.root)({"id": "rule-two"}), r.TOP_MULTIPLIER)  # clamped

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

    def test_query_syntax_is_never_fts_syntax(self):
        self.write("memory/items.jsonl", [item("rule-a", "Quote every term in the match expression.")])
        self.assertEqual(self.ids('match "term" OR NEAR(x*) -- quote', floor=0), ["rule-a"])

    def test_empty_memory_and_empty_query(self):
        self.assertEqual(r.recall("anything", brain_root=self.root), [])
        self.write("memory/items.jsonl", [item("rule-a", "Something.")])
        self.assertEqual(r.recall("the of and", brain_root=self.root), [])

    def test_recency_decay(self):
        self.assertEqual(r.recency({"created": "2026-11-01"}), 1.0)
        self.assertAlmostEqual(r.recency({"created": "2025-11-10"}), 0.7, places=2)
        self.assertGreater(r.recency({"created": "2026-05-10"}), 0.7)


class GoldenRegressionTest(unittest.TestCase):
    """Recall quality on the 60 labelled queries (40 dev, 20 held-out) over the
    real brain's items, read only, through the full ranking and packing path
    with k=5, a large budget and no floor.

    Measured when this test was written (2026-11-10, 141 items):
      dev      recall@5 0.758, MRR 0.854
      heldout  recall@5 0.825, MRR 0.850
      pooled   recall@5 0.781, MRR 0.853
    BM25 alone on the same queries gives 0.803 / 0.878 pooled (the memo in
    docs/research/round2/04 measured 0.803 / 0.876 with the same design and
    no Spanish stop-words); the coverage packing costs 0.02 recall@5 because
    it skips near-duplicate siblings that the labels count as relevant, which
    is its purpose at k=3. The test fails if pooled recall@5 or MRR drops more
    than 0.03 below the measured values."""

    RECALL5, MRR = 0.781, 0.853

    def scores(self, pool, queries):
        rec = mrr = 0.0
        for q in queries:
            got = [x["id"] for x in r.select(q["query"], pool, k=5, budget_tokens=10 ** 6, floor=0.0)][:5]
            rel = set(q["relevant"])
            rec += len(rel & set(got)) / len(rel)
            mrr += next((1 / (i + 1) for i, x in enumerate(got) if x in rel), 0.0)
        return rec / len(queries), mrr / len(queries)

    def setUp(self):
        self.queries = c.read_jsonl(GOLDEN)
        self.pool = it.load_items(ROOT)
        self.env = mock.patch.dict(os.environ, {"BRAIN_NOW": "2026-11-10T12:00:00Z"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_golden_set_shape(self):
        self.assertEqual(len(self.queries), 60)
        self.assertEqual(sorted({q["split"] for q in self.queries}), ["dev", "heldout"])
        ids = {i["id"] for i in self.pool}
        self.assertEqual([x for q in self.queries for x in q["relevant"] if x not in ids], [])

    def test_recall_at_5_and_mrr_do_not_regress(self):
        by_split = {s: self.scores(self.pool, [q for q in self.queries if q["split"] == s]) for s in ("dev", "heldout")}
        rec, mrr = self.scores(self.pool, self.queries)
        self.assertGreaterEqual(rec, self.RECALL5 - 0.03, by_split)
        self.assertGreaterEqual(mrr, self.MRR - 0.03, by_split)

    def test_fallback_scores_equal_fts5_on_the_golden_set(self):
        docs = [r._fields(i) for i in self.pool]
        for q in self.queries:
            words = r.query_words(q["query"])
            for a, b in zip(r._fts5_relevance(docs, words), r._python_relevance(docs, words)):
                self.assertAlmostEqual(a, b, places=9, msg=q["query"])


if __name__ == "__main__":
    unittest.main()
