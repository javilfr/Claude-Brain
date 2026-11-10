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

from engine import common as c, contract, detect, gate, state  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
