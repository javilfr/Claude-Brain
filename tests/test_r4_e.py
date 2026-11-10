"""Package E of the 2026-11-10 improvement plan: token ledger, guard, lint
and hooks. Each test names the finding it pins (docs/review/2026-11-10-audit).
Everything runs in temporary folders; nothing here pushes or writes into the
brain the tests are run from."""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import common as c  # noqa: E402
from engine import guard, ledger, learn, lint, mlearn  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "ledger"
MAIN = FIX / "sess-1.jsonl"
SUBS = [FIX / "sess-1" / "subagents" / "agent-x.jsonl"]
MODELS = json.loads((ROOT / "memory" / "models.json").read_text())
OPUS, SONNET, HELPER = 0.0116, 0.00122, 0.024   # worked out in tests/test_ledger.py


def sh(cwd, *args, **kw):
    return subprocess.run(list(args), cwd=str(cwd), capture_output=True, text=True, **kw)


def git_init(path: Path) -> None:
    for cmd in (["git", "init", "-q", "-b", "work"], ["git", "config", "user.email", "t@example.invalid"],
                ["git", "config", "user.name", "t"], ["git", "config", "commit.gpgsign", "false"]):
        sh(path, *cmd)


def write_transcript(path: Path, stamps: list[str], model: str = "claude-opus-5-5", usage: dict | None = None) -> Path:
    usage = usage or {"input_tokens": 10, "output_tokens": 10}
    rows = [{"type": "assistant", "timestamp": ts, "message": {"id": f"m{i}", "model": model, "usage": usage}}
            for i, ts in enumerate(stamps)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


class LedgerBase(unittest.TestCase):
    """A temporary brain (models and learning constants only) beside one managed project."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.brain = self.tmp / "brain"
        (self.brain / "memory").mkdir(parents=True)
        for f in ("models.json", "ml_config.json"):
            shutil.copy(ROOT / "memory" / f, self.brain / "memory" / f)
        self.proj = self.tmp / "proj"
        (self.proj / ".brain" / "log").mkdir(parents=True)
        c.write_json(self.proj / ".brain" / "project.json",
                     {"contract": 1, "family": "software", "gates": [{"id": "checks", "kind": "command", "command": "make test"}]})
        rows = [{"session": "sess-1", "gate": "checks", "exit": 0, "at": "2026-11-10T10:15:00Z", "commit": "abc"}]
        (self.proj / ".brain" / "log" / "gates.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        self.env = mock.patch.dict(os.environ, {"BRAIN_NOW": "2026-11-10T11:00:00Z", "HOME": str(self.tmp / "home")})
        self.env.start()
        for name in ("BRAIN_TRANSCRIPT", "BRAIN_PROJECT", "CLAUDE_CODE_SESSION_ID", "BRAIN_SESSION_ID"):
            os.environ.pop(name, None)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp)

    def tracked(self, sid="sess-1"):
        return [r for f in sorted((self.brain / "learning" / "inbox").glob(f"*-{sid}.jsonl")) for r in c.read_jsonl(f)]

    def live_files(self):
        return sorted((self.brain / "learning" / "inbox" / ".live").glob("*.jsonl"))

    def marker(self):
        return c.read_json(self.proj / ".brain" / "log" / ledger.OPEN_MARKER)

    def close_cmd(self, *argv, sid="sess-1", transcript=MAIN, project=True):
        p = argparse.ArgumentParser(prog="brain")
        ledger.register(p.add_subparsers())
        args = p.parse_args(["close", *(["--project", str(self.proj)] if project else []), *argv])
        args.brain_root = self.brain
        buf = io.StringIO()
        env = {"BRAIN_SESSION_ID": sid, **({"BRAIN_TRANSCRIPT": str(transcript)} if transcript else {})}
        with mock.patch.dict(os.environ, env), redirect_stdout(buf):
            code = args.func(args)
        return code, buf.getvalue()


class ClosedSessionTest(LedgerBase):
    def test_stale_marker_of_a_closed_session_keeps_its_real_ledger(self):
        """core-03: checkpoint --push sends the open marker to the remote, close
        removes it only locally; a later boot that finds the marker again must
        not replace the session's real ledger with an 'unrecorded' stub."""
        ledger.mark_open(self.proj, "sess-1")
        stale = self.marker()
        code, out = self.close_cmd("--class", "build", "--tier", "2", "--outcome", "ok")
        self.assertEqual(code, 0, out)
        self.assertIsNone(self.marker())
        c.write_json(self.proj / ".brain" / "log" / ledger.OPEN_MARKER, stale)   # what a new clone holds
        line = ledger.repair_unclosed(self.proj, stale, self.brain)              # transcript is gone
        led = next(r for r in self.tracked() if r["kind"] == "ledger")
        self.assertNotIn("unrecorded", led)
        self.assertIn("claude-opus-5-5", led["models"])
        self.assertEqual(line, "")

    def test_boot_takes_over_the_marker_of_a_closed_session_silently(self):
        """core-03, both routes: the marker pushed before the close, and the
        marker left on a second project the session never closed on."""
        other = self.tmp / "other"
        c.write_json(other / ".brain" / "project.json", {"contract": 1, "family": "data"})
        for project in (self.proj, other):
            ledger.mark_open(project, "sess-1", brain_root=self.brain)
        self.close_cmd("--class", "build")
        c.write_json(self.proj / ".brain" / "log" / ledger.OPEN_MARKER, {"session": "sess-1", "at": "2026-11-10T10:00:00Z"})
        for project in (self.proj, other):
            with self.subTest(project.name):
                self.assertIsNone(ledger.mark_open(project, "sess-2", brain_root=self.brain))
                self.assertEqual(c.read_json(project / ".brain" / "log" / ledger.OPEN_MARKER)["session"], "sess-2")
        self.assertNotIn("unrecorded", next(r for r in self.tracked() if r["kind"] == "ledger"))

    def test_an_unclosed_session_is_still_reported(self):
        ledger.mark_open(self.proj, "sess-1", brain_root=self.brain)
        prev = ledger.mark_open(self.proj, "sess-2", brain_root=self.brain)
        self.assertEqual(prev["session"], "sess-1")
        self.assertIn("transcript is gone", ledger.repair_unclosed(self.proj, prev, self.brain))

    def test_a_real_record_is_never_replaced_by_a_stub(self):
        """core-03: a record an earlier capture left (not a close) survives a
        repair that finds neither a live file nor a transcript."""
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj)
        line = ledger.repair_unclosed(self.proj, {"session": "sess-1", "at": "2026-11-10T10:00:00Z"}, self.brain)
        self.assertIn("kept", line)
        self.assertNotIn("\n", line)
        self.assertIn("claude-opus-5-5", next(r for r in self.tracked() if r["kind"] == "ledger")["models"])

    def test_repro_prints_no_earlier_session_line(self):
        """core-03, through the command line: boot, checkpoint --push, close,
        then a new session on the project as the remote holds it."""
        ws = self.tmp / "ws"
        brain = ws / "Claude-Brain"
        shutil.copytree(ROOT, brain, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "docs", "tests"))
        shutil.rmtree(brain / "learning" / "inbox", ignore_errors=True)
        c.write_json(brain / "learning" / "radar" / "state.json", {"sources": {"x": {"last_checked": "2026-11-10T10:59:00Z"}}})
        remote, app = ws / "remote.git", ws / "app"
        sh(ws, "git", "init", "-q", "--bare", "-b", "main", str(remote))
        app.mkdir()
        git_init(app)
        sh(app, "git", "remote", "add", "origin", str(remote))
        (app / "README.md").write_text("# app\n")
        env = dict(os.environ, BRAIN_SESSION_ID="sess-X", BRAIN_TRANSCRIPT=str(MAIN))

        def b(*args, **extra):
            r = sh(ws, sys.executable, str(brain / "bin" / "brain"), *args, env={**env, **extra})
            self.assertEqual(r.returncode, 0, f"brain {' '.join(args)}\n{r.stdout}\n{r.stderr}")
            return r.stdout

        b("init", str(app), "--family", "software", "--title", "App")
        sh(app, "git", "add", "-A")
        sh(app, "git", "commit", "-q", "-m", "init")
        b("boot", "Continue")
        marker = app / ".brain" / "log" / ledger.OPEN_MARKER
        stale = c.read_json(marker)
        self.assertEqual(stale["session"], "sess-X")
        b("checkpoint", "--done", "CB-1", "--push")
        b("close", "--class", "software.feature", "--tier", "2", "--outcome", "ok")
        self.assertFalse(marker.exists())
        c.write_json(marker, stale)                                  # what a new container clones
        out = b("boot", "Continue", BRAIN_SESSION_ID="sess-Y", BRAIN_TRANSCRIPT=str(ws / "none.jsonl"))
        self.assertNotIn("earlier session", out)
        (inbox,) = (brain / "learning" / "inbox").glob("*-sess-X.jsonl")
        led = next(r for r in c.read_jsonl(inbox) if r["kind"] == "ledger")
        self.assertNotIn("unrecorded", led)
        self.assertIn("claude-opus-5-5", led["models"])


class CloseSizeTest(LedgerBase):
    def state(self, tier):
        c.write_text(self.proj / ".brain" / "STATE.md", f"# State\n\ncontract: 1\nstage: build\ntier: {tier}\nitem: x\n\n## Notes\n\ntier: 3\n")

    def outcome(self):
        return next(r for r in self.tracked() if r["kind"] == "outcome")

    def test_close_without_tier_takes_the_size_from_state_then_manifest(self):
        """e2e-trial-10: the documented close (no --tier) must label the outcome
        with the size the work ran at, or the sizing learner learns nothing."""
        self.state(2)
        code, out = self.close_cmd("--outcome", "ok", "--class", "software.feature", "--request", "build x")
        self.assertEqual(code, 0, out)
        o = self.outcome()
        self.assertEqual((o["tier"], next(r for r in self.tracked() if r["kind"] == "ledger")["tier"]), (2, 2))
        st = mlearn.fold(mlearn.empty_state(), [o], mlearn.config(self.brain))
        self.assertIn("2", st["sizing"]["counts"], "the sizing learner got a label for size 2")

    def test_manifest_size_is_the_fallback_and_the_flag_overrides(self):
        m = c.load_manifest(self.proj)
        m["tier"] = 3
        c.write_json(self.proj / ".brain" / "project.json", m)
        self.close_cmd("--class", "software.feature")
        self.assertEqual(self.outcome()["tier"], 3)
        self.state(2)
        self.close_cmd("--class", "software.feature")
        self.assertEqual(self.outcome()["tier"], 2)
        self.close_cmd("--class", "software.feature", "--tier", "1")
        self.assertEqual(self.outcome()["tier"], 1)

    def test_no_recorded_size_stays_empty(self):
        self.close_cmd("--class", "software.feature")
        self.assertIsNone(self.outcome()["tier"])


class LiveCaptureTest(LedgerBase):
    def test_hook_leaves_a_git_brain_clean(self):
        """lead-02: the session-end hook must not dirty the tree after every turn."""
        brain = self.tmp / "gitbrain"
        shutil.copytree(ROOT / "engine", brain / "engine", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / ".claude" / "hooks", brain / ".claude" / "hooks")
        (brain / "memory").mkdir()
        shutil.copy(ROOT / "memory" / "models.json", brain / "memory" / "models.json")
        shutil.copy(ROOT / ".gitignore", brain / ".gitignore")
        c.write_json(brain / "VERSION.json", {"brain": "1.0.0", "learned_zone_locked": False})
        git_init(brain)
        sh(brain, "git", "add", "-A")
        sh(brain, "git", "commit", "-q", "-m", "base")
        stdin = json.dumps({"session_id": "sess-1", "transcript_path": str(MAIN)})
        cwd = self.tmp / "elsewhere"
        cwd.mkdir()
        p = subprocess.run([sys.executable, "-B", str(brain / ".claude" / "hooks" / "session_end.py")], input=stdin,
                           capture_output=True, text=True, cwd=str(cwd))
        self.assertEqual((p.returncode, p.stdout + p.stderr), (0, ""))
        self.assertEqual(sh(brain, "git", "status", "--porcelain").stdout, "")
        (live,) = (brain / "learning" / "inbox" / ".live").glob("*-sess-1.jsonl")
        (rec,) = c.read_jsonl(live)
        self.assertEqual(rec["kind"], "ledger")
        self.assertIn("claude-opus-5-5", rec["models"])
        self.assertEqual(list((brain / "learning" / "inbox").glob("*.jsonl")), [])

    def test_real_gitignore_covers_the_live_folder(self):
        self.assertEqual(sh(ROOT, "git", "check-ignore", "-q", "learning/inbox/.live/2026-11-10-s.jsonl").returncode, 0)

    def test_live_capture_writes_nothing_in_the_project_and_keeps_the_session_open(self):
        """lead-02: a live capture is provisional, so the open marker stays
        (a later boot can still repair) and the project tree is not touched."""
        ledger.mark_open(self.proj, "sess-1", brain_root=self.brain)
        before = sorted(p.name for p in (self.proj / ".brain" / "log").iterdir())
        r = ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj, live=True)
        self.assertEqual(self.marker()["session"], "sess-1")
        self.assertEqual(sorted(p.name for p in (self.proj / ".brain" / "log").iterdir()), before)
        self.assertFalse((self.proj / "STATUS.md").exists())
        self.assertEqual((r["run_record"], Path(r["inbox"]).parent.name), ("", ".live"))
        self.assertEqual(self.tracked(), [])

    def test_close_after_a_live_capture_writes_one_tracked_record_and_removes_the_live_file(self):
        """lead-02: same totals, one tracked file, no live file left."""
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, None, live=True)
        (live,) = self.live_files()
        (was,) = c.read_jsonl(live)
        code, out = self.close_cmd("--class", "build", project=False)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.live_files(), [])
        self.assertEqual(len(list((self.brain / "learning" / "inbox").glob("*.jsonl"))), 1)
        (led,) = [r for r in self.tracked() if r["kind"] == "ledger"]
        self.assertEqual(led["models"]["claude-opus-5-5"], was["models"]["claude-opus-5-5"])
        self.assertEqual((led["id"], led["classes"]), (was["id"], ["build"]))

    def test_captures_keep_what_the_other_copy_knew(self):
        """lead-02: close → hook → close: what close declared survives in both
        directions, although the hook now writes somewhere else."""
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj, outcome="ok", classes=["build"], tier=2,
                       declared={"risk": "trivial", "est_tokens": 9000}, closed=True)
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj, live=True)
        (live,) = self.live_files()
        lrecs = c.read_jsonl(live)
        o = next(r for r in lrecs if r["kind"] == "outcome")
        led = next(r for r in lrecs if r["kind"] == "ledger")
        self.assertEqual((o["task_class"], o["risk"], o["est_tokens"], o["tier"]), ("build", "trivial", 9000, 2))
        self.assertEqual((led["classes"], led["outcome"], led.get("closed")), (["build"], "ok", True))
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj)
        o2 = next(r for r in self.tracked() if r["kind"] == "outcome")
        self.assertEqual((o2["risk"], o2["est_tokens"], o2["id"]), ("trivial", 9000, o["id"]))
        self.assertEqual(self.live_files(), [])

    def test_a_capture_that_cannot_see_the_project_keeps_the_outcomes(self):
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj, classes=["build"], tier=2)
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, None)
        self.assertEqual(sorted(r["kind"] for r in self.tracked()), ["ledger", "outcome"])

    def test_repair_uses_the_live_file_when_the_transcript_is_gone(self):
        """lead-02: the live file first, then the transcript, then the gap."""
        ledger.mark_open(self.proj, "sess-1", brain_root=self.brain)
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj, live=True)
        prev = ledger.mark_open(self.proj, "sess-2", brain_root=self.brain)
        self.assertEqual(prev["session"], "sess-1")
        line = ledger.repair_unclosed(self.proj, prev, self.brain)
        self.assertIn("last capture", line)
        self.assertNotIn("\n", line)
        (led,) = [r for r in self.tracked() if r["kind"] == "ledger"]
        self.assertNotIn("unrecorded", led)
        self.assertAlmostEqual(led["models"]["claude-opus-5-5"]["cost"], OPUS, places=9)
        self.assertEqual(self.live_files(), [])
        (run,) = (self.proj / ".brain" / "log").glob("*-sess-1.json")
        self.assertAlmostEqual(c.read_json(run)["totals"]["cost"], OPUS + SONNET + HELPER, places=6)
        self.assertEqual(self.marker()["session"], "sess-2")

    def test_a_live_file_does_not_fail_the_learned_zone_checks(self):
        """lead-02: the live file sits inside learning/, which `learn verify`
        and `guard diff` replay; an ignored, provisional file must not fail a locked brain."""
        c.write_json(self.brain / "VERSION.json", {"learned_zone_locked": True})
        shutil.copy(ROOT / ".gitignore", self.brain / ".gitignore")
        (self.brain / "evals").mkdir()
        (self.brain / "evals" / "known_project_ids.txt").write_text("# ids\n")
        git_init(self.brain)
        sh(self.brain, "git", "add", "-A")
        sh(self.brain, "git", "commit", "-q", "-m", "base")
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, None, live=True)
        self.assertEqual(len(self.live_files()), 1)
        self.assertEqual(sh(self.brain, "git", "status", "--porcelain").stdout, "")
        ok, lines = learn.verify(self.brain, "HEAD")
        self.assertTrue(ok, lines)
        ok, lines = guard.check_diff(self.brain, "HEAD")
        self.assertTrue(ok, lines)
        self.assertIn("0 kernel, 0 learned, 0 inbox", lines[0])
        self.assertEqual(learn.pending_inbox(self.brain), [])

    def test_promote_live_is_what_a_checkpoint_can_call(self):
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, None, live=True)
        written = ledger.promote_live(self.brain, "sess-1")
        self.assertEqual(written.parent.name, "inbox")
        self.assertEqual([r["kind"] for r in self.tracked()], ["ledger"])
        self.assertEqual(self.live_files(), [])
        self.assertIsNone(ledger.promote_live(self.brain, "sess-1"))

    def test_close_promotes_the_live_file_of_a_session_that_died(self):
        """lead-02: with no project there is no open marker, so the next close
        is what moves a dead session's capture into the tracked inbox."""
        ledger.capture(self.brain, "dead-1", MAIN, SUBS, None, live=True)
        self.close_cmd(project=False)
        self.assertEqual(self.live_files(), [])
        self.assertEqual([r["kind"] for r in self.tracked("dead-1")], ["ledger"])
        self.assertEqual([r["kind"] for r in self.tracked("sess-1")], ["ledger"])


class UnitsTest(LedgerBase):
    def test_active_minutes_cap_idle_gaps(self):
        """quality2-03: two bursts of 4 and 3 minutes twelve hours apart are not
        727 minutes of work; the idle gap counts as the cap (five minutes)."""
        t = write_transcript(self.tmp / "two.jsonl", ["2026-11-10T08:00:00Z", "2026-11-10T08:02:00Z", "2026-11-10T08:04:00Z",
                                                      "2026-11-10T20:04:00Z", "2026-11-10T20:05:00Z", "2026-11-10T20:07:00Z"])
        s = ledger.summarise(t, [], MODELS)
        self.assertEqual((s["wall_minutes"], s["active_minutes"]), (727.0, 12.0))
        self.assertEqual(ledger.summarise(t, [], MODELS, gap_minutes=1.0)["active_minutes"], 5.0)
        self.assertEqual(ledger.summarise(MAIN, SUBS, MODELS)["active_minutes"], 19.0)

    def test_gap_cap_is_read_from_the_learning_constants(self):
        self.assertEqual(ledger.gap_cap(self.brain), 5.0)
        cfg = c.read_json(self.brain / "memory" / "ml_config.json")
        cfg["ledger"] = {"active_gap_minutes": 2}
        c.write_json(self.brain / "memory" / "ml_config.json", cfg)
        self.assertEqual(ledger.gap_cap(self.brain), 2.0)

    def test_outcome_carries_output_equivalent_tokens(self):
        """quality2-03: cost divided by the main model's output price, the unit
        HR wages use; the raw token count (mostly cache reads) stays beside it."""
        s = ledger.summarise(MAIN, SUBS, MODELS)
        self.assertEqual((s["tokens_oe"], s["tokens_oe_main"]), (1841, 641))   # $0.03682 and $0.01282 at $20 per million
        ledger.capture(self.brain, "sess-1", MAIN, SUBS, self.proj, classes=["build", "fix"], tier=2)
        recs = self.tracked()
        o = next(r for r in recs if r["kind"] == "outcome")
        led = next(r for r in recs if r["kind"] == "ledger")
        self.assertEqual((o["tokens_oe"], o["tokens_oe_all"], o["active_minutes"]), (320, 920, 9.5))
        self.assertEqual((o["tokens"], o["minutes"]), (4205, 15.0))             # existing fields stay
        self.assertEqual((led["tokens_oe"], led["active_minutes"], led["wall_minutes"]), (1841, 19.0, 30.0))

    def test_unknown_usage_has_no_units(self):
        ledger.capture(self.brain, "sess-1", None, [], self.proj, classes=["build"])
        o = next(r for r in self.tracked() if r["kind"] == "outcome")
        self.assertEqual((o["tokens_oe"], o["tokens_oe_all"], o["active_minutes"]), (None, None, None))

    def test_unknown_model_is_flagged_not_silently_priced(self):
        """quality2-04: the fallback price is a guess, so say which model got it."""
        s = ledger.summarise(MAIN, SUBS, MODELS)
        self.assertEqual(s["unpriced_models"], ["mystery-model"])
        lines = ledger.format_summary("sess-1", s)
        self.assertEqual([l for l in lines if "fallback rate" in l],
                         ["priced at the fallback rate: mystery-model; add it to memory/models.json"])
        self.assertLessEqual(len(lines), 12)
        code, out = self.close_cmd()
        self.assertIn("priced at the fallback rate: mystery-model", out)
        self.assertLessEqual(len(out.splitlines()), 15)
        self.assertEqual(ledger.summarise(MAIN, [], MODELS)["unpriced_models"], [])
        self.assertNotIn("fallback", "\n".join(ledger.format_summary("sess-1", ledger.summarise(MAIN, [], MODELS))))

    def test_fast_mode_is_priced_only_with_a_recorded_multiplier(self):
        """quality2-04: fast mode was priced as standard without a word."""
        t = write_transcript(self.tmp / "fast.jsonl", ["2026-11-10T08:00:00Z"],
                             usage={"input_tokens": 0, "output_tokens": 1_000_000, "speed": "fast"})
        s = ledger.summarise(t, [], MODELS)
        self.assertEqual((s["totals"]["cost"], s["fast_at_standard"]), (20.0, 1))
        self.assertTrue(any("fast mode" in l for l in ledger.format_summary("s", s)))
        cfg = json.loads(json.dumps(MODELS))
        cfg["models"]["claude-opus-5-5"]["fast_multiplier"] = 3
        s = ledger.summarise(t, [], cfg)
        self.assertEqual((s["totals"]["cost"], s["fast_at_standard"]), (60.0, 0))

    def test_ledger_command_shows_both_units(self):
        lines = ledger.format_summary("sess-1", ledger.summarise(MAIN, SUBS, MODELS))
        self.assertIn("19.0 active", lines[0])
        self.assertTrue(any("1.8k output-equivalent" in l for l in lines), lines)


class CloseNoteTest(LedgerBase):
    def test_a_note_that_holds_a_credential_is_refused(self):
        """redteam-07: the note goes into the project's run record, which the
        next checkpoint commits and pushes."""
        code, out = self.close_cmd("--note", "deploy key is ghp_" + "a1B2" * 9)
        self.assertNotEqual(code, 0)
        self.assertIn("refused", out)
        self.assertNotIn("ghp_", out)
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertEqual(self.tracked(), [])
        self.assertEqual(list((self.proj / ".brain" / "log").glob("*-sess-1.json")), [])
        code, out = self.close_cmd("--note", "greeting fixed; docs next")
        self.assertEqual(code, 0, out)


def temp_brain(locked: bool) -> Path:
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "engine", tmp / "engine", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / ".claude" / "hooks", tmp / ".claude" / "hooks")
    (tmp / "memory").mkdir()
    shutil.copy(ROOT / "memory" / "models.json", tmp / "memory" / "models.json")
    c.write_json(tmp / "VERSION.json", {"brain": "1.0.0", "learned_zone_locked": locked})
    return tmp


def run_guard(brain: Path, payload, cwd: Path | None = None) -> tuple[int, str, str]:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    p = subprocess.run([sys.executable, "-B", str(brain / ".claude" / "hooks" / "guard_paths.py")], input=stdin,
                       capture_output=True, text=True, timeout=20, cwd=str(cwd or brain))
    return p.returncode, p.stdout, p.stderr


class GuardHookTest(unittest.TestCase):
    """quality-path-08: after the lock, one edit removed it. I-09 needs the
    hook to stop at kernel files, to refuse the lock's own files, and to see
    shell writes."""

    def setUp(self):
        self.brain = temp_brain(locked=True)

    def tearDown(self):
        shutil.rmtree(self.brain)

    def edit(self, rel, key="file_path"):
        return run_guard(self.brain, {"tool_name": "Edit", "tool_input": {key: str(self.brain / rel)}})

    def bash(self, command, cwd=None):
        return run_guard(self.brain, {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd or self.brain)})

    def test_guard_hook_asks_for_kernel_paths_when_locked(self):
        for rel in ("engine/learn.py", "CLAUDE.md", "memory/models.json", "docs/new-file.md"):
            with self.subTest(rel):
                code, out, err = self.edit(rel)
                self.assertEqual((code, err), (0, ""))
                decision = json.loads(out)["hookSpecificOutput"]
                self.assertEqual((decision["hookEventName"], decision["permissionDecision"]), ("PreToolUse", "ask"))
                self.assertIn("kernel change: needs the owner", decision["permissionDecisionReason"])
                self.assertEqual(len(out.strip().splitlines()), 1)

    def test_guard_hook_denies_the_lock_machinery(self):
        for rel in ("VERSION.json", ".claude/hooks/guard_paths.py", ".claude/hooks/new.py", ".claude/settings.json", "engine/guard.py"):
            with self.subTest(rel):
                code, out, err = self.edit(rel)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("lock", err)
                self.assertEqual(len(err.strip().splitlines()), 1)

    def test_guard_hook_reads_notebook_path(self):
        code, _, err = self.edit("memory/analysis.ipynb", key="notebook_path")
        self.assertEqual(code, 2)
        self.assertIn("learned zone", err)
        self.assertEqual(self.edit("learning/inbox/a.ipynb", key="notebook_path")[0], 0)

    def test_inbox_state_and_outside_paths_pass_silently(self):
        for rel in ("learning/inbox/2026-11-10-s.jsonl", "learning/radar/state.json"):
            self.assertEqual(self.edit(rel), (0, "", ""))
        outside = run_guard(self.brain, {"tool_input": {"file_path": str(self.brain.parent / "elsewhere.txt")}})
        self.assertEqual(outside, (0, "", ""))

    def test_bash_write_to_learned_zone_is_caught(self):
        b = self.brain
        writes = [
            "echo x >> memory/items.jsonl",
            f"echo x > {b}/owner/standing.jsonl",
            "cat new.jsonl | tee -a stats/ml.json",
            "sed -i 's/a/b/' playbooks/software.md",
            "rm -f memory/items.jsonl",
            "rm -rf memory",
            "mv memory/items.jsonl /tmp/gone.jsonl",
            "cp /tmp/forged.jsonl memory/items.jsonl",
            "git checkout -- memory/items.jsonl",
            "git restore learning/manifest.jsonl",
            "cd /tmp && truncate -s 0 \"$CLAUDE_PROJECT_DIR\"/memory/items.jsonl",
            "python3 -c \"open('memory/items.jsonl', 'w').write('x')\"",
            "sed -i 's/true/false/' VERSION.json",
            "echo '{}' > .claude/settings.json",
            "rm .claude/hooks/guard_paths.py",
            "cd memory && rm items.jsonl",
            "cd memory; echo x > items.jsonl",
            "bash -lc 'echo x > memory/items.jsonl'",
            "python3 - <<'PY'\nfrom pathlib import Path\nPath('memory/items.jsonl').write_text('x')\nPY",
            "git checkout -- .",
            "sudo rm -rf .claude",
        ]
        for command in writes:
            with self.subTest(command):
                code, out, err = self.bash(command)
                self.assertEqual((code, out), (2, ""), err)
                self.assertEqual(len(err.strip().splitlines()), 1)
                lock = any(x in command for x in ("VERSION", ".claude", "-- ."))
                self.assertIn("lock" if lock else "brain learn", err)
        reads = [
            "cat memory/items.jsonl",
            "wc -l memory/items.jsonl 2>/dev/null",
            "grep -c rule memory/items.jsonl > /tmp/count.txt",
            "cp memory/items.jsonl /tmp/backup.jsonl",
            "python3 bin/brain learn status 2>&1 | head -5",
            "git diff -- memory/items.jsonl",
            "echo x >> learning/inbox/2026-11-10-s.jsonl",
            "rm /tmp/memory/items.jsonl",
            "echo 'rm memory/items.jsonl is what the guard stops'",
            "sed -n 1,5p VERSION.json",
            "python3 bin/brain recall x > /tmp/out.txt; cat memory/items.jsonl",
            "python3 -c \"print(open('memory/items.jsonl').read())\"",
            "git checkout main",
            "git stash",
            "cp -r memory /tmp/backup",
            "cd /tmp && rm items.jsonl",
        ]
        for command in reads:
            with self.subTest(command):
                self.assertEqual(self.bash(command), (0, "", ""))

    def test_bash_paths_are_resolved_from_the_working_folder(self):
        sub = self.brain / "memory"
        self.assertEqual(self.bash("rm items.jsonl", cwd=sub)[0], 2)
        self.assertEqual(self.bash("rm items.jsonl", cwd=self.brain.parent)[0], 0)
        self.assertEqual(self.bash(f"rm {self.brain.name}/memory/items.jsonl", cwd=self.brain.parent)[0], 2)
        self.assertEqual(self.bash(f"git -C {self.brain} checkout -- memory/items.jsonl", cwd=self.brain.parent)[0], 2)

    def test_hook_still_fails_open_and_stays_fast(self):
        import time
        for stdin in ("not json", "", "[]", '{"tool_input": {}}', '{"tool_input": {"command": 5}}',
                      '{"tool_input": {"command": "echo \\"unbalanced"}}', '{"tool_input": {"command": ""}}'):
            with self.subTest(stdin):
                t0 = time.monotonic()
                self.assertEqual(run_guard(self.brain, stdin), (0, "", ""))
                self.assertLess(time.monotonic() - t0, 1.0)

    def test_an_unlocked_brain_behaves_as_before(self):
        c.write_json(self.brain / "VERSION.json", {"learned_zone_locked": False})
        for payload in ({"tool_input": {"file_path": str(self.brain / "VERSION.json")}},
                        {"tool_input": {"file_path": str(self.brain / "engine" / "learn.py")}},
                        {"tool_input": {"file_path": str(self.brain / "memory" / "items.jsonl")}},
                        {"tool_input": {"notebook_path": str(self.brain / "memory" / "a.ipynb")}},
                        {"tool_input": {"command": "rm -rf memory"}, "cwd": str(self.brain)}):
            with self.subTest(str(payload)[:60]):
                self.assertEqual(run_guard(self.brain, payload), (0, "", ""))


class GuardEngineTest(unittest.TestCase):
    def test_zone_of_ignores_case(self):
        """quality-path-08: on a disk that ignores case MEMORY/items.jsonl is memory/items.jsonl."""
        for path, zone in {"MEMORY/items.jsonl": "learned", "Owner/standing.jsonl": "learned",
                           "Learning/Inbox/a.jsonl": "inbox", "LEARNING/RADAR/state.json": "state",
                           "memory/MODELS.json": "kernel", "learning/promotion_rules.md": "kernel",
                           "Engine/learn.py": "kernel"}.items():
            with self.subTest(path):
                self.assertEqual(guard.zone_of(path), zone)

    def test_lock_machinery_is_named_in_one_place(self):
        for rel in ("VERSION.json", ".claude/settings.json", ".claude/hooks/x.py", "engine/guard.py", "version.json"):
            self.assertTrue(guard.is_lock_file(rel), rel)
        for rel in ("engine/learn.py", "memory/items.jsonl", ".claude/skills/x/SKILL.md"):
            self.assertFalse(guard.is_lock_file(rel), rel)

    def test_unlocking_in_a_diff_fails_guard(self):
        """quality-path-08: `guard diff` exited 0 on a diff that set the lock back to false."""
        root = Path(tempfile.mkdtemp())
        try:
            c.write_json(root / "VERSION.json", {"learned_zone_locked": True})
            (root / "evals").mkdir()
            (root / "evals" / "known_project_ids.txt").write_text("# ids\n")
            git_init(root)
            sh(root, "git", "add", "-A")
            sh(root, "git", "commit", "-q", "-m", "locked")
            ok, lines = guard.check_diff(root, "HEAD")
            self.assertTrue(ok, lines)
            for unlocked in ({"learned_zone_locked": False}, {"brain": "1.0.0"}):
                with self.subTest(unlocked):
                    c.write_json(root / "VERSION.json", unlocked)
                    ok, lines = guard.check_diff(root, "HEAD")
                    self.assertFalse(ok)
                    hit = [l for l in lines[:15] if "unlocks the learned zone" in l]
                    self.assertEqual(len(hit), 1, lines)
            (root / "VERSION.json").unlink()
            self.assertFalse(guard.check_diff(root, "HEAD")[0])
        finally:
            shutil.rmtree(root)

    def test_first_lock_is_not_an_unlock(self):
        root = Path(tempfile.mkdtemp())
        try:
            c.write_json(root / "VERSION.json", {"learned_zone_locked": False})
            git_init(root)
            sh(root, "git", "add", "-A")
            sh(root, "git", "commit", "-q", "-m", "open")
            c.write_json(root / "VERSION.json", {"learned_zone_locked": True})
            ok, lines = guard.check_diff(root, "HEAD")
            self.assertTrue(ok, lines)
        finally:
            shutil.rmtree(root)


class SettingsTest(unittest.TestCase):
    def commands(self):
        s = json.loads((ROOT / ".claude" / "settings.json").read_text())
        return [h["command"] for event in s["hooks"].values() for entry in event for h in entry["hooks"]]

    def test_hook_commands_exit_zero_when_the_script_is_missing(self):
        """quality-path-09: python3 exits 2 when it cannot open the script, and
        2 is the code that blocks an edit and blocks stopping."""
        empty = Path(tempfile.mkdtemp())
        try:
            self.assertGreaterEqual(len(self.commands()), 3)
            for command in self.commands():
                for env in ({"CLAUDE_PROJECT_DIR": str(empty)}, {}):
                    with self.subTest(command=command[-40:], env=bool(env)):
                        base = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
                        p = subprocess.run(["sh", "-c", command], input="{}", capture_output=True, text=True,
                                           env={**base, **env}, cwd=str(empty))
                        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))
        finally:
            shutil.rmtree(empty)

    def test_hook_commands_still_run_the_scripts(self):
        brain = temp_brain(locked=True)
        try:
            shutil.copy(ROOT / ".claude" / "settings.json", brain / ".claude" / "settings.json")
            payload = json.dumps({"tool_input": {"file_path": str(brain / "memory" / "items.jsonl")}})
            for command in [x for x in self.commands() if "guard_paths.py" in x]:
                p = subprocess.run(["sh", "-c", command], input=payload, capture_output=True, text=True,
                                   env={**os.environ, "CLAUDE_PROJECT_DIR": str(brain)})
                self.assertEqual(p.returncode, 2, p.stderr)
        finally:
            shutil.rmtree(brain)

    def test_the_guard_also_sees_shell_and_notebook_calls(self):
        s = json.loads((ROOT / ".claude" / "settings.json").read_text())
        matchers = {m for e in s["hooks"]["PreToolUse"] if "guard_paths.py" in e["hooks"][0]["command"] for m in e["matcher"].split("|")}
        self.assertLessEqual({"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"}, matchers)


def lint_brain(tmp: Path) -> Path:
    b = tmp / "brain"
    for d in (".claude/skills/demo", ".claude/agents", "method", "playbooks", "contract/template", "engine", "bin",
              "evals", "memory", "owner", "docs", "hr/rack", "tests"):
        (b / d).mkdir(parents=True)
    (b / "CLAUDE.md").write_text("# Brain\nUse `BRAIN boot` first.\n")
    (b / "contract/template/CLAUDE.stub.md").write_text("stub\n")
    (b / "bin/brain").write_text("import sys\n")
    (b / "engine/ok.py").write_text("import json\nfrom . import common\n")
    return b


class LintCommandTest(unittest.TestCase):
    """quality-path-13 and instructions-18: what the command check let through."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.b = lint_brain(Path(self._tmp.name))
        self.tree = lint.command_tree()

    def tearDown(self):
        self._tmp.cleanup()

    def skill(self, body: str, description: str = "d"):
        (self.b / ".claude/skills/demo/SKILL.md").write_text(f"---\nname: demo\ndescription: {description}\n---\n{body}")

    def errors(self) -> str:
        return " | ".join(lint.check_commands(self.b, self.tree))

    def test_invalid_choice_is_an_error(self):
        """quality-path-13: `BRAIN checkpoint --stage shipping` passed the lint."""
        self.skill("Run `BRAIN checkpoint --stage shipping`, then `BRAIN close --outcome great`, then `brain close --tier 9`,\n"
                   "then `BRAIN guard path x --mode strict` and `BRAIN close --est-tokens many`.\n")
        errs = self.errors()
        for needle in ("'shipping'", "'great'", "'9'", "'strict'", "'many'"):
            self.assertIn(needle, errs)
        self.assertEqual(len(lint.check_commands(self.b, self.tree)), 5)
        self.assertIn(".claude/skills/demo/SKILL.md: `brain checkpoint`", errs)

    def test_valid_and_schematic_values_pass(self):
        self.skill("`BRAIN checkpoint --stage build --tier 2`, `BRAIN close --outcome ok|partial|failed`,\n"
                   "`BRAIN checkpoint --stage <stage> --tier N --done \"<what was finished>\" --push`,\n"
                   "`brain close --tier 2 --class software.feature --used ID:FOLLOWED --est-tokens <n>`,\n"
                   "`BRAIN close --outcome`, `BRAIN guard path <file> --mode work|learn|bootstrap`, `brain close [--tier N]`\n")
        self.assertEqual(lint.check_commands(self.b, self.tree), [])

    def test_missing_required_option_is_an_error(self):
        """quality-path-13: `BRAIN req drop R-001` (no --reason) passed the lint."""
        self.skill("`BRAIN req drop R-001` and `BRAIN guard path --mode work`\n")
        errs = lint.check_commands(self.b, self.tree)
        self.assertEqual(len(errs), 2, errs)
        self.assertTrue(any("`brain req drop`" in e and "--reason" in e for e in errs), errs)
        self.assertTrue(any("`brain guard path`" in e and "path" in e for e in errs), errs)
        self.skill("`BRAIN req drop R-001 --reason \"superseded by R-004\"`, `BRAIN req drop <id> --reason \"<why>\"`,\n"
                   "the bare names `BRAIN req drop` and `brain guard path`, and `BRAIN guard path memory/items.jsonl`;\n"
                   "a flag or a slot named alone is a reference, not a call: `BRAIN req evidence --done`, `BRAIN req drop <id>`\n")
        self.assertEqual(lint.check_commands(self.b, self.tree), [])

    def test_path_and_variable_call_forms_are_checked(self):
        """quality-path-13: only `BRAIN x`, `bin/brain x` and `brain x` after a space were read."""
        self.skill("`python3 Claude-Brain/bin/brain bogus --nope`, `\"$BRAIN\" req bogus`, `$BRAIN frobnicate`,\n"
                   "`${BRAIN} checkpoint --finished X` and `python3 \"$CLAUDE_PROJECT_DIR\"/bin/brain nonesuch`\n")
        errs = self.errors()
        for needle in ("`brain bogus` does not exist", "`brain req bogus` does not exist", "`brain frobnicate` does not exist",
                       "no flag --finished", "`brain nonesuch` does not exist"):
            self.assertIn(needle, errs)
        self.skill("`python3 Claude-Brain/bin/brain boot \"<request>\"`, `\"$BRAIN\" req list`, `$BRAIN doctor`,\n"
                   "`python3 <folder of this file>/bin/brain lint`\n")
        self.assertEqual(lint.check_commands(self.b, self.tree), [])

    def test_a_chain_is_read_as_separate_commands(self):
        self.skill("```\nBRAIN gate && BRAIN release --push\nBRAIN lint | head -5\nBRAIN ledger --json > /tmp/ledger.json  # keep it\n"
                   "BRAIN doctor; BRAIN budget\n```\n")
        self.assertEqual(lint.check_commands(self.b, self.tree), [])
        self.skill("```\nBRAIN gate && BRAIN release --force\n```\n")
        self.assertEqual(lint.check_commands(self.b, self.tree), [".claude/skills/demo/SKILL.md: `brain release` has no flag --force"])

    def test_stale_command_in_a_memory_item_is_an_error(self):
        """quality-path-13: the handover note, the HR guidelines, the rack and the item files were not scanned."""
        row = {"id": "rule-a", "text": "Run builds through `brain frobnicate` so only failures enter the conversation."}
        (self.b / "memory/items.jsonl").write_text(json.dumps(row) + "\n")
        (self.b / "hr/rack/build.jsonl").write_text(json.dumps({"id": "t-1", "method": ["First `brain run -- make test`.", "Then `brain req approve R-1`."]}) + "\n")
        (self.b / "playbooks/software.jsonl").write_text(json.dumps({"id": "pb-1", "text": "Release with `brain release --force`."}) + "\n")
        (self.b / "owner/standing.jsonl").write_text(json.dumps({"id": "own-1", "text": "He says `brain status --loud`."}) + "\n")
        (self.b / "docs/NEXT_SESSION.md").write_text("Pre-register with `brain eval preregister`.\n")
        (self.b / "hr/GUIDELINES.md").write_text("`brain hr hire --chek x` renders the brief.\n")
        errs = self.errors()
        for needle in ("memory/items.jsonl (rule-a): `brain frobnicate` does not exist", "hr/rack/build.jsonl (t-1): `brain req approve` does not exist",
                       "playbooks/software.jsonl (pb-1): `brain release` has no flag --force", "owner/standing.jsonl (own-1): `brain status` has no flag --loud",
                       "docs/NEXT_SESSION.md: `brain eval preregister` does not exist", "hr/GUIDELINES.md: `brain hr` has no flag --chek"):
            self.assertIn(needle, errs)
        self.assertEqual(len(lint.check_commands(self.b, self.tree)), 6)
        (self.b / "memory/items.jsonl").write_text(json.dumps({"id": "rule-a", "text": "Use `brain run` and `brain recall \"<topic>\"`."}) + "\n")
        for rel in ("hr/rack/build.jsonl", "playbooks/software.jsonl", "owner/standing.jsonl", "docs/NEXT_SESSION.md", "hr/GUIDELINES.md"):
            (self.b / rel).unlink()
        self.assertEqual(lint.check_commands(self.b, self.tree), [])

    def test_the_real_data_files_are_scanned(self):
        labels = {label.split(" (")[0] for label, _ in lint.command_texts(ROOT)}
        for rel in ("docs/NEXT_SESSION.md", "hr/GUIDELINES.md", "memory/items.jsonl", "playbooks/software.jsonl", "CLAUDE.md"):
            self.assertIn(rel, labels)
        self.assertTrue(any(l.startswith("hr/rack/") for l in labels))

    def test_commands_nobody_names_are_listed(self):
        """instructions-18: a subcommand no instruction file names is a dead feature or a missing line."""
        self.skill("`BRAIN req add --quote \"x\"` then `BRAIN req list|check` and `brain hr`\n")
        unnamed = lint.unnamed_commands(self.b, self.tree)
        for name in ("lint", "guard diff", "req drop", "hr hire"):
            self.assertIn(name, unnamed)
        for name in ("boot", "req add", "req list", "req check"):
            self.assertNotIn(name, unnamed)


class LintRuleTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.b = lint_brain(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def skill(self, body: str, description: str = "d"):
        (self.b / ".claude/skills/demo/SKILL.md").write_text(f"---\nname: demo\ndescription: {description}\n---\n{body}")

    def test_repeated_sentence_fails_the_lint(self):
        """quality-path-13: EXECUTION_PLAN 4.6 lists repeated sentences among what lint exits non-zero on."""
        sentence = "Run builds and tests through the output filter so that only failures enter the conversation.\n"
        for name in ("a", "b"):
            (self.b / f"method/{name}.md").write_text(f"# {name}\n\n{sentence}")
        self.assertFalse(any("repeated in" in e for e in lint.run(self.b)[0]))
        (self.b / "method/c.md").write_text(f"# c\n\n{sentence}")
        errs, notes = lint.run(self.b)
        self.assertEqual(len([e for e in errs if "repeated in 3 files" in e]), 1, errs)
        self.assertFalse(any("repeated in" in n for n in notes))

    def test_constant_that_disagrees_with_the_code_is_reported(self):
        """quality-path-13: models.json said recall budget 600, the code uses 300, and nothing compared them."""
        self.assertEqual(lint.check_constants(self.b), [])                       # no file, nothing to compare
        c.write_json(self.b / "memory/models.json", {"limits": {"max_parallel_helpers": 4, "recall_budget_tokens": 600}})
        (hit,) = lint.check_constants(self.b)
        for needle in ("memory/models.json", "limits.recall_budget_tokens", "600", "300", "engine/recall.py"):
            self.assertIn(needle, hit)
        c.write_json(self.b / "memory/models.json", {"limits": {"max_parallel_helpers": 4, "recall_budget_tokens": 300}})
        self.assertEqual(lint.check_constants(self.b), [])
        c.write_json(self.b / "memory/models.json", {"models": {}})
        self.assertEqual(lint.check_constants(self.b), [])

    def test_trigger_phrase_without_a_routing_case_is_reported(self):
        """instructions-18: 26 quoted trigger phrases had no case in evals/routing.jsonl."""
        self.skill("body\n", 'Resume or ship. Use for "Start running", "Ship it", or "Nuevo proyecto: …".')
        (self.b / "evals/routing.jsonl").write_text(json.dumps({"text": "ok start running now", "tier": 2}) + "\n"
                                                    + json.dumps({"text": "Nuevo proyecto: una web", "tier": 2}) + "\n")
        self.assertEqual(lint.check_triggers(self.b), ['demo: trigger phrase "ship it" has no case in evals/routing.jsonl'])
        with open(self.b / "evals/routing.jsonl", "a") as f:
            f.write(json.dumps({"text": "Ship it!", "tier": 2}) + "\n")
        self.assertEqual(lint.check_triggers(self.b), [])

    def test_every_real_skill_has_its_trigger_phrases_read(self):
        triggers = lint.skill_triggers(ROOT)
        self.assertEqual(sorted(triggers), sorted(p.parent.name for p in (ROOT / ".claude" / "skills").glob("*/SKILL.md")))
        self.assertTrue(all(t == t.lower() and not t.endswith("…") for ts in triggers.values() for t in ts))

    def test_marked_fact_that_drifted_is_an_error(self):
        """quality-path-20: numbers restated by hand drift; a marked number is compared with the code."""
        doc = self.b / "docs/BUILD_STATUS.md"
        (self.b / "tests/test_x.py").write_text("class T:\n    def test_a(self): pass\n    def test_b(self): pass\n\ndef helper(): pass\n")
        (self.b / "hr/rack/a.jsonl").write_text('{"id": "t-1"}\n{"id": "t-2"}\n{"id": "t-3"}\n')
        size = len((self.b / "CLAUDE.md").read_bytes())
        self.assertEqual({k: f(self.b) for k, f in lint.FACTS.items()},
                         {"engine-modules": 1, "claude-md-bytes": size, "templates": 3, "tests": 2})
        doc.write_text(f"Core: <!-- fact: engine-modules -->1<!-- /fact --> modules, `CLAUDE.md` <!-- fact: claude-md-bytes -->{size}<!-- /fact --> bytes,\n"
                       "<!-- fact: templates -->3<!-- /fact --> templates, <!-- fact: tests -->2<!-- /fact --> tests.\n")
        self.assertEqual(lint.check_facts(self.b), [])
        doc.write_text("Core: <!-- fact: engine-modules -->21<!-- /fact --> modules, `CLAUDE.md` <!-- fact: claude-md-bytes -->5,356<!-- /fact --> bytes; "
                       "<!-- fact: tests -->2<!-- /fact --> tests; <!-- fact: lines -->9500<!-- /fact --> lines.\n")
        errs = lint.check_facts(self.b)
        self.assertEqual(len(errs), 3, errs)
        self.assertIn("docs/BUILD_STATUS.md: engine-modules is marked 21 but the code says 1", errs[0] + errs[1] + errs[2])
        self.assertTrue(any("claude-md-bytes is marked 5,356" in e and str(size) in e for e in errs))
        self.assertTrue(any("unknown fact 'lines'" in e for e in errs))
        self.assertTrue(all("lint --fix-facts" in e for e in errs if "unknown" not in e))
        self.assertTrue(any("fact" in e for e in lint.run(self.b)[0]))
        self.assertEqual(lint.fix_facts(self.b), 2)
        text = doc.read_text()
        self.assertIn("<!-- fact: engine-modules -->1<!-- /fact -->", text)
        self.assertIn(f"<!-- fact: claude-md-bytes -->{size:,}<!-- /fact -->", text)
        self.assertEqual([e for e in lint.check_facts(self.b) if "unknown" not in e], [])
        self.assertEqual(lint.fix_facts(self.b), 0)

    def test_a_marker_shown_as_an_example_is_not_a_claim(self):
        doc = self.b / "docs/HOWTO.md"
        example = "Mark a number like this: `<!-- fact: tests -->410<!-- /fact -->`.\n\n```\n<!-- fact: templates -->7<!-- /fact -->\n```\n"
        doc.write_text(example)
        self.assertEqual(lint.check_facts(self.b), [])
        self.assertEqual(lint.fix_facts(self.b), 0)
        self.assertEqual(doc.read_text(), example)

    def test_fact_values_of_the_real_brain(self):
        self.assertEqual(lint.FACTS["templates"](ROOT), 100)
        self.assertEqual(lint.FACTS["engine-modules"](ROOT), len([p for p in (ROOT / "engine").glob("*.py") if p.name != "__init__.py"]))
        self.assertEqual(lint.FACTS["claude-md-bytes"](ROOT), (ROOT / "CLAUDE.md").stat().st_size)
        self.assertGreater(lint.FACTS["tests"](ROOT), 400)

    def test_absolute_rule_without_a_reason_in_a_skill_or_agent_is_noted(self):
        """instructions-18: the reason check read only CLAUDE.md."""
        self.skill("1. Never push to main.\n2. Always run the gate, because a red build must not ship.\n")
        (self.b / ".claude/agents/builder.md").write_text("---\nname: builder\ndescription: never mind\n---\nAlways return the path.\n")
        notes = lint.unscoped_absolutes(self.b)
        self.assertEqual(len(notes), 2, notes)
        self.assertTrue(notes[0].startswith(".claude/agents/builder.md:5:") or notes[1].startswith(".claude/agents/builder.md:5:"), notes)
        self.assertTrue(any(n.startswith(".claude/skills/demo/SKILL.md:5:") for n in notes), notes)

    def test_token_number_in_an_agent_body_is_noted(self):
        """instructions-18: hr/GUIDELINES.md forbids token numbers in agent text; all six agents had one."""
        (self.b / ".claude/agents/builder.md").write_text("---\nname: builder\ndescription: builds; 2,000 tokens here is front matter\n---\n"
                                                         "Return, in under about 2,000 tokens: files changed.\nKeep the reply short.\nUse 40k tokens at most.\n")
        notes = lint.agent_token_numbers(self.b)
        self.assertEqual(len(notes), 2, notes)
        self.assertTrue(notes[0].startswith(".claude/agents/builder.md:5:"), notes)
        (self.b / ".claude/agents/builder.md").write_text("---\nname: builder\ndescription: d\n---\nReturn a short list; long logs go in a file.\n")
        self.assertEqual(lint.agent_token_numbers(self.b), [])

    def test_a_rule_listed_as_note_only_does_not_fail_the_lint(self):
        """The lead's switch: a new rule that fires on files another package owns reports until they are fixed."""
        self.skill("body\n", 'Use for "Ship it".')
        (self.b / "evals/routing.jsonl").write_text(json.dumps({"text": "hello"}) + "\n")
        with mock.patch.object(lint, "NOTE_ONLY", frozenset({"triggers"})):
            errs, notes = lint.run(self.b)
            self.assertFalse(any("ship it" in e for e in errs))
            self.assertTrue(any("ship it" in n for n in notes))
        with mock.patch.object(lint, "NOTE_ONLY", frozenset()):
            errs, notes = lint.run(self.b)
            self.assertTrue(any("ship it" in e for e in errs))

    def test_helper_reply_over_cap_is_reported(self):
        """quality-path-13: the spec's 'sub-agent replies over cap' rule was missing from lint --transcript."""
        big, small = "x" * 9000, "y" * 400
        rows = [
            {"type": "assistant", "message": {"model": "m1", "content": [{"type": "tool_use", "id": "a1", "name": "Agent", "input": {}},
                                                                       {"type": "tool_use", "id": "a2", "name": "Task", "input": {}},
                                                                       {"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "a.py"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "a1", "content": big},
                                                     {"type": "tool_result", "tool_use_id": "a2", "content": [{"type": "text", "text": small}]},
                                                     {"type": "tool_result", "tool_use_id": "r1", "content": big}]}},
        ]
        t = Path(self._tmp.name) / "t.jsonl"
        t.write_text("".join(json.dumps(r) + "\n" for r in rows))
        lines = lint.transcript_report(t, [])
        self.assertIn("helper replies over ~2,000 tokens: 1 of 2", "\n".join(lines))
        self.assertLessEqual(len(lines), 8)


class LintOutputTest(unittest.TestCase):
    def lint(self, *args):
        return sh(ROOT, sys.executable, str(ROOT / "bin" / "brain"), "lint", *args)

    def test_lint_output_stays_short_and_notes_are_grouped(self):
        """I-04: one line per rule with a count, however many hits a rule has."""
        r = self.lint()
        self.assertEqual(r.returncode, 0, r.stdout)
        lines = r.stdout.strip().splitlines()
        self.assertLessEqual(len(lines), 15, r.stdout)
        self.assertRegex(lines[-1], r"^lint: 0 error\(s\), \d+ note\(s\)")
        notes = [l for l in lines if l.startswith("note:")]
        self.assertTrue(all(len(l) <= 260 for l in notes), notes)

    def test_all_flag_lists_every_hit(self):
        self.assertEqual(self.lint("--all").returncode, 0)
        short, full = self.lint().stdout, self.lint("--all").stdout
        total = int(re.search(r"(\d+) note\(s\)", short).group(1))
        self.assertEqual(len([l for l in full.splitlines() if l.startswith("note:")]), total)


if __name__ == "__main__":
    unittest.main()
