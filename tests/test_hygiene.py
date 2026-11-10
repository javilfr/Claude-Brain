"""Session hygiene: checkpoints that reach the next session, and resume."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import common as c, contract, gate, state  # noqa: E402


def sh(cwd, *args):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


class HygieneTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.remote = self.ws / "remote.git"
        sh(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.p = self.ws / "proj"
        self.p.mkdir()
        for cmd in (["git", "init", "-q", "-b", "work"], ["git", "config", "user.email", "t@example.invalid"],
                    ["git", "config", "user.name", "t"], ["git", "config", "commit.gpgsign", "false"],
                    ["git", "remote", "add", "origin", str(self.remote)]):
            sh(self.p, *cmd)
        (self.p / "README.md").write_text("# x\n")
        contract.init(self.p, "Proj", "software")
        sh(self.p, "git", "add", "-A")
        sh(self.p, "git", "commit", "-q", "-m", "init")
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    def remote_has(self, rel: str) -> str:
        return sh(self.remote, "git", "show", f"work:{rel}").stdout

    def test_checkpoint_push_makes_state_visible_to_a_new_clone(self):
        state.checkpoint(self.p, item="T-3 list view", nxt=["T-4"])
        msg = state.push_bookkeeping(self.p)
        self.assertIn("checkpoint pushed to work", msg)
        self.assertIn("T-3 list view", self.remote_has(".brain/STATE.md"))
        clone = self.ws / "fresh"
        sh(self.ws, "git", "clone", "-q", "-b", "work", str(self.remote), str(clone))
        self.assertEqual(state.read_state(clone)["item"], "T-3 list view")

    def test_push_commits_only_bookkeeping_and_reports_other_work(self):
        (self.p / "feature.py").write_text("x = 1\n")
        state.checkpoint(self.p, item="T-5")
        msg = state.push_bookkeeping(self.p)
        self.assertIn("1 other uncommitted change(s)", msg)
        self.assertEqual(self.remote_has("feature.py"), "")
        self.assertIn("feature.py", sh(self.p, "git", "status", "--porcelain").stdout)

    def test_push_without_remote_or_repo_says_so(self):
        sh(self.p, "git", "remote", "remove", "origin")
        state.checkpoint(self.p, item="T-6")
        self.assertIn("no remote", state.push_bookkeeping(self.p))
        bare = self.ws / "plain"
        bare.mkdir()
        contract.init(bare, "Plain", "knowledge")
        self.assertIn("not a git repository", state.push_bookkeeping(bare))

    def test_resume_is_short_and_names_open_work(self):
        from engine import req
        rows = [{"id": f"R-{i:03d}", "quote": f"requirement number {i}", "passes_when": "check", "status": "open", "evidence": []} for i in range(1, 9)]
        req.save(self.p, rows)
        state.checkpoint(self.p, item="T-7 search", nxt=["T-8", "T-9"], note="half done in src/search.ts", blockers="waiting for an API key")
        (self.p / "src.ts").write_text("x")
        m = c.load_manifest(self.p)
        m["gates"] = [{"id": "checks", "kind": "command", "command": "true"}]
        c.write_json(self.p / ".brain" / "project.json", m)
        gate.run_gates(self.p)
        lines = state.resume_lines(self.p)
        blob = "\n".join(lines)
        self.assertLessEqual(len(lines), 12)
        for needle in ("T-7 search", "waiting for an API key", "half done", "open R-001", "4 more open", "src.ts", "gate checks exit 0"):
            self.assertIn(needle, blob)

    def test_checklist_lists_open_items_only(self):
        from engine import req
        req.save(self.p, [{"id": "R-001", "quote": "open one", "status": "open", "evidence": []},
                          {"id": "R-002", "quote": "finished one", "status": "done", "passes_when": "x", "evidence": ["e"]}])
        state.checkpoint(self.p, item="T-1", nxt=["T-2"])
        items = state.write_checklist(self.p)
        text = (self.p / ".brain" / "CHECKLIST.md").read_text()
        self.assertEqual(len(items), 3)
        self.assertIn("open one", text)
        self.assertNotIn("finished one", text)

    def test_bookkeeping_definition_is_shared_with_gates(self):
        self.assertIs(gate.is_bookkeeping, state.is_bookkeeping)
        self.assertTrue(state.is_bookkeeping(".brain/log/gates.jsonl"))
        self.assertFalse(state.is_bookkeeping("src/app.ts"))


if __name__ == "__main__":
    unittest.main()
