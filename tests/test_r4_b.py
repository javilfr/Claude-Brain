"""Package B of the 2026-11-10 improvement plan: contract, common and doctor.

Each test names the finding(s) it pins (docs/review/2026-11-10-audit/<area>.json).
Every test works in a temporary folder with a stand-in brain beside the
projects; ``common.BRAIN_ROOT`` is pointed at the stand-in, so nothing here
reads or writes the real brain, and nothing is ever pushed anywhere real.
"""
import importlib.machinery
import importlib.util
import io
import json
import os
import random
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

from engine import budget, cache, common as c, contract, detect, state  # noqa: E402

_CLI = None


def cli():
    """bin/brain loaded once as a module, so commands run in this process."""
    global _CLI
    if _CLI is None:
        loader = importlib.machinery.SourceFileLoader("brain_cli_r4b", str(ROOT / "bin" / "brain"))
        spec = importlib.util.spec_from_loader("brain_cli_r4b", loader)
        _CLI = importlib.util.module_from_spec(spec)
        loader.exec_module(_CLI)
    return _CLI


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


def snapshot(path: Path) -> dict:
    """Every file under a folder (git data aside) with its bytes."""
    return {str(f.relative_to(path)): f.read_bytes() for f in sorted(path.rglob("*")) if f.is_file() and ".git" not in f.parts}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name).resolve()
        self.brain = self.ws / "Claude-Brain"
        (self.brain / "memory").mkdir(parents=True)
        c.write_json(self.brain / "memory" / "models.json", {"verified_on": c.today(), "recheck_days": 90, "models": {}})
        shutil.copytree(ROOT / "contract", self.brain / "contract")  # the schema `validate` reads
        self._env = dict(os.environ)
        self.addCleanup(self._restore_env)
        for k in ("BRAIN_PROJECT", "BRAIN_NOW", "CLAUDE_CODE_SESSION_ID", "BRAIN_TRANSCRIPT"):
            os.environ.pop(k, None)
        os.environ["BRAIN_NO_NETWORK"] = "1"
        os.environ["BRAIN_SESSION_ID"] = "r4b-test"
        patch = mock.patch.object(c, "BRAIN_ROOT", self.brain)
        patch.start()
        self.addCleanup(patch.stop)
        self._cwd = os.getcwd()
        self.addCleanup(os.chdir, self._cwd)
        os.chdir(self.brain)  # the documented stance: commands are typed from the brain folder

    def _restore_env(self):
        os.environ.clear()
        os.environ.update(self._env)

    def project(self, name="proj", family="software", git=True) -> Path:
        p = self.ws / name
        if git:
            git_repo(p)
        else:
            p.mkdir(parents=True)
        (p / "README.md").write_text("# x\n")
        contract.init(p, name.title(), family)
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

    def set_manifest(self, p: Path, **changes) -> None:
        path = p / ".brain" / "project.json"
        m = json.loads(path.read_text())
        m.update(changes)
        path.write_text(json.dumps(m, indent=2) + "\n")


# The commands every session leans on. None may ever answer with a traceback.
CORE_COMMANDS = (
    ("boot", "Continue"), ("status",), ("validate",), ("checkpoint", "--item", "x"),
    ("resume",), ("handover",), ("req", "list"), ("gate",),
)


class ManifestShapeTests(Base):
    def test_wrong_typed_manifest_sections_are_one_line_never_a_traceback(self):
        """core-06: a manifest section that is null, a string, a list or a
        number used to end boot, status, checkpoint and handover in a Python
        traceback (and checkpoint had already rewritten STATE.md by then)."""
        p = self.project()
        commit_all(p)
        good = (p / ".brain" / "project.json").read_text()
        for key in ("project", "release", "commands", "paths", "gates"):
            for bad in (None, "text", [1], 7):
                with self.subTest(key=key, bad=bad):
                    (p / ".brain" / "project.json").write_text(good)
                    self.set_manifest(p, **{key: bad})
                    problem = c.manifest_problem(p)
                    self.assertIn(f'"{key}', problem)  # "gates" or "gates[0]"
                    self.assertIn("fix it or restore it from git", problem)
                    boot = "\n".join(detect.boot_lines("Continue", self.brain))
                    self.assertIn("PROBLEM", boot)
                    self.assertIn(f'"{key}', boot)
                    before = snapshot(p)
                    for argv in (("status",), ("checkpoint", "--item", "x", "--push"), ("handover",), ("release",),
                                 ("resume",), ("req", "list"), ("gate",)):
                        code, out = self.run_cli(*argv, "--project", p)
                        self.assertEqual(code, 1, (argv, out))
                        self.assertIn(f'"{key}', out)
                        self.assertLessEqual(len(out.strip().splitlines()), 2, out)
                    self.assertEqual(snapshot(p), before, "a refused command writes nothing")

    def test_inner_shapes_the_commands_rely_on_are_checked_too(self):
        """core-06: the same crash one level down: a gate that is not an
        object, a release branch that is not text, a command that is a list."""
        p = self.project()
        cases = {
            "gates": [["checks"]],
            "release": {"rule": "main-on-green", "branch": 7},
            "commands": {"check_full": ["pytest"]},
            "tier": "2",
        }
        for key, bad in cases.items():
            with self.subTest(key=key):
                self.set_manifest(p, **{key: bad})
                self.assertIn("must be", c.manifest_problem(p))
                code, out = self.run_cli("status", "--project", p)
                self.assertEqual(code, 1, out)
                self.set_manifest(p, **{key: contract.default_manifest("Proj", "software")[key]})
                self.assertEqual(c.manifest_problem(p), "")

    def test_unknown_keys_and_a_valid_manifest_are_not_a_problem(self):
        """core-06: the check must not get in the way of a good manifest or of
        a newer optional key (unknown keys are allowed by the contract)."""
        p = self.project()
        self.set_manifest(p, future_optional={"anything": [1, 2]}, types=["web-app"], languages=["es", "en"])
        self.assertEqual(c.manifest_problem(p), "")
        code, out = self.run_cli("status", "--project", p)
        self.assertEqual(code, 0, out)

    def test_load_manifest_never_hands_out_a_wrong_typed_section(self):
        """core-06: callers that do not pass through need_project (boot's
        sizing, recall, close) read the manifest too; they get usable shapes,
        while the raw file is left exactly as it is."""
        p = self.project()
        self.set_manifest(p, project=None, release="main-on-green", gates=[{"id": "a", "kind": "command", "command": "true"}, "junk"], commands=[1])
        raw = (p / ".brain" / "project.json").read_bytes()
        m = c.load_manifest(p)
        self.assertEqual((m["project"], m["release"], m["commands"]), ({}, {}, {}))
        self.assertEqual(m["gates"], [{"id": "a", "kind": "command", "command": "true"}])
        self.assertEqual(c.load_manifest(p, raw=True)["release"], "main-on-green")
        self.assertEqual((p / ".brain" / "project.json").read_bytes(), raw)


class FuzzTests(Base):
    WRONG = (None, "text", "", 7, -1, 3.5, True, [], [1], [None], ["a", 1], {}, {"x": 1}, "x" * 3000, 10 ** 30)

    def mutate_manifest(self, rng: random.Random, text: str) -> tuple[str, bytes]:
        m = json.loads(text)
        kind = rng.choice(("top", "top", "inner", "inner", "delete", "truncate", "bad-byte", "conflict", "whole"))
        if kind == "top":
            key = rng.choice(sorted(m))
            m[key] = rng.choice(self.WRONG)
            return f"{key}={m[key]!r:.40}", json.dumps(m).encode()
        if kind == "inner":
            key = rng.choice([k for k in sorted(m) if isinstance(m[k], (dict, list)) and m[k]])
            if isinstance(m[key], dict):
                sub = rng.choice(sorted(m[key]))
                m[key][sub] = rng.choice(self.WRONG)
                return f"{key}.{sub}={m[key][sub]!r:.40}", json.dumps(m).encode()
            if isinstance(m[key][0], dict):
                sub = rng.choice(sorted(m[key][0]))
                m[key][0][sub] = rng.choice(self.WRONG)
                m[key].append(rng.choice(self.WRONG))
                return f"{key}[0].{sub}={m[key][0][sub]!r:.40} plus a stray entry", json.dumps(m).encode()
            m[key][0] = rng.choice(self.WRONG)
            return f"{key}[0]={m[key][0]!r:.40}", json.dumps(m).encode()
        if kind == "delete":
            key = rng.choice(sorted(m))
            del m[key]
            return f"no {key}", json.dumps(m).encode()
        raw = text.encode()
        if kind == "truncate":
            n = rng.randrange(0, len(raw))
            return f"cut at byte {n}", raw[:n]
        if kind == "bad-byte":
            n = rng.randrange(0, len(raw))
            return f"0xff at byte {n}", raw[:n] + b"\xff" + raw[n:]
        if kind == "conflict":
            lines = text.splitlines(keepends=True)
            n = rng.randrange(1, len(lines))
            return f"conflict markers at line {n}", "".join(lines[:n] + ["<<<<<<< HEAD\n"] + lines[n:n + 1] + ["=======\n", ">>>>>>> other\n"] + lines[n + 1:]).encode()
        whole = rng.choice(("", "null", "[]", "3", '"x"', "{}", '{"contract": 1}', '{"contract": true}', '{"contract": 1.0}', "\x00\x01"))
        return f"whole file {whole!r}", whole.encode()

    def mutate_state(self, rng: random.Random, text: str) -> tuple[str, bytes]:
        raw = text.encode()
        kind = rng.choice(("truncate", "bad-byte", "conflict", "field", "field", "whole", "long"))
        if kind == "truncate":
            n = rng.randrange(0, len(raw))
            return f"cut at byte {n}", raw[:n]
        if kind == "bad-byte":
            n = rng.randrange(0, len(raw))
            return f"0xff at byte {n}", raw[:n] + b"\xff" + raw[n:]
        if kind == "conflict":
            lines = text.splitlines(keepends=True)
            n = rng.randrange(1, len(lines))
            return f"conflict markers at line {n}", "".join(lines[:n] + ["<<<<<<< HEAD\n"] + lines[n:n + 1] + ["=======\n", ">>>>>>> other\n"] + lines[n + 1:]).encode()
        if kind == "field":
            field = rng.choice(state.FIELDS)
            value = rng.choice(("", "abc", "-5", "99999999999999999999", "not-a-date", ";;;", "none", "\t", "## Log", "2026-13-45T99:99:99Z", "é" * 500))
            out = [f"{field}: {value}" if l.startswith(field + ":") else l for l in text.splitlines()]
            return f"{field}: {value!r:.30}", ("\n".join(out) + "\n").encode()
        if kind == "long":
            return "one 200 kB line", raw + b"- " + b"z" * 200_000 + b"\n"
        whole = rng.choice(("", "\n\n\n", "# State\n", "\x00\x01\x02", "## Notes\n## Log\n- - -\n", "tier: x\nstage\n: \n"))
        return f"whole file {whole!r}", whole.encode()

    def test_no_core_command_ever_answers_with_a_traceback(self):
        """core-16 (fuzz part), core-06, core-05: seeded damage to
        .brain/project.json and .brain/STATE.md; boot, status, validate,
        checkpoint, resume, handover, req list and gate must each end with an
        exit code and short output, never an exception."""
        p = self.project()
        self.set_manifest(p, gates=[{"id": "checks", "kind": "command", "command": "true"}],
                          release={"rule": "main-on-green", "branch": "main", "live_url": ""})
        state.checkpoint(p, item="T-1 list view", nxt=["T-2"], stage="build", note="half done in src/x")
        commit_all(p)
        manifest_path, state_path = p / ".brain" / "project.json", p / ".brain" / "STATE.md"
        good_manifest, good_state = manifest_path.read_text(), state_path.read_text()
        rng = random.Random(20261110)  # fixed: the same damage on every run (I-13)
        failures = []
        for i in range(60):
            target = "project.json" if i % 3 else "STATE.md"
            if target == "project.json":
                what, data = self.mutate_manifest(rng, good_manifest)
                manifest_path.write_bytes(data)
            else:
                what, data = self.mutate_state(rng, good_state)
                state_path.write_bytes(data)
            for argv in CORE_COMMANDS:
                extra = () if argv[0] == "boot" else ("--project", str(p))
                try:
                    code, out = self.run_cli(*argv, *extra)
                except Exception as e:  # noqa: BLE001 - the point of the test
                    failures.append(f"#{i} {target} [{what}] brain {' '.join(argv)}: {type(e).__name__}: {str(e)[:80]}")
                    continue
                if "Traceback" in out or not isinstance(code, int):
                    failures.append(f"#{i} {target} [{what}] brain {' '.join(argv)}: printed a traceback")
                elif len(out.strip().splitlines()) > 15:  # I-04: damage must not turn into a wall of text either
                    failures.append(f"#{i} {target} [{what}] brain {' '.join(argv)}: {len(out.strip().splitlines())} lines")
            manifest_path.write_text(good_manifest)
            state_path.write_text(good_state)
        self.assertEqual(failures, [], f"{len(failures)} crash(es):\n" + "\n".join(failures[:12]))


class ContractTests(Base):
    def test_validate_refuses_a_gate_id_used_twice_and_an_empty_id(self):
        """core-02 (validate side; the release-side refusal is package C's):
        two gates sharing one id mask each other in the gate log, and
        validate called such a manifest valid."""
        p = self.project()
        self.set_manifest(p, gates=[{"id": "checks", "kind": "command", "command": "false"},
                                    {"id": "checks", "kind": "command", "command": "true"},
                                    {"id": " ", "kind": "command", "command": "true"}])
        errs = contract.validate(p)
        self.assertTrue(any("checks" in e and "twice" in e for e in errs), errs)
        self.assertTrue(any("empty id" in e for e in errs), errs)
        code, out = self.run_cli("validate", "--project", p)
        self.assertEqual(code, 1, out)
        self.assertIn("twice", out)
        self.set_manifest(p, gates=[{"id": "checks", "kind": "command", "command": "false"},
                                    {"id": "lint", "kind": "command", "command": "true"}])
        self.assertEqual(contract.validate(p), [])

    def test_validate_names_reserved_keys_that_were_set_but_are_not_read(self):
        """core-18 (note only): privacy.share_lessons and paths.evidence are
        written into every manifest and read by nothing; a manifest that sets
        one away from its default was called valid without a word."""
        p = self.project()
        code, out = self.run_cli("validate", "--project", p)
        self.assertEqual((code, out.strip()), (0, "proj: contract v1 valid"))  # defaults: no extra line
        m = c.load_manifest(p)
        m["privacy"]["share_lessons"] = "none"
        m["paths"]["evidence"] = "proof/"
        self.set_manifest(p, privacy=m["privacy"], paths=m["paths"])
        code, out = self.run_cli("validate", "--project", p)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out.strip().splitlines()), 2, out)
        note = out.strip().splitlines()[1]
        self.assertTrue(note.startswith("note:"), note)
        for needle in ("privacy.share_lessons", "paths.evidence", "reserved"):
            self.assertIn(needle, note)
        self.assertEqual(contract.validate(p), [], "a note, not an error")

    def test_init_with_check_finishes_the_set_up_in_one_call(self):
        """e2e-trial-15: after init the lead ran validate twice and edited
        project.json by hand to fill the commands and the gate."""
        p = git_repo(self.ws / "fresh")
        (p / "README.md").write_text("# fresh\n")
        cmd = "python3 -m unittest discover -s tests -t ."
        code, out = self.run_cli("init", p, "--family", "software", "--title", "Fresh", "--check", cmd)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertIn("valid", out)
        self.assertIn("check", out)
        m = c.load_manifest(p)
        self.assertEqual((m["commands"]["check_fast"], m["commands"]["check_full"]), (cmd, cmd))
        self.assertEqual(m["gates"], [{"id": "checks", "kind": "command", "command": cmd}])
        self.assertEqual(contract.validate(p), [])
        before = snapshot(p)
        code, out = self.run_cli("init", p, "--family", "software", "--title", "Fresh", "--check", cmd)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing changed", out)
        self.assertEqual(snapshot(p), before, "running it twice changes nothing")

    def test_init_check_fills_an_existing_empty_command_and_never_replaces_one(self):
        """e2e-trial-15: the flag also finishes a project whose first init had
        no command, and it never overwrites a command that is already set."""
        p = self.project()
        code, out = self.run_cli("init", p, "--check", "make test")
        self.assertEqual(code, 0, out)
        self.assertEqual(c.load_manifest(p)["gates"][0]["command"], "make test")
        code, out = self.run_cli("init", p, "--check", "make other")
        self.assertEqual(code, 0, out)
        self.assertEqual(c.load_manifest(p)["gates"][0]["command"], "make test")
        self.assertIn("kept", out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)

    def test_init_check_refuses_a_command_that_holds_a_credential(self):
        """e2e-trial-15 with redteam-07: the command is stored in a committed
        file, so a key in it is refused before anything is written."""
        p = git_repo(self.ws / "fresh")
        code, out = self.run_cli("init", p, "--check", "curl -H 'Authorization: Bearer " + "a1B2" * 8 + "' https://example.invalid")
        self.assertEqual(code, 1, out)
        self.assertIn("refused", out)
        self.assertNotIn("a1B2", out)
        self.assertFalse((p / ".brain").exists())

    def test_adopt_and_init_refuse_the_brain_itself_and_folders_inside_it(self):
        """core-14 (1): `brain adopt <the brain>` installed a project contract
        in the brain, edited its CLAUDE.md past the size cap and broke doctor."""
        (self.brain / "CLAUDE.md").write_text("# the brain\n")
        inner = self.brain / "evals" / "thing"
        inner.mkdir(parents=True)
        (inner / "main.py").write_text("print(1)\n")
        before = snapshot(self.brain)
        for argv in (("adopt", self.brain), ("adopt", inner), ("init", self.brain), ("init", inner, "--force")):
            code, out = self.run_cli(*argv)
            self.assertEqual(code, 1, (argv, out))
            self.assertIn("brain itself", out)
            self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertEqual(snapshot(self.brain), before)
        code, out = self.run_cli("adopt", self.brain, "--survey")  # looking is always allowed
        self.assertEqual(code, 0, out)

    def test_adopt_says_what_it_did_to_an_existing_handbook(self):
        """core-14 (1): 'existing files untouched' was untrue: adopt puts a
        pointer block above an existing CLAUDE.md."""
        p = git_repo(self.ws / "legacy")
        (p / "CLAUDE.md").write_text("# Old handbook\nkeep me\n")
        (p / "main.py").write_text("print(1)\n")
        code, out = self.run_cli("adopt", p)
        self.assertEqual(code, 0, out)
        self.assertNotIn("untouched", out)
        self.assertIn("pointer block", out)
        self.assertTrue((p / "CLAUDE.md").read_text().endswith("# Old handbook\nkeep me\n"))

    def test_needs_you_template_gives_the_spanish_resolved_word_too(self):
        """owner-docs-05 (template side; reading RESUELTO is package A's): the
        owner writes Spanish, and the file told him only `RESOLVED:`."""
        p = self.project()
        text = (p / "NEEDS_YOU.md").read_text()
        self.assertIn("`RESOLVED:`", text)
        self.assertIn("`RESUELTO:`", text)
        self.assertLessEqual(len(contract.stub_text("T").encode()), contract.STUB_LIMIT)

    def test_migrate_writes_back_every_key_as_it_found_it(self):
        """core-06 follow-through: the manifest reader now leaves out
        wrong-typed parts; a migration must still write back the file's own
        content, not the reader's tidied copy."""
        p = self.project()
        self.set_manifest(p, contract=0, release="main-on-green", custom={"kept": True})
        mig = self.ws / "migs"
        mig.mkdir()
        (mig / "0_to_1.py").write_text("def migrate(project):\n    return []\n")
        code, msgs = contract.migrate(p, migrations_dir=mig)
        self.assertEqual(code, 0, msgs)
        m = json.loads((p / ".brain" / "project.json").read_text())
        self.assertEqual((m["contract"], m["release"], m["custom"]), (1, "main-on-green", {"kept": True}))


class ResolverTests(Base):
    def two(self):
        return self.project("shop"), self.project("shop-admin")

    def test_with_several_projects_every_command_says_so_and_names_them(self):
        """core-09, instructions-19: boot said 'several projects attached' and
        every later command answered 'no managed project found (attach one, or
        run: brain init <path>)'."""
        shop, admin = self.two()
        before = snapshot(self.ws)
        for argv in (("resume",), ("checkpoint", "--item", "x"), ("status",), ("handover",), ("req", "list"), ("gate",), ("validate",), ("migrate",)):
            code, out = self.run_cli(*argv)
            self.assertEqual(code, 1, (argv, out))
            self.assertEqual(len(out.strip().splitlines()), 1, out)
            for needle in ("2 projects attached", "shop", "shop-admin", "--project"):
                self.assertIn(needle, out, argv)
            self.assertNotIn("attach one", out)
            self.assertNotIn("no project found", out)
        self.assertEqual(snapshot(self.ws), before, "nothing is written while the project is not known")

    def test_project_takes_a_bare_folder_name_and_exact_wins_over_a_longer_match(self):
        """core-09: 'shop' also occurs in 'shop-admin'; the exact name must
        win, and a name that fits several or none is refused with the list."""
        shop, admin = self.two()
        code, out = self.run_cli("checkpoint", "--item", "T-1 in shop", "--project", "shop")
        self.assertEqual(code, 0, out)
        self.assertEqual(state.read_state(shop)["item"], "T-1 in shop")
        self.assertEqual(state.read_state(admin)["item"], "none")
        code, out = self.run_cli("checkpoint", "--item", "T-2 in admin", "--project", "admin")  # the only folder with 'admin' in it
        self.assertEqual(code, 0, out)
        self.assertEqual(state.read_state(admin)["item"], "T-2 in admin")
        code, out = self.run_cli("resume", "--project", "SHOP")
        self.assertEqual(code, 0, out)
        self.assertIn("T-1 in shop", out)
        for name in ("sho", "nosuch"):
            code, out = self.run_cli("resume", "--project", name)
            self.assertEqual(code, 1, out)
            self.assertEqual(len(out.strip().splitlines()), 1, out)
            self.assertIn(name, out)
            self.assertIn("shop-admin", out)
        self.assertEqual(c.resolve_project("shop"), shop)
        self.assertEqual(c.resolve_project(str(admin)), admin)

    def test_pick_named_is_the_one_rule_for_a_spoken_project_name(self):
        """core-09: one rule shared by --project and (once package A calls it)
        boot's --name: exact first, then a substring only when it is unique."""
        shop, admin = self.two()
        both = [shop, admin]
        self.assertEqual(c.pick_named("shop", both), [shop])
        self.assertEqual(c.pick_named("Shop-Admin", both), [admin])
        self.assertEqual(c.pick_named("admin", both), [admin])
        self.assertEqual(c.pick_named("sho", both), both)
        self.assertEqual(c.pick_named("nosuch", both), [])
        self.assertEqual(c.pick_named("  ", both), [])

    def test_environment_and_current_folder_still_choose_the_project(self):
        """core-09: the order stays --project, BRAIN_PROJECT, the folder the
        command is typed in, then the only managed project beside the brain."""
        shop, admin = self.two()
        os.environ["BRAIN_PROJECT"] = "shop-admin"
        self.assertEqual(c.resolve_project(), admin)
        self.assertEqual(c.resolve_project("shop"), shop, "--project beats the environment")
        os.environ.pop("BRAIN_PROJECT")
        (shop / "src").mkdir()
        os.chdir(shop / "src")
        self.assertEqual(c.resolve_project(), shop)
        os.chdir(self.brain)
        self.assertIsNone(c.resolve_project())
        shutil.rmtree(admin)
        self.assertEqual(c.resolve_project(), shop, "a single managed project needs no flag")

    def test_with_no_project_the_message_fits_what_is_attached(self):
        """core-09: in a brain-only session the advice was 'run: brain init
        <path>', which the brain refuses on itself; with an unmanaged
        repository beside the brain it did not name that folder."""
        code, out = self.run_cli("resume")
        self.assertEqual(code, 1, out)
        self.assertIn("no project attached (brain-only session)", out)
        self.assertNotIn("brain init", out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        repo = git_repo(self.ws / "newapp")
        (repo / "main.py").write_text("print(1)\n")
        code, out = self.run_cli("status")
        self.assertEqual(code, 1, out)
        self.assertIn("newapp", out)
        self.assertIn("brain adopt", out)
        code, out = self.run_cli("status", "--project", repo)
        self.assertEqual(code, 1, out)
        self.assertIn("newapp", out)
        self.assertIn("not a managed project", out)


class StaleBrainTests(Base):
    def stale(self, name="app") -> Path:
        p = self.project(name)
        state.checkpoint(p, item="T-1", stage="build")
        self.set_manifest(p, contract=c.CONTRACT_VERSION + 1)
        commit_all(p)
        return p

    def test_stale_brain_commands_write_nothing(self):
        """core-11: boot said 'write nothing to .brain/' and then checkpoint,
        status and boot itself wrote there."""
        p = self.stale()
        before = snapshot(p)
        self.assertEqual(detect.detect(self.brain)["mode"], "stale-brain")
        boot = detect.boot_lines("Continue with the list view", self.brain)
        self.assertIn("stale-brain", boot[0])
        self.assertEqual(snapshot(p), before, "boot wrote into a project with a newer contract")
        for argv in (("checkpoint", "--item", "x", "--note", "written by an old brain", "--push"), ("status",), ("handover",),
                     ("req", "add", "--quote", "it must work offline"), ("gate",), ("resume",), ("init", p), ("adopt", p)):
            extra = () if argv[0] in ("init", "adopt") else ("--project", p)
            code, out = self.run_cli(*argv, *extra)
            self.assertEqual(code, 3, (argv, out))
            self.assertEqual(len(out.strip().splitlines()), 1, out)
            self.assertTrue(out.startswith("stale brain"), out)
            self.assertIn("Update the brain", out)
            self.assertEqual(snapshot(p), before, argv)
        self.assertEqual(sh(p, "git", "status", "--porcelain").stdout, "")
        code, out = self.run_cli("validate", "--project", p)
        self.assertEqual(code, 3, out)
        self.assertIn("stale brain", out)

    def test_no_engine_write_reaches_a_project_with_a_newer_contract(self):
        """core-11: commands that do not pass through need_project (recall's
        log, the session marker, run logs, hire briefs) write through the same
        three helpers; those refuse too, so the rule holds for every module."""
        p = self.stale()
        before = snapshot(p)
        for write in (lambda: c.write_text(p / ".brain" / "log" / "x.txt", "x"),
                      lambda: c.write_json(p / ".brain" / "log" / "open-session.json", {"session": "s"}),
                      lambda: c.append_jsonl(p / ".brain" / "log" / "recall.jsonl", {"ids": []}),
                      lambda: c.write_jsonl(p / ".brain" / "requirements.jsonl", []),
                      lambda: c.write_text(p / "STATUS.md", "# Status\n"),
                      lambda: c.write_json(p / ".brain" / "project.json", {"contract": 1})):
            with self.assertRaises(c.StaleBrain):
                write()
        self.assertEqual(snapshot(p), before)
        self.assertTrue(issubclass(c.StaleBrain, OSError), "callers that already skip an unwritable log keep working")
        os.chdir(p)
        code, out = self.run_cli("run", "--", "true")  # typed inside the stale project: its log would go to .brain/log/run
        self.assertNotIn("Traceback", out)
        self.assertEqual(snapshot(p), before)
        other = self.project("other")  # a project on this brain's contract is written as before
        c.write_text(other / ".brain" / "log" / "x.txt", "x")
        c.append_jsonl(other / ".brain" / "log" / "y.jsonl", {"a": 1})
        self.assertEqual(c.stale_brain(other), "")

    def test_boot_with_a_stale_project_among_several_writes_nothing_to_it(self):
        """core-11: with several projects boot is in mode 'choose', which never
        looked at the contract version before marking the session open."""
        p = self.stale("app")
        self.project("zeta")
        os.environ["BRAIN_NOW"] = "2031-01-01T00:00:00Z"
        text = (p / ".brain" / "STATE.md").read_text().replace("updated: ", "updated: 2031-01-01T00:00:00Z was ")
        (p / ".brain" / "STATE.md").write_text(text)  # the stale one is the most recently active
        before = snapshot(p)
        lines = detect.boot_lines("Continue", self.brain)
        self.assertIn("app", "\n".join(lines))
        self.assertEqual(snapshot(p), before)


class SmallSlipTests(Base):
    """core-14: the slips that live in package B's files. The ones in
    engine/state.py (cost lines, 'unresolved', parallel checkpoints) are
    package A's."""

    def test_total_cap_is_enforced_when_each_part_is_within_its_cap(self):
        """core-14 (4): CLAUDE.md, the stub and every description can each sit
        just under its own cap while the sum passes the 3,200-token total of
        I-03; `brain budget` said nothing."""
        b = self.brain
        (b / "CLAUDE.md").write_text("x" * 5990)
        (b / "contract" / "template" / "CLAUDE.stub.md").write_text("y" * 1991)
        (b / ".claude" / "agents").mkdir(parents=True)
        for i in range(6):
            (b / ".claude" / "agents" / f"a{i}.md").write_text(f"---\nname: a{i}\ndescription: {'d' * 299}\nmodel: sonnet\neffort: low\ntools: Read\n---\nbody\n")
        for i in range(12):
            (b / ".claude" / "skills" / f"s{i:02d}").mkdir(parents=True)
            (b / ".claude" / "skills" / f"s{i:02d}" / "SKILL.md").write_text(f"---\nname: s{i:02d}\ndescription: {'d' * 299}\n---\nbody\n")
        errs, info = budget.check(b)
        self.assertGreater(info["always_loaded_tokens"], 3200)
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("3200", errs[0])
        self.assertIn("in total", errs[0])
        code, out = self.run_cli("budget")
        self.assertEqual(code, 1, out)
        self.assertEqual(budget.check(ROOT)[0], [], "the real brain is within the total")

    def test_a_broken_module_is_named_for_any_of_its_commands(self):
        """core-14 (5): with engine/state.py broken, `brain boot` answered
        "invalid choice: 'boot'" with no cause; only commands whose name
        contained the module's name were explained."""
        copy = self.ws / "broken-brain"
        shutil.copytree(ROOT / "bin", copy / "bin")
        shutil.copytree(ROOT / "engine", copy / "engine", ignore=shutil.ignore_patterns("__pycache__"))
        (copy / "engine" / "state.py").write_text("def broken(:\n")
        for cmd in ("boot", "checkpoint", "status", "release"):
            r = subprocess.run([sys.executable, str(copy / "bin" / "brain"), cmd], capture_output=True, text=True, cwd=str(self.ws))
            out = r.stdout + r.stderr
            self.assertEqual(r.returncode, 1, out)
            self.assertNotIn("invalid choice", out)
            self.assertNotIn("Traceback", out)
            for needle in (f"'{cmd}'", "state (SyntaxError", "brain doctor"):
                self.assertIn(needle, out)
            self.assertEqual(len(out.strip().splitlines()), 1, out)
        r = subprocess.run([sys.executable, str(copy / "bin" / "brain"), "budget"], capture_output=True, text=True, cwd=str(self.ws))
        self.assertNotIn("unavailable", r.stdout, "a command whose module loaded still runs")

    def test_written_files_respect_the_umask_and_keep_their_mode(self):
        """core-14 (6): every file the engine wrote was 0600 (the temp file's
        mode), and adopt turned a project's 0644 CLAUDE.md into 0600."""
        old = os.umask(0o022)
        self.addCleanup(os.umask, old)
        f = self.ws / "new.txt"
        c.write_text(f, "a")
        self.assertEqual(f.stat().st_mode & 0o777, 0o644)
        script = self.ws / "tool.sh"
        script.write_text("#!/bin/sh\n")
        script.chmod(0o755)
        c.write_text(script, "#!/bin/sh\necho hi\n")
        self.assertEqual(script.stat().st_mode & 0o777, 0o755)
        private = self.ws / "private.json"
        private.write_text("{}")
        private.chmod(0o600)
        c.write_json(private, {"a": 1})
        self.assertEqual(private.stat().st_mode & 0o777, 0o600)
        p = git_repo(self.ws / "legacy")
        (p / "CLAUDE.md").write_text("# Old handbook\n")
        (p / "CLAUDE.md").chmod(0o644)
        contract.adopt(p)
        self.assertEqual((p / "CLAUDE.md").stat().st_mode & 0o777, 0o644)
        self.assertEqual((p / ".brain" / "project.json").stat().st_mode & 0o777, 0o644)
        os.umask(0o077)
        g = self.ws / "tight.txt"
        c.write_text(g, "a")
        self.assertEqual(g.stat().st_mode & 0o777, 0o600)

    def test_a_leftover_temp_file_is_not_offered_to_git(self):
        """core-14 (6): an interrupted atomic write leaves `.tmp-*` beside the
        target; inside .brain/ the next checkpoint would have committed it."""
        p = self.project()
        commit_all(p)
        (p / ".brain" / ".tmp-abc123").write_text("half a file")
        (p / ".brain" / "log" / ".tmp-def456").write_text("half a file")
        self.assertEqual(sh(p, "git", "status", "--porcelain").stdout, "")

    def test_the_cache_prunes_itself(self):
        """core-14 (8): cache.prune had no caller outside the tests, so a
        project's .brain/cache only ever grew."""
        d = self.ws / "cache"
        os.environ["BRAIN_NOW"] = "2026-01-01T00:00:00Z"
        cache.put(cache.key("old"), 1, d)
        os.environ["BRAIN_NOW"] = "2026-01-20T00:00:00Z"
        cache.put(cache.key("mid"), 2, d)
        self.assertEqual(cache.get(cache.key("old"), d), 1, "19 days old: kept")
        os.environ["BRAIN_NOW"] = "2026-02-15T00:00:00Z"
        cache.put(cache.key("new"), 3, d)
        self.assertIsNone(cache.get(cache.key("old"), d), "45 days old: dropped by the put itself")
        self.assertEqual((cache.get(cache.key("mid"), d), cache.get(cache.key("new"), d)), (2, 3))
        # At most once a day, so a put stays one small write: an entry that
        # turns old during the day waits for the next day's first put.
        entry = d / cache.key("mid")[:2] / f"{cache.key('mid')}.json"
        entry.write_text(entry.read_text().replace("2026-01-20", "2025-12-01"))
        cache.put(cache.key("again"), 4, d)
        self.assertTrue(entry.is_file())
        os.environ["BRAIN_NOW"] = "2026-02-16T00:00:01Z"
        cache.put(cache.key("next-day"), 5, d)
        self.assertFalse(entry.is_file())


class DoctorProjectTests(Base):
    """core-19: `brain doctor` looked at the brain only; a project with no git
    identity, no remote or a broken contract was found by a later command
    failing with a raw git message."""

    def healthy(self, name="shop") -> Path:
        p = self.project(name)
        remote = self.ws / f"{name}-remote.git"
        sh(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(remote))
        sh(p, "git", "remote", "add", "origin", str(remote))
        commit_all(p)
        sh(p, "git", "push", "-q", "-u", "origin", "work")
        return p

    def test_a_healthy_project_is_one_ok_line(self):
        p = self.healthy()
        before = snapshot(p)
        code, out = self.run_cli("doctor", "--project", p)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertTrue(out.startswith("ok"), out)
        for needle in ("shop", "work"):
            self.assertIn(needle, out)
        self.assertEqual(snapshot(p), before, "a preflight only looks")
        code, out2 = self.run_cli("doctor", "--project")  # no value: the attached project
        self.assertEqual((code, out2), (0, out))

    def test_project_preflight_names_each_fault_and_its_fix(self):
        p = self.project("shop")
        commit_all(p)
        self.set_manifest(p, gates=[{"id": "checks", "kind": "command", "command": "true"},
                                    {"id": "checks", "kind": "command", "command": "false"}])
        sh(p, "git", "checkout", "-q", "--detach")
        sh(p, "git", "config", "--unset", "user.email")
        sh(p, "git", "config", "--unset", "user.name")
        sh(p, "git", "config", "user.useConfigOnly", "true")
        home = self.ws / "empty-home"
        home.mkdir()
        os.environ.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1", XDG_CONFIG_HOME=str(home))
        for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
            os.environ.pop(k, None)
        code, out = self.run_cli("doctor", "--project", "shop")
        lines = out.strip().splitlines()
        self.assertEqual(code, 1, out)
        self.assertLessEqual(len(lines), 8, out)
        self.assertTrue(all(l.startswith("FAIL ") for l in lines), out)
        for what, fix in (("identity", "git config"), ("remote", "remote add origin"), ("detached", "switch"), ("used twice", "own id")):
            hit = [l for l in lines if what in l]
            self.assertEqual(len(hit), 1, (what, out))
            self.assertIn(fix, hit[0])
            self.assertIn(": ", hit[0])

    def test_preflight_covers_the_release_branch_unpushed_work_and_damaged_files(self):
        p = self.healthy("app")
        self.set_manifest(p, release={"rule": "main-on-green", "branch": "work"})
        commit_all(p, "rule")
        code, out = self.run_cli("doctor", "--project", p)
        self.assertEqual(code, 1, out)
        self.assertIn("release branch", out)
        self.assertIn("switch -c", out)
        self.assertIn("not pushed", out)
        self.assertIn("brain release --push", out)  # on the release branch a checkpoint cannot push unreleased work
        self.set_manifest(p, release={"rule": "none", "branch": "main"})
        code, out = self.run_cli("doctor", "--project", p)
        self.assertEqual(code, 1, out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertIn("1 commit(s) on work are not pushed: run `brain checkpoint --push`", out)
        state_file = p / ".brain" / "STATE.md"
        state_file.write_text("<<<<<<< HEAD\n" + state_file.read_text() + "=======\n>>>>>>> other\n")
        code, out = self.run_cli("doctor", "--project", p)
        self.assertEqual(code, 1, out)
        self.assertIn("conflict markers", out)
        self.assertIn(".brain/STATE.md", out)
        state_file.write_bytes(b"# State\n\nstage: build\xff\n")
        code, out = self.run_cli("doctor", "--project", p)
        self.assertIn(".brain/STATE.md", out)
        self.assertIn("checkout -- .brain/STATE.md", out)
        plain = self.project("plain", git=False)
        code, out = self.run_cli("doctor", "--project", plain)
        self.assertEqual(code, 1, out)
        self.assertIn("not a git repository", out)
        self.assertIn("init -b work", out)

    def test_preflight_says_which_project_when_it_cannot_tell(self):
        self.project("shop")
        self.project("shop-admin")
        code, out = self.run_cli("doctor", "--project")
        self.assertEqual(code, 1, out)
        self.assertIn("2 projects attached", out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)

    def test_plain_doctor_stays_as_it_is(self):
        r = subprocess.run([sys.executable, str(ROOT / "bin" / "brain"), "doctor"], capture_output=True, text=True, cwd=str(self.ws),
                           env={**os.environ, "BRAIN_NO_NETWORK": "1"})
        lines = r.stdout.strip().splitlines()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([l.split(":")[0] for l in lines[:-1]],
                         ["ok   python", "ok   full-text search", "ok   engine modules", "ok   version file", "ok   model facts",
                          "ok   memory items", "ok   always-loaded budget", "ok   contract template"])
        self.assertEqual(lines[-1], "brain is healthy")


if __name__ == "__main__":
    unittest.main()
