"""Guard: zones, path decisions, the CI diff check, and the two hooks
(which must fail open and finish fast). Hooks run against a temporary copy
of the brain so the real inbox is never written."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from engine import common as c
from engine import guard

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "ledger"


def temp_brain(locked: bool) -> Path:
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "engine", tmp / "engine", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / ".claude" / "hooks", tmp / ".claude" / "hooks")
    (tmp / "memory").mkdir()
    shutil.copy(ROOT / "memory" / "models.json", tmp / "memory" / "models.json")
    c.write_json(tmp / "VERSION.json", {"brain": "1.0.0", "learned_zone_locked": locked})
    return tmp


def run_hook(brain: Path, name: str, stdin: str, cwd: Path | None = None) -> tuple[int, str, float]:
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, str(brain / ".claude" / "hooks" / name)], input=stdin,
                       capture_output=True, text=True, timeout=20, cwd=str(cwd or brain))
    return p.returncode, p.stdout + p.stderr, time.monotonic() - t0


class ZoneTest(unittest.TestCase):
    def test_zone_of(self):
        cases = {
            "learning/inbox/2026-11-10-s.jsonl": "inbox",
            "./learning/inbox/x.jsonl": "inbox",
            "memory/items.jsonl": "learned",
            "owner/standing.jsonl": "learned",
            "stats/ml.json": "learned",
            "learning/radar/state.json": "state",
            "learning/radarx/a.json": "learned",
            "memory/ml_config.json": "kernel",
            "memory/radar_sources.json": "kernel",
            "playbooks/software.md": "learned",
            "learning/manifest.jsonl": "learned",
            "memory/models.json": "kernel",
            "learning/PROMOTION_RULES.md": "kernel",
            "engine/learn.py": "kernel",
            "CLAUDE.md": "kernel",
            "memoryless/x": "kernel",
        }
        for path, zone in cases.items():
            with self.subTest(path):
                self.assertEqual(guard.zone_of(path), zone)

    def test_zone_of_normalises_dot_dot(self):
        """B4: 'memory/../evals/x' is a kernel file, not a memory file."""
        cases = {
            "memory/../evals/routing.jsonl": "kernel",
            "memory/../owner/standing.jsonl": "learned",
            "learning/inbox/../../CLAUDE.md": "kernel",
            "learning/inbox/../manifest.jsonl": "learned",
            "learning/radar/../../engine/learn.py": "kernel",
            "memory/./items.jsonl": "learned",
            "memory/../memory/models.json": "kernel",
            "../memory/items.jsonl": "kernel",
            "memory/../../x": "kernel",
            "": "kernel",
            "..": "kernel",
        }
        for path, zone in cases.items():
            with self.subTest(path):
                self.assertEqual(guard.zone_of(path), zone)
        self.assertEqual(guard.normalise_rel("memory/../evals/routing.jsonl"), "evals/routing.jsonl")
        self.assertIsNone(guard.normalise_rel("memory/../../x"))


class PathTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        c.write_json(self.root / "VERSION.json", {"learned_zone_locked": True})

    def tearDown(self):
        shutil.rmtree(self.root)

    def check(self, rel, mode="work"):
        return guard.check_path(str(self.root / rel), mode, self.root)

    def test_locked_rules(self):
        self.assertEqual(self.check("learning/inbox/a.jsonl")[0], 0)
        self.assertEqual(self.check("memory/items.jsonl")[0], 2)
        self.assertEqual(self.check("engine/learn.py"), (2, "kernel change: needs the owner"))
        self.assertEqual(self.check("memory/items.jsonl", "learn")[0], 0)
        self.assertEqual(self.check("engine/learn.py", "learn")[0], 2)
        code, reason = self.check("engine/learn.py", "bootstrap")
        self.assertEqual(code, 0)
        self.assertIn("warning", reason)
        self.assertEqual(guard.check_path(str(self.root.parent / "elsewhere.txt"), "work", self.root)[0], 0)
        # State is rewritten by its own script during work; the learning
        # constants and radar sources are kernel: learning never edits its rules (I-09).
        self.assertEqual(self.check("learning/radar/state.json")[0], 0)
        for kernel in ("memory/ml_config.json", "memory/radar_sources.json", "memory/models.json"):
            with self.subTest(kernel):
                self.assertEqual(self.check(kernel), (2, "kernel change: needs the owner"))
                self.assertEqual(self.check(kernel, "learn")[0], 2)

    def test_unlocked_allows_with_warning(self):
        c.write_json(self.root / "VERSION.json", {"learned_zone_locked": False})
        code, reason = self.check("engine/learn.py")
        self.assertEqual(code, 0)
        self.assertIn("warning", reason)


class DiffTest(unittest.TestCase):
    def git(self, *args):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=self.root,
                       check=True, capture_output=True)

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        c.write_json(self.root / "VERSION.json", {"learned_zone_locked": True})
        (self.root / "evals").mkdir()
        (self.root / "evals" / "known_project_ids.txt").write_text("# ids\ntravel-journal\n")
        (self.root / "method").mkdir()
        (self.root / "method" / "a.md").write_text("base\n")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_clean_change_passes(self):
        (self.root / "method" / "a.md").write_text("base\nmore method\n")
        ok, lines = guard.check_diff(self.root, "HEAD")
        self.assertTrue(ok, lines)
        self.assertIn("1 kernel", lines[0])

    def test_state_zone_changes_pass_and_are_counted(self):
        c.write_json(self.root / "learning" / "radar" / "state.json", {"etag": "a"})
        ok, lines = guard.check_diff(self.root, "HEAD")
        self.assertTrue(ok, lines)
        self.assertIn("0 kernel, 0 learned, 0 inbox, 1 state", lines[0])

    def test_secret_and_project_id_fail(self):
        (self.root / "method" / "a.md").write_text("base\ntoken = abcdefghijklmnopqrstuvwxyz0123\n")
        (self.root / "method" / "b.md").write_text("Lessons from Travel-Journal apply here\n")
        ok, lines = guard.check_diff(self.root, "HEAD")
        self.assertFalse(ok)
        self.assertTrue(any("secret-like text added in method/a.md" in l for l in lines), lines)
        self.assertTrue(any("'travel-journal' appears in method/b.md" in l for l in lines), lines)

    def test_hand_edit_of_learned_zone_fails(self):
        c.write_text(self.root / "memory" / "items.jsonl", '{"id": "pb-hand-made"}\n')
        ok, lines = guard.check_diff(self.root, "HEAD")
        self.assertFalse(ok)
        self.assertTrue(any("memory/items.jsonl" in l for l in lines), lines)


class HookTest(unittest.TestCase):
    def setUp(self):
        self.brain = temp_brain(locked=True)

    def tearDown(self):
        shutil.rmtree(self.brain)

    def test_guard_hook_fails_open_on_bad_input(self):
        for stdin in ("not json", "", "[]", '{"tool_input": {}}', '{"tool_input": {"file_path": 5}}'):
            with self.subTest(stdin):
                code, _, secs = run_hook(self.brain, "guard_paths.py", stdin)
                self.assertEqual(code, 0)
                self.assertLess(secs, 1.0)

    def test_guard_hook_blocks_learned_zone_only_when_locked(self):
        learned = json.dumps({"tool_input": {"file_path": str(self.brain / "memory" / "items.jsonl")}})
        inbox = json.dumps({"tool_input": {"file_path": str(self.brain / "learning" / "inbox" / "a.jsonl")}})
        kernel = json.dumps({"tool_input": {"file_path": "engine/learn.py"}, "cwd": str(self.brain)})
        code, err, secs = run_hook(self.brain, "guard_paths.py", learned)
        self.assertEqual(code, 2)
        self.assertIn("learned zone", err)
        self.assertLess(secs, 1.0)
        self.assertEqual(run_hook(self.brain, "guard_paths.py", inbox)[0], 0)
        self.assertEqual(run_hook(self.brain, "guard_paths.py", kernel)[0], 0)
        c.write_json(self.brain / "VERSION.json", {"learned_zone_locked": False})
        self.assertEqual(run_hook(self.brain, "guard_paths.py", learned)[0], 0)

    def test_session_end_hook_is_quiet_and_never_blocks(self):
        for stdin in ("garbage", '{"stop_hook_active": true, "session_id": "x", "transcript_path": "/nope"}',
                      '{"session_id": "x", "transcript_path": "/does/not/exist.jsonl"}'):
            with self.subTest(stdin):
                code, out, _ = run_hook(self.brain, "session_end.py", stdin)
                self.assertEqual((code, out), (0, ""))
        self.assertFalse((self.brain / "learning" / "inbox").exists())

    def test_session_end_hook_records_ledger(self):
        stdin = json.dumps({"session_id": "sess-1", "transcript_path": str(FIX / "sess-1.jsonl")})
        env_cwd = Path(tempfile.mkdtemp())
        try:
            code, out, _ = run_hook(self.brain, "session_end.py", stdin, cwd=env_cwd)
        finally:
            shutil.rmtree(env_cwd)
        self.assertEqual((code, out), (0, ""))
        # lead-02 (2026-11-10 audit): the hook writes the git-ignored live file,
        # not the tracked inbox file, which left the tree dirty after every turn.
        self.assertEqual(list((self.brain / "learning" / "inbox").glob("*.jsonl")), [])
        files = list((self.brain / "learning" / "inbox" / ".live").glob("*-sess-1.jsonl"))
        self.assertEqual(len(files), 1)
        (rec,) = c.read_jsonl(files[0])
        self.assertEqual(rec["kind"], "ledger")
        self.assertIn("claude-opus-5-5", rec["models"])

    def test_settings_register_both_hooks(self):
        s = json.loads((ROOT / ".claude" / "settings.json").read_text())
        pre = s["hooks"]["PreToolUse"][0]
        self.assertEqual(pre["matcher"], "Edit|Write|MultiEdit")
        self.assertIn('"$CLAUDE_PROJECT_DIR"/.claude/hooks/guard_paths.py', pre["hooks"][0]["command"])
        self.assertEqual(s["hooks"]["Stop"][0]["hooks"][0]["timeout"], 20)


if __name__ == "__main__":
    unittest.main()
