"""The lint must agree with the real command line, and must catch each kind of drift."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import lint  # noqa: E402


def make_brain(tmp: Path) -> Path:
    b = tmp / "brain"
    for d in (".claude/skills/demo", ".claude/agents", "method", "playbooks", "contract/template", "engine", "bin", "evals", "memory", "owner"):
        (b / d).mkdir(parents=True)
    (b / "CLAUDE.md").write_text("# Brain\nUse `BRAIN boot` first.\n")
    (b / "contract/template/CLAUDE.stub.md").write_text("stub\n")
    (b / "bin/brain").write_text("import sys\n")
    (b / "engine/ok.py").write_text("import json\nfrom . import common\n")
    return b


class LintTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.b = make_brain(Path(self._tmp.name))
        self.tree = lint.command_tree()

    def tearDown(self):
        self._tmp.cleanup()

    def skill(self, body: str):
        (self.b / ".claude/skills/demo/SKILL.md").write_text("---\nname: demo\ndescription: d\n---\n" + body)

    def test_the_real_brain_is_clean(self):
        errs, _notes = lint.run(ROOT)
        self.assertEqual(errs, [])

    def test_tree_comes_from_the_real_parsers(self):
        self.assertIn("--push", self.tree["checkpoint"]["flags"])
        self.assertIn("check", self.tree["req"]["sub"])
        self.assertIn("--passes-when", self.tree["req"]["sub"]["add"]["flags"])

    def test_unknown_command_flag_and_subcommand_are_errors(self):
        self.skill("Run `BRAIN frobnicate`, then `BRAIN checkpoint --finished X`, then `BRAIN req approve R-1`.\n"
                   "```\nBRAIN release --force\n```\n")
        errs = " | ".join(lint.check_commands(self.b, self.tree))
        for needle in ("`brain frobnicate` does not exist", "no flag --finished", "`brain req approve` does not exist", "no flag --force"):
            self.assertIn(needle, errs)

    def test_valid_calls_and_wrapped_commands_pass(self):
        self.skill("`BRAIN checkpoint --done T-1 --item T-2 --next T-3 --push`\n"
                   "`BRAIN run -- pnpm test --coverage`\n"
                   "`BRAIN req add --quote \"x\" --passes-when \"y\"` and `BRAIN req add|list|check`\n"
                   "`python3 bin/brain release --run-gates --push`\n")
        self.assertEqual(lint.check_commands(self.b, self.tree), [])

    def test_prose_about_the_brain_is_not_a_command(self):
        self.skill("The brain is attached and the `brain repository` holds memory.\n")
        self.assertEqual(lint.check_commands(self.b, self.tree), [])

    def test_non_stdlib_import_is_an_error(self):
        (self.b / "engine/bad.py").write_text("import requests\nimport os\n")
        errs = lint.check_imports(self.b)
        self.assertEqual(len(errs), 1)
        self.assertIn("requests", errs[0])

    def test_broken_link_is_an_error_and_good_link_is_not(self):
        (self.b / "method/a.md").write_text("See [b](b.md) and [missing](nope.md) and [web](https://example.invalid/x).\n")
        (self.b / "method/b.md").write_text("ok\n")
        errs = lint.check_links(self.b)
        self.assertEqual(len(errs), 1)
        self.assertIn("nope.md", errs[0])

    def test_sentence_repeated_in_three_files_is_noted(self):
        sentence = "Run builds and tests through the output filter so that only failures enter the conversation.\n"
        for name in ("a", "b", "c"):
            (self.b / f"method/{name}.md").write_text(f"# {name}\n\n{sentence}")
        notes = lint.check_duplicates(self.b)
        self.assertEqual(len(notes), 1)
        self.assertIn("repeated in 3 files", notes[0])

    def test_project_names_are_errors_only_as_whole_words(self):
        (self.b / "evals/known_project_ids.txt").write_text("acme-shop\n")
        (self.b / "memory/items.jsonl").write_text(json.dumps({"id": "rule-a", "text": "Learned on acme-shop."}) + "\n")
        (self.b / "method/a.md").write_text("The acme-shopping example is fine.\n")
        errs = lint.check_project_ids(self.b)
        self.assertEqual(len(errs), 1)
        self.assertIn("items.jsonl", errs[0])

    def write_transcript(self, rows) -> Path:
        p = Path(self._tmp.name) / "t.jsonl"
        p.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return p

    def test_transcript_rules_count_what_happened(self):
        big = "x" * 30000
        rows = [
            {"type": "assistant", "message": {"model": "m1", "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": big}]}},
            {"type": "assistant", "message": {"model": "m2", "content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "small"}]}},
        ]
        lines = "\n".join(lint.transcript_report(self.write_transcript(rows), []))
        self.assertIn("over ~5,000 tokens in the main conversation: 1", lines)
        self.assertIn("re-reads of a file already read: 1", lines)
        self.assertIn("one at a time in a row: 1", lines)
        self.assertIn("models used by the main conversation: 2", lines)

    def test_skill_audit_counts_only_what_the_owner_typed(self):
        (self.b / ".claude/skills/demo/SKILL.md").write_text('---\nname: demo\ndescription: Use for "Start running" or "Continue".\n---\nbody\n')
        rows = [
            {"type": "user", "message": {"content": "Start running"}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "demo"}}]}},
            {"type": "user", "message": {"content": "[SYSTEM NOTIFICATION] a helper said: Continue"}},
            {"type": "user", "message": {"content": "Continue"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}},
            {"type": "user", "message": {"content": "thanks, discontinued that"}},
        ]
        lines = "\n".join(lint.skill_audit(self.write_transcript(rows), self.b))
        self.assertIn("demo×1", lines)
        self.assertIn("trigger phrase for demo appeared 1 time(s)", lines)


if __name__ == "__main__":
    unittest.main()
