"""Tests for the contract, state, requirements ledger, gates, detection and budgets.

Every test works in a temporary directory; nothing touches the real brain's
learned zone or any real project.
"""
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

from engine import budget, common as c, contract, detect, gate, items, req, state  # noqa: E402


def sh(cwd, *args):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    sh(path, "git", "init", "-q", "-b", "work")
    sh(path, "git", "config", "user.email", "t@example.invalid")
    sh(path, "git", "config", "user.name", "t")
    sh(path, "git", "config", "commit.gpgsign", "false")
    return path


def commit_all(path: Path, msg="c"):
    sh(path, "git", "add", "-A")
    sh(path, "git", "commit", "-q", "-m", msg)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        # A stand-in brain folder: detection only needs its location and model facts.
        self.brain = self.ws / "Claude-Brain"
        (self.brain / "memory").mkdir(parents=True)
        c.write_json(self.brain / "memory" / "models.json", {"verified_on": c.today(), "recheck_days": 90, "models": {}})
        self._env = dict(os.environ)
        os.environ.pop("BRAIN_PROJECT", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    def project(self, name="proj", family="software") -> Path:
        p = git_repo(self.ws / name)
        (p / "README.md").write_text("# x\n")
        contract.init(p, name.title(), family)
        return p


class ContractTests(Base):
    def test_init_for_each_family_validates(self):
        for fam in contract.FAMILIES:
            p = self.project(f"p-{fam}", fam)
            self.assertEqual(contract.validate(p), [], fam)
            self.assertEqual(c.load_manifest(p)["family"], fam)

    def test_init_twice_changes_nothing(self):
        p = self.project()
        before = {f: f.read_bytes() for f in p.rglob("*") if f.is_file() and ".git" not in f.parts}
        self.assertEqual(contract.init(p, "Other Title", "data"), [])
        after = {f: f.read_bytes() for f in p.rglob("*") if f.is_file() and ".git" not in f.parts}
        self.assertEqual(before, after)

    def test_stub_is_small_and_points_to_brain(self):
        p = self.project()
        text = (p / "CLAUDE.md").read_text()
        self.assertLessEqual(len(text.encode()), contract.STUB_LIMIT)
        self.assertIn("bin/brain", text)
        self.assertIn("Brain not attached", text)

    def test_adopt_keeps_existing_files_and_claude_md(self):
        p = git_repo(self.ws / "legacy")
        (p / "CLAUDE.md").write_text("# Old handbook\nkeep me\n")
        (p / "package.json").write_text(json.dumps({"scripts": {"lint": "x", "test": "y", "build": "z", "dev": "d"}}))
        (p / "src").mkdir()
        (p / "src" / "a.ts").write_text("export const a = 1\n")
        before = {str(f.relative_to(p)): f.read_bytes() for f in p.rglob("*") if f.is_file() and ".git" not in f.parts}
        s, made = contract.adopt(p)
        self.assertEqual(s["family"], "software")
        for rel, data in before.items():
            if rel == "CLAUDE.md":
                self.assertTrue((p / rel).read_text().endswith("# Old handbook\nkeep me\n"))
                self.assertIn(contract.BEGIN, (p / rel).read_text())
            else:
                self.assertEqual((p / rel).read_bytes(), data, rel)
        new = {str(f.relative_to(p)) for f in p.rglob("*") if f.is_file() and ".git" not in f.parts} - set(before)
        self.assertTrue(all(n.startswith(".brain/") or n in ("NEEDS_YOU.md", "STATUS.md") for n in new), new)
        m = c.load_manifest(p)
        self.assertEqual(m["commands"]["check_full"], "npm run test && npm run build")
        self.assertEqual(contract.validate(p), [])
        # Adopting again adds no second pointer block.
        contract.adopt(p)
        self.assertEqual((p / "CLAUDE.md").read_text().count(contract.BEGIN), 1)

    def test_survey_writes_nothing(self):
        p = git_repo(self.ws / "legacy2")
        (p / "notes.md").write_text("x")
        contract.survey(p)
        self.assertFalse((p / ".brain").exists())

    def test_project_newer_than_brain_is_not_written(self):
        p = self.project()
        m = c.load_manifest(p)
        m["contract"] = c.CONTRACT_VERSION + 1
        c.write_json(p / ".brain" / "project.json", m)
        snapshot = (p / ".brain" / "project.json").read_bytes()
        errs = contract.validate(p)
        self.assertTrue(errs and errs[0].startswith("stale brain"))
        code, msgs = contract.migrate(p)
        self.assertEqual(code, 3)
        self.assertEqual((p / ".brain" / "project.json").read_bytes(), snapshot)
        self.assertEqual(detect.detect(self.brain)["mode"], "stale-brain")

    def test_migration_chain_runs_once_and_keeps_unknown_keys(self):
        p = self.project()
        m = c.load_manifest(p)
        m["contract"] = 0
        m["custom_key"] = {"kept": True}
        c.write_json(p / ".brain" / "project.json", m)
        mig = self.ws / "migs"
        mig.mkdir()
        (mig / "0_to_1.py").write_text(
            "from pathlib import Path\n"
            "def migrate(project):\n"
            "    f = Path(project) / '.brain' / 'marker.txt'\n"
            "    if f.exists():\n        return []\n"
            "    f.write_text('migrated')\n    return ['added marker.txt']\n")
        self.assertEqual(detect.detect(self.brain)["mode"], "migrate")
        code, msgs = contract.migrate(p, migrations_dir=mig)
        self.assertEqual(code, 0, msgs)
        self.assertEqual(c.load_manifest(p)["contract"], 1)
        self.assertEqual(c.load_manifest(p)["custom_key"], {"kept": True})
        code2, msgs2 = contract.migrate(p, migrations_dir=mig)
        self.assertEqual((code2, msgs2), (0, ["already on contract v1"]))

    def test_schema_rejects_bad_values_and_allows_unknown_keys(self):
        p = self.project()
        m = c.load_manifest(p)
        m["future_optional"] = 1
        c.write_json(p / ".brain" / "project.json", m)
        self.assertEqual(contract.validate(p), [])
        m["family"] = "cooking"
        m["release"] = {"rule": "yolo"}
        c.write_json(p / ".brain" / "project.json", m)
        errs = " ".join(contract.validate(p))
        self.assertIn("family", errs)
        self.assertIn("release.rule", errs)

    def test_manifest_secret_is_flagged(self):
        p = self.project()
        m = c.load_manifest(p)
        m["commands"]["run"] = "API_KEY=" + "sk-" + "a" * 30 + " npm start"
        c.write_json(p / ".brain" / "project.json", m)
        self.assertTrue(any("secret" in e for e in contract.validate(p)))


class DetectTests(Base):
    def test_brain_only(self):
        self.assertEqual(detect.detect(self.brain)["mode"], "brain-only")

    def test_bootstrap_adopt_work_choose(self):
        empty = git_repo(self.ws / "fresh")
        (empty / "README.md").write_text("# fresh\n")
        self.assertEqual(detect.detect(self.brain)["mode"], "bootstrap")
        (empty / "main.py").write_text("print(1)\n")
        d = detect.detect(self.brain)
        self.assertEqual(d["mode"], "adopt")
        self.assertFalse((empty / ".brain").exists())  # detection never writes
        contract.adopt(empty)
        self.assertEqual(detect.detect(self.brain)["mode"], "work")
        second = self.project("second")
        os.environ["BRAIN_NOW"] = "2030-01-01T00:00:00Z"
        state.checkpoint(second, item="later item")
        os.environ.pop("BRAIN_NOW")
        d = detect.detect(self.brain)
        self.assertEqual(d["mode"], "choose")
        self.assertEqual(Path(d["project"]).name, "second")  # most recently active
        self.assertEqual(detect.detect(self.brain, named="fresh")["mode"], "work")

    def test_boot_is_short_and_shows_position(self):
        p = self.project()
        state.checkpoint(p, item="T-7 build the list view", nxt=["T-8", "T-9"], stage="build", note="x" * 5000)
        lines = detect.boot_lines(None, self.brain)
        blob = "\n".join(lines)
        self.assertLessEqual(len(blob.encode()), detect.BOOT_LIMIT)
        self.assertLessEqual(len(lines), 15)
        self.assertIn("T-7 build the list view", blob)
        self.assertIn("mode: work", blob)

    def test_boot_warns_about_a_second_session_and_stale_model_facts(self):
        p = self.project()
        os.environ["BRAIN_SESSION_ID"] = "session-aaaa"
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        state.checkpoint(p, item="x")
        os.environ["BRAIN_SESSION_ID"] = "session-bbbb"
        c.write_json(self.brain / "memory" / "models.json", {"verified_on": "2020-01-01", "recheck_days": 90})
        blob = "\n".join(detect.boot_lines(None, self.brain))
        self.assertIn("WARNING: another session", blob)
        self.assertIn("model facts were verified", blob)


class StateTests(Base):
    def test_checkpoint_round_trip_and_status(self):
        p = self.project()
        state.checkpoint(p, item="A", nxt=["B", "C", "D", "E"], stage="build", note="half done in src/x")
        state.checkpoint(p, done="A", item="B")
        st = state.read_state(p)
        self.assertEqual((st["item"], st["last_done"], st["stage"]), ("B", "A", "build"))
        self.assertEqual(len(st["next_list"]), 3)
        self.assertIn("half done", st["notes"])
        self.assertEqual(c.load_manifest(p)["stage"], "build")
        text = state.write_status(p)
        self.assertLessEqual(len(text.splitlines()), 40)
        self.assertIn("Working on: B", text)

    def test_open_needs_ignores_resolved_items(self):
        p = self.project()
        (p / "NEEDS_YOU.md").write_text("# Needs you\n\n## 1. Connect Vercel\nsteps\n\n## 2. Pick a colour\nRESOLVED: blue\n")
        self.assertEqual(state.open_needs(p), ["1. Connect Vercel"])

    def test_handover_reports_unpushed_and_dirty_work(self):
        p = self.project()
        commit_all(p)
        (p / "new.txt").write_text("x")
        problems, text = state.handover(p, brain_root=self.brain)
        joined = " ".join(problems)
        self.assertIn("uncommitted", joined)
        self.assertIn("never been pushed", joined)
        self.assertIn("Continue", text)
        self.assertTrue((p / ".brain" / "HANDOVER.md").is_file())


class ReqTests(Base):
    def run_cli(self, *argv):
        buf = io.StringIO()
        sys.path.insert(0, str(ROOT / "bin"))
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("brain_cli", str(ROOT / "bin" / "brain"))
        spec = importlib.util.spec_from_loader("brain_cli", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        with redirect_stdout(buf):
            code = mod.main(list(argv))
        return code, buf.getvalue()

    def test_check_blocks_until_every_line_has_evidence(self):
        p = self.project()
        os.environ["BRAIN_PROJECT"] = str(p)
        self.assertEqual(self.run_cli("req", "check")[0], 0)  # empty ledger is fine
        self.run_cli("req", "add", "--quote", "it must work offline", "--passes-when", "airplane-mode test passes")
        self.run_cli("req", "add", "--quote", "make it pretty")
        code, out = self.run_cli("req", "check")
        self.assertEqual(code, 1)
        self.assertIn("R-002: no 'passes when'", out)
        # done cannot be claimed without a test for it
        code, _ = self.run_cli("req", "evidence", "R-002", "looks nice", "--done")
        self.assertEqual(code, 1)
        self.run_cli("req", "evidence", "R-001", "e2e log run 14: offline spec passed", "--done")
        self.run_cli("req", "drop", "R-002", "--reason", "owner said skip")
        code, out = self.run_cli("req", "check")
        self.assertEqual(code, 0, out)
        self.assertIn("| R-001 |", (p / ".brain" / "REQUIREMENTS.md").read_text())

    def test_same_words_are_not_added_twice(self):
        p = self.project()
        os.environ["BRAIN_PROJECT"] = str(p)
        self.run_cli("req", "add", "--quote", "one  thing")
        self.run_cli("req", "add", "--quote", "one thing")
        self.assertEqual(len(req.load(p)), 1)

    def test_done_without_evidence_is_a_problem(self):
        rows = [{"id": "R-001", "quote": "q", "passes_when": "w", "status": "done", "evidence": []}]
        self.assertTrue(any("no evidence" in x for x in req.problems(rows)))


class GateTests(Base):
    def setup_remote(self, p: Path) -> Path:
        remote = self.ws / "remote.git"
        sh(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(remote))
        sh(p, "git", "remote", "add", "origin", str(remote))
        return remote

    def set_gate(self, p: Path, command: str, rule="main-on-green"):
        m = c.load_manifest(p)
        m["gates"] = [{"id": "checks", "kind": "command", "command": command}]
        m["release"] = {"rule": rule, "branch": "main", "live_url": ""}
        c.write_json(p / ".brain" / "project.json", m)

    def test_run_keeps_full_output_in_a_file_and_prints_little(self):
        p = self.project()
        r = gate.run_filtered("for i in $(seq 1 500); do echo line $i; done; echo 'Error: boom' >&2; exit 3", p, p)
        self.assertEqual(r["exit"], 3)
        self.assertLessEqual(len(r["shown"]), gate.MAX_LINES + 5)
        self.assertTrue(any("boom" in l for l in r["shown"]))
        self.assertGreater(len(Path(r["log"]).read_text().splitlines()), 500)
        ok = gate.run_filtered("seq 1 200", p, p)
        self.assertEqual((ok["exit"], len(ok["shown"])), (0, 3))

    def test_release_refuses_without_a_green_gate_on_this_commit(self):
        p = self.project()
        self.setup_remote(p)
        self.set_gate(p, "test -f ok.txt")
        commit_all(p)
        self.assertEqual(gate.green_at_head(p)[0], False)  # never ran
        worst, _ = gate.run_gates(p)
        self.assertNotEqual(worst, 0)
        self.assertFalse(gate.green_at_head(p)[0])  # red
        (p / "ok.txt").write_text("1")
        commit_all(p)
        worst, _ = gate.run_gates(p)
        self.assertEqual(worst, 0)
        self.assertTrue(gate.green_at_head(p)[0])
        # Committing only bookkeeping (the gate log) keeps the gate green…
        commit_all(p, "log")
        self.assertTrue(gate.green_at_head(p)[0])
        # …but changing the work makes it stale.
        (p / "feature.txt").write_text("new work")
        commit_all(p, "work")
        ok, why = gate.green_at_head(p)
        self.assertFalse(ok)
        self.assertIn("work has changed", " ".join(why))

    def test_release_pushes_fast_forward_only_and_never_forces(self):
        p = self.project()
        remote = self.setup_remote(p)
        self.set_gate(p, "true")
        commit_all(p)
        os.environ["BRAIN_PROJECT"] = str(p)

        class A:
            project = None
            push = True
            run_gates = True
            check_live = False
            live_wait = 0
        with redirect_stdout(io.StringIO()) as out:
            code = gate.cmd_release(A())
        self.assertEqual(code, 0, out.getvalue())
        self.assertEqual(sh(remote, "git", "rev-parse", "main").stdout.strip(), sh(p, "git", "rev-parse", "HEAD").stdout.strip())
        # Someone else pushes to main; our branch no longer fast-forwards.
        other = self.ws / "other"
        sh(self.ws, "git", "clone", "-q", str(remote), str(other))
        sh(other, "git", "config", "user.email", "o@example.invalid")
        sh(other, "git", "config", "user.name", "o")
        (other / "theirs.txt").write_text("x")
        commit_all(other, "theirs")
        sh(other, "git", "push", "-q", "origin", "HEAD:main")
        theirs = sh(remote, "git", "rev-parse", "main").stdout.strip()
        (p / "mine.txt").write_text("y")
        commit_all(p, "mine")
        with redirect_stdout(io.StringIO()) as out:
            code = gate.cmd_release(A())
        self.assertEqual(code, 1)
        self.assertIn("Never force-push", out.getvalue())
        self.assertEqual(sh(remote, "git", "rev-parse", "main").stdout.strip(), theirs)

    def test_release_without_push_flag_only_reports(self):
        p = self.project()
        remote = self.setup_remote(p)
        self.set_gate(p, "true")
        commit_all(p)
        os.environ["BRAIN_PROJECT"] = str(p)

        class A:
            project = None
            push = False
            run_gates = True
            check_live = False
            live_wait = 0
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(gate.cmd_release(A()), 0)
        self.assertIn("--push", out.getvalue())
        self.assertNotEqual(sh(remote, "git", "rev-parse", "--verify", "-q", "main").returncode, 0)

    def test_live_check_is_bounded_and_can_require_the_new_version(self):
        page = self.ws / "site"
        page.mkdir()
        (page / "index.html").write_text("<html>build abc1234</html>")
        url = (page / "index.html").as_uri()
        self.assertTrue(gate.check_live(url, "abc1234", wait_seconds=0)[0])
        ok, msg = gate.check_live(url, "fff9999", wait_seconds=0)
        self.assertFalse(ok)
        self.assertIn("old version", msg)
        ok, msg = gate.check_live((page / "missing.html").as_uri(), wait_seconds=0)
        self.assertFalse(ok)

    def test_no_command_gate_means_not_green(self):
        p = self.project()
        commit_all(p)
        ok, why = gate.green_at_head(p)
        self.assertFalse(ok)
        self.assertIn("nothing proves", " ".join(why))

    def test_detectors_flag_skipped_tests_and_stubs(self):
        p = self.project()
        self.setup_remote(p)
        commit_all(p)
        sh(p, "git", "push", "-q", "origin", "HEAD:main")
        sh(p, "git", "fetch", "-q", "origin")
        (p / "a.test.ts").write_text("it.skip('x', () => {})\n")
        (p / "b.py").write_text("def f():\n    raise NotImplementedError\n")
        commit_all(p, "sneaky")
        found = " ".join(gate.diff_detectors(p))
        self.assertIn("skip", found)
        self.assertIn("stubs", found)


class BudgetAndItemTests(Base):
    def test_real_brain_meets_its_budgets(self):
        errs, info = budget.check(ROOT)
        self.assertEqual(errs, [])
        self.assertLessEqual(info["claude_md_bytes"], budget.LIMITS["claude_md"])
        self.assertLessEqual(info["always_loaded_tokens"], 3200)

    def test_budget_flags_long_descriptions_missing_models_and_volatile_text(self):
        b = self.brain
        (b / "contract" / "template").mkdir(parents=True)
        (b / "contract" / "template" / "CLAUDE.stub.md").write_text("stub")
        (b / "CLAUDE.md").write_text("# x\nlast updated 2026-01-01\n")
        (b / ".claude" / "agents").mkdir(parents=True)
        (b / ".claude" / "agents" / "a.md").write_text("---\nname: a\ndescription: " + "d" * 400 + "\n---\nbody\n")
        (b / ".claude" / "skills" / "s").mkdir(parents=True)
        (b / ".claude" / "skills" / "s" / "SKILL.md").write_text("---\nname: s\ndescription: ok\nmodel: opus\n---\nbody\n")
        errs = " | ".join(budget.check(b)[0])
        for needle in ("volatile", "description is 400", "'model' must be set", "must not set 'model'"):
            self.assertIn(needle, errs)

    def test_real_item_files_are_valid_and_have_no_project_names(self):
        files = items.brain_item_files(ROOT)
        self.assertEqual(items.check_files(files), [])

    def test_item_rules(self):
        good = {"id": "rule-x1", "type": "rule", "scope": "global", "text": "Do the thing because reasons.", "trust": "seed",
                "provenance": "docs/research/03", "created": "2026-11-10"}
        self.assertEqual(items.validate_item(items.normalise(good)), [])
        external_rule = dict(good, trust="external")
        self.assertTrue(any("external-trust" in e for e in items.validate_item(items.normalise(external_rule))))
        too_long = dict(good, text="x" * 401)
        self.assertTrue(any("limit" in e for e in items.validate_item(items.normalise(too_long))))
        secret = dict(good, text="use token " + "ghp_" + "a" * 30)
        self.assertTrue(any("secret" in e for e in items.validate_item(items.normalise(secret))))
        self.assertGreater(items.confidence(dict(good, trust="owner-stated")), items.confidence(good))
        self.assertLess(items.confidence(dict(good, harmful=5)), items.confidence(good))


if __name__ == "__main__":
    unittest.main()
