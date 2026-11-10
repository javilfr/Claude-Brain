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
            hr.fold_hire(state, cfg, {"template": "phone-ui-builder-two", "group": "build", "passed": False})
        ranked = hr.select("Build the settings screen for the phone layout", rack, state)
        self.assertEqual(ranked[0]["id"], "phone-ui-builder")
        self.assertTrue(hr.on_probation(hr.hr_state(state), hr.DEFAULT_CFG, "phone-ui-builder-two", "build"))
        self.assertFalse(hr.on_probation(hr.hr_state(state), hr.DEFAULT_CFG, "phone-ui-builder", "build"))

    def test_two_failures_do_not_put_a_template_on_probation(self):
        state = {}
        for _ in range(2):
            hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "build", "passed": False})
        self.assertFalse(hr.on_probation(hr.hr_state(state), hr.DEFAULT_CFG, "t", "build"))

    def test_untried_template_is_not_boosted_on_risky_work(self):
        a = hr.select("Review the diff of this branch before merge", self.rack, {}, risk="high")[0]
        self.assertLessEqual(a["multiplier"], 0.95)

    def test_only_a_check_result_moves_the_pass_record(self):
        state = {}
        hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "g", "passed": None, "wage_tokens": 1000, "actual_tokens": 900})
        hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "g", "passed": "yes"})
        h = hr.hr_state(state)
        self.assertEqual(h["t"], {})
        self.assertEqual(h["ratios"]["t:t"], [0.9])


class Wage(Base):
    def test_band_then_calibration_from_settled_hires(self):
        models = c.read_json(self.b / "memory" / "models.json")
        cold = hr.wage("M", "sonnet", "t", {}, hr.DEFAULT_CFG, models)
        self.assertEqual(cold["tokens"], 60000)
        self.assertAlmostEqual(cold["cost"], 0.60)
        state = {}
        for ratio in (1.4, 1.5, 1.6, 1.5, 1.7, 1.5):
            hr.fold_hire(state, {"hr": {}}, {"template": "t", "group": "g", "size": "M", "wage_tokens": 1000, "actual_tokens": int(1000 * ratio)})
        warm = hr.wage("M", "sonnet", "t", state, hr.DEFAULT_CFG, models)
        self.assertGreater(warm["tokens"], 85000)
        self.assertIn("6 settled", warm["basis"])
        other = hr.wage("M", "sonnet", "never-used", state, hr.DEFAULT_CFG, models)
        self.assertIn("size M", other["basis"])  # falls back to the size band's record

    def test_calibration_is_bounded(self):
        state = {}
        for _ in range(6):
            hr.fold_hire(state, {"hr": {}}, {"template": "t", "size": "S", "wage_tokens": 1000, "actual_tokens": 90000})
        w = hr.wage("S", "haiku", "t", state, hr.DEFAULT_CFG, c.read_json(self.b / "memory" / "models.json"))
        self.assertLessEqual(w["tokens"], 60000)  # at most three times the band

    def test_hire_or_not(self):
        hc = hr.DEFAULT_CFG
        self.assertFalse(hr.hire_or_not(50000, False, True, hc)[0])   # nothing can verify the result
        self.assertFalse(hr.hire_or_not(4000, True, False, hc)[0])    # too small to pay for a cold start
        self.assertTrue(hr.hire_or_not(4000, True, True, hc)[0])      # runs beside other work
        self.assertTrue(hr.hire_or_not(80000, True, False, hc)[0])


class Briefs(Base):
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
                 "size": "M", "passed": i != 0, "wage_tokens": 60000, "actual_tokens": 50000 + i * 1000} for i in range(6)]
        state = mlearn.fold(mlearn.empty_state(), recs, cfg)
        again = mlearn.fold(state, recs, cfg)
        self.assertEqual(json.dumps(state, sort_keys=True), json.dumps(again, sort_keys=True))  # idempotent per record id
        h = hr.hr_state(state)
        self.assertEqual(h["t"]["phone-ui-builder"][2], 6)
        self.assertEqual(h["settled"], 6)
        shuffled = mlearn.fold(mlearn.empty_state(), list(reversed(recs)), cfg)
        self.assertEqual(json.dumps(state, sort_keys=True), json.dumps(shuffled, sort_keys=True))  # order-free

    def test_explicit_template_and_unknown_template(self):
        con = hr.hire("anything at all", brain_root=self.b, project=self.project(), template_id="code-reviewer", check="true")
        self.assertEqual((con["template"], con["base_agent"]), ("code-reviewer", "reviewer"))
        with self.assertRaises(ValueError):
            hr.hire("x", brain_root=self.b, template_id="nope")

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
