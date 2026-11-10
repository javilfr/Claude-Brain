"""Package B, second pass, of the 2026-11-10 improvement plan: contract,
common, doctor and the command line.

Each test names the finding(s) it pins (docs/review/2026-11-10-audit/<area>.json)
or the note another builder left for these files. Every test works in a
temporary folder; nothing here reads or writes the real brain's learned zone,
the real user cache, or any real remote.
"""
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import budget, common as c, contract  # noqa: E402

BRAIN = str(ROOT / "bin" / "brain")
_CLI = None


def cli():
    """bin/brain loaded once as a module, so commands can run in this process."""
    global _CLI
    if _CLI is None:
        loader = importlib.machinery.SourceFileLoader("brain_cli_r4b2", BRAIN)
        spec = importlib.util.spec_from_loader("brain_cli_r4b2", loader)
        _CLI = importlib.util.module_from_spec(spec)
        loader.exec_module(_CLI)
    return _CLI


def sh(cwd, *args, **kw):
    return subprocess.run([str(a) for a in args], cwd=str(cwd), capture_output=True, text=True, **kw)


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
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name).resolve()
        self._env = dict(os.environ)
        self.addCleanup(self._restore_env)
        for k in ("BRAIN_PROJECT", "BRAIN_NOW", "CLAUDE_CODE_SESSION_ID", "BRAIN_TRANSCRIPT", "PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE"):
            os.environ.pop(k, None)
        os.environ["BRAIN_NO_NETWORK"] = "1"
        os.environ["BRAIN_SESSION_ID"] = "r4b2-test"
        os.environ["XDG_CACHE_HOME"] = str(self.ws / "xdg-cache")  # bytecode of commands run here stays in the temp folder
        self._cwd = os.getcwd()
        self.addCleanup(os.chdir, self._cwd)

    def _restore_env(self):
        os.environ.clear()
        os.environ.update(self._env)

    def repo(self, name="proj") -> Path:
        p = git_repo(self.ws / name)
        (p / "README.md").write_text("# x\n")
        return p

    def project(self, name="proj", **kw) -> Path:
        p = self.repo(name)
        contract.init(p, name.title(), kw.pop("family", "software"), kw or None)
        return p

    def run_cli(self, *argv):
        """(exit code, printed text) of one brain command, run in this process."""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = cli().main([str(a) for a in argv])
            except SystemExit as e:  # argparse's own exit on a bad command line
                code = e.code if isinstance(e.code, int) else 1
        return code, out.getvalue() + err.getvalue()

    def brain(self, *argv, cwd=None, script=BRAIN, env=None):
        """One brain command in its own process, as a session types it."""
        return sh(cwd or self.ws, sys.executable, script, *argv, env=env or dict(os.environ))


# ---------------------------------------------------------------- the project explains itself
class SelfExplainingProjectTests(Base):
    def test_init_writes_a_map_of_the_brain_folder_and_never_overwrites_it(self):
        """lead-04 (a): nothing in a project said which file holds what, or
        how a new chat continues. init writes .brain/README.md once; an edited
        one is left alone."""
        p = self.repo()
        made = contract.init(p, "Shop", "software")
        readme = p / ".brain" / "README.md"
        self.assertIn(".brain/README.md", made)
        text = readme.read_text()
        self.assertLessEqual(len(text.splitlines()), 25)
        for name in ("project.json", "STATE.md", "PLAN.md", "DECISIONS.md", "requirements.jsonl", "HANDOVER.md",
                     "memory/lessons.jsonl", "ext/", "log/", "STATUS.md", "NEEDS_YOU.md"):
            self.assertIn(name, text)
        for step in ("bin/brain boot", "resume --adopt", "another branch", "No brain attached"):
            self.assertIn(step, text)
        for writer in ("brain checkpoint", "brain req", "brain handover"):
            self.assertIn(writer, text)
        readme.write_text("# mine\n")
        self.assertEqual(contract.init(p, "Shop", "software"), [])
        self.assertEqual(readme.read_text(), "# mine\n")
        self.assertEqual(contract.validate(p), [])

    def test_adopt_and_migrate_add_the_map_when_it_is_missing(self):
        """lead-04 (a): an existing codebase gets the map at adopt; a project
        made by an earlier brain gets it from `brain migrate`, which keeps a
        map that is already there."""
        p = self.repo("legacy")
        (p / "app.py").write_text("print('hi')\n")
        contract.adopt(p)
        self.assertTrue((p / ".brain" / "README.md").is_file())
        (p / ".brain" / "README.md").unlink()
        code, msgs = contract.migrate(p)
        self.assertEqual(code, 0)
        self.assertTrue((p / ".brain" / "README.md").is_file())
        self.assertIn(".brain/README.md", " ".join(msgs))
        (p / ".brain" / "README.md").write_text("# mine\n")
        code, msgs = contract.migrate(p)
        self.assertEqual((code, msgs), (0, ["already on contract v1"]))
        self.assertEqual((p / ".brain" / "README.md").read_text(), "# mine\n")

    def test_migrate_writes_nothing_to_a_project_on_a_newer_contract(self):
        """lead-04 (a) must not weaken the stale-brain rule: a project on a
        newer contract gets no README from an older brain."""
        p = self.project()
        (p / ".brain" / "README.md").unlink()
        m = json.loads((p / ".brain" / "project.json").read_text())
        m["contract"] = c.CONTRACT_VERSION + 1
        (p / ".brain" / "project.json").write_text(json.dumps(m))
        code, _msgs = contract.migrate(p)
        self.assertEqual(code, 3)
        self.assertFalse((p / ".brain" / "README.md").exists())

    def test_the_stub_says_the_last_chat_may_have_saved_on_its_own_branch(self):
        """lead-04 (b): the pointer block every project carries now says that
        the last chat may have saved on its own branch and how to continue
        from it; it stays under its 2,000-byte cap and the budget passes."""
        stub = (ROOT / "contract" / "template" / "CLAUDE.stub.md").read_text()
        block = stub[stub.index(contract.BEGIN): stub.index(contract.END)]
        self.assertIn("own branch", block)
        self.assertIn("resume --adopt", block)
        self.assertLessEqual(len(stub.encode()), contract.STUB_LIMIT)
        self.assertEqual(budget.check(ROOT)[0], [])
        p = self.project()
        self.assertIn("resume --adopt", (p / "CLAUDE.md").read_text())
        self.assertEqual(contract.validate(p), [])

    def test_a_spanish_project_gets_spanish_owner_files_from_the_first_day(self):
        """Package B's own note from the first pass (theme T7): a project made
        with --language es got an English STATUS.md and NEEDS_YOU.md header."""
        p = self.repo("tienda")
        code, out = self.run_cli("init", p, "--title", "Tienda", "--language", "es")
        self.assertEqual(code, 0, out)
        status, needs = (p / "STATUS.md").read_text(), (p / "NEEDS_YOU.md").read_text()
        self.assertIn("Tienda", status)
        self.assertIn("Todavía no se ha construido nada", status)
        self.assertNotIn("Nothing has been built", status)
        self.assertIn("Cosas que solo tú puedes hacer", needs)
        self.assertIn("RESUELTO:", needs)
        self.assertNotIn("Things only you can do", needs)
        self.assertIn('## N.', needs, "the marker the engine adds items under is unchanged")
        english = self.repo("shop")
        self.run_cli("init", english, "--title", "Shop")
        self.assertIn("Nothing has been built yet", (english / "STATUS.md").read_text())
        self.assertIn("Things only you can do", (english / "NEEDS_YOU.md").read_text())

    def test_init_seeds_a_starter_gitignore_only_when_there_is_none(self):
        """quality-path-14 (the part package C left for contract.init): a
        check that runs Python leaves __pycache__ behind and the next release
        refused the dirty tree. init writes a small starter .gitignore when
        the folder has none and never touches one that exists."""
        p = self.repo()
        made = contract.init(p, "Shop", "software")
        self.assertIn(".gitignore", made)
        commit_all(p)
        (p / "__pycache__").mkdir()
        (p / "__pycache__" / "x.cpython-313.pyc").write_bytes(b"\0")
        (p / "node_modules" / "left-pad").mkdir(parents=True)
        (p / "node_modules" / "left-pad" / "index.js").write_text("x\n")
        self.assertEqual(sh(p, "git", "status", "--porcelain").stdout, "")
        own = self.repo("own")
        (own / ".gitignore").write_text("dist/\n")
        self.assertNotIn(".gitignore", contract.init(own, "Own", "software"))
        self.assertEqual((own / ".gitignore").read_text(), "dist/\n")
        legacy = self.repo("legacy")
        (legacy / "app.py").write_text("print('hi')\n")
        contract.adopt(legacy)
        self.assertFalse((legacy / ".gitignore").exists(), "adopt adds contract files only (tests/test_core.py pins that)")


class AgentsFileTests(Base):
    def test_adopt_keeps_an_agents_file_loading(self):
        """research-platform-05: Claude Code loads AGENTS.md only while no
        CLAUDE.md exists, so adopt (which creates CLAUDE.md) silently switched
        a repository's instructions off. adopt now adds an import line just
        below the managed block, once."""
        p = self.repo("agents")
        (p / "AGENTS.md").write_text("# Agents\n\nRun `make test` before committing.\n")
        commit_all(p)
        code, out = self.run_cli("adopt", p, "--family", "software", "--title", "Agents test")
        self.assertEqual(code, 0, out)
        self.assertIn("AGENTS.md", out, "adopt says what it did")
        lines = (p / "CLAUDE.md").read_text().splitlines()
        self.assertIn("@AGENTS.md", lines)
        self.assertGreater(lines.index("@AGENTS.md"), lines.index(contract.END), "outside the managed block")
        self.assertEqual(lines.index("@AGENTS.md"), lines.index(contract.END) + 1, "just below the end marker")
        before = (p / "CLAUDE.md").read_text()
        code, out = self.run_cli("adopt", p)
        self.assertEqual(code, 0, out)
        self.assertEqual((p / "CLAUDE.md").read_text(), before, "a second adopt adds nothing")
        self.assertEqual(self.run_cli("validate", "--project", p)[0], 0)
        self.assertEqual((p / "AGENTS.md").read_text(), "# Agents\n\nRun `make test` before committing.\n")

    def test_a_handbook_that_already_imports_the_agents_file_gets_no_second_import(self):
        """research-platform-05: a CLAUDE.md that already imports AGENTS.md
        keeps its one import; an existing handbook without one gets the line
        below the block and keeps every line of its own."""
        p = self.repo("imports")
        (p / "AGENTS.md").write_text("# Agents\n")
        (p / "CLAUDE.md").write_text("# Handbook\n\n@AGENTS.md\n\nMore notes.\n")
        contract.adopt(p)
        text = (p / "CLAUDE.md").read_text()
        self.assertEqual(text.count("@AGENTS.md"), 1)
        self.assertTrue(text.endswith("# Handbook\n\n@AGENTS.md\n\nMore notes.\n"))
        q = self.repo("plain")
        (q / "AGENTS.md").write_text("# Agents\n")
        (q / "CLAUDE.md").write_text("# Handbook\n\nNotes.\n")
        _s, made = contract.adopt(q)
        text = (q / "CLAUDE.md").read_text()
        self.assertEqual(text.count("@AGENTS.md"), 1)
        self.assertTrue(text.endswith("# Handbook\n\nNotes.\n"))
        self.assertTrue(any("AGENTS.md" in x for x in made), made)
        none = self.repo("none")
        contract.adopt(none)
        self.assertNotIn("AGENTS", (none / "CLAUDE.md").read_text(), "no AGENTS.md, no import")

    def test_survey_and_validate_say_when_an_agents_file_is_not_loaded(self):
        """research-platform-05: the read-only survey names the AGENTS.md that
        would stop loading, and validate notes one that CLAUDE.md does not
        import (a note, not a failure: the contract itself is valid)."""
        p = self.repo("survey")
        (p / "AGENTS.md").write_text("# Agents\n")
        code, out = self.run_cli("adopt", p, "--survey")
        self.assertEqual(code, 0)
        self.assertIn("AGENTS.md", out)
        self.assertFalse((p / "CLAUDE.md").exists(), "the survey writes nothing")
        contract.adopt(p)
        text = (p / "CLAUDE.md").read_text()
        (p / "CLAUDE.md").write_text(text.replace("@AGENTS.md\n", ""))
        code, out = self.run_cli("validate", "--project", p)
        self.assertEqual(code, 0, out)
        self.assertIn("note: AGENTS.md", out)
        self.assertIn("@AGENTS.md", out, "the note gives the line to add")
        (p / "CLAUDE.md").write_text(text)
        self.assertNotIn("AGENTS", self.run_cli("validate", "--project", p)[1])


class ValidateGateCommandTests(Base):
    def test_validate_refuses_a_gate_command_that_cannot_fail(self):
        """Package C's note for contract.py (quality-path, T2): a gate whose
        command ends in `|| true` is green whatever happens. validate asks the
        gate module's own rule (gate.masked_command) and names the gate."""
        from engine import gate
        p = self.project()
        m = json.loads((p / ".brain" / "project.json").read_text())
        m["gates"] = [{"id": "checks", "kind": "command", "command": "pytest -q || true"},
                      {"id": "lint", "kind": "command", "command": "ruff check ."}]
        (p / ".brain" / "project.json").write_text(json.dumps(m))

        def rule(command, *a, **k):
            return "`|| true` hides a failure" if "|| true" in command else ""

        with mock.patch.object(gate, "masked_command", rule, create=True):
            errs = contract.validate(p)
        hit = [e for e in errs if "checks" in e and "hides a failure" in e]
        self.assertEqual(len(hit), 1, errs)
        self.assertEqual(len(errs), 1, errs)
        self.assertIn(".brain/project.json", hit[0], "the line says where to fix it")


if __name__ == "__main__":
    unittest.main()
