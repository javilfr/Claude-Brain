"""HR: template rack rules, selection, wage, brief, contract, settlement, learning."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import common as c, hr, mlearn  # noqa: E402


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


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.b = Path(self._tmp.name) / "Claude-Brain"
        (self.b / "hr" / "rack").mkdir(parents=True)
        (self.b / "memory").mkdir()
        (self.b / "evals").mkdir()
        shutil.copy(ROOT / "hr" / "template.schema.json", self.b / "hr" / "template.schema.json")
        shutil.copy(ROOT / "memory" / "models.json", self.b / "memory" / "models.json")
        shutil.copy(ROOT / "memory" / "ml_config.json", self.b / "memory" / "ml_config.json")
        self.schema = c.read_json(self.b / "hr" / "template.schema.json")
        self.rack = [
            tpl("phone-ui-builder"),
            tpl("es-en-translator", name="Spanish English Translator", group="language", base_agent="writer", families=["language"],
                when="Text must be translated between Spanish and English for publication.",
                keywords=["translate", "translation", "spanish", "english", "traducir", "traduccion", "castellano"],
                role_line="Translates between Spanish from Spain and English and proves fidelity.", size="S"),
            tpl("code-reviewer", name="Code Reviewer", group="review", base_agent="reviewer",
                when="A diff or branch must be reviewed for defects before merge or release.",
                keywords=["review", "diff", "pull request", "merge", "defects", "revisar"],
                role_line="Reviews a diff against its requirements and reports every finding with evidence.",
                scope_rule="Read-only: report findings with file and line; the author makes the changes.", risk="high"),
        ]
        c.write_jsonl(self.b / "hr" / "rack" / "all.jsonl", self.rack)
        self._env = dict(os.environ)
        os.environ.pop("BRAIN_PROJECT", None)
        os.environ["BRAIN_SESSION_ID"] = "sess-hr"
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    def project(self) -> Path:
        p = Path(self._tmp.name) / "proj"
        (p / ".brain" / "log").mkdir(parents=True)
        c.write_json(p / ".brain" / "project.json", {"contract": 1, "family": "software", "project": {"id": "secret-proj", "title": "Secret Proj"}})
        return p


class RackRules(Base):
    def test_valid_template_passes(self):
        self.assertEqual(hr.validate_template(self.rack[0], self.schema), [])

    def test_each_writing_rule_is_enforced(self):
        cases = {
            "persona": tpl("x-persona", role_line="You are an expert senior engineer who builds screens."),
            "think": tpl("x-think", method=["Think step by step before writing any code, because it helps.", "b because c.", "d because e."]),
            "budget": tpl("x-budget", return_contract="Use at most 5,000 tokens. At most 100 words."),
            "absolute rule has no reason": tpl("x-abs", scope_rule="Never touch other files."),
            "words (limit": tpl("x-long", role_line=" ".join(["word"] * 30)),
            "missing 'done_check'": {k: v for k, v in tpl("x-miss").items() if k != "done_check"},
            "is not one of": tpl("x-agent", base_agent="wizard"),
            "does not match": tpl("Bad_ID"),
        }
        for needle, t in cases.items():
            errs = " | ".join(hr.validate_template(t, self.schema))
            self.assertIn(needle, errs, t["id"])

    def test_audit_requires_exactly_one_hundred_unique_templates(self):
        errs, info = hr.audit(self.b)
        self.assertEqual(info["templates"], 3)
        self.assertTrue(any("exactly 100" in e for e in errs))
        c.write_jsonl(self.b / "hr" / "rack" / "dup.jsonl", [self.rack[0]])
        self.assertTrue(any("duplicate id" in e for e in hr.audit(self.b)[0]))

    def test_rack_naming_a_project_is_refused(self):
        (self.b / "evals" / "known_project_ids.txt").write_text("acme-shop\n")
        c.write_jsonl(self.b / "hr" / "rack" / "all.jsonl", [tpl("phone-ui-builder", when="Build screens like the ones in acme-shop for phones.")])
        self.assertTrue(any("names a project" in e for e in hr.audit(self.b)[0]))


class Selection(Base):
    def test_best_lexical_fit_wins_in_either_language(self):
        self.assertEqual(hr.select("Build the settings screen for the phone layout", self.rack)[0]["id"], "phone-ui-builder")
        self.assertEqual(hr.select("Traducir la página de inicio al castellano", self.rack)[0]["id"], "es-en-translator")
        self.assertEqual(hr.select("Review the diff of this branch before merge", self.rack)[0]["id"], "code-reviewer")

    def test_nothing_fits_returns_empty(self):
        self.assertEqual(hr.select("Calibrate the telescope mount firmware", self.rack), [])

    def test_a_bad_record_lowers_rank_and_probation_is_flagged(self):
        twin = tpl("phone-ui-builder-two", keywords=self.rack[0]["keywords"] + ["screen"])
        rack = self.rack + [twin]
        state = {}
        cfg = {"hr": {}}
        for i in range(8):
            hr.fold_hire(state, cfg, {"template": "phone-ui-builder-two", "group": "build", "passed": False, "sealed": True})
        ranked = hr.select("Build the settings screen for the phone layout", rack, state)
        self.assertEqual(ranked[0]["id"], "phone-ui-builder")
        self.assertTrue(hr.on_probation(hr.hr_state(state), hr.DEFAULT_CFG, "phone-ui-builder-two", "build"))
        self.assertFalse(hr.on_probation(hr.hr_state(state), hr.DEFAULT_CFG, "phone-ui-builder", "build"))

    def test_two_failures_do_not_put_a_template_on_probation(self):
        state = {}
        for _ in range(2):
            hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "build", "passed": False, "sealed": True})
        self.assertFalse(hr.on_probation(hr.hr_state(state), hr.DEFAULT_CFG, "t", "build"))

    def test_untried_template_is_not_boosted_on_risky_work(self):
        a = hr.select("Review the diff of this branch before merge", self.rack, {}, risk="high")[0]
        self.assertLessEqual(a["multiplier"], 0.95)

    def test_only_a_check_result_moves_the_pass_record(self):
        state = {}
        hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "g", "size": "M", "passed": None, "band_tokens": 1000, "actual_tokens": 900})
        hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "g", "passed": "yes", "sealed": True})
        hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "g", "passed": True})                    # not sealed: a claim
        hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "g", "passed": True, "sealed": "yes"})   # not really sealed
        h = hr.hr_state(state)
        self.assertEqual(h["t"], {})
        self.assertEqual(h["ratios"]["t:t"], [0.9])
        hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "g", "passed": True, "sealed": True})
        self.assertEqual(hr.hr_state(state)["t"]["t"][2], 1)


class Wage(Base):
    def test_band_then_calibration_from_settled_hires(self):
        models = c.read_json(self.b / "memory" / "models.json")
        cold = hr.wage("M", "sonnet", "t", {}, hr.DEFAULT_CFG, models)
        self.assertEqual(cold["tokens"], 60000)
        self.assertAlmostEqual(cold["cost"], 0.60)
        state = {}
        for ratio in (1.4, 1.5, 1.6, 1.5, 1.7, 1.5):
            hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "g", "size": "M", "band_tokens": 1000, "actual_tokens": int(1000 * ratio)})
        warm = hr.wage("M", "sonnet", "t", state, hr.DEFAULT_CFG, models)
        self.assertGreater(warm["tokens"], 85000)
        self.assertIn("6 settled", warm["basis"])
        other = hr.wage("M", "sonnet", "never-used", state, hr.DEFAULT_CFG, models)
        self.assertIn("size M", other["basis"])  # falls back to the size band's record

    def test_calibration_is_bounded(self):
        state = {}
        for _ in range(6):
            hr.fold_hire(state, {"hr": {}}, {"template": "t", "size": "S", "band_tokens": 1000, "actual_tokens": 90000})
        w = hr.wage("S", "haiku", "t", state, hr.DEFAULT_CFG, c.read_json(self.b / "memory" / "models.json"))
        self.assertLessEqual(w["tokens"], 60000)  # at most three times the band

    def test_hire_or_not(self):
        hc = hr.DEFAULT_CFG
        self.assertFalse(hr.hire_or_not(50000, False, True, hc)[0])   # nothing can verify the result
        self.assertFalse(hr.hire_or_not(4000, True, False, hc)[0])    # too small to pay for a cold start
        self.assertTrue(hr.hire_or_not(4000, True, True, hc)[0])      # runs beside other work
        self.assertTrue(hr.hire_or_not(80000, True, False, hc)[0])

    def test_estimate_material_counts_existing_files(self):
        # Without it a small job always got a helper (CB-202 trial)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.py").write_text("x = 1\n" * 400)
            n = hr.estimate_material(Path(d), ["a.py", "missing.py"])
            self.assertGreater(n, 0)
            self.assertLess(n, hr.DEFAULT_CFG["hire"]["min_material_tokens"])
            self.assertFalse(hr.hire_or_not(n, True, False, hr.DEFAULT_CFG)[0])


class Briefs(Base):
    def test_agent_without_a_shell_is_told_the_lead_runs_the_check(self):
        # CB-205 review: 17 researcher templates said "{check} passes" to an agent with no Bash
        t = {"id": "r", "role_line": "Finds things.", "method": ["Read sources, because memory is stale."], "drift": "",
             "scope_rule": "Read-only.", "done_check": "Every claim has a source; {check} passes.", "return_contract": "Short.",
             "pitfalls": []}
        b = hr.compose_brief(t, "researcher", "Find X.", "Y.", [], [], "test -s memo.md", "sonnet", "medium", "n.md")
        self.assertIn("the lead's check `test -s memo.md`", b)
        self.assertNotIn("Run `test -s memo.md` yourself", b)
        b = hr.compose_brief(t, "builder", "Find X.", "Y.", [], [], "make test", "sonnet", "medium", "n.md")
        self.assertIn("`make test` passes", b)

    def test_no_check_keeps_the_template_evidence_clauses(self):
        t = {"id": "d", "role_line": "Critiques.", "method": ["Score each criterion, because vague praise hides defects."],
             "drift": "", "scope_rule": "Read-only.", "done_check": "Every criterion has a score and a screenshot; {check} passes.",
             "return_contract": "Short.", "pitfalls": []}
        b = hr.compose_brief(t, "reviewer", "Critique it.", "Y.", [], [], "", "sonnet", "medium", "n.md")
        self.assertIn("Every criterion has a score and a screenshot", b)
        self.assertNotIn("{check}", b)

    def test_outside_content_line_for_templates_that_fetch(self):
        t = {"id": "f", "role_line": "Builds.", "method": ["Fetch the current API docs, because recalled endpoints drift."],
             "drift": "", "scope_rule": "Owns src.", "done_check": "{check} exits 0.", "return_contract": "Short.", "pitfalls": []}
        self.assertIn(hr.HYGIENE, hr.compose_brief(t, "builder", "Do it.", "Y.", [], [], "make", "sonnet", "medium", "n.md"))
        t["method"] = ["Write the parser, because input varies."]
        self.assertNotIn(hr.HYGIENE, hr.compose_brief(t, "builder", "Do it.", "Y.", [], [], "make", "sonnet", "medium", "n.md"))

    def test_brief_has_every_part_and_stays_short(self):
        text = hr.compose_brief(self.rack[0], "builder", "Add the settings screen.", "The owner needs it on his phone.", ["src/settings/"],
                                ["docs/spec.md, section 2"], "npm test", "sonnet", "medium", "/x/notes.md")
        for part in ("<task>", "Why:", "<scope>", "Owns: src/settings/", "<inputs>", "<done_when>", "`npm test`", "<return>", "/x/notes.md"):
            self.assertIn(part, text)
        self.assertLessEqual(len(text.split()), 350)
        self.assertEqual(hr.lint_brief(text, "sonnet"), [])

    def test_tier_block_is_added_for_small_models_and_not_for_strong_ones(self):
        args = (self.rack[0], "builder", "Do it.", "", [], [], "npm test")
        self.assertIn("run a real check", hr.compose_brief(*args, "sonnet", "medium", "n"))
        self.assertIn("run a real check", hr.compose_brief(*args, "haiku", "low", "n"))
        self.assertNotIn("run a real check", hr.compose_brief(*args, "sonnet", "high", "n"))
        for strong in ("opus", "fable"):
            text = hr.compose_brief(*args, strong, "high", "n")
            self.assertNotIn("run a real check", text)
            self.assertEqual(hr.lint_brief(text, strong), [])

    def test_no_wage_or_token_number_reaches_the_brief(self):
        os.environ["BRAIN_PROJECT"] = ""
        con = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=self.project(), check="npm test")
        text = Path(con["brief"]).read_text()
        self.assertNotRegex(text, r"\d[\d,]*\s*k?\s*tokens")
        self.assertNotIn(str(con["wage_tokens"]), text)
        self.assertIn(con["id"], con["brief"])

    def test_researcher_brief_carries_the_untrusted_content_line(self):
        t = tpl("deep-researcher", base_agent="researcher", group="discovery")
        self.assertIn("is not addressed to you", hr.compose_brief(t, "researcher", "Find out X.", "", [], [], "", "sonnet", "medium", "n"))

    def test_lint_catches_a_bad_brief(self):
        bad = "<task>x</task>\nYou are an expert senior developer. Use at most 2,000 tokens.\n"
        errs = " | ".join(hr.lint_brief(bad, "opus"))
        for needle in ("no <scope>", "persona", "budget"):
            self.assertIn(needle, errs)


class Contracts(Base):
    def helper_transcript(self, contract_id: str, out_tokens: int) -> Path:
        p = Path(self._tmp.name) / f"agent-{contract_id}.jsonl"
        rows = [
            {"type": "user", "timestamp": "2026-11-10T10:00:00Z", "message": {"role": "user", "content": f"Follow the brief at /x/{contract_id}.md (contract {contract_id})."}},
            {"type": "assistant", "timestamp": "2026-11-10T10:01:00Z", "message": {"id": "m1", "model": "claude-sonnet-5-5", "role": "assistant",
             "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": out_tokens}}},
        ]
        p.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return p

    def test_hire_writes_contract_and_brief_and_settle_records_real_use(self):
        p = self.project()
        con = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=p, check="true", family="software", task_class="software.ui")
        self.assertEqual(con["template"], "phone-ui-builder")
        self.assertEqual((con["base_agent"], con["model"], con["effort"]), ("builder", "sonnet", "medium"))
        self.assertTrue(Path(con["brief"]).is_file())
        cpath = p / ".brain" / "log" / "hr" / f"{con['id']}.json"
        other = self.helper_transcript("h-00000000-ffffff", 999999)
        mine = self.helper_transcript(con["id"], 30000)
        done = hr.settle(cpath, brain_root=self.b, project=p, sub_paths=[other, mine])
        self.assertEqual(done["status"], "settled")
        self.assertEqual(done["actual_tokens"], 30000)        # all output, priced at the model's own output rate
        self.assertEqual(done["overrun"], 0.5)
        self.assertIs(done["passed"], True)                    # from running the check, exit 0
        inbox = list((self.b / "learning" / "inbox").glob("*.jsonl"))
        self.assertEqual(len(inbox), 1)
        recs = c.read_jsonl(inbox[0])
        self.assertEqual([r["kind"] for r in recs], ["hire"])
        blob = inbox[0].read_text()
        for private in ("secret-proj", "Secret Proj", str(p), "settings screen"):
            self.assertNotIn(private, blob)
        hr.settle(cpath, brain_root=self.b, project=p, sub_paths=[mine])
        self.assertEqual(len(c.read_jsonl(inbox[0])), 1, "settling twice records once")

    def test_failed_check_is_recorded_as_failed_whatever_anyone_claims(self):
        p = self.project()
        con = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=p, check="false")
        cpath = p / ".brain" / "log" / "hr" / f"{con['id']}.json"
        done = hr.settle(cpath, brain_root=self.b, project=p, sub_paths=[self.helper_transcript(con["id"], 1000)])
        self.assertIs(done["passed"], False)

    def test_contract_without_helper_or_check_stays_unmatched_and_records_nothing(self):
        p = self.project()
        con = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=p)
        cpath = p / ".brain" / "log" / "hr" / f"{con['id']}.json"
        done = hr.settle(cpath, brain_root=self.b, project=p, sub_paths=[])
        self.assertEqual(done["status"], "unmatched")
        self.assertFalse((self.b / "learning" / "inbox").exists())

    def test_settled_hires_flow_through_the_real_fold(self):
        cfg = mlearn.config(self.b)
        recs = [{"kind": "hire", "id": f"r{i}", "at": f"2026-11-10T10:0{i}:00Z", "session": "s", "template": "phone-ui-builder", "group": "build",
                 "size": "M", "passed": i != 0, "sealed": True, "wage_tokens": 60000, "band_tokens": 60000, "actual_tokens": 50000 + i * 1000} for i in range(6)]
        state = mlearn.fold(mlearn.empty_state(), recs, cfg)
        again = mlearn.fold(state, recs, cfg)
        self.assertEqual(json.dumps(state, sort_keys=True), json.dumps(again, sort_keys=True))  # idempotent per record id
        h = hr.hr_state(state)
        self.assertEqual(h["t"]["phone-ui-builder"][2], 6)
        self.assertEqual(h["settled"], 6)
        shuffled = mlearn.fold(mlearn.empty_state(), list(reversed(recs)), cfg)
        self.assertEqual(json.dumps(state, sort_keys=True), json.dumps(shuffled, sort_keys=True))  # order-free

    def test_when_nothing_passes_the_floor_the_closest_are_offered_not_chosen(self):
        long_task = "Go through the whole thing for defects prior to handing over, covering engine files, guidelines, schema, plan section and tests, then review"
        con = hr.hire(long_task, brain_root=self.b, project=self.project(), check="true", base_agent="reviewer")
        self.assertIsNone(con["template"])
        self.assertEqual(con["closest"], ["code-reviewer"])

    def test_explicit_template_and_unknown_template(self):
        con = hr.hire("anything at all", brain_root=self.b, project=self.project(), template_id="code-reviewer", check="true")
        self.assertEqual((con["template"], con["base_agent"]), ("code-reviewer", "reviewer"))
        with self.assertRaises(ValueError):
            hr.hire("x", brain_root=self.b, template_id="nope")

    def test_template_none_forces_a_plain_brief(self):
        # The plain arm of a template-versus-plain comparison (CB-203), or a job no template fits
        con = hr.hire("Review this branch for bugs before release", brain_root=self.b, project=self.project(), template_id="none",
                      check="true", base_agent="reviewer")
        self.assertIsNone(con["template"])
        self.assertEqual(con["closest"], [])

    def test_no_template_fits_gives_a_plain_helper_with_a_complete_brief(self):
        con = hr.hire("Calibrate the telescope mount firmware", brain_root=self.b, project=self.project(), check="make test", family="software")
        self.assertIsNone(con["template"])
        text = Path(con["brief"]).read_text()
        for part in ("<task>", "<scope>", "<done_when>", "<return>"):
            self.assertIn(part, text)


class LeadVersusHelpers(Base):
    def test_outcome_charges_the_lead_with_its_own_usage_only(self):
        from engine import ledger
        s = {"main": {"in": 10, "cache_write": 0, "cache_read": 0, "out": 990, "cost": 0.02, "messages": 1},
             "totals": {"in": 10, "cache_write": 0, "cache_read": 0, "out": 99990, "cost": 1.50, "messages": 9},
             "main_model": "claude-opus-5-5", "main_effort": "medium", "wall_minutes": 10.0}
        rec = ledger._outcomes("s1", "2026-11-10T10:00:00Z", "software", ["software.feature"], 2, s, [], set(), {}, c.read_json(self.b / "memory" / "models.json"))[0]
        self.assertEqual((rec["tokens"], rec["cost"]), (1000, 0.02))          # the lead's arm is judged on this
        self.assertEqual((rec["tokens_all"], rec["cost_all"]), (100000, 1.5))  # the task's size, for estimates

    def test_estimates_are_calibrated_on_the_whole_task(self):
        cfg = mlearn.config(self.b)
        recs = [{"kind": "outcome", "id": f"o{i}", "at": f"2026-11-10T10:0{i}:00Z", "session": f"s{i}", "task_class": "software.feature",
                 "family": "software", "tier": 2, "risk": "standard", "model": "opus", "effort": "medium", "has_check": True,
                 "passed": True, "first_pass": True, "rework": 0, "tokens": 1000, "tokens_all": 200000, "cost": 0.02,
                 "minutes": 5, "est_tokens": 100000, "est_minutes": 5} for i in range(6)]
        state = mlearn.fold(mlearn.empty_state(), recs, cfg)
        cal = mlearn.calibrate(state, "software.feature", "software", 100000, 5, cfg)
        self.assertGreater(cal["tokens_p50"], 150000)  # actual was twice the estimate, not a hundredth of it

    def test_settle_open_settles_only_this_sessions_contracts(self):
        p = self.project()
        mine = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=p, check="true")
        os.environ["BRAIN_SESSION_ID"] = "another-session"
        hr.hire("Review the diff of this branch before merge", brain_root=self.b, project=p, check="true")
        os.environ["BRAIN_SESSION_ID"] = "sess-hr"
        line = hr.settle_open(p, brain_root=self.b, sub_paths=[])
        self.assertIn("1 of 1 contract(s) settled", line)
        self.assertEqual(len(hr.open_contracts(p)), 1)
        self.assertEqual(c.read_json(p / ".brain" / "log" / "hr" / f"{mine['id']}.json")["status"], "settled")


class ReviewFindings(Base):
    """One test per defect the independent HR review reproduced."""

    def helper_transcript(self, contract_id: str, out_tokens: int) -> Path:
        return Contracts.helper_transcript(self, contract_id, out_tokens)

    def test_wage_does_not_swing_back_when_real_use_is_steady(self):
        """M1: with real use steady at 90k on a 60k band, the wage must rise and stay risen."""
        models = c.read_json(self.b / "memory" / "models.json")
        state, wages = {}, []
        for i in range(60):
            w = hr.wage("M", "sonnet", "t", state, hr.DEFAULT_CFG, models)
            wages.append(w["tokens"])
            hr.fold_hire(state, {"hr": {}}, {"template": "t", "size": "M", "band_tokens": w["band"], "wage_tokens": w["tokens"], "actual_tokens": 90000})
        self.assertEqual(wages[0], 60000)
        self.assertTrue(all(w == 90000 for w in wages[6:]), wages)

    def test_a_pass_written_into_the_contract_file_is_ignored(self):
        """M2a: the helper cannot pass itself by editing the contract."""
        p = self.project()
        con = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=p, check="false")
        cpath = p / ".brain" / "log" / "hr" / f"{con['id']}.json"
        forged = c.read_json(cpath)
        forged["passed"] = True
        c.write_json(cpath, forged)
        done = hr.settle(cpath, brain_root=self.b, project=p, sub_paths=[self.helper_transcript(con["id"], 100)])
        self.assertIs(done["passed"], False)
        self.assertEqual(done["check_exit"], 1)

    def test_a_check_changed_after_hiring_is_not_run_and_counts_for_nothing(self):
        """M2b: swapping the check for one that always passes is detected."""
        p = self.project()
        con = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=p, check="false")
        cpath = p / ".brain" / "log" / "hr" / f"{con['id']}.json"
        forged = c.read_json(cpath)
        forged["check"] = "true"
        c.write_json(cpath, forged)
        done = hr.settle(cpath, brain_root=self.b, project=p, sub_paths=[self.helper_transcript(con["id"], 100)])
        self.assertIsNone(done["passed"])
        self.assertTrue(done["tampered"])
        rec = c.read_jsonl(next((self.b / "learning" / "inbox").glob("*.jsonl")))[0]
        self.assertFalse(rec["sealed"])
        state = {}
        hr.fold_hire(state, {"hr": {}}, rec)
        self.assertEqual(hr.hr_state(state)["t"], {})

    def run_cli(self, *argv):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("brain_cli_hr", str(ROOT / "bin" / "brain"))
        spec = importlib.util.spec_from_loader("brain_cli_hr", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = mod.main(list(argv))
        return code, buf.getvalue()

    def test_cap_counts_this_sessions_contracts_with_or_without_a_project(self):
        """S1: the four-helper cap applies with no project; other sessions' leftovers do not block."""
        os.environ["TMPDIR"] = str(Path(self._tmp.name) / "tmp")
        Path(os.environ["TMPDIR"]).mkdir()
        import tempfile as _t
        _t.tempdir = None
        try:
            os.environ["BRAIN_SESSION_ID"] = "crashed-session"
            for i in range(4):
                self.run_cli("hr", "hire", f"Build screen number {i} for the phone layout", "--check", "true", "--parallel")
            os.environ["BRAIN_SESSION_ID"] = "sess-hr"
            codes = [self.run_cli("hr", "hire", f"Build another screen {i} for the phone layout", "--check", "true", "--parallel")[0] for i in range(5)]
            self.assertEqual(codes[:4], [0, 0, 0, 0])
            self.assertEqual(codes[4], 1)
            code, out = self.run_cli("hr", "hire", "Build one more screen for the phone layout", "--check", "true", "--parallel", "--dry-run")
            self.assertEqual(code, 0)
            self.assertIn("dry run", out)
        finally:
            _t.tempdir = None

    def test_an_early_settle_leaves_the_contract_open_for_a_later_one(self):
        """S2: settling before the helper's transcript exists must not lose the hire."""
        p = self.project()
        con = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=p)
        cpath = p / ".brain" / "log" / "hr" / f"{con['id']}.json"
        self.assertEqual(hr.settle(cpath, brain_root=self.b, project=p, sub_paths=[])["status"], "unmatched")
        self.assertEqual(len(hr.open_contracts(p)), 1)
        later = hr.settle(cpath, brain_root=self.b, project=p, sub_paths=[self.helper_transcript(con["id"], 500)])
        self.assertEqual(later["status"], "settled")

    def test_same_task_hired_twice_in_one_second_gets_two_contracts(self):
        """S3 (and the replacement rule): ids never collide; the earlier one is superseded."""
        os.environ["BRAIN_NOW"] = "2026-11-10T10:00:00Z"
        p = self.project()
        a = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=p, check="true")
        b = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=p, check="true")
        self.assertNotEqual(a["id"], b["id"])
        self.assertTrue(Path(a["brief"]).is_file() and Path(b["brief"]).is_file())
        self.assertEqual(c.read_json(p / ".brain" / "log" / "hr" / f"{a['id']}.json")["status"], "superseded")
        self.assertEqual(len(hr.open_contracts(p)), 1)

    def test_every_constraint_the_lead_adds_reaches_the_brief(self):
        """S4: lead-supplied lines are never dropped."""
        extras = [f"EXTRA-{i} because reason {i}." for i in range(4)]
        five = tpl("x", method=[f"Method line {i} because of reason {i}." for i in range(5)])
        text = hr.compose_brief(five, "builder", "Do it.", "", [], [], "true", "opus", "high", "n", extras)
        for e in extras:
            self.assertIn(e, text)
        self.assertIn("Method line 4", text)

    def test_brief_length_is_a_note_then_an_error(self):
        """S5: the word limit is real: a note above 350, an error above 500."""
        ok = hr.compose_brief(self.rack[0], "builder", "Do it.", "", [], [], "true", "opus", "high", "n")
        self.assertEqual(hr.lint_brief(ok, "opus"), [])
        huge = hr.compose_brief(self.rack[0], "builder", "word " * 480, "", [], [], "true", "opus", "high", "n")
        self.assertTrue(any("limit 500" in e for e in hr.lint_brief(huge, "opus")))

    def test_without_a_check_the_brief_points_at_no_phantom_command(self):
        """S6."""
        text = hr.compose_brief(self.rack[0], "builder", "Do it.", "", [], [], "", "opus", "high", "n")
        self.assertNotIn("check named in the task", text)
        self.assertNotIn("{check}", text)
        self.assertIn("names the evidence", text)
        with_check = hr.compose_brief(tpl("y", done_check="The screen matches the spec."), "builder", "Do it.", "", [], [], "make ok", "opus", "high", "n")
        self.assertIn("Run `make ok` yourself", with_check)

    def test_one_malformed_template_does_not_break_hiring_and_the_audit_reports_it(self):
        """S8."""
        bad = [{"when": "no id at all"}, {"id": "int-keys", "base_agent": "builder", "name": "x", "when": "x", "role_line": "x", "keywords": [1, 2], "method": ["a"], "families": ["software"]}, "not an object"]
        (self.b / "hr" / "rack" / "broken.jsonl").write_text("".join(json.dumps(x) + "\n" for x in bad))
        con = hr.hire("Build the settings screen for the phone", brain_root=self.b, project=self.project(), check="true")
        self.assertEqual(con["template"], "phone-ui-builder")
        errs = " | ".join(hr.audit(self.b)[0])
        self.assertIn("no text id", errs)
        self.assertIn("every keywords entry must be text", errs)

    def test_audit_really_validates_templates(self):
        """S10: the audit must fail on a template that breaks a writing rule."""
        c.write_jsonl(self.b / "hr" / "rack" / "all.jsonl", [tpl("phone-ui-builder", role_line="You are an expert senior engineer.")])
        self.assertTrue(any("persona" in e for e in hr.audit(self.b)[0]))

    def test_template_role_sets_the_model_tier_and_risk_is_never_lowered(self):
        """S9 and m10: read-only work can run on the reviewer agent at a cheaper tier; a template's risk counts."""
        rack = self.rack + [tpl("repo-map", name="Repo Mapper", group="discovery", base_agent="reviewer", role="researcher", risk="high",
                                keywords=["map", "repo", "unfamiliar", "entry", "structure"], when="An unfamiliar repo must be mapped before a change.")]
        c.write_jsonl(self.b / "hr" / "rack" / "all.jsonl", rack)
        con = hr.hire("Map this unfamiliar repo structure and entry points", brain_root=self.b, project=self.project(), check="true")
        self.assertEqual((con["template"], con["base_agent"], con["model"]), ("repo-map", "reviewer", "sonnet"))
        self.assertEqual(con["risk"], "high")
        self.assertTrue(any("role 'wizard'" in e for e in hr.validate_template(tpl("z", role="wizard"), self.schema)))

    def test_small_things_the_review_listed(self):
        models = c.read_json(self.b / "memory" / "models.json")
        with self.assertRaises(ValueError):                                    # m6
            hr.wage("XXL", "sonnet", "t", {}, hr.DEFAULT_CFG, models)
        self.assertEqual(hr.select("fix it", self.rack), [])                   # m5
        state = {}
        hr.fold_hire(state, {"hr": {}}, {"template": "t", "size": None, "band_tokens": True, "actual_tokens": 5})   # m7
        self.assertEqual(hr.hr_state(state)["ratios"], {})
        for bad in ("You're an expert engineer.", "As a world-class engineer, build it.", "Use five thousand tokens at most."):  # m3
            self.assertTrue(hr.validate_template(tpl("q", role_line="Builds screens.", scope_rule=bad), self.schema), bad)
        self.assertTrue(any("absolute rule" in e for e in hr.validate_template(tpl("q", scope_rule="Always commit when you like."), self.schema)))
        brief = hr.compose_brief(self.rack[0], "builder", "Cut the system prompt below 2,000 tokens.", "", [], [], "true", "sonnet", "medium", "n",
                                 ["Think step by step is banned in our prompts, so remove it."])
        self.assertEqual(hr.lint_brief(brief, "sonnet", "Cut the system prompt below 2,000 tokens.\n\nThink step by step is banned in our prompts, so remove it."), [])  # m4
        self.assertTrue(hr.lint_brief(brief + "\nThink step by step.", "sonnet"))   # m2
        code, out = self.run_cli("hr", "settle", "../../etc/passwd")            # m8
        self.assertEqual(code, 1)
        self.assertIn("not a contract id", out)

    def test_selection_details_the_mutations_removed(self):
        """S10: clamp, family penalty and discount each have a visible effect."""
        state = {}
        for _ in range(40):
            hr.fold_hire(state, {"hr": {}}, {"template": "phone-ui-builder", "group": "build", "passed": True, "sealed": True})
        h = hr.hr_state(state)
        self.assertLessEqual(hr.performance_multiplier(h, hr.DEFAULT_CFG, "phone-ui-builder", "build"), 1.3)
        self.assertLess(h["t"]["phone-ui-builder"][0], 34)   # 40 passes, discounted: old results fade
        same = hr.select("Build the settings screen for the phone layout", self.rack, family="software")[0]["score"]
        other = hr.select("Build the settings screen for the phone layout", self.rack, family="language")[0]["score"]
        self.assertLess(other, same)
        ro = tpl("ro", base_agent="reviewer", method=["Read the diff and fix the bugs you find because that is fastest.", "b because c.", "d because e."])
        self.assertTrue(any("read-only base agent" in e for e in hr.validate_template(ro, self.schema)))
        opus_bad = hr.compose_brief(self.rack[0], "builder", "Do it.", "", [], [], "true", "opus", "high", "n") + "\n" + hr.VERIFY_BLOCK
        self.assertTrue(any("over-verifies" in e for e in hr.lint_brief(opus_bad, "opus")))

    def test_config_overlay_and_ratio_window(self):
        cfgfile = self.b / "memory" / "ml_config.json"
        data = c.read_json(cfgfile)
        data["hr"] = {"bands": {"M": 77000}, "hire": {"max_helpers": 2}}
        c.write_json(cfgfile, data)
        hc = hr.cfg_of(self.b)
        self.assertEqual((hc["bands"]["M"], hc["bands"]["S"], hc["hire"]["max_helpers"]), (77000, 20000, 2))
        state = {}
        for i in range(50):
            hr.fold_hire(state, {"hr": {}}, {"template": "t", "size": "M", "band_tokens": 1000, "actual_tokens": 1000})
        self.assertEqual(len(hr.hr_state(state)["ratios"]["_all"]), hr.DEFAULT_CFG["ratio_cap"])

    def test_staff_and_report_run_end_to_end(self):
        plan = Path(self._tmp.name) / "plan.json"
        plan.write_text(json.dumps({"tickets": [
            {"id": "T-1", "title": "Build the settings screen for the phone layout", "accept": "true"},
            {"id": "T-2", "title": "Translate the home page to Spanish", "accept": ""},
            {"id": "T-3", "title": "Done already", "status": "done"}]}))
        code, out = self.run_cli("hr", "staff", str(plan), "--budget", "0")
        self.assertEqual(code, 1)
        self.assertIn("T-2", out)
        self.assertIn("lead does it", out)
        self.assertNotIn("T-3", out)
        self.assertIn("OVER", out)
        code, out = self.run_cli("hr", "report")
        self.assertEqual(code, 0)
        self.assertIn("rack:", out)

    def test_staff_weighs_small_sequential_tickets_against_a_cold_start(self):
        # Every ticket was assumed parallel, so every small one got a helper (CB-206)
        plan = Path(self._tmp.name) / "plan.json"
        plan.write_text(json.dumps({"agents": 2, "tickets": [
            {"id": "A", "title": "Write the split function", "accept": "true", "est": 15, "files": ["a.py"]},
            {"id": "B", "title": "Write the command line on top", "accept": "true", "est": 15, "files": ["b.py"], "deps": ["A"]},
            {"id": "C", "title": "Write one module", "accept": "true", "est": 15, "files": ["c.py"]}]}))
        _, out = self.run_cli("hr", "staff", str(plan))
        lines = {l.split(":")[0]: l for l in out.splitlines() if ":" in l}
        self.assertIn("wage", lines["A"])           # A overlaps C in the schedule
        self.assertIn("lead does it", lines["B"])   # B runs after A, alone, and is small


class RealRack(unittest.TestCase):
    def test_the_real_rack_is_sound_and_complete(self):
        errs, info = hr.audit(ROOT)
        self.assertEqual(errs, [])
        self.assertEqual(info["templates"], 100)

    def test_every_real_template_renders_a_clean_brief_for_every_tier(self):
        for t in hr.load_rack(ROOT):
            for model, effort in (("haiku", "low"), ("sonnet", "medium"), ("opus", "high"), ("fable", "high")):
                text = hr.compose_brief(t, t["base_agent"], "Do the task described in the plan.", "The owner needs the result.", ["path/a"],
                                        ["path/b"], "make check", model, effort, ".brain/log/hr/notes.md")
                self.assertEqual(hr.lint_brief(text, model), [], (t["id"], model))

    def test_selection_on_the_held_out_requests_does_not_get_worse(self):
        """evals/hr_golden.jsonl: 100 requests the keywords were tuned on (dev)
        and 100 they were not (heldout). Measured after tuning on 2026-11-10:
        heldout top-1 0.78, top-3 0.86 (dev is 1.00 by construction and proves
        nothing). The floor is the measured value minus a small margin."""
        rack = hr.load_rack(ROOT)
        rows = [r for r in c.read_jsonl(ROOT / "evals" / "hr_golden.jsonl") if r.get("split") == "heldout"]
        self.assertEqual(len(rows), 100)
        top1 = top3 = 0
        for r in rows:
            ids = [h["id"] for h in hr.select(r["task"], rack)]
            top1 += bool(ids[:1] and ids[0] in r["expect"])
            top3 += any(i in r["expect"] for i in ids[:3])
        self.assertGreaterEqual(top1 / len(rows), 0.74, f"top-1 {top1}")
        self.assertGreaterEqual(top3 / len(rows), 0.82, f"top-3 {top3}")

    def test_selection_on_the_second_held_out_set(self):
        """evals/hr_golden_2.jsonl: 100 requests written by a helper that never
        ran the selector (CB-204). Measured 2026-11-10: top-1 0.46, top-3 0.63.
        The first held-out set had been looked at while tuning and overstated
        accuracy (0.78 / 0.86). Floors are the measured values minus a margin."""
        rack = hr.load_rack(ROOT)
        rows = [r for r in c.read_jsonl(ROOT / "evals" / "hr_golden_2.jsonl") if r.get("split") == "heldout2"]
        self.assertEqual(len(rows), 100)
        top1 = top3 = 0
        for r in rows:
            ids = [h["id"] for h in hr.select(r["task"], rack)]
            top1 += bool(ids[:1] and ids[0] in r["expect"])
            top3 += any(i in r["expect"] for i in ids[:3])
        self.assertGreaterEqual(top1 / len(rows), 0.42, f"top-1 {top1}")
        self.assertGreaterEqual(top3 / len(rows), 0.59, f"top-3 {top3}")

    def test_owner_style_requests_find_a_sensible_template(self):
        rack = hr.load_rack(ROOT)
        cases = [
            ("Translate the home page into Spanish from Spain", "language"),
            ("Review this branch for bugs before we release", "review"),
            ("Vercel still shows the old version after I pushed, fix the deployment", "quality-ops"),
            ("Research the best way to store photos and compare the options with sources", "discovery"),
            ("Propose five app icon designs for me to choose from", "design"),
            ("Rewrite sixty articles to about nine hundred words each", "writing"),
            ("Get everything ready to continue in a new chat", "support"),
        ]
        for task, group in cases:
            hits = hr.select(task, rack)
            self.assertTrue(hits, task)
            self.assertIn(group, [h["template"]["group"] for h in hits], (task, [h["id"] for h in hits]))


if __name__ == "__main__":
    unittest.main()
