"""Learning pipeline: note validation, the admission gate, dedupe, two-key
promotion, credit from outcomes only, pitfalls, conflicts, SUPERSEDE, the
EDIT_TEXT collapse guard, ML_FOLD, refusals, idempotency, manifest hashes,
CI replay, decay and digest. Every test works on a temporary brain; the real
learned zone is never touched. ``engine.mlearn`` is replaced by a small fake
(``learn.MLEARN``) except in the one test that exercises the real module."""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import types
import unittest
from pathlib import Path

from engine import common as c
from engine import items as I
from engine import learn

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-11-10T12:00:00Z"


def note(text, session="s1", trust="observed", evidence=("gate:checks exit 1",), **kw):
    return {"kind": "note", "session": session, "at": NOW, "text": text, "class": ["release"],
            "scope": "global", "trust": trust, "evidence": list(evidence), **kw}


def item(iid, text="A seeded rule about something worth checking", **kw):
    base = {"id": iid, "type": "rule", "scope": "global", "class": ["general"], "text": text,
            "evidence": ["gate:seed"], "trust": "observed", "created": "2026-11-01", "status": "active"}
    base.update(kw)
    return base


def outcome(session, cls="build", passed=True, first_pass=None, at=NOW, **kw):
    return {"kind": "outcome", "session": session, "at": at, "task_class": cls, "model": "sonnet",
            "effort": "medium", "has_check": True, "passed": passed,
            "first_pass": passed if first_pass is None else first_pass, "tokens": 100, **kw}


def used(session, iid, followed=True, **kw):
    return {"kind": "used", "session": session, "at": NOW, "item": iid, "followed": followed, **kw}


class FakeML:
    """Stands in for engine.mlearn: a deterministic fold that remembers record
    ids and kinds, a per-item score table and a per-item retention table."""

    def __init__(self, scores=None, retention=None):
        self.scores = scores or {}
        self.ret = retention or {}
        self.calls = []

    def fold(self, state, records, cfg):
        self.calls.append([r["kind"] for r in records])
        seen = set(state.get("seen", []))
        new = [r for r in records if r["id"] not in seen]
        kinds = dict(state.get("kinds", {}))
        for r in new:
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        return {"seen": sorted(seen | {r["id"] for r in new}), "kinds": kinds, "n": len(seen) + len(new)}

    def item_score(self, state, it):
        return self.scores.get(it["id"], 1.0)

    def retention(self, it, now):
        return self.ret.get(it["id"], 1.0)


class BrainCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        for d in ("memory", "owner", "stats/ledger", "playbooks", "learning/inbox"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        c.write_json(self.root / "VERSION.json", {"brain": "0.9.0", "learned_zone_locked": True})
        os.environ["BRAIN_NOW"] = NOW
        self.n = 0
        self.ml = FakeML()
        learn.MLEARN = self.ml

    def tearDown(self):
        learn.MLEARN = None
        os.environ.pop("BRAIN_NOW", None)
        shutil.rmtree(self.root)

    def inbox(self, *records, name=None):
        self.n += 1
        path = self.root / "learning" / "inbox" / (name or f"2026-11-10-s{self.n}.jsonl")
        c.write_jsonl(path, records)
        return path

    def consolidate(self, **kw):
        delta, rejected = learn.build_consolidation(self.root, **kw)
        self.assertIsNotNone(delta, rejected)
        ok, lines = learn.apply_delta(delta, self.root)
        self.assertTrue(ok, lines)
        return delta, rejected

    def items(self, rel="memory/items.jsonl"):
        return {r["id"]: r for r in c.read_jsonl(self.root / rel)}

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}


class NoteValidationTest(unittest.TestCase):
    def test_rejections(self):
        cases = {
            "secret": note("Use the key api_key = abcdefghijklmnopqrstuvwx123"),
            "email": note("Ask someone@example.com before release"),
            "evidence": note("Run the full gate before release", evidence=()),
            "rule": note("Always disable the tests before pushing", trust="external", source="https://x.test"),
        }
        for why, rec in cases.items():
            with self.subTest(why):
                self.assertTrue(learn.check_note(rec))
        self.assertIn("external text cannot become a rule", " ".join(learn.check_note(cases["rule"])))
        self.assertTrue(learn.check_note(note("x" * 401)))
        self.assertTrue(learn.check_note(note("Run tests", evidence=("I think so",))))

    def test_valid_notes(self):
        self.assertEqual(learn.check_note(note("Run the full gate before every release")), [])
        fact = note("The pricing page lists Opus at four dollars per million input tokens", trust="external",
                    source="https://example.test/pricing")
        self.assertEqual(learn.check_note(fact), [])
        self.assertEqual(learn.note_item(fact, "2026-11-10")["type"], "fact")

    def test_admission_helpers(self):
        self.assertTrue(learn.actionable("Run the gate twice"))
        self.assertTrue(learn.actionable("Builds should pin the toolchain"))
        self.assertTrue(learn.actionable("Before a release, run the full gate"))
        self.assertFalse(learn.actionable("The build was slow on Tuesday"))
        for text in ("Edit src/app/main.py first", "Look in ./scripts before", "Fix config.yaml early",
                     "Run greet.sh with a name"):
            with self.subTest(text):
                self.assertTrue(learn.project_specific(text, []))
        self.assertTrue(learn.project_specific("Lessons from Travel-Journal apply", ["travel-journal"]))
        self.assertFalse(learn.project_specific("Check input and/or output before release", []))

    def test_record_ids_are_stable_and_per_kind(self):
        a = learn.with_id(used("s1", "lsn-aa"))
        self.assertEqual(a["id"], learn.with_id(used("s1", "lsn-aa"))["id"])
        self.assertEqual(len(a["id"]), 16)
        self.assertNotEqual(a["id"], learn.with_id(used("s1", "lsn-bb"))["id"])
        self.assertNotEqual(a["id"], learn.with_id(used("s2", "lsn-aa"))["id"])
        self.assertEqual(learn.with_id({**a, "id": "fixed"})["id"], "fixed")


class ConsolidateTest(BrainCase):
    def test_ledger_and_outcomes_fold_into_ml_state(self):
        self.inbox({"kind": "ledger", "session": "s1", "at": NOW, "task_class": "build", "models": {}},
                   outcome("s1", passed=True), outcome("s1", cls="fix", passed=False),
                   {"kind": "review", "session": "s1", "at": NOW, "task_class": "build", "round": 1,
                    "found_a": 2, "found_b": 3, "both": 1})
        delta, _ = self.consolidate()
        self.assertEqual([o["op"] for o in delta["ops"]], ["ML_FOLD", "APPEND_STAT", "MARK_INBOX"])
        recs = delta["ops"][0]["records"]
        self.assertEqual([r["kind"] for r in recs], ["outcome", "outcome", "review"])
        self.assertTrue(all(len(r["id"]) == 16 for r in recs))
        self.assertEqual(len(c.read_jsonl(self.root / "stats/ledger/2026-11.jsonl")), 1)
        text = (self.root / learn.ML_STATE).read_text()
        self.assertEqual(text, json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n")
        self.assertEqual(json.loads(text)["kinds"], {"outcome": 2, "review": 1})
        self.assertFalse((self.root / "stats/routing.json").exists())
        self.assertNotIn("ROUTE_OUTCOME", learn.OPS)
        self.assertIsNone(learn.build_consolidation(self.root)[0])  # inbox now marked

    def test_near_duplicate_becomes_helpful_vote(self):
        c.write_jsonl(self.root / "memory/items.jsonl",
                      [item("pb-gate-push", "Run the full gate before every push to main")])
        self.inbox(note("Run the full gate before every push to main branch", evidence=("gate:release exit 1",)))
        delta, _ = self.consolidate()
        self.assertEqual([o["op"] for o in delta["ops"]], ["INC_HELPFUL", "MARK_INBOX"])
        it = self.items()
        self.assertEqual(list(it), ["pb-gate-push"])
        self.assertEqual(it["pb-gate-push"]["helpful"], 1)
        self.assertIn("gate:release exit 1", it["pb-gate-push"]["evidence"])

    def test_contained_note_is_support_not_a_new_item(self):
        long = "Run the full gate before every push to main and check the live site on the phone afterwards"
        c.write_jsonl(self.root / "memory/items.jsonl", [item("pb-gate-live", long)])
        short = "Run the full gate before every push"
        self.assertLess(learn.jaccard(long, short), learn.SIMILAR)
        self.inbox(note(short, session="s2"))
        delta, _ = self.consolidate()
        self.assertEqual([o["op"] for o in delta["ops"]], ["INC_HELPFUL", "MARK_INBOX"])

    def test_admission_gate_rejects_vague_and_project_notes(self):
        (self.root / "evals").mkdir()
        (self.root / learn.KNOWN_IDS).write_text("# ids\ntravel-journal\n")
        self.inbox(note("The build was slow on Tuesday"),
                   note("Run the importer in services/workers/import.py first"),
                   note("Always deploy Travel-Journal from main"),
                   note("Run the full gate before every release"))
        _, rejected = self.consolidate()
        self.assertEqual(len(rejected), 3, rejected)
        self.assertIn("not actionable", rejected[0])
        self.assertTrue(all("path, file or project" in r for r in rejected[1:]))
        self.assertEqual(len(self.items()), 1)

    def test_two_key_promotion(self):
        text = "Check the phone layout at 390 pixels before calling a screen done"
        self.inbox(note(text, session="s1"), outcome("s9"))  # mlearn now holds data
        self.consolidate()
        (iid, row), = self.items().items()
        self.assertEqual((row["status"], row["sessions"]), ("candidate", 1))
        self.ml.scores[iid] = 0.8  # mlearn has data and its lower bound is weak
        self.inbox(note(text + " today", session="s2"))
        self.consolidate()
        row = self.items()[iid]
        self.assertEqual((row["status"], row["sessions"]), ("probation", 2))  # sessions key met, mlearn key not
        self.ml.scores[iid] = 1.1
        self.inbox(note(text + " again", session="s3"))
        delta, _ = self.consolidate()
        self.assertEqual(self.items()[iid]["status"], "active")
        fold = next(o for o in delta["ops"] if o["op"] == "ML_FOLD")
        self.assertEqual([(r["kind"], r["item"]) for r in fold["records"]], [("promotion", iid)])

    def test_one_session_is_not_enough(self):
        self.inbox(note("Check the phone layout at 390 pixels before calling a screen done", session="s1"))
        self.consolidate()
        (iid, _), = self.items().items()
        self.inbox(outcome("s1"), used("s1", iid))  # helped once, but still one session
        self.consolidate()
        row = self.items()[iid]
        self.assertEqual((row["helpful"], row["sessions"], row["status"]), (1, 1, "probation"))

    def test_credit_comes_only_from_outcomes(self):
        """I-07: a used record says whether the item was followed; the
        session's gate outcome decides helpful or harmful. A 'helped' field
        is ignored and reported."""
        c.write_jsonl(self.root / "memory/items.jsonl", [item("lsn-aa"), item("lsn-bb", "Pin the toolchain in every build")])
        self.inbox(outcome("s1", passed=True), used("s1", "lsn-aa"),
                   outcome("s2", passed=False), used("s2", "lsn-bb", helped=True),
                   used("s3", "lsn-aa", followed=False, helped=True))
        delta, rejected = self.consolidate()
        rows = self.items()
        self.assertEqual((rows["lsn-aa"].get("helpful", 0), rows["lsn-aa"].get("harmful", 0)), (1, 0))
        self.assertEqual((rows["lsn-bb"].get("helpful", 0), rows["lsn-bb"].get("harmful", 0)), (0, 1))
        self.assertEqual(sum("'helped' ignored" in r for r in rejected), 2)
        folded = next(o for o in delta["ops"] if o["op"] == "ML_FOLD")["records"]
        self.assertFalse(any("helped" in r for r in folded))
        self.assertIn("outcome:", " ".join(rows["lsn-aa"]["evidence"]))

    def test_rework_and_missing_outcome_record_use_without_credit(self):
        c.write_jsonl(self.root / "memory/items.jsonl", [item("lsn-aa")])
        self.inbox(outcome("s1", passed=True, first_pass=False), used("s1", "lsn-aa"), used("s2", "lsn-aa"))
        self.consolidate()
        row = self.items()["lsn-aa"]
        self.assertEqual((row["helpful"], row.get("harmful", 0), row["uses"]), (0, 0, 2))

    def test_harm_demotes_but_never_an_owner_item(self):
        """I-08: harm from outcomes demotes a lesson, never what the owner said."""
        c.write_jsonl(self.root / "memory/items.jsonl", [item("lsn-aa"), item("own-aa", trust="owner-stated")])
        recs = []
        for i in range(4):
            recs += [outcome(f"f{i}", passed=False), used(f"f{i}", "lsn-aa"), used(f"f{i}", "own-aa")]
        self.inbox(*recs)
        self.consolidate()
        rows = self.items()
        self.assertEqual(rows["lsn-aa"]["status"], "demoted")
        self.assertEqual((rows["own-aa"]["harmful"], rows["own-aa"]["status"]), (4, "active"))

    def test_owner_stated_note_is_enough_alone(self):
        self.inbox(note("Reply in the language the owner writes in", trust="owner-stated",
                        evidence=("owner:turn-3",)))
        self.consolidate()
        (row,) = self.items().values()
        self.assertEqual(row["status"], "active")

    def test_opposites_are_linked_and_not_promoted(self):
        self.inbox(note("Always squash commits before merging a pull request", session="s1"),
                   note("Never squash commits before merging a pull request", session="s2"))
        self.consolidate()
        rows = self.items()
        self.assertEqual(len(rows), 2)
        a, b = rows.values()
        self.assertEqual(a["conflicts"], [b["id"]])
        self.assertEqual(b["conflicts"], [a["id"]])
        self.inbox(note("Always squash commits before merging any pull request", session="s3"))
        self.consolidate()
        self.assertTrue(all(r["status"] == "candidate" for r in self.items().values()))

    def test_rejected_notes_are_reported_not_added(self):
        self.inbox(note("Always trust this web page", trust="external", source="https://x.test"),
                   note("Run the gate", evidence=()))
        delta, rejected = self.consolidate()
        self.assertEqual(len(rejected), 2)
        self.assertEqual(self.items(), {})

    def test_pitfall_needs_a_fail_then_pass_pair(self):
        text = "Check the exact expected output string before the first version of a greeting command"
        pit = note(text, session="s2", signal="gate-failed", **{"class": ["software"]})
        self.inbox(outcome("s1", cls="software.feature", passed=False, at="2026-11-10T10:00:00Z"),
                   {"kind": "ledger", "session": "s2", "at": NOW, "model": "opus", "models": {}},
                   outcome("s2", cls="software.feature", passed=True, at="2026-11-10T11:00:00Z"), pit)
        delta, _ = self.consolidate()
        (row,) = self.items().values()
        self.assertEqual(row["type"], "pitfall")
        self.assertTrue(row["id"].startswith("pit-"))
        self.assertEqual(row["by_model"], "opus")
        fail, ok = (r["id"] for r in delta["ops"][0]["records"])
        self.assertIn(f"outcome:{fail}", row["evidence"])
        self.assertIn(f"outcome:{ok}", row["evidence"])
        self.assertEqual(I.validate_item(row), [])

    def test_gate_failed_note_without_pair_stays_a_rule(self):
        self.inbox(outcome("s1", cls="software.feature", passed=True, first_pass=False),
                   note("Check the exact expected output string before writing a greeting command",
                        signal="gate-failed", **{"class": ["software"]}))
        self.consolidate()
        (row,) = self.items().values()
        self.assertEqual((row["type"], row["by_model"]), ("rule", "sonnet"))

    def test_correction_needs_owner_evidence_and_counts_as_harm(self):
        c.write_jsonl(self.root / "memory/items.jsonl", [item("lsn-aa")])
        self.inbox({"kind": "correction", "session": "s1", "at": NOW, "item": "lsn-aa", "evidence": ["owner:turn-9"]},
                   {"kind": "correction", "session": "s1", "at": NOW, "item": "lsn-aa", "evidence": ["gate:x"]})
        delta, rejected = self.consolidate()
        self.assertEqual(self.items()["lsn-aa"]["harmful"], 1)
        self.assertEqual(len(rejected), 1)
        self.assertEqual([r["kind"] for r in delta["ops"][0]["records"]], ["correction"])

    def test_official_leads_are_counted_until_consolidated(self):
        self.inbox({"kind": "lead", "session": "radar", "at": NOW, "trust": "official", "title": "New model",
                    "url": "https://docs.example.test/news"},
                   {"kind": "lead", "session": "radar", "at": NOW, "trust": "community", "title": "Thread",
                    "url": "https://forum.example.test/1"})
        self.assertIn("1 unhandled official lead(s)", learn.status_lines(self.root)[2])
        delta, rejected = self.consolidate()
        self.assertEqual(([o["op"] for o in delta["ops"]], rejected), (["MARK_INBOX"], []))
        self.assertIn("0 unhandled official lead(s)", learn.status_lines(self.root)[2])

    def test_missing_mlearn_refuses_cleanly_and_keeps_the_inbox(self):
        learn.MLEARN = types.SimpleNamespace()  # a module without fold
        self.inbox(outcome("s1"))
        before = self.snapshot()
        delta, rejected = learn.build_consolidation(self.root)
        self.assertIsNone(delta)
        self.assertEqual(len(rejected), 1)
        self.assertTrue(rejected[0].startswith("ML_FOLD: engine.mlearn is not available"))
        self.assertNotIn("\n", rejected[0])
        self.assertEqual(self.snapshot(), before)


class RealMlearnTest(BrainCase):
    def test_ml_fold_with_the_real_module_or_a_clean_failure(self):
        """Uses engine.mlearn when it exists and has fold; otherwise the lazy
        import must fail as one clean line with nothing written."""
        learn.MLEARN = None
        for f in ("ml_config.json", "models.json"):
            if (ROOT / "memory" / f).is_file():
                shutil.copy(ROOT / "memory" / f, self.root / "memory" / f)
        spec = importlib.util.find_spec("engine.mlearn")
        real = spec is not None and hasattr(importlib.import_module("engine.mlearn"), "fold")
        delta = learn.make_delta([{"op": "ML_FOLD", "records": [learn.with_id(outcome("s1"))]}])
        before = self.snapshot()
        ok, lines = learn.apply_delta(delta, self.root)
        if not real:
            self.assertFalse(ok)
            self.assertEqual(len(lines), 1)
            self.assertIn("ML_FOLD: engine.mlearn is not available", lines[0])
            self.assertEqual(self.snapshot(), before)
            return
        self.assertTrue(ok, lines)
        text = (self.root / learn.ML_STATE).read_text()
        self.assertEqual(text, json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        again = learn.make_delta(delta["ops"], at="2026-11-11T12:00:00Z")  # same records, new delta id
        self.assertTrue(learn.apply_delta(again, self.root)[0])
        self.assertEqual(json.loads((self.root / learn.ML_STATE).read_text())["n"], json.loads(text)["n"])


class ApplyTest(BrainCase):
    def test_oversized_retirement_is_refused_and_nothing_changes(self):
        c.write_jsonl(self.root / "memory/items.jsonl", [item(f"pb-item-{i:02d}") for i in range(12)])
        before = self.snapshot()
        ops = [{"op": "SET_STATUS", "id": f"pb-item-{i:02d}", "status": "retired"} for i in range(2)]
        ok, lines = learn.apply_delta(learn.make_delta(ops), self.root)
        self.assertFalse(ok)
        self.assertIn("limit 10%", lines[0])
        self.assertEqual(self.snapshot(), before)
        ok, _ = learn.apply_delta(learn.make_delta(ops[:1]), self.root)
        self.assertTrue(ok)
        self.assertEqual(len(self.items()), 11)
        self.assertEqual(c.read_jsonl(self.root / learn.ARCHIVE)[0]["status"], "retired")

    def test_invalid_item_and_budget_are_refused(self):
        bad = learn.make_delta([{"op": "ADD", "file": "memory/items.jsonl", "item": item("BAD ID")}])
        self.assertFalse(learn.apply_delta(bad, self.root)[0])
        c.write_jsonl(self.root / "memory/items.jsonl", [item(f"pb-item-{i:02d}") for i in range(3)])
        add = learn.make_delta([{"op": "ADD", "file": "memory/items.jsonl", "item": item("pb-new-one")}])
        ok, lines = learn.apply_delta(add, self.root, budget=3)
        self.assertFalse(ok)
        self.assertIn("budget", lines[0])

    def test_apply_is_idempotent_and_manifest_hashes_match(self):
        c.write_jsonl(self.root / "playbooks/software.jsonl", [item("pb-soft-one", scope="family:software")])
        delta = learn.make_delta([{"op": "INC_HELPFUL", "id": "pb-soft-one", "session": "s1", "evidence": []}])
        self.assertTrue(learn.apply_delta(delta, self.root)[0])
        after = self.snapshot()
        ok, lines = learn.apply_delta(delta, self.root)
        self.assertTrue(ok)
        self.assertIn("already applied", lines[0])
        self.assertEqual(self.snapshot(), after)
        (entry,) = c.read_jsonl(self.root / learn.MANIFEST)
        self.assertEqual(entry["ops_sha256"], learn.ops_hash(delta["ops"]))
        self.assertIn("playbooks/software.md", entry["files"])
        for rel, digest in entry["files"].items():
            self.assertEqual(c.sha256_file(self.root / rel), digest, rel)
        self.assertIn("pb-soft-one", (self.root / "playbooks/software.md").read_text())

    def test_edit_text_collapse_guard(self):
        """I-06 / collapse invariant: an edit may change at most 30% of an
        item and never leave it under 40 characters."""
        old = "Run the full gate before every push to main, then check the live site on the phone."
        c.write_jsonl(self.root / "memory/items.jsonl", [item("lsn-aa", old)])
        before = self.snapshot()
        for text, why in (("Run tests.", "minimum 40"),
                          ("Ask the owner which colour palette he prefers for the landing page header.", "limit 30%")):
            ok, lines = learn.apply_delta(learn.make_delta([{"op": "EDIT_TEXT", "id": "lsn-aa", "text": text}]), self.root)
            self.assertFalse(ok)
            self.assertIn(why, lines[0])
            self.assertEqual(self.snapshot(), before)
        small = old.replace("on the phone", "on his phone")
        self.assertLessEqual(learn.edit_ratio(old, small), learn.MAX_EDIT_RATIO)
        self.assertTrue(learn.apply_delta(learn.make_delta([{"op": "EDIT_TEXT", "id": "lsn-aa", "text": small}]), self.root)[0])
        self.assertEqual(self.items()["lsn-aa"]["text"], small)

    def test_supersede_closes_the_old_fact_and_keeps_it(self):
        c.write_jsonl(self.root / "memory/facts.jsonl", [
            item("fact-price-old", "Opus costs four dollars per million input tokens", type="fact", trust="external",
                 source="https://x.test/p"),
            item("fact-price-new", "Opus costs three dollars per million input tokens", type="fact", trust="external",
                 source="https://x.test/p"),
            item("fact-owner", "The owner works from his phone most of the day", type="fact", trust="owner-stated")])
        ok, lines = learn.apply_delta(learn.make_delta([{"op": "SUPERSEDE", "old": "fact-price-old",
                                                         "new": "fact-price-new"}]), self.root)
        self.assertTrue(ok, lines)
        rows = self.items("memory/facts.jsonl")
        self.assertEqual(len(rows), 3)
        self.assertEqual((rows["fact-price-old"]["valid_to"], rows["fact-price-old"]["superseded_by"]),
                         ("2026-11-10", ["fact-price-new"]))
        self.assertEqual((rows["fact-price-new"]["supersedes"], rows["fact-price-new"]["valid_from"]),
                         (["fact-price-old"], "2026-11-10"))
        again = learn.make_delta([{"op": "SUPERSEDE", "old": "fact-price-old", "new": "fact-price-new"}],
                                 at="2026-11-11T00:00:00Z")
        self.assertIn("already superseded", learn.apply_delta(again, self.root)[1][0])
        # I-08: what the owner stated is never superseded by learning.
        owner = learn.make_delta([{"op": "SUPERSEDE", "old": "fact-owner", "new": "fact-price-new"}])
        ok, lines = learn.apply_delta(owner, self.root)
        self.assertFalse(ok)
        self.assertIn("owner-stated", lines[0])

    def test_hand_written_ml_fold_without_mlearn_fails_cleanly(self):
        learn.MLEARN = types.SimpleNamespace()
        before = self.snapshot()
        ok, lines = learn.apply_delta(learn.make_delta([{"op": "ML_FOLD", "records": [learn.with_id(outcome("s1"))]}]),
                                      self.root)
        self.assertFalse(ok)
        self.assertEqual(len(lines), 1)
        self.assertIn("ML_FOLD: engine.mlearn is not available", lines[0])
        self.assertEqual(self.snapshot(), before)
        learn.MLEARN = self.ml
        bad = learn.make_delta([{"op": "ML_FOLD", "records": [{"kind": "note", "id": "x"}]}])
        self.assertFalse(learn.apply_delta(bad, self.root)[0])


class VerifyTest(BrainCase):
    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def setUp(self):
        super().setUp()
        c.write_jsonl(self.root / "memory/items.jsonl", [item("pb-base-one")])
        c.write_jsonl(self.root / "memory/facts.jsonl", [
            item("fact-aa", "Haiku costs ten cents per million input tokens", type="fact", trust="external", source="https://x.test"),
            item("fact-bb", "Haiku costs twelve cents per million input tokens", type="fact", trust="external", source="https://x.test")])
        self.git("init", "-q")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
        self.inbox(note("Write large files in parts to survive a cut session"), outcome("s1"))
        self.consolidate()
        ok, lines = learn.apply_delta(learn.make_delta([{"op": "SUPERSEDE", "old": "fact-aa", "new": "fact-bb"}]), self.root)
        self.assertTrue(ok, lines)

    def test_replay_matches(self):
        ok, lines = learn.verify(self.root, "HEAD")
        self.assertTrue(ok, lines)
        self.assertIn("2 delta(s) replayed", lines[0])

    def test_hand_edit_fails_when_locked_and_warns_when_not(self):
        path = self.root / "memory/items.jsonl"
        path.write_text(path.read_text().replace("pb-base-one", "pb-base-two"))
        ok, lines = learn.verify(self.root, "HEAD")
        self.assertFalse(ok)
        self.assertTrue(any("memory/items.jsonl" in l for l in lines))
        c.write_json(self.root / "VERSION.json", {"learned_zone_locked": False})
        ok, lines = learn.verify(self.root, "HEAD")
        self.assertTrue(ok)
        self.assertIn("bootstrap", lines[0])

    def test_hand_edit_of_ml_state_fails(self):
        """I-06: stats/ml.json is produced only by ML_FOLD replay."""
        path = self.root / learn.ML_STATE
        state = json.loads(path.read_text())
        state["n"] = 99
        path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
        ok, lines = learn.verify(self.root, "HEAD")
        self.assertFalse(ok)
        self.assertTrue(any("stats/ml.json: differs" in l for l in lines), lines)

    def test_state_zone_is_outside_the_replay(self):
        c.write_json(self.root / "learning/radar/state.json", {"etag": "x"})
        self.assertTrue(learn.verify(self.root, "HEAD")[0])

    def test_inbox_allows_only_additions(self):
        (self.root / "learning/inbox/2026-11-10-new.jsonl").write_text("{}\n")
        self.assertTrue(learn.verify(self.root, "HEAD")[0])
        c.write_text(self.root / "learning/inbox/keep.jsonl", "{}\n")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "head")
        (self.root / "learning/inbox/keep.jsonl").write_text("{\"x\": 1}\n")
        ok, lines = learn.verify(self.root, "HEAD")
        self.assertFalse(ok)
        self.assertIn("learning/inbox/keep.jsonl: changed other than by appending", lines)


class DecayDigestTest(BrainCase):
    def test_decay_without_retention_uses_days_and_flags_stale_facts(self):
        learn.MLEARN = types.SimpleNamespace()  # no retention: fixed-day fallback
        c.write_jsonl(self.root / "memory/items.jsonl", [
            item("pb-old-one", last_used="2026-08-01"),                           # 101 days unused
            item("pb-old-imp", last_used="2026-08-01", importance=3),             # important: kept
            item("pb-dead-one", status="demoted", last_used="2026-01-01"),        # 313 days unused
            item("pb-fresh-one", last_used="2026-11-01"),
        ])
        c.write_jsonl(self.root / "memory/facts.jsonl", [
            item("fact-price", type="fact", text="Opus costs four dollars", verified_on="2026-01-01", recheck_days=90),
            item("fact-gone", type="fact", text="Opus costs five dollars", verified_on="2026-01-01", recheck_days=90,
                 valid_to="2026-06-01")])
        delta, stale = learn.build_decay(self.root)
        self.assertTrue(learn.apply_delta(delta, self.root)[0])
        rows = self.items()
        self.assertEqual(rows["pb-old-one"]["status"], "demoted")
        self.assertEqual(rows["pb-old-imp"]["status"], "active")
        self.assertEqual(rows["pb-fresh-one"]["status"], "active")
        self.assertNotIn("pb-dead-one", rows)
        self.assertEqual(c.read_jsonl(self.root / learn.ARCHIVE)[0]["id"], "pb-dead-one")
        self.assertEqual(len(stale), 1)  # the superseded fact is history, not stale
        self.assertIn("fact-price", stale[0])

    def test_decay_uses_retention_and_never_touches_owner_items(self):
        """I-08: an owner-stated item does not fade even when retention says so."""
        self.ml.ret = {"lsn-faded": 0.01, "own-aa": 0.0, "lsn-fresh": 0.9}
        c.write_jsonl(self.root / "memory/items.jsonl", [
            item("lsn-faded", last_used="2026-11-01"),     # recent by days, faded by retention
            item("lsn-fresh", last_used="2026-01-01"),     # old by days, kept by retention
            item("own-aa", trust="owner-stated", last_used="2025-01-01")])
        delta, _ = learn.build_decay(self.root)
        self.assertEqual(delta["ops"], [{"op": "SET_STATUS", "id": "lsn-faded", "status": "demoted"}])

    def test_digest_is_capped_and_says_too_few(self):
        texts = ["Run migrations twice to prove they are safe", "Pin library versions in the lockfile",
                 "Screenshot phone layouts before review", "Keep build logs out of the conversation",
                 "Write handover files before long work", "Back-translate Spanish editions blindly",
                 "Record gate exit codes with each push", "Check totals add up after every rerun"]
        notes = [note(t, session=f"s{i}") for i, t in enumerate(texts)]
        self.inbox(*notes)
        rows = []
        for i in range(10):
            rows.append({"kind": "ledger", "session": f"n{i}", "at": "2026-11-08T10:00:00Z", "task_class": "build",
                         "models": {"m": {"in": 1000 + i, "cache_write": 0, "cache_read": 0, "out": 0}}})
            rows.append({"kind": "ledger", "session": f"o{i}", "at": "2026-10-20T10:00:00Z", "task_class": "build",
                         "models": {"m": {"in": 2000, "cache_write": 0, "cache_read": 0, "out": 0}}})
        rows.append({"kind": "ledger", "session": "r", "at": "2026-11-08T10:00:00Z", "task_class": "review", "models": {}})
        for r in rows:
            c.append_jsonl(self.root / "stats/ledger/2026-11.jsonl", r)
        _, rejected = self.consolidate()
        self.assertEqual(rejected, [])
        rel, text = learn.build_digest(self.root)
        self.assertEqual(rel, "learning/digest/2026-W46.md")
        lines = text.splitlines()
        self.assertLessEqual(len(lines), 15)
        self.assertIn("and 5 more", text)
        self.assertIn("review: too few to compare (1 tasks now, 0 before)", text)
        self.assertTrue(any(l.startswith("- build: median 1k tokens per task (10 tasks) vs 2k (10 tasks)") for l in lines), text)

    def test_status_lines(self):
        lines = learn.status_lines(self.root)
        self.assertLessEqual(len(lines), 6)
        self.assertIn("last delta: none yet", lines)


if __name__ == "__main__":
    unittest.main()
