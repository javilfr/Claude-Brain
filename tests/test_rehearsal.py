"""End-to-end rehearsal through the real command line, on a copy of the brain.

One story: a new project is bootstrapped, a requirement is recorded, a gate
fails and then passes, the work is released on green, the session is closed
with real-looking token usage, a lesson is noted, and the learning pipeline
turns the session into ledger rows, routing statistics and a candidate item.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cwd, *args, env=None):
    return subprocess.run(list(args), cwd=str(cwd), capture_output=True, text=True, env=env)


class Rehearsal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.brain = self.ws / "Claude-Brain"
        shutil.copytree(ROOT, self.brain, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        self.proj = self.ws / "demo"
        self.proj.mkdir()
        self.remote = self.ws / "remote.git"
        run(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        for cmd in (["git", "init", "-q", "-b", "work"], ["git", "config", "user.email", "t@example.invalid"],
                    ["git", "config", "user.name", "t"], ["git", "config", "commit.gpgsign", "false"],
                    ["git", "remote", "add", "origin", str(self.remote)]):
            run(self.proj, *cmd)
        (self.proj / "README.md").write_text("# demo\n")
        transcript = self.ws / "sess-1.jsonl"
        lines = [
            {"type": "user", "timestamp": "2026-11-10T10:00:00Z", "message": {"role": "user", "content": "New project: a tiny tool"}},
            {"type": "assistant", "timestamp": "2026-11-10T10:05:00Z", "message": {"id": "m1", "model": "claude-opus-5-5", "role": "assistant",
             "usage": {"input_tokens": 100, "cache_creation_input_tokens": 2000, "cache_read_input_tokens": 50000, "output_tokens": 800}}},
            {"type": "assistant", "timestamp": "2026-11-10T10:20:00Z", "message": {"id": "m2", "model": "claude-opus-5-5", "role": "assistant",
             "usage": {"input_tokens": 50, "cache_creation_input_tokens": 500, "cache_read_input_tokens": 90000, "output_tokens": 1200}}},
        ]
        transcript.write_text("".join(json.dumps(l) + "\n" for l in lines))
        self.env = dict(os.environ, BRAIN_SESSION_ID="sess-1", BRAIN_TRANSCRIPT=str(transcript), BRAIN_NOW="2026-11-10T10:30:00Z")
        self.env.pop("CLAUDE_CODE_SESSION_ID", None)
        self.env.pop("BRAIN_PROJECT", None)

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

        b("learn", "note", "--text", "Check the exact expected output string before writing the first version of a command-line greeting.",
          "--class", "software", "--class", "testing", "--evidence", "gate:checks exit 1 then 0", "--signal", "gate-failed")
        closed = b("close", "--outcome", "ok", "--class", "software.feature", "--tier", "2")
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
        routing = json.loads((self.brain / "stats" / "routing.json").read_text())
        self.assertIn("software.feature", routing)
        self.assertTrue(list((self.brain / "stats" / "ledger").glob("*.jsonl")))
        self.assertTrue((self.brain / "learning" / "manifest.jsonl").read_text().strip())
        learned = b("learn", "status").stdout
        self.assertIn("1 candidate", learned)
        second = b("learn", "consolidate").stdout
        self.assertEqual((self.brain / "memory" / "items.jsonl").read_text(), items, "consolidating twice must change nothing")
        b("learn", "digest")
        b("handover", ok=False)  # the copied brain is not a git repository; the note must still be written
        self.assertTrue((self.proj / ".brain" / "HANDOVER.md").is_file())
        b("doctor")


if __name__ == "__main__":
    unittest.main()
