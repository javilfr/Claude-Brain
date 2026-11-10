"""Every frozen fixture must still open, validate and migrate with this brain.

This is what "a project keeps working with the brain" means in practice.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import common as c, contract, detect, state  # noqa: E402

FIX = ROOT / "evals" / "fixtures"


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.brain = self.ws / "Claude-Brain"
        (self.brain / "memory").mkdir(parents=True)
        c.write_json(self.brain / "memory" / "models.json", {"verified_on": c.today(), "recheck_days": 90})

    def tearDown(self):
        self._tmp.cleanup()

    def place(self, name: str) -> Path:
        dst = self.ws / name
        shutil.copytree(FIX / name, dst)
        (dst / ".git").mkdir()  # fixtures are stored without git data
        return dst

    def test_every_managed_fixture_validates_and_migrates_twice(self):
        managed = sorted(p for p in FIX.iterdir() if (p / ".brain" / "project.json").is_file())
        self.assertTrue(managed, "at least one managed fixture must exist")
        for src in managed:
            p = self.place(src.name)
            self.assertEqual(contract.validate(p, ROOT), [], src.name)
            for _ in range(2):
                code, msgs = contract.migrate(p)
                self.assertEqual(code, 0, (src.name, msgs))
            self.assertEqual(c.load_manifest(p)["contract"], c.CONTRACT_VERSION)
            self.assertEqual(contract.validate(p, ROOT), [], src.name)
            shutil.rmtree(p)

    def test_v1_fixture_resumes_where_it_stopped(self):
        p = self.place("project-v1")
        self.assertEqual(detect.detect(self.brain)["mode"], "work")
        st = state.read_state(p)
        self.assertEqual(st["item"], "S-2 draft section two")
        self.assertEqual(st["last_done"], "S-1 outline")
        blob = "\n".join(detect.boot_lines(None, self.brain))
        self.assertIn("S-2 draft section two", blob)
        self.assertIn("requirements: 0/1 done", blob)

    def test_unmanaged_fixture_is_adopted_without_changing_its_files(self):
        p = self.place("unmanaged-app")
        self.assertEqual(detect.detect(self.brain)["mode"], "adopt")
        before = {f.relative_to(p): f.read_bytes() for f in p.rglob("*") if f.is_file()}
        contract.adopt(p)
        for rel, data in before.items():
            if rel.name == "CLAUDE.md":
                self.assertIn("Project rules written before the brain.", (p / rel).read_text())
            else:
                self.assertEqual((p / rel).read_bytes(), data)
        self.assertEqual(contract.validate(p, ROOT), [])
        self.assertEqual(detect.detect(self.brain)["mode"], "work")

    def test_empty_fixture_is_bootstrap(self):
        self.place("empty")
        self.assertEqual(detect.detect(self.brain)["mode"], "bootstrap")


if __name__ == "__main__":
    unittest.main()
