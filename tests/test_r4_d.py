"""Package D (CB-215): the requirements ledger and the done report.

Typed evidence that the engine resolves itself, stored checks that are run,
the owner's request held in the project so the ledger can be checked against
it, drops that stay visible, several lines per `req add`, secrets refused,
and one verdict command, `brain done`.

Every test works in a temporary folder; a remote is a local bare repository.
"""
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import common as c, contract, gate, req, state  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("brain_cli_r4_d", str(ROOT / "bin" / "brain"))
_cli = importlib.util.module_from_spec(importlib.util.spec_from_loader("brain_cli_r4_d", _loader))
_loader.exec_module(_cli)

FAKE_KEY = "sk-" + "a1B2c3D4" * 5  # made up; shaped like a key so the scan fires


def sh(cwd, *args):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def commit_all(path: Path, msg="c"):
    sh(path, "git", "add", "-A")
    sh(path, "git", "commit", "-q", "-m", msg)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self._env = dict(os.environ)
        for k in ("BRAIN_PROJECT", "CLAUDE_CODE_SESSION_ID", "BRAIN_TRANSCRIPT", "BRAIN_NOW"):
            os.environ.pop(k, None)
        os.environ["BRAIN_SESSION_ID"] = "sess-d"
        os.environ["BRAIN_NO_NETWORK"] = "1"
        self.p = self.ws / "proj"
        self.p.mkdir()
        for cmd in (["git", "init", "-q", "-b", "work"], ["git", "config", "user.email", "t@example.invalid"],
                    ["git", "config", "user.name", "t"], ["git", "config", "commit.gpgsign", "false"]):
            sh(self.p, *cmd)
        (self.p / "README.md").write_text("# x\nline two\nline three\n")
        contract.init(self.p, "Proj", "software")
        commit_all(self.p, "init")
        os.environ["BRAIN_PROJECT"] = str(self.p)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    def cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = _cli.main(list(argv))
        return code, buf.getvalue()

    def building(self, tier=2):
        """Project size, build stage: from here the strict rule applies."""
        state.checkpoint(self.p, stage="build", tier=tier, item="T-1")

    def add(self, quote="it must greet people by their name", passes="greet.sh Ana prints Hello Ana", check=None):
        argv = ["req", "add", "--quote", quote, "--passes-when", passes] + (["--check", check] if check else [])
        code, out = self.cli(*argv)
        self.assertEqual(code, 0, out)
        return out.split()[0]

    def row(self, rid="R-001"):
        return req.find(req.load(self.p), rid)

    def ledger(self) -> str:
        return (self.p / ".brain" / "requirements.jsonl").read_text()

    def set_gate(self, command: str):
        m = c.load_manifest(self.p)
        m["gates"] = [{"id": "checks", "kind": "command", "command": command}]
        c.write_json(self.p / ".brain" / "project.json", m)
        commit_all(self.p, "gate")


class EvidenceTests(Base):
    def test_empty_evidence_is_refused(self):
        """quality-path-01: `req evidence R-004 "" --done` closed a line on nothing."""
        self.add()
        before = self.ledger()
        for blank in ("", "   "):
            code, out = self.cli("req", "evidence", "R-001", blank, "--done")
            self.assertEqual(code, 1, out)
            self.assertIn("empty", out)
        self.assertEqual(self.ledger(), before)
        self.assertEqual(self.row()["status"], "open")

    def test_typed_evidence_must_resolve(self):
        """quality-path-01, e2e-trial-06, redteam-08: a gate that never ran, a
        run log that does not exist and a missing file each closed a line."""
        self.add()
        before = self.ledger()
        for item, needle in (("gate:checks exit 0", "no run of gate"), ("run:does-not-exist.log", "no run log"),
                             ("file:/nope/nothing.txt", "no such path"), ("path:no/such/file.py", "no such path"),
                             ("test:test_never_ran", "not in the output"), ("commit:0123456789abcdef", "no commit")):
            code, out = self.cli("req", "evidence", "R-001", item, "--done")
            self.assertEqual(code, 1, f"{item}: {out}")
            self.assertIn(needle, out, item)
            self.assertEqual(self.ledger(), before, item)
        self.assertEqual(len(out.splitlines()), 1, "a refusal is one line")

    def test_free_text_is_a_note_and_closes_nothing_at_project_size(self):
        """redteam-08 ('looks fine' closed a line), e2e-trial-06 (a path that
        does not exist closed a line before its code existed)."""
        self.add()
        self.building()
        for text in ("looks fine", "no/such/file.log"):
            before = self.ledger()
            code, out = self.cli("req", "evidence", "R-001", text, "--done")
            self.assertEqual(code, 1, out)
            self.assertIn("not marked done", out)
            self.assertIn("brain req verify", out)  # the refusal names the next step
            self.assertEqual(self.ledger(), before)
        code, out = self.cli("req", "evidence", "R-001", "looks fine")  # without --done it is kept, as a note
        self.assertEqual(code, 0, out)
        self.assertEqual(self.row()["evidence"], ["note: looks fine"])
        self.assertEqual(self.row()["status"], "open")
        code, out = self.cli("req", "evidence", "R-001", "x" * 300 + " and a second sentence that is far too long to be a file name " * 4)
        self.assertEqual(code, 0, out)  # long free text is a note, never a crash on a path lookup

    def test_strict_check_fails_on_claim_only_lines(self):
        """quality-path-01, redteam-08: before the build stage free text still
        closes a line (decision 8), but the check at project size from build
        on says it is done on a claim, and fails."""
        self.add()
        code, out = self.cli("req", "evidence", "R-001", "e2e log run 14: offline spec passed", "--done")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.row()["status"], "done")
        self.assertEqual(self.cli("req", "check")[0], 0)
        self.building()
        code, out = self.cli("req", "check")
        self.assertEqual(code, 1, out)
        self.assertIn("R-001: done but not verified", out)
        self.assertIn("(not verified)", (self.p / ".brain" / "REQUIREMENTS.md").read_text())

    def test_gate_evidence_needs_a_green_gate_by_this_session_on_the_current_work(self):
        """quality-path-01, redteam-08: `gate:checks` was accepted with no gate run."""
        self.add()
        self.add("it must say goodbye on the way out", "bye.sh prints Bye")
        self.building()
        self.set_gate("test -f ok.txt")
        gate.run_gates(self.p)
        code, out = self.cli("req", "evidence", "R-001", "gate:checks", "--done")
        self.assertEqual(code, 1, out)
        self.assertIn("last exited 1", out)
        (self.p / "ok.txt").write_text("1")
        commit_all(self.p, "work")
        gate.run_gates(self.p)
        head = sh(self.p, "git", "rev-parse", "HEAD").stdout.strip()
        code, out = self.cli("req", "evidence", "R-001", "gate:checks exit 0", "--done")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.row()["evidence"], [f"gate:checks exit 0 @{head[:7]}"])
        self.assertEqual(self.row()["status"], "done")
        os.environ["BRAIN_SESSION_ID"] = "another-session"
        code, out = self.cli("req", "evidence", "R-002", "gate:checks", "--done")
        self.assertEqual(code, 1, out)
        self.assertIn("not by this session", out)
        os.environ["BRAIN_SESSION_ID"] = "sess-d"
        (self.p / "feature.txt").write_text("new work")
        commit_all(self.p, "more work")
        code, out = self.cli("req", "evidence", "R-002", "gate:checks", "--done")
        self.assertEqual(code, 1, out)
        self.assertIn("work has changed", out)
        self.assertEqual(self.row("R-002")["status"], "open")

    def test_run_and_test_evidence_resolve_against_passing_logs(self):
        """quality-path-01, e2e-trial-06: `run:` and `test:` pointers were never opened."""
        self.add()
        self.add("it must say goodbye on the way out", "bye.sh prints Bye")
        self.building()
        good = Path(gate.run_filtered("echo test_greets_by_name ... ok", self.p, self.p)["log"])
        bad = Path(gate.run_filtered("echo test_says_goodbye ... FAIL; exit 3", self.p, self.p)["log"])
        code, out = self.cli("req", "evidence", "R-002", f"run:{bad.name}", "--done")
        self.assertEqual(code, 1, out)
        self.assertIn("exit 3", out)
        code, out = self.cli("req", "evidence", "R-002", "test:test_says_goodbye", "--done")
        self.assertEqual(code, 1, out)
        code, out = self.cli("req", "evidence", "R-001", f"run:{good.name}", "test:test_greets_by_name", "--done")
        self.assertEqual(code, 0, out)
        ev = self.row()["evidence"]
        self.assertTrue(ev[0].startswith(f"run:{good.name} exit 0 #"), ev)
        self.assertEqual(ev[1], f"test:test_greets_by_name in {good.name}")
        # The path `brain run` prints is accepted as it is, and still has to be a passing run.
        code, out = self.cli("req", "evidence", "R-002", str(bad), "--done")
        self.assertEqual(code, 1, out)
        code, out = self.cli("req", "evidence", "R-002", str(good), "--done")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.row("R-002")["evidence"][0].startswith(f"run:{good.name} exit 0 #"))

    def test_path_evidence_must_exist_inside_the_project(self):
        """e2e-trial-06: the skill's own suggestion, a path or path:line, was stored unread."""
        self.add()
        self.building()
        (self.p / "docs" / "evidence").mkdir(parents=True)
        (self.p / "docs" / "evidence" / "shot.txt").write_text("screenshot\n")
        (self.ws / "outside.txt").write_text("x")
        for item, needle in (("README.md:99", "no line 99"), (f"path:{self.ws / 'outside.txt'}", "no such path"),
                             ("path:../outside.txt", "no such path")):
            code, out = self.cli("req", "evidence", "R-001", item, "--done")
            self.assertEqual(code, 1, f"{item}: {out}")
            self.assertIn(needle, out)
        code, out = self.cli("req", "evidence", "R-001", "README.md:2", "shot.txt", "path:docs", "--done")
        self.assertEqual(code, 0, out)
        ev = self.row()["evidence"]
        self.assertRegex(ev[0], r"^path:README\.md:2 #[0-9a-f]{12}$")
        self.assertRegex(ev[1], r"^path:docs/evidence/shot\.txt #[0-9a-f]{12}$")  # found under paths.evidence
        self.assertEqual(ev[2], "path:docs/")
        self.assertEqual(self.row()["status"], "done")

    def test_commit_evidence_must_exist(self):
        self.add()
        self.building()
        head = sh(self.p, "git", "rev-parse", "HEAD").stdout.strip()
        code, out = self.cli("req", "evidence", "R-001", "commit:HEAD", "--done")
        self.assertEqual(code, 1, out)
        code, out = self.cli("req", "evidence", "R-001", f"commit:{head[:9]}", "--done")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.row()["evidence"][0].startswith(f"commit:{head[:12]}"), self.row()["evidence"])

    def test_url_evidence_is_checked_live_unless_the_network_is_off(self):
        """redteam-08: url:<address> checked live."""
        self.add()
        self.building()
        calls = []
        real = gate.check_live
        answers = {"https://up.example.invalid/": (True, "live address answered 200"),
                   "https://down.example.invalid/": (False, "not confirmed after 0s: refused")}

        def fake(url, expect="", wait_seconds=120, every=20.0):
            calls.append((url, wait_seconds))
            return answers[url]
        gate.check_live = fake
        try:
            code, out = self.cli("req", "evidence", "R-001", "url:https://up.example.invalid/", "--done")
            self.assertEqual((code, calls), (1, []), out)  # network off: stored as a note, which closes nothing
            self.assertIn("not marked done", out)
            del os.environ["BRAIN_NO_NETWORK"]
            code, out = self.cli("req", "evidence", "R-001", "url:https://down.example.invalid/", "--done")
            self.assertEqual(code, 1, out)
            self.assertIn("did not answer", out)
            code, out = self.cli("req", "evidence", "R-001", "url:ftp://up.example.invalid/", "--done")
            self.assertEqual(code, 1, out)
            code, out = self.cli("req", "evidence", "R-001", "https://up.example.invalid/", "--done")
            self.assertEqual(code, 0, out)
        finally:
            gate.check_live = real
        self.assertEqual(calls[-1], ("https://up.example.invalid/", 0))  # one bounded try, no polling
        self.assertTrue(self.row()["evidence"][0].startswith("url:https://up.example.invalid/ answered 200"))

    def test_owner_evidence_is_verified_in_the_transcript(self):
        """redteam-08: owner:<quote> verified in the transcript."""
        self.add()
        self.building()
        code, out = self.cli("req", "evidence", "R-001", "owner:the greeting looks right to me now", "--done")
        self.assertEqual(code, 1, out)  # no transcript on disk
        t = self.ws / "sess-d.jsonl"
        t.write_text(json.dumps({"type": "user", "timestamp": "2026-11-10T10:00:00Z",
                                 "message": {"role": "user", "content": "Yes, the greeting looks right to me now, thanks"}}) + "\n")
        os.environ["BRAIN_TRANSCRIPT"] = str(t)
        code, out = self.cli("req", "evidence", "R-001", "owner:ship it without the greeting please", "--done")
        self.assertEqual(code, 1, out)
        code, out = self.cli("req", "evidence", "R-001", "owner:the greeting looks right to me now", "--done")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.row()["evidence"][0].startswith("owner:turn@2026-11-10T10:00:00Z#"), self.row()["evidence"])

    def test_hand_typed_check_evidence_is_refused(self):
        """`check:` items are written by `req verify` only, so one cannot be typed in."""
        self.add()
        self.building()
        code, out = self.cli("req", "evidence", "R-001", "check: exit 0 @abc1234 x.log", "--done")
        self.assertEqual(code, 1, out)
        self.assertIn("brain req verify", out)
        self.assertEqual(self.row()["evidence"], [])


class VerifyTests(Base):
    def test_verify_runs_the_stored_check(self):
        """quality-path-01, e2e-trial-06, redteam-08: the `check` field was
        written and read nowhere. `req verify` runs it and records the result."""
        self.add(check="test -f greet.sh")
        self.add("it must say goodbye on the way out", "bye.sh prints Bye", check="true")
        self.add("it should feel friendly", "the owner says so")  # no check
        self.building()
        code, out = self.cli("req", "verify")
        self.assertEqual(code, 1, out)  # one check fails
        self.assertIn("R-001: check FAILED (exit 1)", out)
        self.assertLessEqual(len(out.splitlines()), 3)
        self.assertEqual(self.row("R-001")["status"], "open")
        r2 = self.row("R-002")
        self.assertEqual(r2["status"], "done")
        self.assertRegex(r2["evidence"][0], r"^check: exit 0 @[0-9a-f]{7}\S* \S+\.log$")
        self.assertEqual(self.row("R-003")["status"], "open")
        (self.p / "greet.sh").write_text("echo Hello\n")
        code, out = self.cli("req", "verify", "R-001")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.row("R-001")["status"], "done")
        code, out = self.cli("req", "verify", "R-003")
        self.assertEqual(code, 1, out)
        self.assertIn("no check", out)

    def test_verify_reopens_a_done_line_whose_check_now_fails(self):
        """e2e-trial-06: a done line stayed done whatever its check said."""
        self.add(check="test -f greet.sh")
        self.building()
        (self.p / "greet.sh").write_text("echo Hello\n")
        self.assertEqual(self.cli("req", "verify")[0], 0)
        self.assertEqual(self.cli("req", "check")[0], 0)
        (self.p / "greet.sh").unlink()
        code, out = self.cli("req", "verify")
        self.assertEqual(code, 1, out)
        r = self.row()
        self.assertEqual(r["status"], "open")
        self.assertFalse(any(e.startswith("check: exit 0") for e in r["evidence"]), r["evidence"])
        self.assertEqual(self.cli("req", "check")[0], 1)

    def test_a_line_with_a_check_is_closed_only_by_its_check(self):
        """redteam-08: a line whose check exits 1 cannot be marked done."""
        self.add(check="python3 -c 'import sys; sys.exit(1)'")
        self.building()
        before = self.ledger()
        code, out = self.cli("req", "evidence", "R-001", "README.md", "--done")
        self.assertEqual(code, 1, out)
        self.assertIn("brain req verify R-001", out)
        self.assertEqual(self.ledger(), before)
        self.assertEqual(self.cli("req", "verify", "R-001")[0], 1)
        self.assertEqual(self.row()["status"], "open")

    def test_identical_checks_run_once_per_call(self):
        """Output and time economy: three lines sharing one command cost one run."""
        marker = self.ws / "runs.txt"
        for i in range(3):
            self.add(f"requirement number {i} of the request", "the suite passes", check=f"echo x >> {marker}")
        self.building()
        code, out = self.cli("req", "verify")
        self.assertEqual(code, 0, out)
        self.assertEqual(marker.read_text().count("x"), 1)
        self.assertEqual(len(out.splitlines()), 1, out)

    def test_verify_leaves_a_dropped_line_dropped(self):
        self.add(check="true")
        self.cli("req", "drop", "R-001", "--reason", "later")
        code, out = self.cli("req", "verify", "R-001")
        self.assertEqual(code, 1, out)
        self.assertIn("brain req reopen R-001", out)
        self.assertEqual(self.cli("req", "verify")[0], 0)
        self.assertEqual(self.row()["status"], "dropped")

    def test_many_failing_checks_do_not_flood_the_output(self):
        for i in range(9):
            self.add(f"requirement number {i} of the request", "the suite passes", check=f"test -f missing-{i}.txt")
        self.building()
        code, out = self.cli("req", "verify")
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertLessEqual(len(lines), 7, out)
        self.assertIn("9 failed", lines[-1])
        self.assertIn("R-007", lines[-1])  # the ones not shown are named
        self.assertRegex(lines[0], r"full output: \.brain/log/run/\S+\.log$")
        self.assertNotIn(str(self.ws), out)

    def test_reopen_returns_a_line_to_open_and_regenerates_the_view(self):
        """e2e-trial-06: with no reopen the ledger had to be edited by hand,
        which left REQUIREMENTS.md stale."""
        self.add()
        self.cli("req", "evidence", "R-001", "README.md", "--done")
        self.assertIn("| done |", (self.p / ".brain" / "REQUIREMENTS.md").read_text())
        code, out = self.cli("req", "reopen", "R-001", "--reason", "the greeting is wrong for two names")
        self.assertEqual(code, 0, out)
        r = self.row()
        self.assertEqual((r["status"], r["evidence"]), ("open", []))
        self.assertIn("two names", r["reopened"])
        self.assertIn("| open |", (self.p / ".brain" / "REQUIREMENTS.md").read_text())
        self.cli("req", "drop", "R-001", "--reason", "later")
        self.assertEqual(self.cli("req", "reopen", "R-001", "--reason", "he asked for it again")[0], 0)
        self.assertEqual(self.row()["status"], "open")
        self.assertNotIn("reason", self.row())


class RequestTests(Base):
    REQUEST = ("New project: a tool that tracks my expenses by month. It must export everything to CSV for my accountant. "
               "Also send me an email summary every Monday morning. Thanks!")

    def test_record_request_stores_each_sentence_once_in_the_project(self):
        """quality-path-02: the request text was stored nowhere."""
        self.assertEqual(req.record_request(self.p, self.REQUEST), 4)
        self.assertEqual(req.record_request(self.p, self.REQUEST), 0)
        rows = c.read_jsonl(self.p / ".brain" / "log" / "request.jsonl")
        self.assertEqual([r["text"] for r in rows][1], "It must export everything to CSV for my accountant.")
        self.assertEqual(req.record_request(self.p, f"Use the key {FAKE_KEY} for the mail service when sending summaries."), 1)
        self.assertNotIn(FAKE_KEY, (self.p / ".brain" / "log" / "request.jsonl").read_text())
        code, out = self.cli("req", "intake", "Please also add a dark mode to every screen.")
        self.assertEqual(code, 0, out)
        self.assertIn("1 new sentence", out)
        self.assertEqual(len(out.splitlines()), 1)

    def test_request_sentence_missing_from_ledger_fails_check(self):
        """quality-path-02: one line for a longer request passed."""
        req.record_request(self.p, self.REQUEST)
        self.add("a tool that tracks my expenses by month", "a month's expenses are listed")
        self.cli("req", "evidence", "R-001", "README.md", "--done")
        code, out = self.cli("req", "check")
        self.assertEqual(code, 1, out)
        self.assertIn("request sentence not in the ledger", out)
        self.assertIn("export everything to CSV", out)
        self.assertIn("email summary every Monday", out)
        self.assertNotIn("Thanks", out)  # too short to be a requirement
        self.assertNotIn("tracks my expenses", out.split("not finished", 1)[-1])
        # A line that is open, done or dropped covers its sentence; so do pieces of one sentence.
        self.add("export everything to CSV", "a CSV file is written")
        self.add("for my accountant", "the columns are the ones the accountant uses")
        self.add("Also send me an email summary every Monday morning", "an email arrives on Monday")
        self.cli("req", "drop", "R-004", "--reason", "no mail service yet")
        code, out = self.cli("req", "check")
        self.assertNotIn("request sentence not in the ledger", out)

    def test_at_most_three_missing_sentences_are_printed(self):
        req.record_request(self.p, " ".join(f"Requirement number {w} needs its own separate ledger line." for w in ("alpha", "beta", "gamma", "delta", "epsilon")))
        self.add("something unrelated to all of that entirely", "x")
        code, out = self.cli("req", "check")
        self.assertEqual(code, 1)
        self.assertEqual(out.count("request sentence not in the ledger"), 3)
        self.assertIn("2 more", out)
        self.assertLessEqual(len(out.splitlines()), 15)

    def test_small_tasks_are_not_held_to_the_request(self):
        state.checkpoint(self.p, tier=1)
        req.record_request(self.p, self.REQUEST)
        self.assertEqual(self.cli("req", "check")[0], 0)

    def test_empty_ledger_fails_at_project_size_once_work_is_recorded(self):
        """quality-path-02: an empty ledger passed until the stage said build."""
        self.assertEqual(self.cli("req", "check")[0], 0)  # nothing has happened yet
        state.checkpoint(self.p, done="T-1 the greeting")
        code, out = self.cli("req", "check")
        self.assertEqual(code, 1, out)
        self.assertIn("ledger is empty at project size", out)
        self.assertEqual(len(out.splitlines()), 1)

    def test_empty_ledger_fails_once_a_gate_has_run(self):
        """quality-path-02 (same defect): a gate record is recorded work."""
        self.set_gate("true")
        gate.run_gates(self.p)
        self.assertEqual(self.cli("req", "check")[0], 1)

    def test_passes_when_change_is_recorded(self):
        """quality-path-02: 'passes when' was rewritten with no trace, then --done accepted."""
        self.add("checkout must feel fast on a phone", "Lighthouse mobile run shows checkout under 2 s")
        code, out = self.cli("req", "set", "R-001", "--passes-when", "page exists")
        self.assertEqual(code, 0, out)
        self.assertIn("Lighthouse", out)
        self.assertEqual(self.row()["passes_when_was"], ["Lighthouse mobile run shows checkout under 2 s"])
        self.assertIn("Lighthouse", (self.p / ".brain" / "REQUIREMENTS.md").read_text())
        self.cli("req", "evidence", "R-001", "README.md", "--done")
        before = self.ledger()
        code, out = self.cli("req", "set", "R-001", "--passes-when", "anything at all")
        self.assertEqual(code, 1, out)
        self.assertIn("brain req reopen R-001", out)
        self.assertEqual(self.ledger(), before)


    def test_a_changed_check_is_recorded_and_its_old_result_is_dropped(self):
        """quality-path-02 (d), for the check: swapping a failing check for an
        easy one must leave a trace and must not keep the old result."""
        self.add(check="true")
        self.building()
        self.assertEqual(self.cli("req", "verify")[0], 0)
        self.cli("req", "reopen", "R-001", "--reason", "look again")
        self.assertEqual(self.cli("req", "verify")[0], 0)
        self.cli("req", "reopen", "R-001", "--reason", "look once more")
        self.cli("req", "evidence", "R-001", "README.md")
        code, out = self.cli("req", "set", "R-001", "--check", "")
        self.assertEqual(code, 0, out)
        self.assertIn("check was: true", out)
        r = self.row()
        self.assertEqual((r["check"], r["check_was"]), ("", ["true"]))
        self.assertFalse(any(e.startswith("check:") for e in r["evidence"]))


class DroppedTests(Base):
    def test_a_ledger_with_every_line_dropped_does_not_pass_at_project_size(self):
        """quality2-02, quality-path-02: three lines, all dropped 'later', passed."""
        for q in ("first thing he asked for", "second thing he asked for", "third thing he asked for"):
            self.add(q, "x")
        for rid in ("R-001", "R-002", "R-003"):
            self.cli("req", "drop", rid, "--reason", "later")
        code, out = self.cli("req", "check")
        self.assertEqual(code, 1, out)
        self.assertIn("every line is dropped", out)
        self.assertIn("brain req reopen", out)
        state.checkpoint(self.p, tier=1)
        self.assertEqual(self.cli("req", "check")[0], 0)  # a small task is not held to this

    def test_check_prints_dropped_lines_with_reasons_every_time(self):
        """quality2-02: a drop was visible only as a count."""
        self.add("it must work offline", "airplane-mode test passes")
        self.add("make it pretty", "he says so")
        self.cli("req", "evidence", "R-001", "README.md", "--done")
        self.cli("req", "drop", "R-002", "--reason", "owner said skip the styling")
        for _ in range(2):
            code, out = self.cli("req", "check")
            self.assertEqual(code, 0, out)
            self.assertIn("R-002", out)
            self.assertIn("make it pretty", out)
            self.assertIn("owner said skip the styling", out)

    def test_many_dropped_lines_do_not_flood_the_check(self):
        for i in range(9):
            self.add(f"wish number {i} from the long list", "x")
        self.cli("req", "evidence", "R-001", "README.md", "--done")
        for i in range(2, 10):
            self.cli("req", "drop", f"R-00{i}", "--reason", "later")
        code, out = self.cli("req", "check")
        self.assertEqual(code, 0, out)
        self.assertLessEqual(len(out.splitlines()), 6)
        self.assertIn("more dropped", out)

    def test_dropped_lines_and_reasons_are_ready_for_the_status_page(self):
        """quality2-02, redteam-08: STATUS.md said 'done with evidence' and
        showed drops as a count. `req.status_lines` is what the page prints,
        and a change to the ledger regenerates the page."""
        self.add("it must work offline", "airplane-mode test passes")
        self.add("make it pretty", "he says so")
        self.add("it must print a receipt", "a receipt prints")
        self.cli("req", "evidence", "R-001", "README.md", "--done")
        self.cli("req", "evidence", "R-003", "looks fine", "--done")
        self.cli("req", "drop", "R-002", "--reason", "owner said skip the styling")
        lines = req.status_lines(self.p)
        self.assertIn("1 verified", lines[0])
        self.assertIn("1 done but not verified", lines[0])
        self.assertIn("1 dropped", lines[0])
        self.assertTrue(any("R-002" in l and "make it pretty" in l and "owner said skip the styling" in l for l in lines[1:]), lines)
        self.assertLessEqual(len(lines), 7)
        self.assertIn("Requirements:", (self.p / "STATUS.md").read_text())  # regenerated by the ledger change


class AddTests(Base):
    def test_add_takes_several_lines_in_one_call(self):
        """e2e-trial-14: four `req add` calls for four lines."""
        code, out = self.cli("req", "add", "--line", "it must greet by name :: greet.sh Ana prints Hello Ana :: sh greet.sh Ana | grep -q Hello",
                             "--line", "it must say goodbye :: bye.sh prints Bye", "--line", "it should feel friendly")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out.splitlines()), 1)
        rows = req.load(self.p)
        self.assertEqual([r["id"] for r in rows], ["R-001", "R-002", "R-003"])
        self.assertEqual((rows[0]["passes_when"], rows[0]["check"]), ("greet.sh Ana prints Hello Ana", "sh greet.sh Ana | grep -q Hello"))
        self.assertEqual((rows[1]["passes_when"], rows[1]["check"]), ("bye.sh prints Bye", ""))
        self.assertIn("R-003", out)  # named as lacking a 'passes when'
        f = self.ws / "lines.txt"
        f.write_text("# from the plan\nit must run on a phone :: opens on a 390 px screen :: pytest tests/test_ui.py::test_phone\n\n"
                     + json.dumps({"quote": "it must print a receipt", "passes_when": "a receipt prints", "implied": True, "assumption": "shops need one"}) + "\n"
                     + "it must say goodbye :: again\n")
        code, out = self.cli("req", "add", "--from", str(f))
        self.assertEqual(code, 0, out)
        rows = req.load(self.p)
        self.assertEqual(len(rows), 5)  # the repeated words are not added twice
        self.assertEqual(rows[3]["check"], "pytest tests/test_ui.py::test_phone")
        self.assertTrue(rows[4]["implied"])
        # The single-line form still works, and nothing at all is still refused.
        self.assertIn("R-006 added", self.cli("req", "add", "--quote", "one more thing", "--passes-when", "x")[1])
        code, out = self.cli("req", "add")
        self.assertEqual(code, 1)
        self.assertEqual(len(req.load(self.p)), 6)

    def test_a_bad_line_adds_nothing(self):
        before = self.ledger()
        code, out = self.cli("req", "add", "--line", "a good line :: x", "--line", " :: no words here")
        self.assertEqual(code, 1, out)
        self.assertEqual(self.ledger(), before)

    def test_text_holding_a_secret_is_refused_by_add_set_and_evidence(self):
        """redteam-07: a key typed into evidence reached requirements.jsonl,
        REQUIREMENTS.md and the remote."""
        self.add()
        before = self.ledger()
        for argv in (("req", "add", "--quote", f"use the key {FAKE_KEY} for mail"),
                     ("req", "add", "--line", f"send mail :: mail arrives :: curl -H 'x-api-key: {FAKE_KEY}' https://mail.example.invalid"),
                     ("req", "set", "R-001", "--passes-when", f"works with {FAKE_KEY}"),
                     ("req", "set", "R-001", "--check", f"curl -H 'x-api-key: {FAKE_KEY}' https://x.example.invalid"),
                     ("req", "evidence", "R-001", f"curl -H 'x-api-key: {FAKE_KEY}' returned 200", "--done"),
                     ("req", "drop", "R-001", "--reason", f"the key {FAKE_KEY} is gone")):
            code, out = self.cli(*argv)
            self.assertEqual(code, 1, f"{argv[:3]}: {out}")
            self.assertIn("refused", out)
            self.assertNotIn(FAKE_KEY, out)
            self.assertEqual(self.ledger(), before, argv[:3])
        self.assertNotIn(FAKE_KEY, (self.p / ".brain" / "REQUIREMENTS.md").read_text())


class DoneTests(Base):
    def setUp(self):
        super().setUp()
        self.remote = self.ws / "remote.git"
        sh(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        sh(self.p, "git", "remote", "add", "origin", str(self.remote))
        sh(self.p, "git", "push", "-q", "-u", "origin", "work")

    def save_and_push(self):
        commit_all(self.p, "bookkeeping")
        sh(self.p, "git", "push", "-q", "origin", "work")

    def done(self):
        code, out = self.cli("done")
        return code, out, out.rstrip().splitlines()[-1]

    def test_done_report_is_red_when_any_part_is_red(self):
        """quality-path-15: release pushed with an open line and `req check`
        passed with no gate ever run; nothing gave one verdict."""
        self.add()
        self.set_gate("test -f greet.sh")
        self.building()
        self.save_and_push()
        code, out, last = self.done()
        self.assertEqual(code, 1, out)
        self.assertTrue(last.startswith("NOT DONE: R-001"), out)
        self.assertIn("not done: R-001", out)
        # A line closed on a note before the build stage is said to be unverified.
        r = req.load(self.p)
        r[0].update(status="done", evidence=["note: looks fine"])
        req.save(self.p, r)
        code, out, last = self.done()
        self.assertEqual(code, 1)
        self.assertIn("done but not verified: R-001", out)
        self.cli("req", "reopen", "R-001", "--reason", "never checked")
        # Requirement verified, but the gate is red.
        (self.p / "notes.txt").write_text("x")
        commit_all(self.p, "work")
        gate.run_gates(self.p)
        self.cli("req", "evidence", "R-001", "notes.txt", "--done")
        self.save_and_push()
        code, out, last = self.done()
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"(?m)^verified: R-001")
        self.assertIn("gate checks", last)
        # Everything green.
        (self.p / "greet.sh").write_text("echo Hello\n")
        commit_all(self.p, "greeting")
        gate.run_gates(self.p)
        self.save_and_push()
        code, out, last = self.done()
        self.assertEqual(code, 0, out)
        self.assertTrue(last.startswith("DONE"), out)
        before = sh(self.p, "git", "status", "--porcelain").stdout
        self.assertEqual(before, "", "the report itself must not write anything")
        # Dirty tree.
        (self.p / "scratch.txt").write_text("x")
        code, out, last = self.done()
        self.assertEqual(code, 1)
        self.assertIn("uncommitted", last)
        (self.p / "scratch.txt").unlink()
        # A commit that is not pushed (bookkeeping only, so the gate stays green).
        state.checkpoint(self.p, note="half-way")
        commit_all(self.p, "checkpoint")
        code, out, last = self.done()
        self.assertEqual(code, 1)
        self.assertIn("not pushed", last)
        sh(self.p, "git", "push", "-q", "origin", "work")
        self.assertEqual(self.done()[0], 0)
        # The work changes after the gate ran: the gate is stale.
        (self.p / "feature.txt").write_text("new work")
        self.save_and_push()
        code, out, last = self.done()
        self.assertEqual(code, 1)
        self.assertIn("gate checks", last)
        self.assertIn("NOT DONE", last)

    def test_done_counts_what_waits_for_the_owner_and_shows_drops(self):
        self.add()
        self.add("make it pretty", "he says so")
        self.building()
        self.cli("req", "evidence", "R-001", "README.md", "--done")
        self.cli("req", "drop", "R-002", "--reason", "later")
        with open(self.p / "NEEDS_YOU.md", "a") as f:
            f.write("\n## Merge the branch\n\n1. Open the pull request.\n")
        self.save_and_push()
        code, out, last = self.done()
        self.assertEqual(code, 0, out)  # no command gate is defined: said, not hidden
        self.assertIn("no command gate", out)
        self.assertIn("dropped: 1", out)
        self.assertRegex(last, r"^DONE\b.*\b1 item\(s\) wait")
        data = json.loads(self.cli("done", "--json")[1])
        self.assertEqual((data["done"], data["reasons"], data["needs_you"]), (True, [], 1))

    def test_done_report_fits_ten_lines(self):
        """quality-path-15: the verdict has to be cheap enough to quote."""
        req.record_request(self.p, "Please add a calendar view that shows every booking of the month.")
        for i in range(12):
            self.add(f"requirement number {i} of a long request", "the suite passes")
        self.building()
        for rid in ("R-001", "R-002", "R-003"):
            self.cli("req", "evidence", rid, "README.md", "--done")
        code, out, last = self.done()
        self.assertEqual(code, 1)
        lines = out.rstrip().splitlines()
        self.assertLessEqual(len(lines), 10, out)
        self.assertTrue(last.startswith("NOT DONE: "), out)
        self.assertRegex(last, r"\(\+\d+ more\)$")
        self.assertTrue(lines[0].startswith("not done: R-004"), out)  # the worst first
        self.assertTrue(all(len(l) <= 200 for l in lines), out)

    def test_done_is_never_given_on_an_empty_ledger_at_project_size(self):
        """quality-path-02 (a) seen from `brain done`: nothing recorded proves nothing."""
        self.save_and_push()
        code, out, last = self.done()
        self.assertEqual(code, 1, out)
        self.assertIn("ledger is empty at project size", last)
        state.checkpoint(self.p, tier=1)
        self.save_and_push()
        code, out, last = self.done()
        self.assertEqual(code, 0, out)  # a small task has no ledger to hold
        self.assertIn("requirements: none recorded", out)

    def test_done_with_every_line_dropped_does_not_say_nothing_was_recorded(self):
        self.add()
        self.building()
        self.cli("req", "drop", "R-001", "--reason", "later")
        code, out, last = self.done()
        self.assertEqual(code, 1)
        self.assertNotIn("none recorded", out)
        self.assertIn("dropped: 1", out)
        self.assertIn("every line is dropped", last)

    def test_done_says_when_the_request_is_not_in_the_ledger(self):
        req.record_request(self.p, "Please add a calendar view that shows every booking of the month.")
        self.add()
        self.building()
        self.cli("req", "evidence", "R-001", "README.md", "--done")
        self.save_and_push()
        code, out, last = self.done()
        self.assertEqual(code, 1, out)
        self.assertIn("request sentence not in the ledger", last)


class CompatibilityTests(Base):
    def test_free_text_before_the_build_stage_still_closes_a_line(self):
        """Decision 8: the strict rule starts at project size from stage build."""
        self.add()
        code, out = self.cli("req", "evidence", "R-001", "gate checks exit 0 on the fix commit", "--done")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.row()["evidence"], ["note: gate checks exit 0 on the fix commit"])
        self.assertEqual(self.cli("req", "check")[0], 0)

    def test_evidence_can_be_closed_later_without_new_items(self):
        self.add()
        self.building()
        self.assertEqual(self.cli("req", "evidence", "R-001", "README.md")[0], 0)
        self.assertEqual(self.row()["status"], "open")
        code, out = self.cli("req", "evidence", "R-001", "--done")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.row()["status"], "done")
        self.assertEqual(self.cli("req", "evidence", "R-001")[0], 1)  # nothing given, nothing to do

    def test_a_dropped_line_that_is_then_closed_loses_its_drop_reason(self):
        self.add()
        self.cli("req", "drop", "R-001", "--reason", "later")
        self.assertEqual(self.cli("req", "evidence", "R-001", "README.md", "--done")[0], 0)
        self.assertEqual(self.row()["status"], "done")
        self.assertNotIn("reason", self.row())
        self.assertNotIn("later", (self.p / ".brain" / "REQUIREMENTS.md").read_text())

    def test_odd_line_numbers_are_text_not_a_crash(self):
        self.add()
        for text in ("README.md:\u00b2", "README.md:0", "README.md:99999999999"):
            code, out = self.cli("req", "evidence", "R-001", text)
            self.assertIn(code, (0, 1), out)
        self.assertEqual(self.row()["status"], "open")

    def test_a_hand_edited_row_of_the_wrong_shape_is_read_without_a_traceback(self):
        """T9 (fragile on bad input), for the ledger's new fields."""
        req.save(self.p, [{"id": "R-001", "quote": "q one two three", "passes_when": "w", "status": "done", "evidence": "looks fine",
                           "passes_when_was": "x", "check": None},
                          {"id": "R-002", "quote": 7, "status": "dropped", "reason": None, "evidence": None}])
        m = c.load_manifest(self.p)
        m["paths"], m["gates"] = "docs", {"id": "checks"}
        c.write_json(self.p / ".brain" / "project.json", m)
        self.building()
        for argv in (("req", "check"), ("req", "list"), ("done",), ("req", "evidence", "R-001", "README.md"), ("req", "verify")):
            code, out = self.cli(*argv)
            self.assertIn(code, (0, 1), f"{argv}: {out}")
        self.assertIsInstance(req.status_lines(self.p), list)
        self.assertEqual(req.evidence_of({"evidence": "looks fine"}), ["looks fine"])  # one item, not ten letters
        self.assertEqual(req.evidence_of({"evidence": None}), [])

    def test_list_marks_lines_done_on_a_note(self):
        self.add()
        self.cli("req", "evidence", "R-001", "looks fine", "--done")
        self.assertIn("[done, not verified]", self.cli("req", "list")[1])


if __name__ == "__main__":
    unittest.main()
