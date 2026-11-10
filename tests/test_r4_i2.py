"""Package I2 of the 2026-11-10 improvement plan: HR settling, pay, briefs,
audit and staffing.

Each test names the finding(s) it pins (docs/review/2026-11-10-audit/<area>.json).
Every test works in a temporary folder with a stand-in brain; the shared temp
folder is redirected into it and no project beside the real brain can be
reached, so nothing here leaves a contract, a seal or a run log behind.
"""
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import common as c, hr, mlearn  # noqa: E402

_CLI = None
_TREE = None


def cli():
    """bin/brain loaded once as a module, so commands run in this process."""
    global _CLI, _TREE
    if _CLI is None:
        loader = importlib.machinery.SourceFileLoader("brain_cli_r4i2", str(ROOT / "bin" / "brain"))
        spec = importlib.util.spec_from_loader("brain_cli_r4i2", loader)
        _CLI = importlib.util.module_from_spec(spec)
        loader.exec_module(_CLI)
        _TREE = _CLI.build()
    return _CLI


def tpl(tid, **over):
    t = {
        "id": tid, "name": "Phone Screen Builder", "group": "build", "base_agent": "builder", "families": ["software"],
        "when": "A phone-first screen or component must be built from a spec or screenshot.",
        "keywords": ["screen", "phone", "mobile", "component", "layout", "pantalla"],
        "role_line": "Builds phone-first screens from a spec and proves them at phone size.",
        "method": ["Build at a 390 pixel wide viewport first, because that is where the owner reviews.",
                   "Use the project's design tokens for colour and spacing so the screen matches the rest.",
                   "Capture a screenshot at phone size as evidence, since tests miss what the eye catches."],
        "drift": "Default: a generic centred card layout. Instead: follow the spec's layout and the platform's own patterns.",
        "scope_rule": "Change only the files you own; at the edge, report what else needs changing instead of changing it.",
        "done_check": "{check} passes and a phone-size screenshot shows the screen as specified.",
        "return_contract": "First line: done or not done. Then files changed, the check's last line, the screenshot path. At most 150 words.",
        "pitfalls": ["Layout that only works on a desktop viewport."],
        "needs": ["the spec or screenshot", "the acceptance command"],
        "size": "M", "risk": "standard", "sources": ["docs/research/round3/04-domain-methods.md area 1"], "version": 1, "status": "active",
    }
    t.update(over)
    return t


REVIEWER = dict(name="Code Reviewer", group="review", base_agent="reviewer",
                when="A diff or branch must be reviewed for defects before merge or release.",
                keywords=["review", "diff", "pull request", "merge", "defects", "revisar"],
                role_line="Reviews a diff against its requirements and reports every finding with evidence.",
                scope_rule="Read-only: report findings with file and line; the author makes the changes.", risk="high")
RESEARCHER = dict(name="Deep Researcher", group="discovery", base_agent="researcher", families=["knowledge"],
                  when="A question must be answered from cited sources.",
                  keywords=["research", "sources", "cited", "question", "investigar", "memo"],
                  role_line="Answers one question from primary sources and cites each claim.",
                  scope_rule="Read-only apart from the memo: write the memo and nothing else, so the project stays as it was.",
                  done_check="Every key claim has a fetched URL and a quoted passage; {check} passes.",
                  return_contract="First line: the answer and a confidence. Then the findings with sources. At most 200 words.")


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name).resolve()
        self.b = self.ws / "Claude-Brain"
        (self.b / "hr" / "rack").mkdir(parents=True)
        (self.b / "memory").mkdir()
        (self.b / "evals").mkdir()
        shutil.copy(ROOT / "hr" / "template.schema.json", self.b / "hr" / "template.schema.json")
        shutil.copy(ROOT / "memory" / "models.json", self.b / "memory" / "models.json")
        shutil.copy(ROOT / "memory" / "ml_config.json", self.b / "memory" / "ml_config.json")
        self.schema = c.read_json(self.b / "hr" / "template.schema.json")
        self.models = c.read_json(self.b / "memory" / "models.json")
        self.rack = [tpl("phone-ui-builder"), tpl("code-reviewer", **REVIEWER), tpl("deep-researcher", **RESEARCHER)]
        c.write_jsonl(self.b / "hr" / "rack" / "all.jsonl", self.rack)
        env = mock.patch.dict(os.environ, {"BRAIN_SESSION_ID": "sess-i2", "TMPDIR": str(self.ws / "tmp")})
        env.start()
        self.addCleanup(env.stop)
        for k in ("BRAIN_PROJECT", "CLAUDE_CODE_SESSION_ID", "BRAIN_TRANSCRIPT", "BRAIN_NOW"):
            os.environ.pop(k, None)
        (self.ws / "tmp").mkdir()
        tempfile.tempdir = None                      # the next gettempdir() reads TMPDIR again
        self.addCleanup(setattr, tempfile, "tempdir", None)
        # "No project" must hold wherever the tests run: a managed project
        # beside the real brain would otherwise receive contracts.
        stub = mock.patch.object(c, "sibling_dirs", lambda *_a, **_k: [])
        stub.start()
        self.addCleanup(stub.stop)

    def project(self, name="proj") -> Path:
        p = self.ws / name
        (p / ".brain" / "log").mkdir(parents=True)
        c.write_json(p / ".brain" / "project.json", {"contract": 1, "family": "software", "project": {"id": "secret-proj", "title": "Secret Proj"}})
        return p

    def transcript(self, name: str, prompt: str, out_tokens: int, model: str = "claude-sonnet-5-5", effort: str = "medium") -> Path:
        p = self.ws / f"agent-{name}.jsonl"
        rows = [
            {"type": "user", "timestamp": "2026-11-10T10:00:00Z", "message": {"role": "user", "content": prompt}},
            {"type": "assistant", "timestamp": "2026-11-10T10:01:00Z", "effort": effort,
             "message": {"id": f"m-{name}", "model": model, "role": "assistant",
                         "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": out_tokens}}},
        ]
        p.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return p

    def helper(self, cid: str, out_tokens: int, name: str | None = None, **kw) -> Path:
        """A helper transcript started with the delegation line `hr hire` prints."""
        return self.transcript(name or cid, f"Follow the brief at /x/{cid}.md (contract {cid}).", out_tokens, **kw)

    def hire(self, task="Build the settings screen for the phone", project=None, **kw):
        return hr.hire(task, brain_root=self.b, project=project, **kw)

    def cpath(self, project: Path, con: dict) -> Path:
        return project / ".brain" / "log" / "hr" / f"{con['id']}.json"

    def inbox(self) -> list[dict]:
        return [r for f in sorted((self.b / "learning" / "inbox").glob("*.jsonl")) for r in c.read_jsonl(f)]

    def run_cli(self, *argv):
        buf = io.StringIO()
        with mock.patch.object(c, "BRAIN_ROOT", self.b), redirect_stdout(buf):
            code = cli().main(list(argv), _TREE)
        return code, buf.getvalue()


# ---------------------------------------------------------------- isolation
class Isolation(Base):
    def run_old(self, name: str):
        from tests import test_hr
        suite = unittest.defaultTestLoader.loadTestsFromName(name, test_hr)
        result = unittest.TestResult()
        suite.run(result)
        return result

    def test_hr_tests_cannot_write_into_a_project_beside_the_brain(self):
        """ml-planning-07, templates-a-30: with a managed project beside the
        brain, the old HR tests wrote eight contracts into it and failed on the
        second run."""
        app = self.project("app")
        with mock.patch.object(c, "sibling_dirs", lambda *_a, **_k: [app]):
            for _ in range(2):
                r = self.run_old("ReviewFindings.test_cap_counts_this_sessions_contracts_with_or_without_a_project")
                self.assertTrue(r.wasSuccessful(), r.failures + r.errors)
        self.assertFalse((app / ".brain" / "log" / "hr").exists(), "contracts were written into the neighbour project")

    def test_running_the_hr_tests_leaves_nothing_in_the_shared_temp_folder(self):
        """hr-14: the old tests left hundreds of seal files in the machine's temp folder."""
        shared = self.ws / "shared-tmp"
        shared.mkdir()
        with mock.patch.dict(os.environ, {"TMPDIR": str(shared)}):
            tempfile.tempdir = None
            try:
                r = self.run_old("Contracts.test_hire_writes_contract_and_brief_and_settle_records_real_use")
                r2 = self.run_old("ReviewFindings.test_small_things_the_review_listed")
            finally:
                tempfile.tempdir = None
        self.assertTrue(r.wasSuccessful() and r2.wasSuccessful(), r.failures + r.errors + r2.failures + r2.errors)
        self.assertEqual(sorted(p.name for p in shared.iterdir()), [])


# ---------------------------------------------------------------- settling
class Settling(Base):
    def test_a_hire_nobody_worked_does_not_move_the_templates_record(self):
        """e2e-trial-07: the lead did the work itself, settle ran the check, and
        the template earned a pass for it."""
        p = self.project()
        con = self.hire(project=p, check="true")
        done = hr.settle(self.cpath(p, con), brain_root=self.b, project=p, sub_paths=[])
        self.assertIs(done["helper_seen"], False)
        state = {}
        for r in self.inbox():
            self.assertIs(r["helper_seen"], False)
            hr.fold_hire(state, {"hr": {}}, r)
        self.assertEqual(hr.hr_state(state)["t"], {})
        self.assertEqual(hr.hr_state(state)["g"], {})

    def test_a_worked_hire_still_counts(self):
        """e2e-trial-07, the other side: with a helper transcript the result counts as before."""
        p = self.project()
        con = self.hire(project=p, check="python3 -c 'import sys; sys.exit(0)'")
        done = hr.settle(self.cpath(p, con), brain_root=self.b, project=p, sub_paths=[self.helper(con["id"], 1000)])
        self.assertIs(done["helper_seen"], True)
        state = {}
        hr.fold_hire(state, {"hr": {}}, self.inbox()[0])
        self.assertEqual(hr.hr_state(state)["t"]["phone-ui-builder"][2], 1)

    def test_a_record_without_the_field_folds_as_it_always_did(self):
        """e2e-trial-07: records written before this change carry no helper_seen
        and must fold to the same numbers, or the replay check breaks."""
        state = {}
        hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "g", "passed": True, "sealed": True})
        self.assertEqual(hr.hr_state(state)["t"]["t"], [1.0, 0.0, 1])

    def test_close_drops_a_brief_that_was_never_delegated(self):
        """instructions-09: a brief written and never delegated was settled by
        close as a failed hire against its template."""
        p = self.project()
        con = self.hire(project=p, check="test -f never-made.txt")
        line = hr.settle_open(p, brain_root=self.b, sub_paths=[])
        self.assertIn("1 brief never delegated", line)
        self.assertIn("dropped", line)
        self.assertEqual(self.inbox(), [])
        self.assertEqual(c.read_json(self.cpath(p, con))["status"], "unused")
        self.assertEqual(hr.open_contracts(p), [])
        self.assertEqual(len(line.splitlines()), 1)

    def test_close_reports_used_and_unused_briefs_in_one_line(self):
        """instructions-09: one line, whatever the mix."""
        p = self.project()
        used = self.hire(project=p, check="true")
        self.hire("Review the diff of this branch before merge", project=p, check="true")
        line = hr.settle_open(p, brain_root=self.b, sub_paths=[self.helper(used["id"], 500)])
        self.assertIn("1 of 1 contract(s) settled", line)
        self.assertIn("1 brief never delegated", line)
        self.assertEqual(len(line.splitlines()), 1)

    def test_a_settled_failure_is_not_shown_as_run_again_and_retry_records_the_second_result(self):
        """e2e-trial-07: a second settle printed the same CHECK FAILED line as
        if it had run again; a retry had nowhere to be recorded."""
        p = self.project()
        con = self.hire(project=p, check="test -f done.txt")
        t = self.helper(con["id"], 800)
        with mock.patch.object(c, "transcript_paths", lambda *_a, **_k: (None, [t])):
            code, out = self.run_cli("hr", "settle", con["id"], "--project", str(p))
            self.assertEqual(code, 1)
            self.assertIn("CHECK FAILED", out)
            (p / "done.txt").write_text("x")
            code, out = self.run_cli("hr", "settle", con["id"], "--project", str(p))
            self.assertEqual(code, 1)
            self.assertIn("not re-run", out)
            self.assertIn("--retry", out)
            self.assertNotIn("CHECK FAILED", out)
            code, out = self.run_cli("hr", "settle", con["id"], "--project", str(p), "--retry")
            self.assertEqual(code, 0, out)
            again = self.run_cli("hr", "settle", con["id"], "--project", str(p), "--retry")
        final = c.read_json(self.cpath(p, con))
        self.assertIs(final["passed"], False)               # the first result is the one the template is judged on
        self.assertIs(final["passed_after_retry"], True)
        self.assertEqual(len(self.inbox()), 1)
        self.assertIs(self.inbox()[0]["passed"], False)
        self.assertEqual(again[0], 1)                       # one retry, as the build skill says
        self.assertIn("already", again[1])

    def test_abandon_without_an_id_names_the_open_contracts(self):
        """instructions-09: 'name an existing contract to abandon' gave no next step."""
        p = self.project()
        con = self.hire(project=p, check="true")
        code, out = self.run_cli("hr", "settle", "--abandon", "--project", str(p))
        self.assertEqual(code, 1)
        self.assertIn(con["id"], out)
        self.assertIn("--abandon", out)

    def test_settle_sums_every_run_of_the_helper(self):
        """hr-02: the same brief delegated twice was credited with the first run only."""
        p = self.project()
        con = self.hire(project=p, check="true")
        subs = [self.helper(con["id"], 30000, name="first"), self.helper(con["id"], 50000, name="second")]
        done = hr.settle(self.cpath(p, con), brain_root=self.b, project=p, sub_paths=subs)
        self.assertEqual((done["actual_tokens"], done["runs"]), (80000, 2))
        self.assertEqual(self.inbox()[0]["runs"], 2)

    def test_a_reviewer_naming_the_contract_is_not_the_helper(self):
        """hr-02: any transcript that mentioned the id matched, so a reviewer of
        the work was taken for the builder."""
        p = self.project()
        con = self.hire(project=p, check="true")
        reviewer = self.transcript("a-reviewer", f"Review the work delivered under contract {con['id']}; its brief was {con['brief']}.", 7000)
        builder = self.helper(con["id"], 44000, name="z-builder")
        done = hr.settle(self.cpath(p, con), brain_root=self.b, project=p, sub_paths=[reviewer, builder])
        self.assertEqual((done["actual_tokens"], done["runs"]), (44000, 1))

    def test_suffixed_contract_id_does_not_match_its_base(self):
        """hr-02: h-…-abc123 and h-…-abc123-2 are two contracts."""
        con = {"id": "h-20261110-abc123", "wage_tokens": 1}
        other = self.helper("h-20261110-abc123-2", 9000)
        self.assertIsNone(hr.find_helper_usage(con, [other], self.models))
        mine = self.helper("h-20261110-abc123", 100, name="mine")
        self.assertEqual(hr.find_helper_usage(con, [other, mine], self.models)["out_tokens"], 100)

    def test_record_names_the_model_and_effort_that_ran(self):
        """hr-02: the record stored the planned model and effort, whatever ran."""
        p = self.project()
        con = self.hire(project=p, check="true")
        self.assertEqual((con["model"], con["effort"]), ("sonnet", "medium"))
        t = self.helper(con["id"], 1000, model="claude-opus-5-5", effort="high")
        with mock.patch.object(c, "transcript_paths", lambda *_a, **_k: (None, [t])):
            code, out = self.run_cli("hr", "settle", con["id"], "--project", str(p))
        rec = self.inbox()[0]
        self.assertEqual((rec["ran_model"], rec["ran_effort"]), ("opus", "high"))
        self.assertEqual((rec["model"], rec["effort"]), ("sonnet", "medium"))   # the arm that was chosen stays on the record
        self.assertIn("ran on opus/high", out)
        self.assertEqual(len(out.strip().splitlines()), 1)

    def test_close_runs_a_shared_check_once(self):
        """hr-08: three contracts with one acceptance command ran it three times."""
        p = self.project()
        check = "echo run >> runs.txt"
        cons = [self.hire(f"Build screen number {i} for the phone layout", project=p, check=check) for i in range(3)]
        subs = [self.helper(con["id"], 100) for con in cons]
        line = hr.settle_open(p, brain_root=self.b, sub_paths=subs)
        self.assertIn("3 of 3 contract(s) settled", line)
        self.assertEqual((p / "runs.txt").read_text().splitlines(), ["run"])
        self.assertEqual([c.read_json(self.cpath(p, con))["check_exit"] for con in cons], [0, 0, 0])

    def test_a_slow_check_times_out_at_settle_and_records_no_result(self):
        """hr-08: settle ran a check with a one-hour limit; the limit now comes from the HR config."""
        cfgfile = self.b / "memory" / "ml_config.json"
        data = c.read_json(cfgfile)
        data["hr"] = {"settle_timeout": 1}
        c.write_json(cfgfile, data)
        p = self.project()
        con = self.hire(project=p, check="sleep 5")
        done = hr.settle(self.cpath(p, con), brain_root=self.b, project=p, sub_paths=[self.helper(con["id"], 100)])
        self.assertIsNone(done["passed"])
        self.assertEqual(done["check_timed_out"], 1)
        self.assertIsNone(self.inbox()[0]["passed"])
        self.assertEqual(hr.cfg_of(ROOT).get("settle_timeout", hr.DEFAULT_CFG.get("settle_timeout")), 600)

    def test_a_rewritten_template_starts_with_a_clean_record(self):
        """hr-11: version 2 of a template inherited version 1's record and started on probation."""
        state, cfg = {}, {"hr": {}}
        for _ in range(6):
            hr.fold_hire(state, cfg, {"template": "game-builder", "template_version": 1, "group": "build", "passed": False, "sealed": True})
        h = hr.hr_state(state)
        self.assertTrue(hr.on_probation(h, hr.DEFAULT_CFG, "game-builder", "build"))
        self.assertTrue(hr.on_probation(h, hr.DEFAULT_CFG, "game-builder", "build", version=1))
        self.assertFalse(hr.on_probation(h, hr.DEFAULT_CFG, "game-builder", "build", version=2))
        self.assertEqual(hr.pass_posterior(h, hr.DEFAULT_CFG, "game-builder", "build", version=2)[2], 0)
        self.assertEqual(hr.performance_multiplier(h, hr.DEFAULT_CFG, "game-builder", "build", version=2), 1.0)
        for _ in range(3):
            hr.fold_hire(state, cfg, {"template": "game-builder", "template_version": 2, "group": "build", "passed": True, "sealed": True})
        self.assertEqual(hr.pass_posterior(h, hr.DEFAULT_CFG, "game-builder", "build", version=2)[2], 3)
        self.assertEqual(hr.pass_posterior(h, hr.DEFAULT_CFG, "game-builder", "build", version=1)[2], 6)

    def test_old_records_and_version_one_share_one_record(self):
        """hr-11: records written before the version was stored belong to version 1 and still fold."""
        state, cfg = {}, {"hr": {}}
        hr.fold_hire(state, cfg, {"template": "t", "group": "g", "passed": True, "sealed": True})
        hr.fold_hire(state, cfg, {"template": "t", "template_version": 1, "group": "g", "passed": True, "sealed": True})
        self.assertEqual(hr.hr_state(state)["t"]["t"][2], 2)
        self.assertEqual(list(hr.hr_state(state)["t"]), ["t"])

    def test_settle_puts_the_template_version_on_the_contract_and_the_record(self):
        """hr-11: the contract and the hire record never said which wording was hired."""
        rack = [tpl("phone-ui-builder", version=3)] + self.rack[1:]
        c.write_jsonl(self.b / "hr" / "rack" / "all.jsonl", rack)
        p = self.project()
        con = self.hire(project=p, check="true")
        done = hr.settle(self.cpath(p, con), brain_root=self.b, project=p, sub_paths=[self.helper(con["id"], 100)])
        self.assertEqual(done["template_version"], 3)
        rec = self.inbox()[0]
        self.assertEqual(rec["template_version"], 3)
        state = mlearn.fold(mlearn.empty_state(), [rec], mlearn.config(self.b))
        self.assertEqual(list(hr.hr_state(state)["t"]), ["phone-ui-builder@3"])

    def test_report_keeps_an_earlier_versions_line(self):
        """hr-11: the old wording's totals stay visible as history."""
        rack = [tpl("phone-ui-builder", version=2)] + self.rack[1:]
        c.write_jsonl(self.b / "hr" / "rack" / "all.jsonl", rack)
        state = mlearn.empty_state()
        for _ in range(6):
            hr.fold_hire(state, {"hr": {}}, {"template": "phone-ui-builder", "template_version": 1, "group": "build", "passed": False, "sealed": True})
        with mock.patch.object(mlearn, "load", lambda *_a, **_k: state):
            lines = hr.report_lines(self.b)
        old = [l for l in lines if l.startswith("phone-ui-builder")]
        self.assertEqual(len(old), 1, lines)
        self.assertIn("earlier wording", old[0])
        self.assertFalse(any("ON PROBATION" in l for l in lines), lines)

    def test_check_kinds(self):
        """hr-17: 'true', 'test -s file' and a full test suite all counted as the same pass."""
        cases = {
            "": "none", "   ": "none",
            "true": "structural", "test -s research/api.md": "structural", "[ -f out.txt ] && grep -q END out.txt": "structural",
            "ls docs/memo.md": "structural", "wc -l data.csv": "structural", "test -f a; test -f b || true": "structural",
            "python3 -m unittest discover -s tests -t .": "behavioural", "npm test": "behavioural",
            "test -f a && python3 check.py": "behavioural", "grep -c END out.txt": "behavioural", "make check": "behavioural",
            "test -f \"$(./build.sh)\"": "behavioural",
        }
        for cmd, kind in cases.items():
            self.assertEqual(hr.check_kind(cmd), kind, cmd)

    def test_a_structural_pass_moves_the_record_less_than_a_behavioural_one(self):
        """hr-17: only a behavioural pass counts at full weight; the kind is stored with the record."""
        p = self.project()
        con = self.hire(project=p, check="test -d .brain")
        hr.settle(self.cpath(p, con), brain_root=self.b, project=p, sub_paths=[self.helper(con["id"], 30000)])
        rec = self.inbox()[0]
        self.assertEqual(rec["check_kind"], "structural")
        weak, strong, failed = {}, {}, {}
        hr.fold_hire(weak, {"hr": {}}, rec)
        hr.fold_hire(strong, {"hr": {}}, dict(rec, check_kind="behavioural"))
        hr.fold_hire(failed, {"hr": {}}, dict(rec, passed=False))
        w, s, f = (hr.hr_state(x)["t"]["phone-ui-builder"] for x in (weak, strong, failed))
        self.assertEqual(s, [1.0, 0.0, 1])
        self.assertTrue(0.0 < w[0] < 1.0 and w[1] == 0.0 and w[2] == 1, w)
        self.assertEqual(f, [0.0, 1.0, 1])                              # failing even a weak check is a full failure
        self.assertEqual(hr.hr_state(weak)["ratios"]["t:phone-ui-builder"], [0.5])   # the wage ratio is recorded either way

    def test_the_seal_is_removed_once_the_contract_is_finished(self):
        """hr-14: seals were never deleted."""
        p = self.project()
        a = self.hire(project=p, check="true")
        self.assertTrue(hr.seal_path(a["id"]).is_file())
        hr.settle(self.cpath(p, a), brain_root=self.b, project=p, sub_paths=[self.helper(a["id"], 10)])
        self.assertFalse(hr.seal_path(a["id"]).exists())
        b = self.hire("Review the diff of this branch before merge", project=p, check="true")
        self.run_cli("hr", "settle", b["id"], "--abandon", "--project", str(p))
        self.assertFalse(hr.seal_path(b["id"]).exists())
        d = self.hire("Build the other settings screen for the phone", project=p, check="true")
        hr.settle_open(p, brain_root=self.b, sub_paths=[])
        self.assertFalse(hr.seal_path(d["id"]).exists())

    def test_the_seal_is_described_as_a_guard_against_accidents(self):
        """hr-14: the seal was described as proof; whoever can read the contract can rewrite it."""
        doc = " ".join((hr.seal_path.__doc__ or "").split())
        self.assertIn("accidental", doc)
        self.assertIn("not against a helper that sets out to cheat", doc)

    def test_settle_says_when_several_projects_are_attached_and_none_was_named(self):
        """Package B's note to I: with several projects attached and no --project,
        settle looked in the temp folder and said nothing."""
        a, b = self.project("alpha"), self.project("beta")
        with mock.patch.object(c, "sibling_dirs", lambda *_a, **_k: [a, b]):
            code, out = self.run_cli("hr", "settle")
        self.assertIn("2 projects attached", out)
        self.assertIn("--project", out)


if __name__ == "__main__":
    unittest.main()
