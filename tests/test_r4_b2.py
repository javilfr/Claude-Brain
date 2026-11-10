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


# ---------------------------------------------------------------- start-up and the command line
def engine_copy(dest: Path) -> Path:
    """bin/ and engine/ as a fresh clone has them: no compiled files."""
    shutil.copytree(ROOT / "bin", dest / "bin", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "engine", dest / "engine", ignore=shutil.ignore_patterns("__pycache__"))
    return dest


LOADED = (
    "import runpy, sys\n"
    "sys.argv = sys.argv[1:]\n"
    "try:\n    runpy.run_path(sys.argv[0], run_name='__main__')\nexcept SystemExit:\n    pass\n"
    "print('LOADED ' + ' '.join(sorted(m for m in sys.modules if m.split('.')[0] in ('engine', 'urllib', 'sqlite3', 'ssl'))))\n"
)


def loaded_modules(cwd, *argv) -> set[str]:
    """The engine modules (and the slow standard ones) one brain call loads."""
    r = sh(cwd, sys.executable, "-c", LOADED, BRAIN, *argv)
    line = [l for l in r.stdout.splitlines() if l.startswith("LOADED")]
    return set(line[-1].split()[1:]) if line else {"<the call printed no module list>", r.stdout + r.stderr}


class StartUpTests(Base):
    def test_bytecode_is_kept_in_the_user_cache_and_never_in_the_tree(self):
        """performance-03 (1): bin/brain switched bytecode off, so a fresh
        clone compiled every module on every call (about 240 ms each). The
        compiled files now live under the user's cache folder; the checkout
        stays as git left it."""
        copy = engine_copy(self.ws / "clone")
        xdg = self.ws / "xdg"
        env = dict(os.environ, XDG_CACHE_HOME=str(xdg))
        r = self.brain("detect", script=str(copy / "bin" / "brain"), env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cached = [f.name for f in (xdg / "claude-brain" / "pyc").rglob("*.pyc")]
        self.assertTrue(any(n.startswith("common.") for n in cached), cached)
        self.assertTrue(any(n.startswith("detect.") for n in cached), cached)
        self.assertEqual([str(f) for f in copy.rglob("*") if f.name == "__pycache__" or f.suffix == ".pyc"], [])
        self.assertEqual(self.brain("detect", script=str(copy / "bin" / "brain"), env=env).stdout, r.stdout)

    def test_the_users_own_bytecode_settings_win(self):
        """performance-03 (1): PYTHONDONTWRITEBYTECODE still means no compiled
        files anywhere, and a PYTHONPYCACHEPREFIX the user set is used as it is."""
        copy = engine_copy(self.ws / "clone")
        script = str(copy / "bin" / "brain")
        xdg = self.ws / "xdg-none"
        self.brain("detect", script=script, env=dict(os.environ, XDG_CACHE_HOME=str(xdg), PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(list(xdg.rglob("*.pyc")) + list(copy.rglob("*.pyc")), [])
        mine = self.ws / "mine"
        self.brain("detect", script=script, env=dict(os.environ, XDG_CACHE_HOME=str(xdg), PYTHONPYCACHEPREFIX=str(mine)))
        self.assertTrue(list(mine.rglob("common.*.pyc")))
        self.assertEqual(list(xdg.rglob("*.pyc")) + list(copy.rglob("*.pyc")), [])

    def test_loading_the_command_line_as_a_module_changes_nothing_in_the_caller(self):
        """performance-03 (1): the test suite and the hooks load bin/brain as
        a module; that must not move the caller's own bytecode settings."""
        before = (sys.pycache_prefix, sys.dont_write_bytecode)
        loader = importlib.machinery.SourceFileLoader("brain_cli_probe", BRAIN)
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("brain_cli_probe", loader))
        loader.exec_module(mod)
        self.assertEqual((sys.pycache_prefix, sys.dont_write_bytecode), before)

    def test_a_command_loads_only_the_module_that_owns_it(self):
        """performance-03 (2): every call imported all twenty modules (and
        through them urllib, ssl, xml, sqlite). A command now loads the one
        module that registers it; help and a mistyped command load them all."""
        self.assertEqual(loaded_modules(self.ws, "budget"), {"engine", "engine.common", "engine.budget"})
        self.assertEqual(loaded_modules(self.ws, "validate", "--project", self.ws / "nowhere"), {"engine", "engine.common", "engine.contract"})
        everything = loaded_modules(self.ws, "--help")
        self.assertGreater(len([m for m in everything if m.startswith("engine.")]), 15, "help lists every command, so it loads every module")
        helped = self.brain("--help")
        for cmd in ("boot", "checkpoint", "hr", "doctor", "skill-audit"):
            self.assertIn(f"\n    {cmd} ", helped.stdout)
        typo = self.brain("chekpoint")
        self.assertEqual(typo.returncode, 2)
        self.assertIn("checkpoint", typo.stderr, "a mistyped command still names the real ones")

    def test_the_command_table_matches_what_the_modules_register(self):
        """performance-03 (2): the table that says which module owns a command
        cannot drift from the code: it is compared with what each module's
        register() really adds."""
        from engine import COMMANDS, MODULES
        self.assertEqual(sorted(set(COMMANDS.values()) - set(MODULES)), [], "a table entry names a module that is not in MODULES")
        for module in MODULES:
            _parser, sub, broken = cli().build([module])
            self.assertEqual(broken, [])
            registered = set(sub.choices)
            listed = {cmd for cmd, owner in COMMANDS.items() if owner == module}
            fix = "; ".join(f"add '{cmd}': '{module}'" for cmd in sorted(registered - listed)) or f"remove {sorted(listed - registered)}"
            self.assertEqual(registered, listed, f"engine/__init__.py COMMANDS is out of date: {fix}")
        self.assertEqual(set(cli().build()[1].choices), set(COMMANDS))

    def test_a_command_missing_from_the_table_still_runs(self):
        """performance-03 (2): the table is a short cut, not a gate: a command
        it does not list is found by loading every module, as before."""
        from engine import COMMANDS
        with mock.patch.dict(COMMANDS, clear=True):
            code, out = self.run_cli("budget")
        self.assertEqual(code, 0, out)
        self.assertIn("always-loaded", out)
        with mock.patch.dict(COMMANDS, {"budget": "items"}):  # a wrong entry is no worse
            self.assertEqual(self.run_cli("budget")[0], 0)

    def test_a_broken_or_missing_module_is_still_named_in_one_line(self):
        """performance-03 (acceptance: a broken module is still named) and
        package D's note for bin/brain: `brain done` joins the commands that
        answer "is unavailable: failed to load ..." when their module does not
        import, and doctor still lists what failed."""
        copy = engine_copy(self.ws / "broken-brain")
        script = str(copy / "bin" / "brain")
        (copy / "engine" / "req.py").write_text("def broken(:\n")
        (copy / "engine" / "route.py").unlink()
        for argv, needle in ((("done",), "req (SyntaxError"), (("req", "list"), "req (SyntaxError"),
                             (("route", "fix the bug"), "route (ModuleNotFoundError")):
            r = self.brain(*argv, script=script)
            out = r.stdout + r.stderr
            self.assertEqual(r.returncode, 1, out)
            self.assertEqual(len(out.strip().splitlines()), 1, out)
            for want in (f"'{argv[0]}' is unavailable", needle, "brain doctor"):
                self.assertIn(want, out)
            self.assertNotIn("Traceback", out)
        r = self.brain("detect", script=script)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("unavailable", r.stdout, "a command whose module loads still runs")
        doctor = self.brain("doctor", script=script)
        self.assertIn("modules that failed to load:", doctor.stdout)
        self.assertIn("req (SyntaxError", doctor.stdout)


class UsageTests(Base):
    def test_help_is_short_and_lists_each_command_once(self):
        """performance-08: `brain --help` printed the list of commands three
        times (3.8 kB). The braces list is gone; each command keeps its line."""
        r = self.brain("--help")
        self.assertEqual(r.returncode, 0)
        self.assertLessEqual(len(r.stdout.encode()), 2800)
        self.assertNotIn("{detect,boot", r.stdout)
        self.assertEqual(r.stdout.count("checkpoint"), 1)

    def test_a_usage_error_is_one_line_that_names_the_commands_help(self):
        """performance-08: a missing argument or a mistyped flag printed the
        whole usage block (250 to 760 bytes) before the one line that
        mattered. Now: one line, what is wrong, and which help to read."""
        p = self.project()
        cases = (
            (("init",), "path", "brain init --help", 120),
            (("req", "set"), "id", "brain req set --help", 120),
            (("boot", "--nmae", "shop"), "--nmae", "brain boot --help", 140),
            (("req", "add", "--qoute", "x", "--project", p), "--qoute", "brain req add --help", 140),
            (("checkpoint", "--stage", "building", "--project", p), "'building'", "brain checkpoint --help", 260),
        )
        for argv, names, helps, cap in cases:
            r = self.brain(*argv)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertEqual(r.stdout, "")
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
            self.assertIn(names, r.stderr)
            self.assertIn(f"(see: {helps})", r.stderr)
            self.assertNotIn("usage:", r.stderr)
            self.assertLessEqual(len(r.stderr.encode()), cap, r.stderr)

    def test_a_mistyped_flag_is_answered_with_the_flag_that_was_meant(self):
        """performance-08: the session's transcripts show a help look-up after
        most mistyped flags. The one line now offers the closest real flag."""
        r = self.brain("boot", "--nmae", "shop")
        self.assertIn("did you mean --name?", r.stderr)
        r = self.brain("init", ".", "--zzz")
        self.assertNotIn("did you mean", r.stderr, "nothing close: no guess")

    def test_an_invalid_choice_still_names_the_valid_ones(self):
        """performance-08 (acceptance): the short error keeps the list of
        valid values, for an option and for a sub-command."""
        r = self.brain("checkpoint", "--stage", "building")
        for stage in ("intake", "build", "verify", "done"):
            self.assertIn(stage, r.stderr)
        r = self.brain("req", "ad")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        for name in ("add", "evidence", "check"):
            self.assertIn(name, r.stderr)

    def test_a_command_run_in_this_process_reports_usage_errors_the_same_way(self):
        """performance-08: callers that reuse one command tree (the test
        suites) get the same one-line answers."""
        tree = cli().build()
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            cli().main(["boot", "--nmae"], tree=tree)
        self.assertEqual(stop.exception.code, 2)
        self.assertEqual(len(err.getvalue().strip().splitlines()), 1)
        self.assertIn("(see: brain boot --help)", err.getvalue())


if __name__ == "__main__":
    unittest.main()
