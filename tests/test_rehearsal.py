"""End-to-end rehearsal through the real command line, on a copy of the brain.

One story: a new project is bootstrapped, a requirement is recorded, a gate
fails and then passes, the work is released on green, the session is closed
with real-looking token usage, a lesson is noted, and the learning pipeline
turns the session into ledger rows, learning statistics and a candidate item.
A second session then meets the same lesson again and confirms it, which is
how a noted lesson earns its place (learning-02).

The copy keeps this repository's engine and method but not its memory: the
learned zone is replaced by a small frozen one (``frozen_brain``), so the
rehearsal says the same thing whatever the real brain has learned, demoted
or forgotten since (redteam-09).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _item(iid, text, **kw):
    base = {"id": iid, "type": "rule", "scope": "global", "class": ["general"], "text": text, "trust": "seed",
            "provenance": "tests/test_rehearsal.py", "created": "2026-11-01", "status": "active", "importance": 2}
    base.update(kw)
    return base


# A small memory with one of each kind of shipped knowledge. It is frozen
# here on purpose: tests must not read the brain's live learned state.
FROZEN_MEMORY = {
    "memory/items.jsonl": [
        _item("rule-evidence-first", "Check each claim against a tool result of this session before reporting progress.", importance=3),
        _item("rule-large-files", "Write large files in parts so a cut session loses little."),
        _item("rule-quiet-runs", "Run builds through the runner so only the result enters the conversation.", importance=1)],
    "memory/facts.jsonl": [
        _item("fact-cache-hour", "The main conversation's prompt cache lasts one hour within plan usage.", type="fact",
              trust="derived", source="docs/research/02-claude-code-platform.md", verified_on="2026-11-01", recheck_days=60)],
    "owner/standing.jsonl": [
        _item("own-main-green", "Main is updated only on a green gate and never force-pushed.", type="standing",
              trust="owner-stated", importance=3, **{"class": ["release"]}),
        _item("own-no-terminal", "The owner has no terminal: give clicks or a file to read.", type="standing",
              trust="owner-stated", importance=3)],
    "owner/preferences.jsonl": [
        _item("pref-short-plain", "He reads on his phone: keep replies short and in plain words.", type="preference",
              trust="observed")],
    "playbooks/software.jsonl": [
        _item("sw-test-integrity", "Do not skip, delete or loosen a test to get a pass.", type="playbook",
              scope="family:software", importance=3, **{"class": ["testing"]}),
        _item("sw-reproduce-first", "Fix a bug by first making it fail with a check.", type="playbook",
              scope="family:software", **{"class": ["testing"]})],
    "playbooks/language.jsonl": [
        _item("lang-two-reads", "A fresh reviewer reads the target text once without the source.", type="playbook",
              scope="family:language", importance=1, **{"class": ["review"]})],
}
SHIPPED_IDS = sorted(r["id"] for rows in FROZEN_MEMORY.values() for r in rows)
STATE_DIRS = ("learning/inbox", "learning/radar", "learning/deltas", "learning/digest", "stats")
STATE_FILES = ("learning/manifest.jsonl", "learning/CHANGELOG.md", "memory/archive.jsonl")


def freeze_memory(brain: Path) -> None:
    """Replace a brain's learned zone with the frozen memory: no inbox, no
    deltas, no statistics, and item files that hold only ``FROZEN_MEMORY``."""
    for rel in STATE_DIRS:
        shutil.rmtree(brain / rel, ignore_errors=True)
    for rel in STATE_FILES:
        (brain / rel).unlink(missing_ok=True)
    live = [p for d in ("memory", "owner", "playbooks") for p in sorted((brain / d).glob("*.jsonl"))
            if p.name not in ("archive.jsonl",)]
    for p in live:
        if p.relative_to(brain).as_posix() not in FROZEN_MEMORY:
            p.unlink()
            p.with_suffix(".md").unlink(missing_ok=True)
    for rel, rows in FROZEN_MEMORY.items():
        path = brain / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    sys.path.insert(0, str(ROOT))
    try:
        from engine import items
    finally:
        sys.path.remove(str(ROOT))
    for p in sorted((brain / "playbooks").glob("*.jsonl")):
        p.with_suffix(".md").write_text(items.render_markdown(p), encoding="utf-8")


def frozen_brain(dst: Path, src: Path = ROOT) -> Path:
    """A copy of the brain at ``src`` (engine, method, contract) whose memory
    is the frozen one, whatever ``src`` has learned."""
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    freeze_memory(dst)
    return dst


def run(cwd, *args, env=None):
    return subprocess.run(list(args), cwd=str(cwd), capture_output=True, text=True, env=env)


class Rehearsal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.brain = frozen_brain(self.ws / "Claude-Brain")
        self.proj = self.ws / "demo"
        self.proj.mkdir()
        self.remote = self.ws / "remote.git"
        run(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        for cmd in (["git", "init", "-q", "-b", "work"], ["git", "config", "user.email", "t@example.invalid"],
                    ["git", "config", "user.name", "t"], ["git", "config", "commit.gpgsign", "false"],
                    ["git", "remote", "add", "origin", str(self.remote)]):
            run(self.proj, *cmd)
        (self.proj / "README.md").write_text("# demo\n")
        self.env = self.session("sess-1", "2026-11-10", "New project: a tiny tool")

    def session(self, sid, day, opening):
        """The environment of one chat: its id, its transcript and its clock."""
        transcript = self.ws / f"{sid}.jsonl"
        lines = [
            {"type": "user", "timestamp": f"{day}T10:00:00Z", "message": {"role": "user", "content": opening}},
            {"type": "assistant", "timestamp": f"{day}T10:05:00Z", "message": {"id": "m1", "model": "claude-opus-5-5", "role": "assistant",
             "usage": {"input_tokens": 100, "cache_creation_input_tokens": 2000, "cache_read_input_tokens": 50000, "output_tokens": 800}}},
            {"type": "assistant", "timestamp": f"{day}T10:20:00Z", "message": {"id": "m2", "model": "claude-opus-5-5", "role": "assistant",
             "usage": {"input_tokens": 50, "cache_creation_input_tokens": 500, "cache_read_input_tokens": 90000, "output_tokens": 1200}}},
        ]
        transcript.write_text("".join(json.dumps(l) + "\n" for l in lines))
        env = dict(os.environ, BRAIN_SESSION_ID=sid, BRAIN_TRANSCRIPT=str(transcript), BRAIN_NOW=f"{day}T10:30:00Z")
        env.pop("CLAUDE_CODE_SESSION_ID", None)
        env.pop("BRAIN_PROJECT", None)
        return env

    def tearDown(self):
        self._tmp.cleanup()

    def brain_cmd(self, *args, ok=True):
        r = run(self.ws, sys.executable, str(self.brain / "bin" / "brain"), *args, env=self.env)
        if ok:
            self.assertEqual(r.returncode, 0, f"brain {' '.join(args)}\n{r.stdout}\n{r.stderr}")
        self.assertNotIn("Traceback", r.stderr)
        return r

    def commit(self, msg):
        run(self.proj, "git", "add", "-A")
        run(self.proj, "git", "commit", "-q", "-m", msg)

    def test_full_story(self):
        b = self.brain_cmd
        self.assertIn("mode: bootstrap", b("boot", "New project: a tiny tool that greets people").stdout)
        b("init", str(self.proj), "--family", "software", "--title", "Greeter", "--release", "main-on-green")
        out = b("boot", "Continue").stdout
        self.assertIn("mode: work", out)
        self.assertLessEqual(len(out.encode()), 1600)

        b("req", "add", "--quote", "it must greet by name", "--passes-when", "running greet.sh Ana prints Hello Ana")
        self.assertEqual(b("req", "check", ok=False).returncode, 1)

        manifest = json.loads((self.proj / ".brain" / "project.json").read_text())
        manifest["gates"] = [{"id": "checks", "kind": "command", "command": "sh greet.sh Ana | grep -qx 'Hello Ana'"}]
        (self.proj / ".brain" / "project.json").write_text(json.dumps(manifest, indent=2))
        (self.proj / "greet.sh").write_text('echo "Hi $1"\n')
        self.commit("first try")
        self.assertEqual(b("gate", ok=False).returncode, 1)
        refused = b("release", "--push", ok=False)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("refusing", refused.stdout)
        self.assertNotEqual(run(self.remote, "git", "rev-parse", "--verify", "-q", "main").returncode, 0)

        (self.proj / "greet.sh").write_text('echo "Hello $1"\n')
        self.commit("fix greeting")
        b("gate")
        b("req", "evidence", "R-001", "gate checks exit 0 on the fix commit", "--done")
        b("req", "check")
        b("checkpoint", "--done", "T-1 greeting", "--item", "T-2 docs", "--next", "T-3 release", "--stage", "verify")
        self.commit("bookkeeping")
        released = b("release", "--push")
        self.assertIn("released", released.stdout)
        self.assertEqual(run(self.remote, "git", "rev-parse", "main").stdout.strip(), run(self.proj, "git", "rev-parse", "HEAD").stdout.strip())

        before = b("learn", "status").stdout
        self.assertIn("0 candidate, 0 probation", before)
        noted = b("learn", "note", "--text", "Check the exact expected output string before writing the first version of a command-line greeting.",
                  "--class", "software", "--class", "testing", "--evidence", "gate:checks exit 1 then 0", "--signal", "gate-failed").stdout
        self.assertRegex(noted, r"it becomes lsn-[a-z0-9-]+ \(a candidate; pit-[a-z0-9-]+ if its gate went red then green\)")
        recalled = b("recall", "check expected output", "--json").stdout
        self.assertLessEqual(len(json.loads(recalled)), 3, "recall shows three items at most by default")
        self.assertTrue((self.proj / ".brain" / "log" / "recall.jsonl").is_file(), "recall writes its injection log")
        refused = b("close", "--used", "lsn-x:maybe", ok=False)
        self.assertEqual(refused.returncode, 2)
        closed = b("close", "--outcome", "ok", "--class", "software.feature", "--tier", "2", "--risk", "standard",
                   "--est-tokens", "50000")
        self.assertIn("$", closed.stdout)
        again = b("close", "--outcome", "ok", "--class", "software.feature", "--tier", "2")
        inbox = list((self.brain / "learning" / "inbox").glob("*.jsonl"))
        self.assertEqual(len(inbox), 1)
        records = [json.loads(l) for l in inbox[0].read_text().splitlines() if l.strip()]
        self.assertEqual(sum(r["kind"] == "ledger" for r in records), 1, "closing twice must not double-count")
        blob = inbox[0].read_text()
        for private in ("Greeter", "demo", "greet.sh", str(self.proj)):
            self.assertNotIn(private, blob.replace("greeting", ""), f"project detail {private!r} leaked into the brain")
        status = (self.proj / "STATUS.md").read_text()
        self.assertIn("Last session", status)

        b("learn", "consolidate")
        items = (self.brain / "memory" / "items.jsonl").read_text()
        self.assertIn("exact expected output string", items)
        self.assertFalse((self.brain / "stats" / "routing.json").exists())
        ml = (self.brain / "stats" / "ml.json").read_text()
        self.assertEqual(ml, json.dumps(json.loads(ml), indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        self.assertGreaterEqual(json.loads(ml)["n"], 1, "the session's outcome was folded into the statistics")
        outcome = next(r for r in records if r["kind"] == "outcome")
        self.assertEqual((outcome["passed"], outcome["first_pass"], outcome["has_check"], outcome["est_tokens"]),
                         (True, False, True, 50000))
        self.assertTrue(list((self.brain / "stats" / "ledger").glob("*.jsonl")))
        self.assertTrue((self.brain / "learning" / "manifest.jsonl").read_text().strip())
        learned = b("learn", "status").stdout
        self.assertIn("1 candidate", learned)
        row = next(json.loads(l) for l in items.splitlines() if "exact expected output string" in l)
        lesson = row["id"]
        self.assertEqual((row["type"], row["status"]), ("pitfall", "candidate"), "red then green in one session: a pitfall")
        self.assertIn(lesson, noted, "the note said which id the lesson would get")
        second = b("learn", "consolidate").stdout
        self.assertEqual((self.brain / "memory" / "items.jsonl").read_text(), items, "consolidating twice must change nothing")
        digest = b("learn", "digest").stdout
        self.assertIn("What I now treat as your instruction", digest)
        self.assertFalse((self.brain / "learning" / "digest").exists(), "a report must not leave a file behind")
        b("handover", ok=False)  # the copied brain is not a git repository; the note must still be written
        self.assertTrue((self.proj / ".brain" / "HANDOVER.md").is_file())
        b("doctor")

        # A later chat meets the same trouble, words the lesson differently, is
        # shown the earlier one, and confirms it: the lesson earns probation.
        self.env = self.session("sess-2", "2026-11-12", "Continue")
        b("gate")
        reworded = "Before writing a command's first version, check the exact output string its test expects."
        shown = b("learn", "note", "--text", reworded, "--class", "software", "--evidence", "gate:checks").stdout
        self.assertIn(f"close to {lesson} (candidate)", shown)
        confirmed = b("learn", "note", "--text", reworded, "--class", "software", "--evidence", "gate:checks",
                      "--confirms", lesson).stdout
        self.assertIn(f"counts for {lesson}", confirmed)
        b("close", "--outcome", "ok", "--class", "software.feature", "--tier", "1")
        b("learn", "consolidate")
        after = b("learn", "status").stdout
        self.assertIn("0 candidate, 1 probation", after)
        rows = [json.loads(l) for l in (self.brain / "memory" / "items.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), len(FROZEN_MEMORY["memory/items.jsonl"]) + 1, "the reworded note did not become a second lesson")


if __name__ == "__main__":
    unittest.main()
